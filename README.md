# AI Management Consulting Platform

CMPE 256 hackathon prototype: one Gemini-powered Manager Agent routes questions to
Technology, Clinical, SEC and Corporate Responsibility specialists. Specialists
search separate Chroma knowledge bases, cite retrieved evidence and contribute to
cross-domain recommendations.

The application uses FastAPI and a browser chat interface. Embeddings are computed
locally with FastEmbed; Gemini is used for routing, answers and proposal generation.

## Start the existing installation

Open PowerShell in the project root (the folder containing `run.ps1`):

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1 -SkipInstall -SkipIngestion -Port 8502
```

Open [Consulting chat](http://127.0.0.1:8502/).
Keep the server terminal open. Press **Ctrl+C** in that terminal to stop it.

| Address | Purpose |
|---|---|
| [Chat](http://127.0.0.1:8502/) | Ask consulting questions and inspect evidence |
| [Evaluation](http://127.0.0.1:8502/evaluation/view) | View the saved evaluation report |
| [API documentation](http://127.0.0.1:8502/docs) | Explore the API endpoints |
| [Health](http://127.0.0.1:8502/health) | Check whether the server is running |

Examples below explicitly select port **8502**. The launcher's default, when
`-Port` is omitted, is **8000**.

## First-time setup

Requirements:

- Python **3.14 or newer**, available through `python`.
- A Gemini API key with access to your selected model.
- Internet access for dependency installation, the first embedding-model download
  and fetching public documentation.
- Node.js if you want to run the JavaScript renderer regression test.

### Create `backend/.env`

From the project root, open a new or existing configuration file:

```powershell
notepad .\backend\.env
```

Save the file as **`.env` inside the `backend` folder** (next to `llm.py`).
In Notepad, choose **All files** as the file type so it is not saved as `.env.txt`.
Copy this format into the file and replace the API-key placeholder:

```dotenv
# Required: your Gemini API key
GEMINI_API_KEY=replace_with_your_gemini_api_key

# Optional: omit this line to use the application's default model
GEMINI_MODEL=gemini-2.5-flash
```

Use one `NAME=value` setting per line, without commas or a JSON wrapper.
Lines starting with `#` are comments. If the file already contains your key,
keep it and update only the settings you intend to change.

`GEMINI_API_KEY` is required. `GEMINI_MODEL` is optional and defaults to
`gemini-2.5-flash`; replace it with a model available to your API account when
needed. A configured model does not guarantee account access or available quota.
Local embeddings do not require a separate API key. `.env` files are ignored by
Git; never commit your key or paste the file's contents into chat.

### Run the setup

Run the full setup from the project root:

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1 -Port 8502
```

The launcher creates `backend/.venv`, installs dependencies, checks that a key is
configured, fetches the listed public sources, indexes documents and starts the
server. The first embedding-model download and indexing can take several minutes.
The execution-policy option applies to this PowerShell invocation; it does not
change your saved execution policy. Activation of `.venv` is not required.

## Restart after changing the key or model

1. Stop the existing server with **Ctrl+C** in its terminal.
2. Save `backend/.env`.
3. Run the existing-installation command again.
4. Refresh the browser; use **Ctrl+F5** if the interface still looks outdated.

If the launcher reports that the app is already running, it reuses that server.
It does **not** restart it or reload `.env`.

Existing process environment variables take precedence over `backend/.env`,
followed by the root `.env`. A previously set `$env:GEMINI_MODEL` or
`$env:GEMINI_API_KEY` can therefore override the file.

## Launcher options

| Option | Behavior |
|---|---|
| `-Port 8502` | Choose the local server port; default is 8000 |
| `-SkipInstall` | Skip installing dependencies; requires an existing environment |
| `-SkipIngestion` | Skip both source fetching and indexing |
| `-SkipSourceFetch` | Index existing local documents without fetching URLs |
| `-RefreshSources` | Download cached reference-list sources again during ingestion |
| `-Reload` | Enable development reload; off by default |
| `-CheckOnly` | Check whether the app is running or the port is available, then exit |
| `-PythonCommand C:\Python314\python.exe` | Choose Python when creating the environment |

For example, index newly added local documents without downloading public sources:

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1 -SkipInstall -SkipSourceFetch -Port 8502
```

Stop an already-running server first; otherwise the launcher returns its existing
URL before performing installation or ingestion.

## Documents and linked sources

Clinical and technology ingestion scans both:

```text
backend/data/clinical/        backend/documents/clinical/
backend/data/technology/      backend/documents/technology/
```

PDFs and substantive TXT documents are supported. Trial CSVs are preserved but
not embedded as unstructured clinical evidence. Unreadable documents and files
whose contents do not match their `.pdf` extension are reported as skipped.

TXT reference lists provide URLs, not evidence by themselves. Normal startup
fetches their contents, caches successful downloads, indexes them and gives Gemini
relevant retrieved passages. It does not crawl arbitrary links. Agilent sources
are assigned to Clinical; Cisco and Google Cloud sources go to Technology.
Blocked pages, redirects and insufficient content are reported in
`backend/data/public_source_report.json` without inventing replacement content.

SEC and CSR use dedicated ingestion scripts. The configured sources include
Alphabet fiscal 2024, Agilent fiscal 2025, Cisco fiscal 2025 and SOFI 2023/2024.
See the [backend reference](backend/README.md) for file locations and individual
fetch/index commands.

## What the chat provides

- Manager-selected specialists, routing reasons and a model-reported confidence
  indicator, explicitly distinguished from measured accuracy.
- Retrieved excerpts, source labels, PDF page numbers and public links when known.
- An executive synthesis for multi-domain questions with at least two usable
  specialist findings.
- Ranked proposals for advice questions, with an owner, prerequisites, qualitative
  expected impact and a measurable success indicator.
- Optional customer requirements, ranking weights and mandatory checks.

Proposal scores combine semantic similarity to requirements and source-domain
coverage. They are not estimates of ROI, reliability or compatibility. Equipment
purchases are held when compatibility or regulatory checks are unknown or failed;
the model cannot certify these checks.

Questions are independent: the backend does not retain conversation context or
customer profiles. Messages remain only in the current browser page and are
cleared on refresh or with the Clear button.

## Tests and evaluation

From the project root:

```powershell
Push-Location .\backend
try {
    .\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
} finally {
    Pop-Location
}
```

The saved run reports **62 passing regression tests**. On six developer-labeled
retrieval cases, mean source Recall@5 was **1.000** and labeled-page Recall@5 was
**0.667**. Two fixed-candidate ranking cases achieved Precision@1 of **1.000**.
These small diagnostic suites do not establish general recommendation quality.

The saved live run encountered Gemini quota exhaustion after one completed
routing case. Full routing accuracy and live cross-domain response quality were
not established. Human quality review remains pending. See the
[evaluation protocol](backend/evaluation/README.md) for reproducible commands,
labels, the optional model rubric and the human review template.

## Troubleshooting

| Symptom | Next step |
|---|---|
| App already running | Open its printed URL; stop it first to apply configuration changes |
| `WinError 10013` or port unavailable | Check for an existing server, or use `-Port 8503` and open that port |
| Installation canceled | Rerun full setup and let it finish; use `-SkipInstall` only if dependencies are already installed |
| Missing Gemini key | Configure `backend/.env`, check environment-variable overrides and restart |
| HTTP 429 / quota exhausted | Wait for the account's quota reset or review its API limits; restarting does not restore quota |
| Browser says it cannot reach the server | Keep the server running and open its HTTP address rather than the HTML file directly |
| HTTP 403 fetching a source | Obtain an authorized local copy and rerun local ingestion; the app does not bypass access restrictions |
| Wrong or missing evidence | Check the source files, selected company/year and ingestion output |

Citation checks validate reference labels against retrieved sources, not whether
every claim follows from the evidence. Original source files remain unchanged;
clinical display titles use hash-verified cover-title metadata where available.
Two mislabeled clinical PDFs remain skipped. Agilent equipment specifications
remain unavailable where source access fails. Review recommendations against
actual requirements and source documents before making decisions.
