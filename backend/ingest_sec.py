"""Index the verified SEC PDFs; reruns skip unchanged chunks."""

import hashlib
import json
from pathlib import Path

from rag.ingestion import load_and_split
from rag.sec_sections import risk_factor_pages
from rag.indexing import BATCH_SIZE, add_batch
from rag.vector_store import get_vector_store


PDF_DIR = Path(__file__).resolve().parent / "data" / "sec"
REPORTS = {
    "6c821d1a-cf4e-4310-9801-df9399aa701b.pdf": ("Alphabet", "2024-12-31"),
    "8873e505-7403-4c46-b377-81d814482cbb.pdf": ("Agilent", "2025-10-31"),
}


def ingest_sec():
    for filename in REPORTS:
        if not (PDF_DIR / filename).is_file():
            raise FileNotFoundError(PDF_DIR / filename)

    reports = dict(REPORTS)
    if (PDF_DIR / 'Cisco-2025-Annual-Report.pdf').is_file():
        reports['Cisco-2025-Annual-Report.pdf'] = ('Cisco', '2025-07-26')
    store = get_vector_store("sec")
    for filename, (company, period) in reports.items():
        chunks = [
            chunk for chunk in load_and_split(str(PDF_DIR / filename))
            if chunk.page_content.strip()
        ]
        if not chunks:
            raise ValueError(f"No readable text in {filename}")
        sidecar = (PDF_DIR / filename).with_suffix('.source.json')
        provenance = json.loads(sidecar.read_text('utf-8')) if sidecar.exists() else {}
        risk_pages = risk_factor_pages(chunks)
        ids = []
        for index, chunk in enumerate(chunks):
            chunk.metadata['section'] = 'risk_factors' if chunk.metadata.get('page') in risk_pages else 'other'
            chunk.metadata.update(
                source=filename, company=company, reporting_period=period,
                domain="sec", ingestion_owner="sec_v1", source_url=provenance.get("source_url", ""),
            )
            identity = f"sec_v1|{filename}|{period}|{index}|{chunk.page_content}"
            ids.append(hashlib.sha256(identity.encode()).hexdigest())

        existing = set(store.get(where={"$and": [
            {"source": {"$eq": filename}},
            {"ingestion_owner": {"$eq": "sec_v1"}},
        ]}, include=["metadatas"])["ids"])
        retained = [(key, chunk.metadata) for key, chunk in zip(ids, chunks) if key in existing]
        for start in range(0, len(retained), BATCH_SIZE):
            batch = retained[start:start+BATCH_SIZE]
            store._collection.update(ids=[key for key, _ in batch], metadatas=[m for _, m in batch])
        pending = [(key, chunk) for key, chunk in zip(ids, chunks) if key not in existing]
        for start in range(0, len(pending), BATCH_SIZE):
            batch = pending[start:start + BATCH_SIZE]
            add_batch(
                store,
                documents=[chunk for _, chunk in batch],
                ids=[key for key, _ in batch],
            )
            print(f"{company}: indexed {min(start + BATCH_SIZE, len(pending))}/{len(pending)} new chunks")
        obsolete = sorted(existing - set(ids))
        for start in range(0, len(obsolete), 64):
            store.delete(ids=obsolete[start:start + 64])
        print(f"{company} ({period}): {len(chunks)} chunks ready; {len(pending)} added")


if __name__ == "__main__":
    ingest_sec()
