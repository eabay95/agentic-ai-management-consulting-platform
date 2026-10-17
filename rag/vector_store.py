import hashlib
import chromadb
from chromadb.config import Settings
from config import DATA, DOMAINS
from .embeddings import Embeddings


class VectorStore:
    def __init__(self, path=None, backend=None):
        self.embeddings = Embeddings(backend)
        self.client = chromadb.PersistentClient(path=str(path or DATA/'chroma'), settings=Settings(anonymized_telemetry=False))
        signature = hashlib.sha256(self.embeddings.signature.encode()).hexdigest()[:10]
        self.collections = {d:self.client.get_or_create_collection(f'{d}_{signature}',
                            metadata={'hnsw:space':'cosine'}) for d in DOMAINS}

    def upsert(self, domain, records):
        collection = self.collections[domain]
        for start in range(0, len(records), 48):
            batch = records[start:start+48]
            collection.upsert(ids=[c['id'] for c in batch], documents=[c['text'] for c in batch],
                              metadatas=[c['metadata'] for c in batch],
                              embeddings=self.embeddings.encode([c['text'] for c in batch]))

    def search(self, domain, query, customer_id, k=5, year=None, organization=None):
        collection = self.collections[domain]
        if not collection.count():
            return []
        clauses = [{'customer_id':{'$in':['public', customer_id]}}]
        if year:
            clauses.append({'year':str(year)})
        if organization:
            clauses.append({'source_organization':organization})
        where = clauses[0] if len(clauses)==1 else {'$and':clauses}
        result = collection.query(query_embeddings=self.embeddings.encode([query]),
                    n_results=min(k,collection.count()), where=where,
                    include=['documents','metadatas','distances'])
        return [dict(id=i,text=t,metadata=m,distance=float(d)) for i,t,m,d in
                zip(result['ids'][0],result['documents'][0],result['metadatas'][0],result['distances'][0])
                if d < 0.92]

    def inventory(self, customer_id='public'):
        rows = []
        for domain, collection in self.collections.items():
            result = collection.get(where={'customer_id':{'$in':['public',customer_id]}}, include=['metadatas'])
            counts = {}
            for metadata in result['metadatas']:
                key = (metadata['original_path'],metadata['customer_id'])
                counts.setdefault(key,{**metadata,'chunks':0})['chunks'] += 1
            rows.extend(counts.values())
        return rows
