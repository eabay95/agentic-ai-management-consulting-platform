from llm import get_model, get_gemini_client
from typing import Any
import json
import re

CROSS_INSTRUCTIONS = """
You are the Cross-Agent Management Consulting Synthesizer.

Your responsibility is to combine findings from multiple
specialist agents into one coherent consulting answer.

Rules:
1. Only synthesize questions that genuinely require
   multiple specialist domains.
2. Use ONLY the supplied specialist findings and evidence.
3. Do not invent company facts, statistics, or citations.
4. Connect insights across domains rather than repeating
   each specialist's answer separately.
5. Cite factual claims using domain-qualified source IDs,
   such as [technology:1], [sec:S1], or [csr:S2].
6. Do not confuse sources from different domains.
7. Explicitly identify missing evidence or conflicting findings.
8. Distinguish documented facts from your own recommendations.
9. Provide prioritized consulting actions when appropriate.
10. Keep answers concise and professionally structured.

Response structure:

Integrated assessment:
Explain the combined findings across relevant domains.

Recommendations:
Provide actionable, prioritized recommendations
supported by the available evidence.

Limitations:
Identify missing information, unavailable specialists,
or unsupported conclusions.
"""


class CrossAgent:
    def __init__(
            self,
            client: Any = None,
            model: str | None = None,
    ):
        self.client = client
        self.model = model or get_model()

    def validate(
        self,
        question: str,
        agent_results: dict[str, dict[str, Any]],
    ) -> None:

        if not isinstance(question, str) or not question.strip():
            raise ValueError("Question must be a non-empty string.")

        if not isinstance(agent_results, dict):
            raise ValueError("agent_results must be a dictionary.")

        valid_domains = {"technology", "clinical", "sec", "csr"}

        if len(set(agent_results) & valid_domains) < 2:
            raise ValueError(
                "Cross-agent synthesis requires at least "
                "two specialist domains."
            )


    def prepare_evidence(
        self,
        agent_results: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:

        prepared = {}
        skipped = {}

        for domain, result in agent_results.items():
            status = result.get("status")

            if not self.has_usable_answer(result):
                skipped[domain] = "no_usable_evidence"
                continue

            answer = result.get("answer", "").strip()
            sources = result.get("sources", [])

            if not answer or not sources:
                skipped[domain] = "missing_answer_or_sources"
                continue

            normalized_sources = []

            for index, source in enumerate(sources, start=1):
                original_id = source.get("id") or str(index)

                normalized_sources.append({
                    "id": f"{domain}:{original_id}",
                    "document": source.get(
                        "document",
                        source.get("source", "Unknown")
                    ),
                    "page": source.get(
                        "pdf_page",
                        source.get("page")
                    ),
                    "excerpt": source.get(
                        "excerpt",
                        source.get("passage")
                    ),
                })

            prepared[domain] = {
                "answer": answer,
                "sources": normalized_sources,
            }

        return {
            "prepared": prepared,
            "skipped": skipped,
        }


    def run(
        self,
        question: str,
        agent_results: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:

        # Validate that multiple specialist domains were supplied.
        self.validate(question, agent_results)

        evidence = self.prepare_evidence(agent_results)

        prepared = evidence["prepared"]
        skipped = evidence["skipped"]

        # A complete cross-agent synthesis requires evidence
        # from at least two specialist domains.
        if len(prepared) < 2:
            return {
                "status": "insufficient_evidence",
                "question": question,
                "answer": (
                    "Cross-agent synthesis requires usable evidence "
                    "from at least two specialist domains."
                ),
                "used_domains": list(prepared),
                "skipped_domains": skipped,
                "sources": [],
            }

        # Create the Gemini client only when synthesis is needed.
        if self.client is None:
            self.client = get_gemini_client()

        payload = {
            "question": question,
            "specialist_findings": prepared,
            "unavailable_specialists": skipped,
        }

        response = self.client.models.generate_content(
            model=self.model,
            config={
                "system_instruction": CROSS_INSTRUCTIONS
            },
            contents=json.dumps(payload, ensure_ascii=False),
        )

        answer = (response.text or "").strip()

        if not answer:
            raise RuntimeError(
                "Cross-agent synthesis returned an empty answer."
            )

        sources = [
            source
            for finding in prepared.values()
            for source in finding["sources"]
        ]

        citation_check = self.validate_citations(answer, sources)

        return {
            "status": "generated_needs_review",
            "question": question,
            "answer": answer,
            "used_domains": list(prepared),
            "skipped_domains": skipped,
            "sources": sources,
            "citation_check": citation_check,
        }

    def validate_citations(
        self,
        answer: str,
        sources: list[dict[str, Any]],
    ) -> dict[str, Any]:
        valid_ids = {source["id"] for source in sources}

        # Extract every bracketed citation group.
        groups = re.findall(r"\[([^\[\]]+)\]", answer)

        cited_ids = set()
        invalid_ids = set()

        for group in groups:
            # Ignore brackets that aren't citation-shaped.
            if not re.match(r"^[a-z]+:", group.strip()):
                continue

            for citation in group.split(","):
                citation_id = citation.strip()

                if not re.fullmatch(
                    r"[a-z]+:(?:[A-Z]\d+|\d+)",
                    citation_id,
                ):
                    invalid_ids.add(citation_id)
                elif citation_id not in valid_ids:
                    invalid_ids.add(citation_id)
                else:
                    cited_ids.add(citation_id)

        return {
            "valid": bool(cited_ids) and not invalid_ids,
            "cited_ids": sorted(cited_ids),
            "invalid_ids": sorted(invalid_ids),
        }


    def has_usable_answer(self, result: dict[str, Any]) -> bool:
        status = result.get("status", "")

        if status in {"error", "insufficient_evidence"}:
            return False

        answer = result.get("answer", "")

        if not isinstance(answer, str) or not answer.strip():
            return False

        if not result.get("sources"):
            return False

        answer_lower = answer.lower()

        insufficient_phrases = [
            "i don't know",
            "i do not know",
            "provided context does not contain",
            "not enough information",
            "insufficient evidence",
            "no relevant information",
            "cannot answer based on",
        ]

        if any(
            phrase in answer_lower
            for phrase in insufficient_phrases
        ):
            return False

        return True


