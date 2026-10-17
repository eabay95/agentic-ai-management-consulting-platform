"""Reproduce the inventory without modifying the professor's source files."""
import hashlib
import json
import zipfile
from pathlib import Path
import pandas as pd
import pymupdf

ROOT=Path(__file__).resolve().parents[1]
sources=ROOT/'professor_resources'
output=ROOT/'artifacts'
output.mkdir(exist_ok=True)
manifest=[]
for path in sorted(sources.iterdir()):
    entry=dict(name=path.name,bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    if path.suffix=='.zip':
        with zipfile.ZipFile(path) as archive:
            entry['members']=[]
            for member in archive.infolist():
                item=dict(name=member.filename,bytes=member.file_size)
                if member.filename.endswith('.csv'):
                    with archive.open(member) as stream:
                        frame=pd.read_csv(stream,nrows=5)
                        item['columns']=frame.columns.tolist()
                        item['preview_rows']=len(frame)
                if member.filename.endswith('.pdf'):
                    with pymupdf.open(stream=archive.read(member),filetype='pdf') as document:
                        item['pages']=len(document)
                        item['cover_excerpt']=document[0].get_text()[:1800]
                entry['members'].append(item)
    elif path.suffix=='.txt':
        entry['text']=path.read_text('utf-8-sig')
    elif path.suffix=='.pdf':
        with pymupdf.open(path) as document:
            entry['pages']=len(document)
            transcript='\n\n'.join(f'PAGE {i+1}\n{p.get_text()}' for i,p in enumerate(document))
            (output/'assignment_text.txt').write_text(transcript,encoding='utf-8')
    manifest.append(entry)
(output/'resource_inventory.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
print('Inventory saved to artifacts/resource_inventory.json; assignment transcript saved.')
