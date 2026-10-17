import uuid
import streamlit as st
from customer.context import CustomerStore
from recommendations.consulting_ranker import DEFAULT_WEIGHTS
from ui import manager, show_answer
from llm import configured, provider, key_variable, model_name

st.title('AI Management Consulting')
st.caption('Ask a question. Your manager brings together the right specialists and supporting sources.')
customers = CustomerStore()
with st.expander('Customer profiles · optional'):
    with st.form('customer'):
        company = st.text_input('Company name')
        industry = st.text_input('Industry')
        requirements = st.text_area('Business requirements')
        equipment = st.text_area('Equipment / technology information')
        budget = st.text_input('Budget, currency and constraints')
        constraints = st.text_area('Mandatory compatibility / regulatory requirements')
        if st.form_submit_button('Create profile'):
            try:
                created = customers.create(company, industry, requirements, equipment, budget, constraints)
                st.session_state['consulting_conversation'] = created['id']
                st.rerun()
            except ValueError as error:
                st.error(str(error))
profiles = customers.list()
names = {p['id']: p['company'] for p in profiles}
selected = st.selectbox('Conversation', ['guest', *names],
                        format_func=lambda value: 'Guest / Demo' if value == 'guest' else names[value],
                        key='consulting_conversation')
if selected == 'guest':
    profile = st.session_state.setdefault('guest_profile', dict(
        id=str(uuid.uuid4()), company='Guest / Demo', industry='', requirements='',
        equipment='', budget='', constraints='', history=[]))
    st.session_state.pop('active_customer', None)
    st.caption('Guest conversation stays in this browser session. No profile required.')
else:
    profile = customers.get(selected)
    st.session_state['active_customer'] = selected
    st.caption(f"Customer: {profile['company']} · Separate saved history · Selection is not authentication.")
    with st.expander('Current customer requirements'):
        st.json({k: v for k, v in profile.items() if k != 'history'})
if st.button('Clear Chat', key='clear_consulting_chat'):
    profile['history'] = []
    if selected != 'guest':
        customers.save(profile)
    st.rerun()
with st.expander('Reasoning and recommendation settings'):
    use_llm = st.toggle(f'Use {provider().title()} reasoning', value=configured(), key='consulting_use_llm')
    st.caption(f'Reasoning provider: {provider().title()} · Model: {model_name()}')
    weights = {key: st.slider(key.replace('_', ' ').title(), 0.0, 1.0, value, 0.05, key='weight_'+key)
               for key, value in DEFAULT_WEIGHTS.items()}
    st.caption('Weights apply only to verified numeric factors. Mandatory checks cannot be overridden.')
if not configured():
    st.caption(f'Evidence-only mode: source excerpts work now. Add {key_variable()} to .env and restart Streamlit for generated consulting analysis.')
if not profile['history']:
    with st.chat_message('assistant', avatar=':material/support_agent:'):
        st.write('How can I help? Ask about food security, Cisco networking, company financial disclosures, or clinical research. I will show which specialists participate and the sources they retrieve.')
for index, turn in enumerate(profile['history']):
    with st.chat_message('user', avatar=':material/person:'):
        st.write(turn['question'])
    with st.chat_message('assistant', avatar=':material/support_agent:'):
        show_answer(turn['answer'], key_prefix=f"{profile['id']}_{index}")
clicked = None
if profile['history']:
    suggestions = profile['history'][-1]['answer'].get('followups', [])
    if suggestions:
        st.caption('Explore this evidence')
        for index, suggestion in enumerate(suggestions):
            if st.button(suggestion, key=f"followup_{profile['id']}_{len(profile['history'])}_{index}"):
                clicked = suggestion
question = st.chat_input('Ask your management consulting team…', key='consulting_chat_input')
question = clicked or question
if question:
    with st.chat_message('user', avatar=':material/person:'):
        st.write(question)
    with st.spinner('Manager routing specialists and retrieving evidence…'):
        try:
            if sum(weights.values()) <= 0:
                st.error('At least one ranking weight must be positive.')
            else:
                answer = manager().answer(question, profile, use_llm, weights)
                if selected == 'guest':
                    profile['history'].append(dict(question=question, answer=answer))
                else:
                    customers.append(selected, question, answer)
                st.rerun()
        except Exception as error:
            st.error(f'Consulting unavailable: {type(error).__name__}. Check dependencies and knowledge-base ingestion.')
