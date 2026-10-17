import streamlit as st
from config import DATA

st.set_page_config(page_title='SJSU | Decision Studio',page_icon='◈',layout='wide')
st.markdown('''<style>
.stApp {background:#f5f7fb;} h1,h2,h3 {color:#14344b;}
[data-testid="stSidebar"] {background:#102d43;}
[data-testid="stSidebar"] * {color:#e9f2fa;}
[data-testid="stMetric"] {background:white;padding:16px;border-radius:12px;}
</style>''',unsafe_allow_html=True)
st.sidebar.title('◈ Decision Studio')
st.sidebar.caption('CMPE 256 · SJSU · October 17, 2026')
st.sidebar.caption('Enterprise evidence. Practical decisions.')
st.navigation([
    st.Page('pages/consulting.py',title='AI Management Consulting',icon=':material/forum:'),
    st.Page('pages/retail.py',title='Retail Market Basket',icon=':material/shopping_cart:'),
    st.Page('pages/apriori_analytics.py',title='Apriori Analytics',icon=':material/analytics:'),
    st.Page('pages/knowledge_base.py',title='Knowledge Base',icon=':material/library_books:'),
    st.Page('pages/evaluation.py',title='System Evaluation',icon=':material/fact_check:'),
]).run()
