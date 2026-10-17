import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')
DATA = ROOT / 'data'
RESOURCES = ROOT / 'professor_resources'
DOMAINS = ('technology', 'clinical', 'sec', 'csr')
MODEL = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')
