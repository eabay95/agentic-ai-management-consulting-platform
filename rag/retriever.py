import re


def retrieve(store, domain, question, customer_id, k=5):
    years = sorted(set(re.findall(r'\b20\d{2}\b', question)))
    organizations = [None]
    if domain == 'sec':
        organizations = [name for name in ('Cisco','Agilent','Alphabet') if name.lower() in question.lower()]
        if 'google' in question.lower() and 'Alphabet' not in organizations:
            organizations.append('Alphabet')
        organizations = organizations or [None]
    elif domain == 'clinical' and re.search(r'\b(agilent|instrument|instruments|assay|throughput)\b',question,re.I):
        organizations = ['Agilent']
    elif domain == 'technology':
        organizations = []
        if re.search(r'\bcisco\b', question, re.I):
            organizations.append('Cisco')
        if re.search(r'\b(google|gcp)\b', question, re.I):
            organizations.append('Google Cloud')
        organizations = organizations or [None]
    evidence = []
    for year in years or [None]:
        for organization in organizations:
            evidence.extend(store.search(domain, question, customer_id, k, year, organization))
    # General SOFI reports cannot establish a named equipment supplier's CSR record.
    if (domain == 'csr' and re.search(r'\b(cisco|agilent|alphabet|google)\b', question, re.I)
            and not re.search(r'\b(food|hunger|nutrition|malnutrition|conflict|war)\b', question, re.I)):
        evidence = [e for e in evidence if not e['metadata']['document_name'].upper().startswith('SOFI-')]
    return list({e['id']:e for e in evidence}.values())
