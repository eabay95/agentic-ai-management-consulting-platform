"""Guard domain boundaries while retaining explicit multi-domain requests."""
import re

CLINICAL_INTENT = re.compile(
    r'\b(?:clinical|medical|patient\w*|cardiovascular|heart attacks?|heart disease|'
    r'diabetes|covid(?:-19)?|laborator\w*|assays?|diagnos\w*)\b', re.I)
ENTERPRISE_TECHNOLOGY_INTENT = re.compile(
    r'\b(?:cisco|catalyst|routers?|networking|cloud|gcp|mcp|rag|'
    r'model context protocol|retrieval.augmented generation|infrastructure|'
    r'servers?|deploy\w*|integrat\w*|cybersecurity|kubernetes|'
    r'software architecture|latency|edge computing|iot)\b', re.I)


def clinical_without_enterprise_technology(question):
    return bool(CLINICAL_INTENT.search(question) and not ENTERPRISE_TECHNOLOGY_INTENT.search(question))


def apply_domain_policy(question, domains):
    domains = list(dict.fromkeys(domains))
    adjustments = []
    if clinical_without_enterprise_technology(question):
        if 'clinical' not in domains:
            domains.insert(0, 'clinical')
            adjustments.append('Added Clinical: the question concerns medical research or laboratory evidence.')
        if 'technology' in domains:
            domains.remove('technology')
            adjustments.append('Excluded Technology: medical machine-learning methods alone do not request enterprise infrastructure analysis.')
    return domains, adjustments
