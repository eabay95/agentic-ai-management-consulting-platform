from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document

from llm import get_embeddings

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "chroma_db_local_bge_small_en_v15"

VALID_DOMAINS = {
    "technology",
    "clinical",
    "sec",
    "csr",
}

def get_vector_store(collection_name: str):
    if collection_name not in VALID_DOMAINS:
        raise ValueError(f"Unknown domain: {collection_name}")
    
    return Chroma(
        collection_name=collection_name,
        embedding_function=get_embeddings(),
        persist_directory=str(DB_PATH),
    )


def store_documents(documents: list[Document], collection_name: str):
    vector_store = get_vector_store(collection_name)
    vector_store.add_documents(documents=documents)
    return len(documents)

