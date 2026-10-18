from __future__ import annotations

import json
from typing import Any

from llm import get_model, get_gemini_client
from rag.citations import check_citations
from rag.retrieval import retrieve_documents


INSTRUCTIONS = """Write for quick reading: lead with a direct one-sentence answer, then short
bullets with bold labels and citations. Aim for 150-250 words unless more detail
is requested. Include only sections relevant to the question. Give recommendations
when advice is requested; simple factual/list questions need a focused answer.
Use plain language and avoid repeating the question or evidence limitations.


You are the Clinical Consulting Agent.
Address clinical research and laboratory requirements only. Peer specialists cover networking, financial disclosures and CSR; do not treat those separate scopes as missing clinical evidence.

Your job is to answer clinical, laboratory, diagnostic, assay, and healthcare
technology questions using only the provided evidence.

Do not invent facts. If the evidence is insufficient, clearly say so.
Distinguish general heart-disease risk modeling from prediction of acute heart
attacks. Attribute results and limitations to the research; do not imply validated
clinical effectiveness or calibrated risk probabilities without supporting evidence.
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

        documents = retrieve_documents(self.vector_store, "clinical", question, k)

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
                    "document": metadata.get("document_title") or metadata.get("document_name") or metadata.get("source"),
                    "page": page,
                    "excerpt": document.page_content,
                    "source_url": metadata.get("source_url", ""),
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
            self.client = get_gemini_client()

        response = self.client.models.generate_content(
            model=self.model,
            config={"system_instruction": INSTRUCTIONS},
            contents=json.dumps(
                {
                    "question": question,
                    "evidence": sources,
                },
                ensure_ascii=False,
            ),
        )

        answer = (response.text or '').strip()
        citation_check = check_citations(answer, sources)
        if not citation_check['valid']:
            return dict(status='citation_error', domain='clinical', question=question, sources=sources,
                        answer='The clinical answer was withheld because it lacked valid source citations.', citation_check=citation_check)
        return {
            "citation_check": citation_check,
            "status": "completed",
            "domain": "clinical",
            "question": question,
            "answer": (response.text or "").strip(),
            "sources": sources,
        }

    def run(self, question: str, *, k: int = 8) -> dict[str, Any]:
        """Run the clinical specialist using the common agent interface."""
        return self.analyze(question, k=k)
