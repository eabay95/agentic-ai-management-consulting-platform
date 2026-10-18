import logging
from functools import lru_cache
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from agents.manager import ManagerAgent


app = FastAPI()

manager = ManagerAgent()
logger = logging.getLogger(__name__)


class QuestionRequest(BaseModel):
    question: str


@app.get("/")
def main():
    return {
        "message": "Management Consulting Platform is running"
    }


@app.post("/route")
def route_question(request: QuestionRequest):
    return manager.route(request.question)


# CSR API integration by Raheem Saeed
class CSRQuestionRequest(BaseModel):
    question: str = Field(min_length=3, max_length=4000)
    report_year: Literal[2023, 2024] | None = None


@lru_cache(maxsize=1)
def get_csr_agent():
    from agents.csr import CSRAgent

    return CSRAgent()


@lru_cache(maxsize=1)
def get_clinical_agent():
    from agents.clinical import ClinicalAgent

    return ClinicalAgent()


@lru_cache(maxsize=1)
def get_sec_agent():
    from agents.sec import SECAgent

    return SECAgent()


@lru_cache(maxsize=1)
def get_technology_agent():
    from agents.technology import TechnologyAgent

    return TechnologyAgent()


def run_specialist(domain: str, question: str, report_year: int | None):
    """Run the specialist that corresponds to a Manager-selected domain."""
    if domain == "clinical":
        return get_clinical_agent().run(question)

    if domain == "sec":
        return get_sec_agent().run(question)

    if domain == "technology":
        return get_technology_agent().run(question)

    if domain == "csr":
        return get_csr_agent().run(
            question=question,
            report_year=report_year,
        )

    raise ValueError(f"Unsupported specialist domain: {domain}")


@app.post("/csr")
def ask_csr(request: CSRQuestionRequest):
    question = request.question.strip()

    if len(question) < 3:
        raise HTTPException(
            status_code=422,
            detail="Enter a question with at least 3 non-space characters.",
        )

    try:
        return get_csr_agent().run(
            question=question,
            report_year=request.report_year,
        )
    except Exception:
        logger.exception("CSR request failed")
        raise HTTPException(
            status_code=500,
            detail=(
                "The CSR request could not be completed. "
                "Check the server logs, API configuration, "
                "and CSR document ingestion."
            ),
        ) from None
        
# Manager-to-CSR orchestration by Raheem Saeed
@app.post("/consult")
def consult(request: CSRQuestionRequest):
    question = request.question.strip()

    if len(question) < 3:
        raise HTTPException(
            status_code=422,
            detail="Enter a question with at least 3 non-space characters.",
        )

    try:
        routing = manager.route(question)
        domains = routing["domains"]

        if not domains:
            return {
                **routing,
                "agent_results": {},
                "pending_domains": [],
            }

        agent_results = {}

        for domain in domains:
            try:
                agent_results[domain] = run_specialist(
                    domain,
                    question,
                    request.report_year,
                )
            except Exception as error:
                logger.exception("Specialist request failed: %s", domain)
                agent_results[domain] = {
                    "domain": domain,
                    "status": "error",
                    "question": question,
                    "error": str(error),
                }

        incomplete_statuses = {"error", "insufficient_evidence"}
        pending_domains = [
            domain for domain in domains
            if agent_results.get(domain, {}).get("status") in incomplete_statuses
        ]

        if pending_domains:
            status = "partial"
        else:
            status = "completed"

        return {
            **routing,
            "status": status,
            "agent_results": agent_results,
            "pending_domains": pending_domains,
        }

    except Exception:
        logger.exception("Consulting request failed")
        raise HTTPException(
            status_code=500,
            detail=(
                "The consulting request could not be completed. "
                "Check the server logs, API configuration, "
                "and CSR document ingestion."
            ),
        ) from None

