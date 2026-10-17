import json
from contextlib import nullcontext
from types import SimpleNamespace
import pytest
import llm
from agents.technology import TechnologyAgent
from agents.manager import ManagerAgent


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch):
    for name in ('LLM_PROVIDER', 'GEMINI_API_KEY', 'GEMINI_MODEL', 'OPENAI_API_KEY'):
        monkeypatch.delenv(name, raising=False)


def test_provider_selection(monkeypatch):
    assert llm.provider() == 'gemini' and not llm.configured()
    monkeypatch.setenv('OPENAI_API_KEY', 'openai-test')
    assert llm.provider() == 'openai'
    monkeypatch.setenv('GEMINI_API_KEY', 'gemini-test')
    assert llm.provider() == 'gemini'
    monkeypatch.setenv('LLM_PROVIDER', 'openai')
    assert llm.provider() == 'openai'
    monkeypatch.setenv('LLM_PROVIDER', 'invalid')
    with pytest.raises(ValueError, match='LLM_PROVIDER'):
        llm.provider()


def mock_client(monkeypatch, text):
    from google import genai
    calls = {}
    def generate_content(**kwargs):
        calls.update(kwargs)
        return SimpleNamespace(text=text)
    def client(**kwargs):
        calls['client'] = kwargs
        return nullcontext(SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)))
    monkeypatch.setattr(genai, 'Client', client)
    monkeypatch.setenv('GEMINI_API_KEY', 'gemini-test')
    return calls


def test_gemini_sdk_contract(monkeypatch):
    calls = mock_client(monkeypatch, '{"claims": []}')
    monkeypatch.setenv('GEMINI_MODEL', 'test-model')
    assert llm.generate_json('Use evidence only', {'question':'router'}) == {'claims':[]}
    assert calls['model'] == 'test-model'
    assert calls['config'].system_instruction == 'Use evidence only'
    assert calls['config'].response_mime_type == 'application/json'
    assert json.loads(calls['contents']) == {'question':'router'}
    assert calls['client']['http_options'].timeout == 60_000


@pytest.mark.parametrize('text', ['', 'not JSON', '[]'])
def test_bad_response_rejected(monkeypatch, text):
    mock_client(monkeypatch, text)
    with pytest.raises(ValueError):
        llm.generate_json('instructions', {})


def test_missing_gemini_key_does_not_use_openai(monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER', 'gemini')
    monkeypatch.setenv('OPENAI_API_KEY', 'unrelated-test-key')
    with pytest.raises(ValueError, match='GEMINI_API_KEY'):
        llm.generate_json('instructions', {})


class EvidenceStore:
    def search(self, *args, **kwargs):
        return [dict(id='a'*64, text='The platform has modular network interfaces for expansion.',
                     metadata={'source_organization':'Cisco'}, distance=.2)]


def test_gemini_specialist_validates_quotes(monkeypatch):
    mock_client(monkeypatch, json.dumps(dict(claims=[
        dict(text='Modular interfaces.', source_id='a'*64, quote='modular network interfaces for expansion.'),
        dict(text='Invented.', source_id='fake', quote='fabricated compatibility claim')],
        recommendations=[], questions=[], limitations=[])))
    answer = TechnologyAgent().run('Cisco router', {'id':'guest'}, EvidenceStore())
    assert answer['status'] == 'generated' and len(answer['claims']) == 1


def test_gemini_failure_keeps_evidence(monkeypatch):
    mock_client(monkeypatch, '')
    answer = TechnologyAgent().run('Cisco router', {'id':'guest'}, EvidenceStore())
    assert answer['status'] == 'api_error' and answer['evidence']
    assert 'Gemini reasoning failed' in answer['limitations'][0]


def test_manager_synthesis_uses_gemini(monkeypatch):
    from google import genai
    mock_client(monkeypatch, '{}')
    def generate_content(**kwargs):
        if 'findings' in json.loads(kwargs['contents']):
            return SimpleNamespace(text=json.dumps({'summary': 'Review the modular interfaces ['+'a'*64+'].'}))
        return SimpleNamespace(text=json.dumps(dict(claims=[dict(text='Modular interfaces.',source_id='a'*64,
            quote='modular network interfaces for expansion.')],recommendations=[],questions=[],limitations=[])))
    monkeypatch.setattr(genai, 'Client', lambda **kwargs: nullcontext(SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))))
    result = ManagerAgent(EvidenceStore()).answer('Cisco router', {'id':'guest','history':[]})
    assert result['mode'] == 'gemini' and 'Review the modular interfaces' in result['summary']
