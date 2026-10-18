import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from agents.manager import ManagerAgent
from agents.cross import CrossAgent
from agents.tasks import build_specialist_tasks
from recommendations.planner import RecommendationPlanner, advice_requested


app = FastAPI()

manager = ManagerAgent()
logger = logging.getLogger(__name__)


class QuestionRequest(BaseModel):
    question: str


@app.get("/")
def main():
    return FileResponse(Path(__file__).resolve().parent / "web" / "index.html")


@app.get("/health")
def health():
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
    requirements: str = Field(default='', max_length=4000)
    recommendation_weights: dict[str, float] | None = None
    mandatory_constraints: list[str] = Field(default_factory=list, max_length=20)


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

@lru_cache(maxsize=1)
def get_cross_agent():
    return CrossAgent()


@lru_cache(maxsize=1)
def get_recommendation_planner():
    return RecommendationPlanner()


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
        specialist_tasks = build_specialist_tasks(question, domains)

        for domain in domains:
            try:
                agent_results[domain] = run_specialist(
                    domain,
                    specialist_tasks[domain],
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


        # Check whether synthesis is actually required.
        requires_cross = (
            routing.get("requires_cross_domain_reasoning", False)
            and len(domains) >= 2
        )

        synthesis = None

        if requires_cross:
            try:
                synthesis = get_cross_agent().run(
                    question=question,
                    agent_results=agent_results,
                )
            except Exception:
                logger.exception("Cross-agent synthesis failed")
                synthesis = {
                    "status": "error",
                    "answer": "Cross-agent synthesis could not be completed.",
                    "used_domains": [],
                    "skipped_domains": {},
                    "sources": [],
                }

        recommendations = None
        if advice_requested(question):
            try:
                recommendations = get_recommendation_planner().run(
                    question, agent_results, request.requirements,
                    request.recommendation_weights, request.mandatory_constraints)
            except Exception:
                logger.exception('Recommendation planning failed')
                recommendations = dict(status='error', ranked=[], held=[], rejected=[],
                                       limitations=['Proposal ranking could not be completed; specialist evidence remains available.'])

        # Do not mistake insufficient evidence for a completed answer.
        incomplete_statuses = {
            "error",
            "insufficient_evidence",
            "uncited_needs_review",
            "citation_error",
        }

        pending_domains = [
            domain
            for domain in domains
            if agent_results.get(domain, {}).get("status")
            in incomplete_statuses
            or not agent_results.get(domain, {}).get("sources")
            or not agent_results.get(domain, {}).get("answer", "").strip()
        ]

        # A synthesis error also makes the consultation incomplete.
        synthesis_incomplete = (
            requires_cross
            and (
                synthesis is None
                or synthesis.get("status")
                in {"error", "insufficient_evidence", "citation_error"}
            )
        )

        status = (
            "partial"
            if pending_domains or synthesis_incomplete or (recommendations and recommendations.get('status') == 'error')
            else "completed"
        )

        return {
            **routing,
            "status": status,
            "agent_results": agent_results,
            "specialist_tasks": specialist_tasks,
            "pending_domains": pending_domains,
            "synthesis": synthesis,
            "recommendations": recommendations,
        }


    except Exception as error:
        if getattr(error, 'code', None) == 429:
            raise HTTPException(status_code=429, detail='Gemini request quota is exhausted. Retry after your quota resets or review your API account limits. Retrieved documents and indexes are preserved.') from None
        logger.exception("Consulting request failed")
        raise HTTPException(
            status_code=500,
            detail=(
                "The consulting request could not be completed. "
                "Check the server logs, API configuration, "
                "and CSR document ingestion."
            ),
        ) from None



@app.get('/evaluation')
def evaluation_report():
    import json
    report = Path(__file__).resolve().parent / 'evaluation' / 'results.json'
    return json.loads(report.read_text('utf-8')) if report.exists() else {'status': 'not_run', 'instructions': 'Run python -m evaluation.run --live'}


@app.get('/evaluation/view')
def evaluation_page():
    return FileResponse(Path(__file__).resolve().parent / 'web' / 'evaluation.html')
