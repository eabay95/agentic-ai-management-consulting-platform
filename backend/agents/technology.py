from rag.pipeline import graph
from rag.response_text import response_text


class TechnologyAgent:
    def __init__(self, client=None, vector_store=None, model: str | None = None):
        self.client = client
        self.vector_store = vector_store
        self.domain = 'technology'
        self.model = model

    def run(self, question: str) -> dict:
        if not isinstance(question, str) or not question.strip():
            raise ValueError('Question cannot be empty.')
        state = {'question': question.strip(), 'domain': self.domain}
        if self.vector_store is not None:
            state['vector_store'] = self.vector_store
        if self.client is not None:
            state['chat_model'] = self.client
        response = graph.invoke(state)
        sources = []
        for index, document in enumerate(response.get('context', []), 1):
            metadata = document.metadata
            page = metadata.get('page_number')
            if page is None and isinstance(metadata.get('page'), int):
                page = metadata['page'] + 1
            sources.append(dict(id=f'T{index}', document=metadata.get('document_name') or metadata.get('source', 'Unknown'),
                                page=page, excerpt=document.page_content, source_url=metadata.get('source_url', '')))
        return dict(status=response.get('status', 'completed'), domain=self.domain,
                    question=question.strip(), answer=response_text(response.get('answer', '')),
                    sources=sources)

    def analyze(self, question: str) -> dict:
        return self.run(question)
