import json
import streamlit as st
from config import ROOT
from evaluation.evaluate_agents import evaluate_routing,evaluate_retrieval
from ui import manager

st.title('System Evaluation')
st.write('Measured checks are separate from human judgments about answer quality.')
if st.button('Evaluate labeled routing cases'):
    st.json(evaluate_routing())
if st.button('Evaluate retrieval against labeled source references'):
    try:
        st.json(evaluate_retrieval(manager().store))
    except Exception as error:
        st.error(f'Retrieval evaluation failed: {error}')
for name in ['routing_results.json','retrieval_results.json','retail_results.json','test_results.json']:
    path = ROOT/'artifacts'/name
    if path.exists():
        with st.expander(name,expanded=True):
            st.json(json.loads(path.read_text('utf-8')))
st.info('Citation ID and verbatim-excerpt checks are automatic structural checks. They do not prove that a claim follows from a source. Groundedness, relevance and completeness require human review; no scores are invented for unreviewed answers.')
st.subheader('Human review protocol')
st.write('Run each labeled question, inspect source pages, and score groundedness, recommendation relevance and completeness from 1–5. Record reviewer, source IDs, answer mode and rationale. Review equipment recommendations against manufacturer specifications. Evaluate generated answers separately from evidence-only output.')
path = ROOT/'evaluation'/'consulting_questions.json'
st.json(json.loads(path.read_text('utf-8')))
