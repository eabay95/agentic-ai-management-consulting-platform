"""Shared model settings and factories for all agents and RAG components."""

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


def _load_environment():
    # Explicit paths make configuration independent of the working directory.
    backend_dir = Path(__file__).resolve().parent
    load_dotenv(backend_dir / ".env")
    load_dotenv(backend_dir.parent / ".env")


def get_model() -> str:
    _load_environment()
    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def get_api_key() -> str:
    _load_environment()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or not api_key.strip():
        raise ValueError("GEMINI_API_KEY is missing. Add it to your environment or .env file.")
    return api_key


def get_gemini_client():
    from google import genai

    return genai.Client(api_key=get_api_key())


def get_chat_model():
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(model=get_model(), google_api_key=get_api_key(), vertexai=False)


# Keep the model fixed so every collection uses the same vector space.
LOCAL_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"


def get_embeddings():
    return _get_local_embeddings()


@lru_cache(maxsize=1)
def _get_local_embeddings():
    from langchain_community.embeddings.fastembed import FastEmbedEmbeddings

    return FastEmbedEmbeddings(
        model_name=LOCAL_EMBEDDING_MODEL,
        cache_dir=str(Path(__file__).resolve().parent / ".cache" / "fastembed"),
        providers=["CPUExecutionProvider"],
    )
