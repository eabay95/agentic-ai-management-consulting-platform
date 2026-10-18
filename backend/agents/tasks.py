"""Focused specialist questions for multi-domain consultations; no extra API call."""
import re


def build_specialist_tasks(question, domains):
    if len(domains) < 2:
        return {domain: question for domain in domains}
    companies = [name for name in ('Cisco','Agilent','Alphabet','Google') if re.search(r'\b'+name+r'\b', question, re.I)]
    models = list(dict.fromkeys(re.findall(r'\b(?:Catalyst|ASR|ISR)\s+[A-Za-z0-9-]+\b', question, re.I)))
    sofi_years = list(dict.fromkeys(re.findall(r'\bSOFI\s*(?:report\s*)?(20\d{2})\b', question, re.I)))
    fiscal_years = list(dict.fromkeys(re.findall(r'\b(?:fiscal(?:\s+year)?|FY)\s*(20\d{2})\b', question, re.I)))
    if not fiscal_years:
        fiscal_years = sorted(set(re.findall(r'\b20\d{2}\b', question)) - set(sofi_years))
    context = ' '.join(word for word in ('nonprofit','field operations','laboratory') if word in question.lower())
    source_company = ', '.join(companies) or 'the requested supplier'
    concerns = [term for term in ('power','redundancy','environmental','bandwidth','connectivity','security','performance','cloud','MCP','RAG')
                if re.search(r'(?<![\w-])'+term+r'\b', question, re.I)]
    technology = ('Evaluate the documented technical capabilities and operational requirements of '
                  + ' '.join([source_company, *models]) + (' for '+context if context else '') + '. Technical concerns: '
                  + ', '.join(concerns or ['connectivity','power','environmental suitability','performance'])
                  + '. Explain evidence limitations within this technical scope, next actions and measurable success indicators.')
    sec = ('Analyze ' + source_company + ' financial and operational risks disclosed in '
           + ('fiscal ' + ' and '.join(fiscal_years) if fiscal_years else 'the relevant filings')
           + '. Retrieve risk-factor disclosures including supply-chain exposure, financial condition and supplier continuity '
             'where documented. Explain source limitations, next due-diligence actions and measurable indicators.')
    food_topic = bool(re.search(r'\b(food|SOFI|hunger|nutrition|malnutrition)\b', question, re.I))
    csr = (('Using SOFI ' + (' and '.join(sofi_years) or 'reports') + ', analyze food-access, healthy-diet affordability '
            'and food-security priorities relevant to ' + (context or 'the customer')
            + '. Propose program-aligned next actions and measurable indicators, labeling operational applications as inferences.')
           if food_topic else 'Assess ' + source_company + ' sustainability and corporate responsibility using relevant evidence. '
                                 'Do not substitute food-security reports for company-specific environmental performance. '
                                 'Identify source limitations and measurable due-diligence actions.')
    clinical_topics = re.findall(r'\b(?:heart attacks?|heart disease|diabetes|COVID(?:-19)?|assays?|instruments?|throughput|laboratory)\b', question, re.I)
    clinical = ('Analyze the uploaded clinical research and stated requirements concerning '
                + ', '.join(clinical_topics or ['the clinical decision'])
                + (' for Agilent' if 'Agilent' in companies else '')
                + '. Explain documented capabilities or methods, research limitations and evidence-based next steps.')
    tasks = dict(technology=technology,sec=sec,csr=csr,clinical=clinical)
    return {domain:tasks[domain] for domain in domains}
