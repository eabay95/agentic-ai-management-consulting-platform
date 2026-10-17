import argparse
import json
from pathlib import Path
from config import DATA, RESOURCES, DOMAINS
from .document_loader import safe_extract, load_document
from .chunker import chunks

ARCHIVES = {'Clinical.zip':'clinical','FoodSecurity.zip':'csr',
            'UnitedStatesSecuritiesandExchangeCommission(SEC).zip':'sec','Retail.zip':'retail'}


def extract_resources():
    for name, domain in ARCHIVES.items():
        safe_extract(RESOURCES/name, DATA/domain)


def ingest_file(store, path, domain, customer_id='public'):
    records = list(chunks(load_document(path, domain, customer_id)))
    if not records:
        return 0
    collection = store.collections[domain]
    existing = collection.get(ids=[r['id'] for r in records],include=[])
    if len(existing['ids']) == len(records):
        return len(records)
    # Embed before replacing an earlier version. An API failure leaves old evidence usable.
    store.upsert(domain, records)
    old = collection.get(where={'$and':[{'original_path':str(Path(path).resolve())},
                                       {'customer_id':customer_id}]}, include=['metadatas'])
    valid = {r['id'] for r in records}
    stale = [i for i in old['ids'] if i not in valid]
    if stale:
        collection.delete(ids=stale)
    return len(records)


def ingest_all(store):
    report = []
    for domain in DOMAINS:
        seen = set()
        for path in sorted((DATA/domain).rglob('*')):
            if path.suffix.lower() not in ('.pdf','.txt'):
                continue
            try:
                import hashlib
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                if digest in seen:
                    report.append(dict(path=str(path),status='duplicate skipped'))
                    continue
                seen.add(digest)
                count = ingest_file(store,path,domain)
                report.append(dict(path=str(path),status='indexed' if count else 'no extractable evidence',chunks=count))
            except Exception as error:
                report.append(dict(path=str(path),status='error',error=str(error)))
    DATA.mkdir(exist_ok=True)
    (DATA/'ingestion_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--extract',action='store_true')
    parser.add_argument('--index',action='store_true')
    args = parser.parse_args()
    if args.extract:
        extract_resources()
        print('Resources safely extracted.')
    if args.index:
        from .vector_store import VectorStore
        report = ingest_all(VectorStore())
        print(json.dumps(report,indent=2))
        if any(r['status']=='error' for r in report):
            raise SystemExit(1)
