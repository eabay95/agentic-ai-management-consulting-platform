"""Source filters prevent a named supplier/period from falling back to another."""
import re
from agents.routing_policy import clinical_without_enterprise_technology


def retrieve_documents(store, domain, question, k=5):
    if domain == 'technology' and clinical_without_enterprise_technology(question):
        return []
    lower = question.lower()
    clauses = []
    if domain == 'sec':
        companies = [name for name in ('Cisco', 'Alphabet', 'Agilent') if name.lower() in lower]
        if 'google' in lower and 'Alphabet' not in companies:
            companies.append('Alphabet')
        if companies:
            clauses.append({'company': {'$in': companies}})
        records = store.get(include=['metadatas'])['metadatas']
        years = set(re.findall(r'\b20\d{2}\b', question))
        if years:
            periods = sorted({m['reporting_period'] for m in records
                              if m.get('reporting_period', '')[:4] in years
                              and (not companies or m.get('company') in companies)})
            if not periods:
                return []
            clauses.append({'reporting_period': {'$in': periods}})
        if re.search(r'\brisks?\b', question, re.I) and any(m.get('section') == 'risk_factors' and (not companies or m.get('company') in companies) and (not years or m.get('reporting_period', '')[:4] in years) for m in records):
            clauses.append({'section': {'$eq': 'risk_factors'}})
    elif domain == 'technology':
        organizations = []
        if 'cisco' in lower: organizations.append('Cisco')
        if re.search(r'\b(google|gcp|mcp|rag)\b', lower): organizations.append('Google Cloud')
        if organizations:
            clauses.append({'source_organization': {'$in': organizations}})
        families = list(dict.fromkeys(re.sub(r'\s+', ' ', name).lower() for name in re.findall(r'(?i)\b(?:Catalyst\s+(?:8300|8200|8000V)|ASR\s+1000)\b', question)))
        if families:
            clauses.append({'product_family': {'$in': families}})
    elif domain == 'clinical' and re.search(r'\b(agilent|instrument|instruments|assay|throughput)\b', lower):
        clauses.append({'source_organization': {'$eq': 'Agilent'}})
    query = {'k': k}
    if clauses:
        query['filter'] = clauses[0] if len(clauses) == 1 else {'$and': clauses}
    return store.similarity_search(question, **query)
