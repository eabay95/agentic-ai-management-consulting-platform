from __future__ import annotations

import json
from typing import Any

from llm import get_model, get_openai_client


INSTRUCTIONS = """
You are the Clinical Consulting Agent.

Your job is to answer clinical, laboratory, diagnostic, assay, and healthcare
technology questions using only the provided evidence.

Do not invent facts. If the evidence is insufficient, clearly say so.
Provide a concise, professional answer and refer to the provided source IDs.
"""


class ClinicalAgent:
    def __init__(
        self,
        client: Any = None,
        vector_store: Any = None,
        model: str | None = None,
    ):
        self.client = client
        self.vector_store = vector_store
        self.model = model or get_model()

    def analyze(self, question: str, *, k: int = 8) -> dict[str, Any]:
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be a non-empty string")

        if k <= 0:
            raise ValueError("k must be greater than zero")

        question = question.strip()

        if self.vector_store is None:
            from rag.vector_store import get_vector_store

            self.vector_store = get_vector_store("clinical")

        documents = self.vector_store.similarity_search(question, k=k)

        sources = []

        for index, document in enumerate(documents, start=1):
            metadata = getattr(document, "metadata", {}) or {}
            page = metadata.get("page")

            if isinstance(page, int):
                page = page + 1

            sources.append(
                {
                    "id": f"C{index}",
                    "source": metadata.get("source"),
                    "page": page,
                    "excerpt": document.page_content,
                }
            )

        if not sources:
            return {
                "status": "insufficient_evidence",
                "domain": "clinical",
                "question": question,
                "answer": (
                    "There is not enough clinical evidence in the knowledge base "
                    "to answer this question."
                ),
                "sources": [],
            }

        if self.client is None:
            self.client = get_openai_client()

        response = self.client.responses.create(
            model=self.model,
            store=False,
            instructions=INSTRUCTIONS,
            input=json.dumps(
                {
                    "question": question,
                    "evidence": sources,
                },
                ensure_ascii=False,
            ),
        )

        return {
            "status": "completed",
            "domain": "clinical",
            "question": question,
            "answer": response.output_text.strip(),
            "sources": sources,
        }