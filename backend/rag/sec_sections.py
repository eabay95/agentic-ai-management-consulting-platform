"""Identify physical PDF pages in the actual Item 1A body, excluding TOCs."""
import re


def risk_factor_pages(documents):
    by_page = {}
    for document in documents:
        page = document.metadata.get('page')
        if isinstance(page, int):
            by_page.setdefault(page, []).append(document.page_content)
    pages = sorted(by_page)
    start = None
    end = None
    for page in pages:
        text = '\n'.join(by_page[page])
        if start is None and re.search(r'(?mi)^\s*Item\s+1A\.?\s*Risk\s+Factors\s*(?:\n|$)', text):
            start = page
        elif start is not None and re.search(r'(?mi)^\s*Item\s+1B\.?\s*(?:\n|Unresolved)', text):
            end = page
            break
    return set(range(start, (end if end is not None else pages[-1])+1)) if start is not None else set()
