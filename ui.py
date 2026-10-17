import streamlit as st
from config import RESOURCES


@st.cache_resource
def manager():
    from rag.vector_store import VectorStore
    from agents.manager import ManagerAgent
    return ManagerAgent(VectorStore())


@st.cache_data
def retail_model(support=0.005,confidence=0.08,lift=1.0,max_len=3):
    from recommendations.apriori import load_baskets,mine
    baskets = load_baskets(RESOURCES/'Retail.zip')
    itemsets,rules = mine(baskets,support,confidence,lift,max_len)
    return baskets,itemsets,rules


def parameters():
    with st.sidebar.expander('Apriori parameters'):
        support = st.number_input('Minimum support',0.001,1.0,0.005,0.001,format='%.3f',key='support')
        confidence = st.slider('Minimum confidence',0.0,1.0,0.08,0.01,key='confidence')
        lift = st.number_input('Minimum lift',0.0,20.0,1.0,0.1,key='lift')
        max_len = st.slider('Maximum itemset length',2,5,3,key='max_len')
    return dict(support=support,confidence=confidence,lift=lift,max_len=max_len)


def show_answer(answer, key_prefix='answer'):
    st.caption('Mode: '+answer.get('mode','unknown'))
    st.markdown(answer['summary'])
    sources = {}
    for specialist in answer.get('specialists', []):
        for evidence in specialist.get('evidence', []):
            metadata = evidence['metadata']
            identity = (metadata.get('original_path'), metadata['document_name'], metadata.get('source_url'))
            entry = sources.setdefault(identity, dict(metadata=metadata, pages=set()))
            if metadata.get('page'):
                entry['pages'].add(metadata['page'])
    st.caption('Sources retrieved for this response')
    if not sources:
        st.caption('No supporting sources found. No citations are available for this response.')
    for index, entry in enumerate(sources.values(), 1):
        metadata = entry['metadata']
        pages = ', '.join(str(page) for page in sorted(entry['pages']))
        st.write(f"[{index}] {metadata['document_name']} · " + (f'PDF page(s) {pages}' if pages else 'Web/text source · no page number'))
        url = metadata.get('source_url', '')
        if url.startswith('https://') or url.startswith('http://'):
            if pages and '.pdf' in url.lower():
                url = url.split('#')[0] + f"#page={min(entry['pages'])}"
            st.link_button('Open source', url)
        else:
            from pathlib import Path
            from config import DATA
            path = Path(metadata.get('original_path', '')).resolve()
            if path.is_file() and any(path.is_relative_to(root.resolve()) for root in (DATA, RESOURCES)):
                st.download_button('Download source', path.read_bytes(), file_name=metadata['document_name'],
                                   key=f'{key_prefix}_source_{index}', on_click='ignore')
    if answer['routes']:
        with st.expander('Agent routing and task ledger',expanded=True):
            for domain,reason in answer['routes'].items():
                specialist = next(r for r in answer['specialists'] if r['domain']==domain)
                st.write(f"**{domain.upper()}** · {reason} · {specialist['status']}")
    for specialist in answer['specialists']:
        with st.expander(specialist['domain'].upper()+' · Evidence and analysis'):
            for claim in specialist['claims']:
                st.write(claim['text'])
                st.caption('Source: '+claim['source_id'])
                st.text(claim['quote'])
            for evidence in specialist['evidence']:
                metadata = evidence['metadata']
                st.markdown(f"**{metadata['document_name']}** · PDF page {metadata['page']} · {metadata['year'] or 'year unknown'}")
                st.caption(f"{metadata['source_organization']} · {evidence['id']}")
                st.text(evidence['text'])
                st.caption('Source path: '+metadata['original_path'])
                if metadata['source_url']:
                    st.link_button('Original public documentation',metadata['source_url'])
            for limitation in specialist['limitations']:
                st.warning(limitation)
    if answer.get('ranked'):
        st.subheader('Recommendations passing mandatory checks')
        for i,candidate in enumerate(answer['ranked'],1):
            st.write(f"{i}. {candidate.get('title','Proposal')}: {candidate.get('rationale','')}")
            st.caption('Numeric score unavailable: no verified numeric factors supplied.')
    for candidate in answer.get('pending',[]):
        st.info(f"Proposal pending compatibility/regulatory verification: {candidate.get('title','')} — {candidate.get('rationale','')}")
    if answer['questions']:
        st.subheader('Information needed / next steps')
        for question in answer['questions']:
            st.write('• '+question)
