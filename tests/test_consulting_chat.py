import pytest
from streamlit.testing.v1 import AppTest
from agents.manager import ManagerAgent, route
from agents.followups import suggest_followups
from rag.retriever import retrieve


QUESTIONS = [
    ('List the major reasons for food insecurity in 2023 according to the State of Food Security and Nutrition in the World 2023 report.', {'csr'}),
    ('List the major reasons for food insecurity in 2024.', {'csr'}),
    ('Explain malnutrition in war zones using the SOFI 2023 report.', {'csr'}),
    ('Explain the impact of increased food prices on food security.', {'csr'}),
    ("What are Cisco's major financial risks according to its 2025 SEC filing?", {'sec'}),
    ('What troubleshooting steps are recommended for Cisco Catalyst routers?', {'technology'}),
    ('Evaluate Cisco networking infrastructure, financial risks and sustainability.', {'technology', 'sec', 'csr'}),
]


@pytest.mark.parametrize('question,expected', QUESTIONS)
def test_requested_example_routes(question, expected):
    assert set(route(question)) == expected


def test_guest_chat_followups_citations_and_customer_isolation(monkeypatch, tmp_path):
    import customer.context
    monkeypatch.setattr(customer.context, 'DATA', tmp_path)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    named = customer.context.CustomerStore().create('Named Demo')
    app = AppTest.from_file('app.py', default_timeout=45).run()
    assert not app.exception
    assert app.chat_input and app.chat_message[0].name == 'assistant'
    assert app.selectbox(key='consulting_conversation').value == 'guest'
    app.chat_input[0].set_value(QUESTIONS[0][0]).run()
    assert not app.exception
    history = app.session_state['guest_profile']['history']
    assert len(history) == 1
    answer = history[0]['answer']
    assert set(answer['routes']) == {'csr'}
    evidence = answer['specialists'][0]['evidence']
    assert evidence and all(e['metadata']['document_name'] == 'SOFI-2023.pdf' for e in evidence)
    assert all(e['metadata']['page'] > 0 for e in evidence)
    assert any('SOFI-2023.pdf' in m.value and 'PDF page(s)' in m.value for m in app.markdown)
    assert app.get('download_button')  # Real local professor report is accessible.
    assert answer['followups'] and all('2023' in q for q in answer['followups'])
    app.run()
    assert len(app.session_state['guest_profile']['history']) == 1
    followup = answer['followups'][0]
    next(b for b in app.button if b.label == followup).click().run()
    assert not app.exception
    assert len(app.session_state['guest_profile']['history']) == 2
    assert app.session_state['guest_profile']['history'][1]['question'] == followup
    app.selectbox(key='consulting_conversation').set_value(named['id']).run()
    assert len(app.chat_message) == 1  # Named conversation starts empty.
    app.chat_input[0].set_value(QUESTIONS[4][0]).run()
    assert not app.exception
    saved = customer.context.CustomerStore().get(named['id'])
    assert len(saved['history']) == 1
    assert set(saved['history'][0]['answer']['routes']) == {'sec'}
    app.button(key='clear_consulting_chat').click().run()
    assert customer.context.CustomerStore().get(named['id'])['history'] == []
    assert len(app.session_state['guest_profile']['history']) == 2
    app.selectbox(key='consulting_conversation').set_value('guest').run()
    assert len(app.chat_message) == 4
    app.button(key='clear_consulting_chat').click().run()
    assert app.session_state['guest_profile']['history'] == []
    assert app.chat_input


def test_no_evidence_no_suggestions_or_citations():
    class EmptyStore:
        def search(self, *args, **kwargs):
            return []
    answer = ManagerAgent(EmptyStore()).answer('food insecurity 2023', {'id':'guest','history':[]}, False)
    assert 'Insufficient supporting evidence' in answer['summary']
    assert answer['followups'] == []
    assert not answer['specialists'][0]['evidence']


def test_topic_suggestions_require_supporting_text():
    result = dict(domain='csr', evidence=[dict(text='Food prices reduce affordability.', metadata={'year':'2023'})])
    suggestions = suggest_followups('food security', [result])
    assert len(suggestions) == 1 and 'prices' in suggestions[0]
    assert 'war' not in suggestions[0] and '2024' not in suggestions[0]


def test_source_and_year_filters():
    class RecordingStore:
        def __init__(self): self.calls = []
        def search(self, *args):
            self.calls.append(args)
            return []
    store = RecordingStore()
    retrieve(store, 'technology', QUESTIONS[5][0], 'guest')
    assert store.calls[0][-1] == 'Cisco'
    retrieve(store, 'sec', QUESTIONS[4][0], 'guest')
    assert store.calls[-1][-2:] == ('2025', 'Cisco')


def test_followup_year_replaces_previous_year():
    class RecordingStore:
        def __init__(self): self.calls = []
        def search(self, *args):
            self.calls.append(args)
            return []
    store = RecordingStore()
    ManagerAgent(store).answer('What about 2024?', dict(id='guest', history=[dict(question='food insecurity 2023')]), False)
    assert len(store.calls) == 1 and store.calls[0][-2] == '2024'


def test_real_example_sources_stay_in_domain_and_requested_period():
    from ui import manager
    store = manager().store
    for question, domains in QUESTIONS[:6]:
        domain = next(iter(domains))
        evidence = retrieve(store, domain, question, 'guest')
        assert evidence
        assert all(e['metadata']['domain'] == domain for e in evidence)
        if '2023' in question:
            assert all(e['metadata']['year'] == '2023' for e in evidence)
        if '2024' in question:
            assert all(e['metadata']['year'] == '2024' for e in evidence)
        if domain in ('sec', 'technology'):
            assert all(e['metadata']['source_organization'] == 'Cisco' for e in evidence)
        if domain == 'sec':
            assert all(e['metadata']['year'] == '2025' for e in evidence)
    assert retrieve(store, 'csr', 'Evaluate Cisco sustainability.', 'guest') == []


@pytest.mark.parametrize('citation,accepted', [('a'*64, True), ('fabricated-source', False)])
def test_manager_rejects_fabricated_synthesis_citations(monkeypatch, citation, accepted):
    manager = ManagerAgent(None)
    source_id = 'a'*64
    result = dict(domain='technology', status='generated',
                  evidence=[dict(id=source_id, text='Cisco router interfaces.', metadata={})],
                  claims=[dict(source_id=source_id, text='Documented interfaces.')],
                  recommendations=[], questions=[], limitations=[])
    monkeypatch.setattr(manager.specialists['technology'], 'run', lambda *args: result)
    text = f'Proposed next step [{source_id}] [{citation}]'
    monkeypatch.setattr('agents.manager.generate_json', lambda *args: {'summary':text})
    answer = manager.answer('Cisco router connectivity', {'id':'guest','history':[]}, True)
    assert (answer['summary'] == text) is accepted
