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
configured, indexes the configured SEC/CSR PDFs and supported clinical/technology documents, and starts the API at
`http://127.0.0.1:8000/docs`. Ingestion computes embeddings locally; unchanged
chunks are skipped. Missing configured PDFs or a failed step stop startup.
Clinical/technology ingestion reports reference lists, structured CSVs and unreadable files as skipped.

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
The low-level store_documents example adds documents directly. Use the ingestion
scripts for stable IDs and repeatable indexing.

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

## Added clinical and technology documents

The root launcher now also runs `ingest_domains.py`. To ingest these domains alone:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe ingest_domains.py
```

Clinical and technology PDF/TXT content is indexed into its own collection with
stable IDs and PDF page metadata. Repeat runs skip existing chunks; modified
files replace obsolete chunks after successful ingestion. Trial CSV files remain
preserved as structured data rather than being embedded as unstructured evidence.
TXT reference lists containing URLs are explicitly skipped: a URL description is
not a source document. Download the actual approved Cisco/Google documentation
into `data/technology` and Agilent instrument documentation into `data/clinical`,
then rerun ingestion. This script does not fetch or fabricate linked content.


## Technology response and source setup

Technology answers are normalized from Gemini text blocks to plain text; the
chat renderer also handles structured responses safely. Empty retrieval returns
`insufficient_evidence` without a model call. Source excerpts, PDF pages and
public URLs are preserved. The pipeline uses a local evidence-only prompt and
does not require a LangSmith prompt download at startup.

The professor-listed Google Cloud RAG page can be downloaded and indexed with:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe fetch_technology.py
.\.venv\Scripts\python.exe ingest_domains.py --domain technology
```

The fetcher only permits exact HTTPS references in `data/technology/*.txt`,
rejects redirects, limits downloads to 25 MB and saves source URL provenance.
Use `--url` to select a different professor-listed reference. It does not crawl
or substitute descriptions for content. Other Cisco/Google sources still need
fetching before questions requiring their documentation can be answered.

After code changes, restart the server and refresh the browser to load the
updated renderer. Run `python -m unittest discover -s tests -v` for regression
tests; the renderer regression test also requires Node.js.


## Reading all professor reference links

Normal startup now fetches every exact HTTPS URL in the root clinical/technology
TXT reference lists before indexing. Agilent references go into clinical even if
Agilent.txt is in the technology directory. Google/Cisco content goes into technology.
Gemini receives matching passages retrieved from that content; a URL in a prompt
is not a guarantee that its contents have been retrieved.

Successful downloads are cached. `data/public_source_report.json` records each
source's domain, availability and any error. Blocked pages (including HTTP 403)
remain unavailable; no content is invented and redirects are not followed.
Use `-RefreshSources` with the launcher to download cached sources again,
`-SkipSourceFetch` to index only local content, or `-SkipIngestion` to skip
both fetching and indexing. To refresh sources separately:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe fetch_technology.py --all
.\.venv\Scripts\python.exe ingest_domains.py
```

The browser's network error means it could not reach the consulting endpoint,
not that a professor URL failed. Keep the API running, open the page from the
server URL rather than a local HTML file, and refresh after a server reload.
