"""Fetch and cache the public documentation explicitly listed by the professor."""
import argparse
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, build_opener, HTTPRedirectHandler

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_URL = 'https://cloud.google.com/use-cases/retrieval-augmented-generation'


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class PageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.parts = []
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'nav', 'footer', 'header'):
            self.hidden += 1
    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'nav', 'footer', 'header'):
            self.hidden = max(0, self.hidden - 1)
    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


def reference_sources():
    sources = {}
    for location in ('technology', 'clinical'):
        for path in sorted((BASE_DIR / 'data' / location).glob('*.txt')):
            domain = 'clinical' if 'agilent' in path.name.lower() else location
            for url in re.findall(r'https://[^\s]+', path.read_text('utf-8-sig')):
                sources[url] = dict(domain=domain, reference_file=path.name)
    return sources


def fetch(url, refresh=False):
    sources = reference_sources()
    if url not in sources:
        raise ValueError('URL must exactly match a professor-listed HTTPS reference.')
    output = BASE_DIR / 'data' / sources[url]['domain'] / 'public_web'
    name = hashlib.sha256(url.encode()).hexdigest()[:20]
    if not refresh:
        for suffix in ('.pdf', '.txt'):
            candidate = output / (name + suffix)
            sidecar = candidate.with_suffix('.source.json')
            if candidate.is_file() and sidecar.is_file() and json.loads(sidecar.read_text('utf-8')).get('source_url') == url:
                return candidate
    request = Request(url, headers={'User-Agent': 'CMPE256-Research-Prototype/1.0'})
    with build_opener(NoRedirect).open(request, timeout=30) as response:
        content = response.read(25_000_001)
        content_type = response.headers.get_content_type()
        if len(content) > 25_000_000:
            raise ValueError('Document exceeds 25 MB.')
        if content.startswith(b'%PDF-'):
            suffix = '.pdf'
        elif content_type == 'text/html':
            parser = PageText()
            parser.feed(content.decode(response.headers.get_content_charset() or 'utf-8', errors='replace'))
            text = '\n'.join(parser.parts)
            if len(text) < 200:
                raise ValueError('Insufficient source content; not indexed.')
            if any(term in text.lower() for term in ('verify you are human', 'checking your browser', 'access denied', 'captcha')) and len(text) < 2500:
                raise ValueError('Access challenge returned instead of documentation.')
            content, suffix = text.encode('utf-8'), '.txt'
        else:
            raise ValueError(f'Unsupported source content type: {content_type}')
    output.mkdir(parents=True, exist_ok=True)
    path = output / (name + suffix)
    path.write_bytes(content)
    path.with_suffix('.source.json').write_text(json.dumps({
        'source_url': url, 'domain': sources[url]['domain'],
        'fetched_at': datetime.now(timezone.utc).isoformat(),
    }), encoding='utf-8')
    return path


def fetch_all(refresh=False):
    sources = reference_sources()
    def attempt(url):
        try:
            path = fetch(url, refresh=refresh)
            return dict(url=url, **sources[url], status='available', path=str(path))
        except Exception as error:
            return dict(url=url, **sources[url], status='unavailable', error=str(error))
    with ThreadPoolExecutor(max_workers=4) as pool:
        report = list(pool.map(attempt, sources))
    report_path = BASE_DIR / 'data' / 'public_source_report.json'
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    for row in report:
        print(f"{row['domain']}: {row['status']} - {row['url']}", flush=True)
        if row.get('error'):
            print(f"  {row['error']}", flush=True)
    print(f"{sum(r['status'] == 'available' for r in report)}/{len(report)} listed sources available. Full report: {report_path}", flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default=DEFAULT_URL)
    parser.add_argument('--all', action='store_true', help='Read every listed source, including Agilent clinical references.')
    parser.add_argument('--refresh', action='store_true', help='Download again rather than reuse successful cached content.')
    args = parser.parse_args()
    if args.all:
        fetch_all(args.refresh)
    else:
        print('Saved actual source content:', fetch(args.url, refresh=args.refresh))
