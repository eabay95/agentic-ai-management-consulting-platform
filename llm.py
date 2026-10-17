"""Provider selection shared by the manager, specialists and consulting UI."""
import json
import os
import config  # Load the project's .env before resolving provider settings.


def provider():
    selected = os.getenv('LLM_PROVIDER', 'auto').strip().lower()
    if selected == 'auto':
        return 'gemini' if os.getenv('GEMINI_API_KEY') else 'openai' if os.getenv('OPENAI_API_KEY') else 'gemini'
    if selected not in ('gemini', 'openai'):
        raise ValueError('LLM_PROVIDER must be auto, gemini or openai.')
    return selected


def key_variable():
    return 'GEMINI_API_KEY' if provider() == 'gemini' else 'OPENAI_API_KEY'


def configured():
    return bool(os.getenv(key_variable(), '').strip())


def model_name():
    return os.getenv('GEMINI_MODEL', 'gemini-flash-latest') if provider() == 'gemini' else os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')


def generate_json(instructions, payload):
    if not configured():
        raise ValueError(f'{key_variable()} is required for {provider()} reasoning.')
    if provider() == 'gemini':
        from google import genai
        from google.genai import types
        with genai.Client(api_key=os.environ['GEMINI_API_KEY'],
                          http_options=types.HttpOptions(timeout=60_000)) as client:
            response = client.models.generate_content(
                model=model_name(), contents=json.dumps(payload),
                config=types.GenerateContentConfig(system_instruction=instructions,
                                                    response_mime_type='application/json'))
        text = response.text
    else:
        from openai import OpenAI
        response = OpenAI(timeout=60, max_retries=1).responses.create(
            model=model_name(), store=False, instructions=instructions,
            input=json.dumps(payload), text={'format': {'type': 'json_object'}})
        text = response.output_text
    if not text:
        raise ValueError('The reasoning provider returned no response text.')
    result = json.loads(text)
    if not isinstance(result, dict):
        raise ValueError('The reasoning provider must return a JSON object.')
    return result
