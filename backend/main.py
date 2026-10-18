from fastapi import FastAPI
from pydantic import BaseModel

from agents.manager import ManagerAgent


app = FastAPI()

manager = ManagerAgent()


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