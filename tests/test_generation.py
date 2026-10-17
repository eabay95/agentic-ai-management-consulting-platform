from types import SimpleNamespace
import pytest
from agents.technology import TechnologyAgent
from agents.manager import ManagerAgent
from rag.embeddings import Embeddings


@pytest.fixture(autouse=True)
def select_openai(monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER', 'openai')


class Store:
    def search(self,domain,*args,**kwargs):
        if domain!='technology': return []
        return [dict(id='a'*64,text='The platform has modular network interfaces for expansion.',
                     metadata=dict(document_name='manual.pdf',page=3,domain=domain),distance=.2)]


def test_specialist_generation_contract(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','unit-test-key-not-real')
    monkeypatch.setattr('agents.base.generate_json',lambda *args:{
        'claims':[dict(text='Interfaces are modular.',source_id='a'*64,quote='modular network interfaces for expansion.')],
        'recommendations':[dict(title='Check interface requirements',source_ids=['a'*64],constraints={})],
        'questions':['Which model?'],'limitations':['Compatibility unknown']})
    result=TechnologyAgent().run('router interfaces',{'id':'customer','history':[]},Store())
    assert result['status']=='generated'
    assert len(result['claims'])==1 and len(result['recommendations'])==1


def test_api_failure_preserves_evidence(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','unit-test-key-not-real')
    def fail(*args): raise RuntimeError('API unavailable')
    monkeypatch.setattr('agents.base.generate_json',fail)
    result=TechnologyAgent().run('router interfaces',{'id':'customer'},Store())
    assert result['status']=='api_error' and result['evidence']


def test_embedding_api_contract(monkeypatch):
    seen={}
    def create(**kwargs):
        seen.update(kwargs)
        return SimpleNamespace(data=[SimpleNamespace(index=1,embedding=[0.,1.]),SimpleNamespace(index=0,embedding=[1.,0.])])
    monkeypatch.setenv('OPENAI_API_KEY','unit-test-key-not-real')
    monkeypatch.setattr('openai.OpenAI',lambda **kwargs:SimpleNamespace(embeddings=SimpleNamespace(create=create)))
    assert Embeddings('openai').encode(['first','second'])==[[1.,0.],[0.,1.]]
    assert seen['input']==['first','second']


def test_response_api_contract(monkeypatch):
    from agents.base import generate_json
    monkeypatch.setenv('OPENAI_API_KEY', 'unit-test-key-not-real')
    seen={}
    def create(**kwargs):
        seen.update(kwargs)
        return SimpleNamespace(output_text='{"claims": []}')
    monkeypatch.setattr('openai.OpenAI',lambda **kwargs:SimpleNamespace(responses=SimpleNamespace(create=create)))
    assert generate_json('instructions',{'question':'test'})=={'claims':[]}
    assert seen['store'] is False and seen['text']['format']['type']=='json_object'
