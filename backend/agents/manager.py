import json
from typing import Any

from llm import get_model, get_gemini_client


DOMAIN_PROFILES = {
    "technology": (
        "Enterprise technology, Cisco, IBM, Google infrastructure, "
        "networking, servers, cloud systems, software, hardware, "
        "technical failures, and replacement components."
    ),
    "clinical": (
        "Healthcare, medical diagnostics, laboratory operations, "
        "Agilent instruments, clinical equipment, assays, calibration, "
        "and medical replacement parts."
    ),
    "sec": (
    "SEC filings, annual reports, financial performance, revenue, "
    "financial risk, operational risk, competitive risk, company risk, "
    "business risks, competition, regulatory compliance, "
    "and securities analysis."
    ),
    "csr": (
        "Corporate social responsibility, ESG, sustainability, "
        "food security, carbon emissions, environmental impact, "
        "and social responsibility."
    ),
}


class ManagerAgent:
    """
    Uses Gemini to classify customer questions
    and route them to specialist agents.
    """

    def __init__(self, client=None):
        self.client = client if client is not None else get_gemini_client()
        self.model = get_model()

    def classify(self, question: str) -> dict[str, Any]:
        if not question or not question.strip():
            raise ValueError("Question cannot be empty.")

        domain_description = "\n".join(
            f"- {domain}: {description}"
            for domain, description in DOMAIN_PROFILES.items()
        )

        instructions = f"""
You are the Management Consulting Manager Agent.

Classify the customer question into one or more domains.

Allowed domains:
{domain_description}

Rules:
1. Return only valid JSON.
2. Select multiple domains if the question crosses domains.
3. Do not invent domains.
4. If the question is too vague, return an empty domains list.
5. Confidence must be between 0 and 1.
6. Explain why each domain was selected.
7. List missing information needed for a better answer.
8. If the question asks about financial, operational, competitive,
regulatory, or company risk, include the sec domain.

Return exactly this JSON structure:

{{
  "domains": ["technology"],
  "confidence": {{
    "technology": 0.92
  }},
  "reasons": {{
    "technology": "The question concerns enterprise networking."
  }},
  "missing_information": [],
  "requires_cross_domain_reasoning": false
}}
"""

        response = self.client.models.generate_content(
            model=self.model,
            config={"system_instruction": instructions, "response_mime_type": "application/json"},
            contents=f"Return a JSON object for this customer question:\n{question}",

        )

        result = json.loads((response.text or ""))

        valid_domains = [
            domain
            for domain in result.get("domains", [])
            if domain in DOMAIN_PROFILES
        ]

        confidence = {
            domain: float(
                result.get("confidence", {}).get(domain, 0.0)
            )
            for domain in valid_domains
        }

        return {
            "domains": valid_domains,
            "confidence": confidence,
            "reasons": result.get("reasons", {}),
            "missing_information": result.get(
                "missing_information",
                [],
            ),
            "requires_cross_domain_reasoning": len(
                valid_domains
            ) > 1,
        }

    def route(self, question: str) -> dict[str, Any]:
        classification = self.classify(question)

        if not classification["domains"]:
            return {
                "status": "needs_more_context",
                "question": question,
                **classification,
            }

        return {
            "status": "routed",
            "question": question,
            **classification,
        }


if __name__ == "__main__":
    manager = ManagerAgent()

    question = (
        "How can Cisco technology improve sustainability "
        "while reducing financial risk?"
    )

    result = manager.route(question)
    print(json.dumps(result, indent=2))
