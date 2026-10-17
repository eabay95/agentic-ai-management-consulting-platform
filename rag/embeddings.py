import os
from sklearn.feature_extraction.text import HashingVectorizer


class Embeddings:
    def __init__(self, backend=None):
        self.backend = backend or os.getenv('EMBEDDING_BACKEND', 'local')
        if self.backend not in ('local', 'openai'):
            raise ValueError('EMBEDDING_BACKEND must be local or openai.')
        self.model = os.getenv('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small')
        self.signature = self.model if self.backend == 'openai' else 'hashing-2048-v1'
        self.vectorizer = HashingVectorizer(n_features=2048, alternate_sign=False, norm='l2', stop_words='english')

    def encode(self, texts):
        if self.backend == 'local':
            return self.vectorizer.transform(texts).toarray().tolist()
        if not os.getenv('OPENAI_API_KEY'):
            raise ValueError('OPENAI_API_KEY is required for semantic embeddings.')
        from openai import OpenAI
        result = OpenAI(timeout=60, max_retries=2).embeddings.create(model=self.model, input=texts)
        return [d.embedding for d in sorted(result.data, key=lambda d:d.index)]
