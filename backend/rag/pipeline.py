import os
from dotenv import load_dotenv
from typing_extensions import List, TypedDict
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from langsmith import Client
from rag.vector_store import get_vector_store
from langgraph.graph import START, StateGraph

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
llm = ChatOpenAI(model="gpt-4o-mini",api_key=api_key)

client = Client()
prompt = client.pull_prompt(
    "rlm/rag-prompt",
    dangerously_pull_public_prompt=True
)

class State(TypedDict):
    question: str
    domain: str
    context: List[Document]
    answer: str

def retrieve(state: State):
    vector_store = get_vector_store(state["domain"])
    retrieved_docs = vector_store.similarity_search(state["question"],k=5)
    return {"context": retrieved_docs}

def generate(state: State):
    docs_content = "\n\n".join(doc.page_content for doc in state["context"])
    messages = prompt.invoke({"question": state["question"], "context": docs_content})
    response = llm.invoke(messages)
    return {"answer": response.content}

graph_builder = StateGraph(State).add_sequence([retrieve, generate])
graph_builder.add_edge(START, "retrieve")
graph = graph_builder.compile()