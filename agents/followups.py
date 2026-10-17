"""Topic suggestions grounded in retrieved text, without generating new claims."""
import re


def suggest_followups(question, results):
    suggestions = []
    for result in results:
        evidence = result.get('evidence', [])
        if not evidence:
            continue
        text = ' '.join(e['text'] for e in evidence).lower()
        years = sorted({str(e['metadata'].get('year', '')) for e in evidence} - {''})
        period = ' and '.join(years)
        suffix = f' in the {period} report' if period else ' in the cited sources'
        domain = result['domain']
        if domain == 'csr':
            for pattern, topic in [(r'price|cost|afford', 'food prices and access to healthy diets'),
                                   (r'conflict|war', 'conflict and malnutrition'),
                                   (r'hunger|insecurity', 'the main drivers of food insecurity')]:
                if re.search(pattern, text):
                    suggestions.append(f'Explain {topic}{suffix}.')
        elif domain == 'sec':
            companies = sorted({e['metadata'].get('source_organization', '') for e in evidence} - {''})
            subject = ' and '.join(companies) or 'the company'
            if re.search(r'risk|uncertain', text):
                suggestions.append(f'Explain the disclosed financial risks for {subject}{suffix}.')
            if re.search(r'revenue|income', text):
                suggestions.append(f'What revenue and income information is disclosed for {subject}{suffix}?')
            elif 'cash flow' in text:
                suggestions.append(f'What cash-flow information is disclosed for {subject}{suffix}?')
        elif domain == 'technology':
            if re.search(r'catalyst|router|interface|network', text):
                vendor = 'Cisco ' if any(e['metadata'].get('source_organization') == 'Cisco' for e in evidence) else ''
                suggestions.append(f'Which {vendor}router model and interface details should we verify against the cited documentation before troubleshooting?')
            elif re.search(r'cloud|retrieval|mcp', text):
                suggestions.append('What cloud architecture limitations are described in the cited technology documentation?')
        elif domain == 'clinical':
            if any(e['metadata'].get('source_organization') == 'Agilent' for e in evidence):
                suggestions.append('Which Agilent instrument capabilities are documented, and which laboratory requirements still need verification?')
            else:
                suggestions.append('What limitations does the cited clinical research identify?')
    return [s for s in dict.fromkeys(suggestions) if s.casefold().strip(' .?') != question.casefold().strip(' .?')][:3]
