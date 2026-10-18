"""Normalize model text blocks without displaying reasoning or arbitrary objects."""


def response_text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return '\n'.join(text for part in value if (text := response_text(part)))
    if isinstance(value, dict) and value.get('type', 'text') == 'text':
        text = value.get('text')
        if isinstance(text, str):
            return text
        if isinstance(text, dict) and isinstance(text.get('value'), str):
            return text['value']
    return ''
