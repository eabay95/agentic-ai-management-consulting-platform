from pathlib import Path

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".csv"}


def load_and_split(input_path: str):
    path = Path(input_path)

    if path.is_file():
        files = [path]
    elif path.is_dir():
        files = [
            file
            for file in path.rglob("*")
            if file.is_file()
            and file.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
    else:
        raise FileNotFoundError(f"Path does not exist: {input_path}")

    documents = []

    for file in files:
        extension = file.suffix.lower()

        if extension == ".pdf":
            loader = PyMuPDFLoader(str(file))
            documents.extend(loader.load())
        else:
            text = file.read_text(
                encoding="utf-8",
                errors="ignore",
            )

            if text.strip():
                documents.append(
                    Document(
                        page_content=text,
                        metadata={
                            "source": str(file),
                            "file_type": extension,
                        },
                    )
                )

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
    )

    return text_splitter.split_documents(documents)