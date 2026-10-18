"""Retrieve Cisco's official 2025 annual report, preserving source provenance."""
import json
from pathlib import Path
from urllib.request import Request, urlopen
import pymupdf

BASE = Path(__file__).resolve().parent
OUTPUT = BASE / 'data' / 'sec' / 'Cisco-2025-Annual-Report.pdf'
URLS = (
    'https://www.cisco.com/c/dam/en_us/about/annual-report/2025-cisco-full-annual-report.pdf',
    'https://investor.cisco.com/files/doc_financials/2025/ar/2025-Cisco-Full-Annual-Report.pdf',
)


def fetch():
    if OUTPUT.is_file():
        return OUTPUT
    errors = []
    for url in URLS:
        try:
            with urlopen(Request(url, headers={'User-Agent':'CMPE256-Research-Prototype/1.0'}), timeout=30) as response:
                content = response.read(25_000_001)
            if len(content) > 25_000_000 or not content.startswith(b'%PDF-'):
                raise ValueError('Not a supported PDF response.')
            with pymupdf.open(stream=content, filetype='pdf') as document:
                cover = ' '.join(document[i].get_text() for i in range(min(30, len(document))))
                if 'CISCO SYSTEMS' not in cover.upper() or 'July 26, 2025' not in cover:
                    raise ValueError('Could not verify Cisco fiscal 2025 cover metadata.')
            OUTPUT.parent.mkdir(parents=True, exist_ok=True)
            OUTPUT.write_bytes(content)
            OUTPUT.with_suffix('.source.json').write_text(json.dumps({'source_url':url}),encoding='utf-8')
            print('Verified official Cisco fiscal 2025 annual report:', OUTPUT, flush=True)
            return OUTPUT
        except Exception as error:
            errors.append(dict(url=url,error=str(error)))
    (BASE/'data'/'sec_fetch_report.json').write_text(json.dumps(errors,indent=2),encoding='utf-8')
    print('Cisco filing unavailable; see data/sec_fetch_report.json. Existing filings remain usable.',flush=True)
    return None


if __name__ == '__main__':
    fetch()
