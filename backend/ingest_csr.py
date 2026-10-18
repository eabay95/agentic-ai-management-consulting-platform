# CSR document ingestion -- Raheem 

import hashlib
from pathlib import Path


from rag.ingestion import load_and_split
from rag.indexing import BATCH_SIZE, add_batch
from rag.vector_store import get_vector_store


BASE_DIR = Path(__file__).resolve().parent
PDF_DIR = BASE_DIR / "data" / "csr"
INGESTION_OWNER = "csr_sofi_v1"

REPORTS = {
    "SOFI-2023.pdf": 2023,
    "SOFI-2024.pdf": 2024,
}




def ingest_csr():

    # Check both files before starting ingestion.
    for filename in REPORTS:
        if not (PDF_DIR / filename).is_file():
            raise FileNotFoundError(f"Missing report: {PDF_DIR / filename}")

    vector_store = get_vector_store("csr")

    for filename, report_year in REPORTS.items():
        documents = [
            document
            for document in load_and_split(str(PDF_DIR / filename))
            if document.page_content.strip()
        ]

        if not documents:
            raise ValueError(f"No readable text found in {filename}.")

        document_ids = []

        for index, document in enumerate(documents):
            # PDF loader pages start at zero; citations start at one.
            page_number = int(document.metadata["page"]) + 1

            document.metadata = {
                "source": filename,
                "report_year": report_year,
                "page_number": page_number,
                "domain": "csr",
                "ingestion_owner": INGESTION_OWNER,
            }

            identity = (
                f"{INGESTION_OWNER}|{filename}|{page_number}|"
                f"{index}|{document.page_content}"
            )
            document_ids.append(
                hashlib.sha256(identity.encode("utf-8")).hexdigest()
            )

        existing = vector_store.get(
            where={
                "$and": [
                    {"source": {"$eq": filename}},
                    {"ingestion_owner": {"$eq": INGESTION_OWNER}},
                ]
            },
            include=["metadatas"],
        )
        existing_ids = set(existing["ids"])

        # Skip passages already stored by an earlier run.
        pending = [
            (document_id, document)
            for document_id, document in zip(document_ids, documents)
            if document_id not in existing_ids
        ]

        for start in range(0, len(pending), BATCH_SIZE):
            batch = pending[start : start + BATCH_SIZE]

            add_batch(
                vector_store,
                documents=[document for _, document in batch],
                ids=[document_id for document_id, _ in batch],
            )

            completed = min(start + BATCH_SIZE, len(pending))
            print(f"{filename}: stored {completed}/{len(pending)} new passages")

        # Remove outdated passages only after new passages are stored.
        obsolete_ids = sorted(existing_ids - set(document_ids))

        for start in range(0, len(obsolete_ids), BATCH_SIZE):
            vector_store.delete(
                ids=obsolete_ids[start : start + BATCH_SIZE]
            )

        print(
            f"{filename}: ready with {len(documents)} passages "
            f"({len(pending)} added, {len(obsolete_ids)} outdated removed)"
        )

    print("CSR report ingestion completed.")


if __name__ == "__main__":
    ingest_csr()
