# Backend reference

For installation, Gemini configuration, restart instructions and Windows startup
commands, use the [main README](../README.md). This document describes the current
backend and individual maintenance commands.

## Architecture

```text
Browser chat -> POST /consult -> Manager Agent -> selected specialists
                                                | Technology
                                                | Clinical
                                                | SEC
                                                | Corporate Responsibility
                                                      |
                                              domain-specific retrieval
                                                      |
                                             cited specialist answers
                                                      |
                                        cross-domain synthesis when needed
                                                      |
                                      ranked proposals for advice questions
```

| Component | Responsibility |
|---|---|
| `main.py` | FastAPI routes and specialist orchestration |
| `llm.py` | Gemini settings, client factories and local embedding model |
| `agents/manager.py` | Classify intent, select domains and explain routing |
| `agents/technology.py`, `clinical.py`, `sec.py`, `csr.py` | Domain-specific answers |
| `agents/cross.py` | Combine usable findings from multiple domains |
| `rag/` | Loading, chunking, Chroma storage, retrieval and citation checks |
| `recommendations/` | Generate structured proposals and rank eligible candidates |
| `web/` | Chat and saved evaluation interfaces |
| `evaluation/` | Labeled cases, evaluation scripts, results and review template |

## Configuration and storage

Create `backend/.env` using the copyable template in the
[main README's environment setup](../README.md#create-backendenv).
When working from this directory, the file path is simply `.env`.

Configuration precedence is process environment, then `backend/.env`, then the
root `.env`. All reasoning agents use `GEMINI_API_KEY` and `GEMINI_MODEL`.
`GEMINI_MODEL` defaults to `gemini-2.5-flash`; set it to a model available to your
account when needed. Restart the server after changing configuration.

Embeddings use FastEmbed's `BAAI/bge-small-en-v1.5` on CPU. Its first use downloads
the model into `.cache/fastembed/`. Cached local embedding generation requires no
Gemini calls. Vectors are stored in `chroma_db_local_bge_small_en_v15/` with separate
`technology`, `clinical`, `sec` and `csr` collections. Changing the embedding model
requires a separate or rebuilt index with matching vectors.

The API is a local prototype. It has no user authentication, persistent customer
profiles or server-side conversation history. `/consult` treats each question
independently. Model confidence is not calibrated accuracy.

## Source locations

Paths in this section are relative to `backend`.

| Domain | Inputs |
|---|---|
| Technology | PDF/TXT files under `data/technology/` and `documents/technology/` |
| Clinical | PDF/TXT files under `data/clinical/` and `documents/clinical/` |
| SEC | Filing PDFs configured in `ingest_sec.py` under `data/sec/` |
| CSR | `data/csr/SOFI-2023.pdf` and `data/csr/SOFI-2024.pdf` |

Reference lists are read from the top level of `data/technology/*.txt` and
`data/clinical/*.txt`. Fetched content is saved under the appropriate domain's
`public_web/` subdirectory with `.source.json` provenance. Agilent references are
routed to Clinical even when `Agilent.txt` is stored in Technology.

The public-source fetcher allows only exact listed HTTPS URLs, rejects redirects,
limits downloads to 25 MB and caches successful results. It records failures in
`data/public_source_report.json`. It does not crawl or treat descriptions as
retrieved documentation. Some sites return HTTP 403 and require authorized local
copies instead.

`fetch_sec.py` separately retrieves Cisco's
[official fiscal 2025 annual report](https://www.cisco.com/c/dam/en_us/about/annual-report/2025-cisco-full-annual-report.pdf),
verifies the company and fiscal period, and saves its source URL. The SEC ingestion
configuration also includes Alphabet fiscal 2024 and Agilent fiscal 2025.

Clinical papers with mismatched filenames retain their original paths. Verified
cover titles in `data/clinical_titles.json` are used for display only when the PDF
hash matches. CSV trial records are preserved but not embedded. Two files with
`.pdf` names actually contain CSV data and are skipped.

## Fetch and index manually

Run these commands from the **backend directory**. No environment activation is
necessary when using its explicit Python path.

Fetch the listed public sources and the Cisco filing:

```powershell
.\.venv\Scripts\python.exe fetch_technology.py --all
.\.venv\Scripts\python.exe fetch_sec.py
```

Use `fetch_technology.py --all --refresh` to download successful cached reference
sources again. A single listed URL can be selected with `--url`.

Index each domain:

```powershell
.\.venv\Scripts\python.exe ingest_sec.py
.\.venv\Scripts\python.exe ingest_csr.py
.\.venv\Scripts\python.exe ingest_domains.py
```

To update only clinical or technology documents:

```powershell
.\.venv\Scripts\python.exe ingest_domains.py --domain clinical
.\.venv\Scripts\python.exe ingest_domains.py --domain technology
```

Dedicated scripts use stable chunk IDs, skip unchanged embeddings and remove
obsolete passages for modified files after storing replacements. Original input
files are preserved. Missing configured SEC/CSR documents stop their ingestion;
unsupported or unreadable clinical/technology inputs are reported as skipped.
Deleting a source file does not automatically purge its previously indexed chunks.

After adding an SEC filing, update its verified company and full fiscal date in
`ingest_sec.py` before indexing. Do not infer these fields from an opaque filename.
Avoid using the low-level `store_documents` helper for repeat ingestion: it does
not provide the scripts' stable-ID handling.

## Retrieval, citations and recommendations

SEC retrieval filters explicitly named companies and filing periods. Technology
queries naming Cisco or Google use the corresponding source organization.
Clinical instrument/Agilent questions use Agilent manufacturer evidence rather
than treating general research papers as equipment specifications. CSR can filter
SOFI 2023/2024 by the requested report year.

Answers expose evidence excerpts and one-based physical PDF pages when available.
Citation validation recognizes grouped labels and domain-qualified references.
Missing or invalid references cause answers to be withheld. Source identity
checks do not establish claim entailment or guarantee that retrieved passages
fully answer the question.

Cross-domain synthesis requires at least two usable specialist findings. Failed,
uncited or insufficient-evidence results are excluded. Its sources have
qualified IDs such as `technology:T1` and `sec:S1`.

Advice questions may produce up to three proposals with an owner, prerequisites,
qualitative expected impact, success metric and supporting source IDs. The chat
accepts optional requirements and ranking weights. Default weights are:

| Factor | Weight | Meaning |
|---|---|---|
| Requirement match | 0.7 | Computed cosine similarity to the customer's question and requirements |
| Domain coverage | 0.3 | Fraction of requested domains represented by proposal citations |

Scores compare the generated eligible proposals; they do not estimate cost,
reliability, regulatory compliance or ROI. Unknown numeric business inputs remain
unknown. Procurement requires verified compatibility and regulatory checks, and
additional configured mandatory checks apply to actions too. Unknown/failed checks
hold a proposal out of ranking. The model cannot self-certify checks. The ranker
supports explicit operator assertions for controlled use; the chat does not
provide a purchase-approval workflow or authentication boundary.

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Chat interface |
| GET | `/health` | Server health |
| GET | `/docs` | Interactive API documentation |
| POST | `/route` | Manager classification without running specialists |
| POST | `/consult` | Run selected specialists, synthesis and advice ranking |
| POST | `/csr` | Query the CSR specialist directly |
| GET | `/evaluation` | Saved evaluation report as JSON |
| GET | `/evaluation/view` | Evaluation report page |

Example consultation body:

```json
{
  "question": "Should we pilot Cisco Catalyst 8300 networking considering supplier financial risk?",
  "requirements": "Prioritize availability; equipment compatibility is not yet verified.",
  "recommendation_weights": {
    "requirement_match": 0.7,
    "domain_coverage": 0.3
  },
  "mandatory_constraints": []
}
```

For CSR, `report_year` optionally accepts `2023` or `2024`. `/consult` returns
routing information, `agent_results`, `pending_domains`, optional `synthesis` and
optional `recommendations`. Partial results remain explicit. Gemini quota errors
at the manager are reported as HTTP 429; specialist failures can appear in partial
consultation results.

## Verification

Run tests from **backend** so the ingestion scripts are importable:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

The saved snapshot contains 62 passing tests covering ingestion, source filters,
citation rejection, cross-domain synthesis, ranking weights, mandatory checks,
quality-rubric validation, API integration and JavaScript rendering. Node.js is
needed for the renderer test. Regression tests do not measure general answer
accuracy. Evaluation commands and their limitations are documented in the
[evaluation protocol](evaluation/README.md); the saved results distinguish local
measurements, quota-blocked live checks and pending human review.

Clinical research questions about machine-learning methods route to Clinical;
mentioning ML or neural networks alone does not select enterprise Technology.
Explicit cloud deployment/networking questions still support both specialists.
The routing guard is tested with the exact heart-attack research example; this
regression result does not replace live routing evaluation.

Multi-domain consultations now expose `specialist_tasks` with separate domain
questions. Technology does not receive the SEC/SOFI subquestions, and financial
risk searches use the identified Item 1A body when available. Named Catalyst
queries filter to the corresponding product family. Cross-domain synthesis uses
structured status/source checks instead of discarding any answer containing the
phrase "insufficient evidence"; a valid technical answer may still have a caveat
about another domain. Every usable specialist must be cited in the synthesis or
the integrated answer is withheld. This behavior is covered by regression tests,
including the nonprofit/Catalyst 8300/fiscal 2025/SOFI 2024 example.
