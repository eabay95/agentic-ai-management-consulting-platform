"""Fetch only exact professor-listed URLs; no implicit crawling or redirects."""
import hashlib
import json
import re
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup
from config import DATA, RESOURCES


def approved_sources():
    result = {}
    for path in RESOURCES.glob('*.txt'):
        domain = 'clinical' if path.name == 'Agilent.txt' else 'technology'
        for url in re.findall(r'https://[^\s]+',path.read_text('utf-8-sig')):
            result[url] = domain
    return result


def fetch(url):
    sources = approved_sources()
    if url not in sources:
        raise ValueError('URL must exactly match a professor-provided public reference.')
    # No redirects: even an approved source cannot redirect into a private service.
    with httpx.Client(timeout=30, follow_redirects=False) as client:
        with client.stream('GET',url,headers={'User-Agent':'CMPE256-Research-Prototype/1.0'}) as response:
            response.raise_for_status()
            content = bytearray()
            for block in response.iter_bytes():
                content.extend(block)
                if len(content) > 25_000_000:
                    raise ValueError('Source exceeds 25 MB download limit.')
            kind = response.headers.get('content-type','').lower()
    if content.startswith(b'%PDF'):
        extension, body = '.pdf', bytes(content)
    elif 'text/html' in kind:
        soup = BeautifulSoup(bytes(content),'html.parser')
        for tag in soup(['script','style','nav','footer','header']):
            tag.decompose()
        text = soup.get_text(' ',strip=True)
        if len(text) < 200:
            raise ValueError('Page contains insufficient extractable documentation.')
        extension, body = '.txt', text.encode('utf-8')
    else:
        raise ValueError(f'Unsupported response content type: {kind}')
    destination = DATA/sources[url]/'public_web'
    destination.mkdir(parents=True,exist_ok=True)
    path = destination/(hashlib.sha256(url.encode()).hexdigest()[:20]+extension)
    path.write_bytes(body)
    host = urlparse(url).hostname
    organization = 'Agilent' if 'agilent' in host else 'Cisco' if 'cisco' in host else 'Google Cloud'
    path.with_suffix(path.suffix+'.json').write_text(json.dumps(dict(source_url=url,source_organization=organization)),encoding='utf-8')
    return path, sources[url]


if __name__ == '__main__':
    from concurrent.futures import ThreadPoolExecutor
    def attempt(url):
        try:
            path, domain = fetch(url)
            return dict(url=url,domain=domain,path=str(path),status='downloaded')
        except Exception as error:
            return dict(url=url,status='unavailable',error=str(error))
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(attempt,approved_sources()))
    DATA.mkdir(exist_ok=True)
    (DATA/'public_source_report.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(json.dumps(results,indent=2))
