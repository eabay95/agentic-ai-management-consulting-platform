"""Index added clinical/technology documents without treating URL lists as evidence."""
import argparse
import json
import hashlib
import re
from pathlib import Path

from rag.ingestion import load_and_split
from rag.indexing import BATCH_SIZE, add_batch
from rag.vector_store import get_vector_store

BASE_DIR = Path(__file__).resolve().parent


def prepare_documents(path, domain):
    path = Path(path)
    sidecar = path.with_suffix('.source.json')
    provenance = json.loads(sidecar.read_text('utf-8')) if sidecar.exists() else {}
    if path.suffix.lower() == '.txt' and not provenance.get('source_url') and re.search(r'https?://', path.read_text(encoding='utf-8-sig')):
        return [], 'Reference URL list: fetch actual documentation before indexing.'
    if path.suffix.lower() == '.csv':
        return [], 'Structured trial dataset preserved; not embedded as unstructured clinical evidence.'
    if path.suffix.lower() == '.pdf':
        with path.open('rb') as source:
            header = source.read(1024)
        if b'%PDF-' not in header:
            return [], 'Not a PDF: file contents do not match its .pdf extension. Replace it with the original paper.'
    if domain == 'technology' and not provenance.get('source_url'):
        from fetch_technology import reference_sources
        from urllib.parse import urlsplit
        for url in reference_sources():
            if Path(urlsplit(url).path).name == path.name:
                provenance['source_url'] = url
                break
    documents = [d for d in load_and_split(str(path)) if d.page_content.strip()]
    if not documents:
        raise ValueError(f'No extractable text: {path.name}')
    title_record = {}
    catalog = BASE_DIR / 'data' / 'clinical_titles.json'
    if domain == 'clinical' and catalog.exists():
        record = json.loads(catalog.read_text('utf-8')).get(path.name, {})
        if record.get('sha256') == hashlib.sha256(path.read_bytes()).hexdigest():
            title_record = record
    for document in documents:
        if title_record:
            document.metadata['document_title'] = title_record['title']
        if provenance.get('source_url'):
            document.metadata['source_url'] = provenance['source_url']
        identifying_text = (str(path) + ' ' + provenance.get('source_url', '') + ' ' + ' '.join(d.page_content for d in documents[:2])).lower()
        family = re.search(r'(?i)\b(Catalyst\s+(?:8300|8200|8000V)|ASR\s+1000)\b', identifying_text)
        if family:
            document.metadata['product_family'] = re.sub(r'\s+', ' ', family.group(1)).lower()
        document.metadata['source_organization'] = ('Agilent' if 'agilent' in identifying_text else 'Cisco' if 'cisco' in identifying_text else 'Google Cloud' if 'cloud.google.com' in identifying_text else 'Research authors')
        document.metadata.update(domain=domain, document_name=path.name,
                                 ingestion_owner=f'{domain}_documents_v1')
        page = document.metadata.get('page')
        if isinstance(page, int):
            document.metadata['page_number'] = page + 1
    return documents, ''


def ingest_domain(domain):
    folder = BASE_DIR / 'data' / domain
    document_folder = BASE_DIR / 'documents' / domain
    if not folder.is_dir() and not document_folder.is_dir():
        print(f'{domain}: no data directory; nothing to ingest.')
        return
    store = None
    total = 0
    paths = sorted([*folder.rglob('*'), *document_folder.rglob('*')])
    for path in paths:
        if not path.is_file() or path.suffix.lower() not in {'.pdf', '.txt', '.csv'}:
            continue
        try:
            documents, reason = prepare_documents(path, domain)
        except Exception as error:
            print(f'{domain}/{path.name}: unreadable document ({type(error).__name__}); skipped.')
            continue
        if reason:
            print(f'{domain}/{path.name}: skipped. {reason}')
            continue
        if store is None:
            store = get_vector_store(domain)
        owner = f'{domain}_documents_v1'
        relative = path.relative_to(folder).as_posix() if path.is_relative_to(folder) else 'documents/' + path.relative_to(document_folder).as_posix()
        for document in documents:
            document.metadata['ingestion_file'] = relative
        identifiers = [hashlib.sha256(
            f'{owner}|{relative}|{i}|{document.page_content}'.encode('utf-8')
        ).hexdigest() for i, document in enumerate(documents)]
        existing = store.get(where={'$and': [
            {'ingestion_owner': {'$eq': owner}},
            {'ingestion_file': {'$eq': relative}}
        ]}, include=['metadatas'])
        existing_ids = set(existing['ids'])
        retained = [(key, doc.metadata) for key, doc in zip(identifiers, documents) if key in existing_ids]
        for start in range(0, len(retained), BATCH_SIZE):
            batch = retained[start:start+BATCH_SIZE]
            store._collection.update(ids=[i for i, _ in batch], metadatas=[m for _, m in batch])
        pending = [(identifier, document) for identifier, document in zip(identifiers, documents)
                   if identifier not in existing_ids]
        for start in range(0, len(pending), BATCH_SIZE):
            batch = pending[start:start + BATCH_SIZE]
            add_batch(store, documents=[d for _, d in batch], ids=[i for i, _ in batch])
        stale = sorted(existing_ids - set(identifiers))
        for start in range(0, len(stale), BATCH_SIZE):
            store.delete(ids=stale[start:start + BATCH_SIZE])
        total += len(documents)
        print(f'{domain}/{path.name}: {len(documents)} passages ready ({len(pending)} new).')
    print(f'{domain}: {total} passages ready from supported substantive documents.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--domain', choices=['clinical', 'technology', 'all'], default='all')
    args = parser.parse_args()
    for domain in (['clinical', 'technology'] if args.domain == 'all' else [args.domain]):
        ingest_domain(domain)
