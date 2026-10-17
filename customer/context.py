import json
import uuid
from pathlib import Path
from config import DATA


class CustomerStore:
    """Local prototype persistence; customer selection is not authentication."""
    def __init__(self, path=None):
        self.path = Path(path or DATA/'customers')
        self.path.mkdir(parents=True,exist_ok=True)

    def _file(self, customer_id):
        # Disallow arbitrary paths and the reserved public knowledge identity.
        if str(uuid.UUID(customer_id)) != customer_id:
            raise ValueError('Invalid customer ID.')
        return self.path/(customer_id+'.json')

    def list(self):
        return [json.loads(p.read_text('utf-8')) for p in sorted(self.path.glob('*.json'))]

    def create(self, company, industry='', requirements='', equipment='', budget='', constraints=''):
        if not company.strip():
            raise ValueError('Company name is required.')
        profile = dict(id=str(uuid.uuid4()), company=company.strip(), industry=industry,
                       requirements=requirements,equipment=equipment,budget=budget,constraints=constraints,history=[])
        self.save(profile)
        return profile

    def get(self, customer_id):
        return json.loads(self._file(customer_id).read_text('utf-8'))

    def save(self, profile):
        target = self._file(profile['id'])
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps(profile,indent=2),encoding='utf-8')
        temporary.replace(target)

    def append(self, customer_id, question, answer):
        profile = self.get(customer_id)
        profile['history'].append(dict(question=question,answer=answer))
        self.save(profile)
