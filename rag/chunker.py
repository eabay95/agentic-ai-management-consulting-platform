import hashlib
import re


def chunks(pages, size=1400, overlap=180):
    if not 0 <= overlap < size:
        raise ValueError('Overlap must be smaller than chunk size.')
    for text, metadata in pages:
        text = re.sub(r'[ \t]+', ' ', text)
        start = 0
        while start < len(text):
            end = min(start+size, len(text))
            if end < len(text):
                boundary = text.rfind(' ', start+size//2, end)
                if boundary > start:
                    end = boundary
            body = text[start:end].strip()
            identity = '|'.join(str(metadata[k]) for k in ('document_hash', 'domain', 'customer_id', 'page'))
            identifier = hashlib.sha256(f'{identity}|{start}|{body}'.encode()).hexdigest()
            if body:
                yield dict(id=identifier, text=body, metadata={**metadata, 'offset': start})
            if end == len(text):
                break
            start = end-overlap
