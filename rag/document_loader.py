"""Page-preserving loaders and bounded, traversal-safe archive extraction."""
import hashlib
import json
import re
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath
import pymupdf


def safe_extract(archive, destination, max_bytes=600_000_000):
    destination = Path(destination).resolve()
    with zipfile.ZipFile(archive) as source:
        members = source.infolist()
        if sum(m.file_size for m in members) > max_bytes:
            raise ValueError('Archive exceeds extraction size limit.')
        for member in members:
            name = PurePosixPath(member.filename.replace('\\', '/'))
            target = (destination / str(name)).resolve()
            if (name.is_absolute() or '..' in name.parts or ':' in str(name)
                    or not target.is_relative_to(destination)
                    or stat.S_ISLNK(member.external_attr >> 16)):
                raise ValueError(f'Unsafe archive member: {member.filename}')
        for member in members:
            target = destination / member.filename.replace('\\', '/')
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.open(member) as src, target.open('wb') as dst:
                    shutil.copyfileobj(src, dst)


def load_document(path, domain, customer_id='public'):
    path = Path(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    sidecar = path.with_suffix(path.suffix+'.json')
    extra = json.loads(sidecar.read_text('utf-8')) if sidecar.exists() else {}
    organization = next((o for o in ['Cisco', 'Agilent', 'Alphabet'] if o.lower() in str(path).lower()), '')
    if domain == 'csr':
        organization = 'FAO / IFAD / UNICEF / WFP / WHO'
    metadata = dict(document_name=path.name, domain=domain, source_organization=organization,
                    original_path=str(path.resolve()), page=0, year='', source_url='',
                    customer_id=customer_id, document_hash=digest, **{})
    metadata.update({k:v for k,v in extra.items() if k in ('source_url', 'source_organization', 'year', 'document_name')})
    if path.suffix.lower() == '.pdf':
        with pymupdf.open(path) as document:
            first = '\n'.join(document[i].get_text() for i in range(min(3, len(document))))
            if not metadata['year']:
                # Only use an explicit fiscal/report year, not an arbitrary body date.
                year = re.search(r'(?:SOFI[- ]|fiscal year ended[^\n]*?)(20\d{2})', path.name+' '+first, re.I)
                metadata['year'] = year.group(1) if year else ''
            for number, page in enumerate(document, 1):
                text = page.get_text().strip()
                if text:
                    yield text, {**metadata, 'page': number}
    elif path.suffix.lower() == '.txt':
        text = path.read_text('utf-8-sig').strip()
        # Reference lists are a source registry, not substantive retrieved evidence.
        if re.search(r'https?://', text) and not metadata['source_url']:
            return
        if text:
            yield text, metadata
    else:
        raise ValueError('Only PDF and TXT documents are supported.')
