from rag.pipeline import graph

class TechnologyAgent:
    def __init__(self, client=None, vector_store=None, model: str | None = None):
        self.client = client
        self.vector_store = vector_store
        self.domain = "technology"

    def run(self, question: str) -> dict:
        
        if not question or not question.strip():
            raise ValueError("Question cannot be empty.")
        
        response = graph.invoke({"question": question, "domain": self.domain})
        sources = [
            {
                "document": doc.metadata.get("source", "Unknown"),
                "page": (
                    doc.metadata["page"] + 1
                    if isinstance(doc.metadata.get("page"), int)
                    else None
                ),
            }
            for doc in response.get("context", [])
        ]
        return {
            "status": "completed",
            "domain": self.domain,
            "question": question,
            "answer": response.get("answer", ""),
            "sources": sources
        }

    def analyze(self, question: str) -> dict:
        """Compatibility alias for callers that use analyze()."""
        return self.run(question)
