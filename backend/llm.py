"""Shared model settings and factories for all agents and RAG components."""

import os
from pathlib import Path

from dotenv import load_dotenv


def _load_environment():
    # Explicit paths make configuration independent of the working directory.
    backend_dir = Path(__file__).resolve().parent
    load_dotenv(backend_dir / ".env")
    load_dotenv(backend_dir.parent / ".env")


def get_model() -> str:
    _load_environment()
    return os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


def get_api_key() -> str:
    _load_environment()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or not api_key.strip():
        raise ValueError("OPENAI_API_KEY is missing. Add it to your environment or .env file.")
    return api_key


def get_openai_client():
    from openai import OpenAI

    return OpenAI(api_key=get_api_key())


def get_chat_model():
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=get_model(), api_key=get_api_key())


def get_embeddings():
    from langchain_openai import OpenAIEmbeddings

    _load_environment()
    return OpenAIEmbeddings(
        model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002"),
        api_key=get_api_key(),
    )
