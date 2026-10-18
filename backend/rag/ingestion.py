from pathlib import Path
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

def load_and_split(pdf_path: str):
    path = Path(pdf_path)
    loader = PyMuPDFLoader(str(path))
    documents = loader.load()
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )

    return text_splitter.split_documents(documents)