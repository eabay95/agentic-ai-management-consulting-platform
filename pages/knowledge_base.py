import json
import uuid
import streamlit as st
from config import DATA,DOMAINS
from customer.context import CustomerStore
from rag.ingestion import extract_resources,ingest_all,ingest_file
from rag.public_sources import approved_sources,fetch
from ui import manager

st.title('Knowledge Base')
st.write('Inspect provenance, index the supplied reports, or add documents to a specific customer’s collection.')
try:
    store = manager().store
except Exception as error:
    st.error(f'Vector database unavailable: {error}')
    st.stop()
st.caption(f'Embedding backend: {store.embeddings.backend} · {store.embeddings.signature}')
if store.embeddings.backend=='local':
    st.info('Offline lexical hashing embeddings are active. Set EMBEDDING_BACKEND=openai and rebuild to enable semantic retrieval. Each model/backend uses separate persistent collections.')
if st.button('Extract and index professor resources',type='primary'):
    with st.spinner('Safely extracting archives and indexing PDF pages…'):
        try:
            extract_resources()
            st.dataframe(ingest_all(store))
        except Exception as error:
            st.error(f'Ingestion failed: {error}')
active = st.session_state.get('active_customer','public')
inventory = store.inventory(active)
st.subheader('Indexed document metadata')
if inventory:
    st.dataframe(inventory,width='stretch')
else:
    st.info('No documents indexed for this customer and embedding backend yet.')
report_path = DATA/'ingestion_report.json'
if report_path.exists():
    with st.expander('Last ingestion report'):
        st.json(json.loads(report_path.read_text('utf-8')))
st.subheader('Additional documents')
scope = st.radio('Document visibility',['Current customer (private)','Shared public'],horizontal=True)
domain = st.selectbox('Knowledge domain',DOMAINS)
upload = st.file_uploader('PDF or TXT document',type=['pdf','txt'])
if st.button('Ingest uploaded document',disabled=upload is None):
    if scope.startswith('Current') and active=='public':
        st.error('Select a customer in AI Management Consulting first.')
    else:
        customer_id = active if scope.startswith('Current') else 'public'
        if customer_id!='public':
            CustomerStore().get(customer_id)
        folder = DATA/'uploads'/customer_id/domain
        folder.mkdir(parents=True,exist_ok=True)
        # A random local name prevents overwrites and ignores untrusted upload paths.
        suffix = '.pdf' if upload.name.lower().endswith('.pdf') else '.txt'
        path = folder/(str(uuid.uuid4())+suffix)
        path.write_bytes(upload.getvalue())
        path.with_suffix(path.suffix+'.json').write_text(json.dumps({'document_name':upload.name.replace('\\','/').split('/')[-1]}),encoding='utf-8')
        try:
            count = ingest_file(store,path,domain,customer_id)
            st.success(f'Indexed {count} chunks for {customer_id}.')
        except Exception as error:
            st.error(f'Unsupported or unreadable document: {error}')
st.caption('Customer filtering isolates retrieval and histories in this local demonstration. It is not a production access-control boundary.')
st.subheader('Professor-approved public documentation')
sources = approved_sources()
url = st.selectbox('Reference URL',list(sources))
st.caption('Fetches only this exact URL, with no crawling or redirect following. Access failures are reported; descriptions are never substituted for content.')
if st.button('Fetch selected public source and index'):
    try:
        with st.spinner('Retrieving public documentation…'):
            path,domain = fetch(url)
            count = ingest_file(store,path,domain)
        st.success(f'Indexed {count} chunks from the fetched source.')
    except Exception as error:
        st.error(f'Public source unavailable: {error}')
source_report = DATA/'public_source_report.json'
if source_report.exists():
    with st.expander('Public source access report'):
        st.dataframe(json.loads(source_report.read_text('utf-8')),width='stretch')
st.subheader('Structured clinical research datasets')
trials = sorted((DATA/'clinical').rglob('*.csv'))
if trials:
    st.caption('Trial registrations are research records, not proof of treatment effectiveness or equipment specifications. These tables are not automatically embedded.')
    selected_trial = st.selectbox('Trial dataset',trials,format_func=lambda p:p.name)
    import pandas as pd
    preview = pd.read_csv(selected_trial,nrows=100,dtype='string')
    st.dataframe(preview,width='stretch')
    st.caption('Preview: first 100 records. Full preserved CSV: '+str(selected_trial))
