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
    documents = [d for d in load_and_split(str(path)) if d.page_content.strip()]
    if not documents:
        raise ValueError(f'No extractable text: {path.name}')
    for document in documents:
        if provenance.get('source_url'):
            document.metadata['source_url'] = provenance['source_url']
        document.metadata.update(domain=domain, document_name=path.name,
                                 ingestion_owner=f'{domain}_documents_v1')
        page = document.metadata.get('page')
        if isinstance(page, int):
            document.metadata['page_number'] = page + 1
    return documents, ''


def ingest_domain(domain):
    folder = BASE_DIR / 'data' / domain
    if not folder.is_dir():
        print(f'{domain}: no data directory; nothing to ingest.')
        return
    store = None
    total = 0
    for path in sorted(folder.rglob('*')):
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
        relative = path.relative_to(folder).as_posix()
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
