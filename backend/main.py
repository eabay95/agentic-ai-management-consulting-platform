import logging
from functools import lru_cache
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from agents.manager import ManagerAgent
from agents.csr import CSRAgent


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
    return CSRAgent()


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

        if "csr" in domains:
            agent_results["csr"] = get_csr_agent().run(
                question=question,
                report_year=request.report_year,
            )

        pending_domains = [
            domain for domain in domains
            if domain not in agent_results
        ]

        if pending_domains:
            status = "partial" if agent_results else "pending_specialists"
        else:
            status = agent_results["csr"]["status"]

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

