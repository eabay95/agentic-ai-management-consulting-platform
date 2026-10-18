# Backend

## Chat interface

Open the server's home address (for example `http://127.0.0.1:8080/`) for the
chat interface. It submits questions to `/consult` and shows each specialist's
answer with expandable sources. Questions are independent; the backend does not
retain conversation context. Messages stay in the current page only.
API documentation remains at `/docs`; the status endpoint is `/health`.

## One-command startup on Windows

Install Python 3.14+ and set `GEMINI_API_KEY` in `backend/.env` first:

```dotenv
GEMINI_API_KEY=your-key-here
```

From the project root, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

The launcher creates `backend/.venv`, installs dependencies, validates the key is
configured, indexes the configured SEC and CSR PDFs, and starts the API at
`http://127.0.0.1:8000/docs`. Ingestion computes embeddings locally; unchanged
chunks are skipped. Missing configured PDFs or a failed step stop startup.
Technology and clinical documents still require separate ingestion.

For subsequent runs when dependencies and documents are already set up:

```powershell
.\run.ps1 -SkipInstall -SkipIngestion
```

Use `-Port 8001` to change the port, or `-PythonCommand C:\Python314\python.exe`
to choose the interpreter used to create the environment. Stop with Ctrl+C.

## Shared LLM configuration

`llm.py` owns model selection, API credentials, and Gemini/LangChain client
creation for the manager, SEC specialist, and RAG components. Set these in your
environment or in `backend/.env` (the root `.env` is also supported):

```dotenv
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-2.5-flash
```

Existing environment variables take precedence, followed by `backend/.env`, then
the root `.env`. The RAG answer model now uses the same `GEMINI_MODEL` as agents.
Changing the embedding model requires rebuilding the vector index.

## SEC specialist

Run from the `backend` directory. Set `GEMINI_API_KEY` in your environment or
`.env`; `GEMINI_MODEL` optionally overrides the default model.

Install project dependencies with `python -m pip install -e .`.

Ingest your authoritative filing PDFs once:

```python
from rag.ingestion import load_and_split
from rag.vector_store import store_documents

chunks = load_and_split("path/to/cisco-2025.pdf")
for chunk in chunks:
    chunk.metadata.update(company="Cisco", reporting_period="2025")
store_documents(chunks, "sec")
```

Repeat for Agilent. Verify each PDF's actual reporting period before labeling it.
Repeated ingestion currently adds duplicates; storage is the existing shared RAG
implementation.

```python
from agents.sec import SECAgent

result = SECAgent().analyze(
    "What financial, competitive, and operational risks does Cisco disclose?"
)
print(result["answer"])
print(result["sources"])
```

Results contain an answer and retrieved excerpts with source IDs and one-based
PDF page numbers. An empty collection returns `insufficient_evidence` without
calling the answer model. Retrieved excerpts are candidates, not a guarantee of
relevance or complete company coverage. Citations and factual support still need
evaluation against the filings; generated citations are not programmatically
verified. This specialist is callable directly and is not yet wired into `/route`.

Run offline SEC agent tests with:

```powershell
python -m unittest discover -s tests -v
```

## Gemini migration

Install the updated dependencies with `python -m pip install -e .`.
Set `GEMINI_API_KEY` in `backend/.env`. All agents now use `GEMINI_MODEL`.
Document embeddings now run locally using FastEmbed's `BAAI/bge-small-en-v1.5`
model on CPU. The first use downloads the model to `backend/.cache/fastembed/`;
after download, embedding generation requires no API key or embedding API calls.
Gemini remains the chat provider and still requires `GEMINI_API_KEY` to answer.
`GEMINI_EMBEDDING_MODEL` is no longer used.

Local vectors are stored in `backend/chroma_db_local_bge_small_en_v15/`.
Existing Gemini/OpenAI indexes are preserved. Re-run `python ingest_sec.py` and
`python ingest_csr.py` to populate the new index; ingest technology/clinical data
again too. The model is fixed in `llm.py`; changing it requires a new index path.
There are no quota-related pauses during local ingestion.

From the project root, run `powershell -ExecutionPolicy Bypass -File .\run.ps1`
to install the new dependency, re-index, and start the API. Do not use
`-SkipInstall` or `-SkipIngestion` for the first run after this change.
The previous `uv.lock` must be regenerated with `uv lock` before locked installs.
