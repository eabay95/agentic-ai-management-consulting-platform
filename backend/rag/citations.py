"""Citation identity checks. These do not prove that sources entail claims."""
import re

FAILED_STATUSES = {'error', 'insufficient_evidence', 'citation_error', 'uncited_needs_review'}


def check_citations(answer, sources):
    valid = {str(source['id']) for source in sources}
    cited, invalid = set(), set()
    for group in re.findall(r'\[([^\[\]\n]+)\]', answer):
        if not re.search(r'(?:\b[A-Z]\d+\b|\b[a-z]+:)', group):
            continue
        for label in group.split(','):
            label = label.strip()
            if label in valid:
                cited.add(label)
            else:
                invalid.add(label)
    return dict(valid=bool(cited) and not invalid, cited_ids=sorted(cited), invalid_ids=sorted(invalid),
                note='Source labels only; claim support requires review of the cited passages.')


def usable_result(result):
    return (result.get('status') not in FAILED_STATUSES
            and isinstance(result.get('answer'), str) and bool(result['answer'].strip())
            and bool(result.get('sources')) and result.get('citation_check', {}).get('valid', True))


def source_registry(results):
    registry = {}
    for domain, result in results.items():
        if not usable_result(result):
            continue
        for index, source in enumerate(result['sources'], 1):
            if not (source.get('excerpt') or source.get('passage')):
                continue
            label = f"{domain}:{source.get('id') or index}"
            registry[label] = dict(id=label, document=source.get('document') or source.get('source'),
                                   page=source.get('pdf_page', source.get('page')),
                                   excerpt=source.get('excerpt') or source.get('passage'),
                                   source_url=source.get('source_url', ''))
    return registry
