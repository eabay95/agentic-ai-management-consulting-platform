import hashlib
import zipfile
import pytest
from rag.document_loader import safe_extract,load_document
from rag.chunker import chunks
from rag.vector_store import VectorStore
from rag.ingestion import ingest_file
from agents.base import validate_claims


def test_traversal_rejected_before_extract(tmp_path):
    archive=tmp_path/'evil.zip'
    with zipfile.ZipFile(archive,'w') as source:
        source.writestr('ok.txt','safe')
        source.writestr('../evil.txt','unsafe')
    with pytest.raises(ValueError):
        safe_extract(archive,tmp_path/'output')
    assert not (tmp_path/'output'/'ok.txt').exists()


def test_stable_page_chunks():
    metadata=dict(document_hash='hash',domain='sec',customer_id='public',page=4)
    pages=[('fiscal risk disclosure '*200,metadata)]
    first=list(chunks(pages))
    assert first==list(chunks(pages))
    assert len(first)>1 and all(c['metadata']['page']==4 for c in first)


def test_reference_lists_not_evidence(tmp_path):
    path=tmp_path/'sources.txt'
    path.write_text('Amazing component https://www.cisco.com/example',encoding='utf-8')
    assert list(load_document(path,'technology'))==[]


def test_citation_validation():
    evidence=[dict(id='valid',text='The report discloses supply chain risks.')]
    assert len(validate_claims([dict(text='Risk',source_id='valid',quote='discloses supply chain risks')],evidence))==1
    assert validate_claims([dict(source_id='fake',quote='discloses supply chain risks')],evidence)==[]
    assert validate_claims([dict(source_id='valid',quote='Invented source excerpt')],evidence)==[]


def test_persistent_store_isolation_and_updates(tmp_path):
    store=VectorStore(tmp_path/'chroma',backend='local')
    public=tmp_path/'public.txt'; public.write_text('Cisco router connectivity public diagnostics manual')
    private=tmp_path/'private.txt'; private.write_text('Cisco router connectivity private confidential calibration')
    ingest_file(store,public,'technology')
    ingest_file(store,private,'technology','customer-a')
    assert any(e['metadata']['customer_id']=='customer-a' for e in store.search('technology','Cisco router connectivity','customer-a'))
    assert all(e['metadata']['customer_id']=='public' for e in store.search('technology','Cisco router connectivity','customer-b'))
    assert store.search('sec','Cisco router connectivity','customer-a')==[]
    count=store.collections['technology'].count()
    ingest_file(store,private,'technology','customer-a')
    assert store.collections['technology'].count()==count
    private.write_text('Cisco router connectivity revised calibration')
    ingest_file(store,private,'technology','customer-a')
    assert store.collections['technology'].count()==count
    assert not any('confidential' in e['text'] for e in store.search('technology','Cisco router','customer-a'))
    reopened=VectorStore(tmp_path/'chroma',backend='local')
    assert reopened.collections['technology'].count()==count
