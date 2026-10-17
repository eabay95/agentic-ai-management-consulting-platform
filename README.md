# SJSU Decision Studio

A Streamlit hackathon application combining a shared consulting manager and four
domain specialists with a separate Apriori retail checkout demonstration. It uses
the actual CMPE 256 resources and preserves the originals.

Five pages provide consulting and separate customer histories, live shopping-cart
recommendations, Apriori analytics, knowledge-base management and system
evaluation. See [resource inspection](docs/RESOURCE_NOTES.md) for the data inventory.

## Windows PowerShell setup

For one-command setup and launch, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run.ps1
```

The launcher creates `.venv`, installs dependencies when requirements change,
preserves your existing `.env`, safely extracts the supplied archives and updates
the index before opening Streamlit. No virtual-environment activation is required.
Python 3.11+ and internet access for the initial dependency installation are needed.
The execution-policy flag applies only to this invocation, not your saved policy.
Stop the server with Ctrl+C. If port 8501 is in use, append `-Port 8502`.

Optional switches: `-FetchPublic` downloads the professor-approved online documents
(use it on your first setup for technology sources); `-SetupOnly` prepares without
starting Streamlit; `-Reinstall` reruns dependency installation; `-NoBrowser` keeps
the browser closed; `-Plan` prints the steps without changing anything. Indexing
uses your `.env` embedding settings; `EMBEDDING_BACKEND=local` needs no API key.
If a step fails, the launcher stops with an error and can be rerun after fixing it.

Python 3.11+ is required; this workspace was tested on Python 3.14. Dependencies
are pinned to tested versions.

```powershell
Set-Location 'C:\Users\James\OneDrive\Desktop\vscode files\market-basket-recommendation'
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

For Gemini, add your key to the local `.env` (a template has been created here):

```dotenv
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-flash-latest
EMBEDDING_BACKEND=local
```

Restart Streamlit after saving `.env`. In consulting settings, enable **Use
Gemini reasoning**. The manager and all four specialists use Gemini with the same
citation checks. Local embeddings need no OpenAI key and no index rebuild.
Gemini embeddings are not implemented; optional OpenAI embeddings still require
an OpenAI key.

`LLM_PROVIDER=auto` prefers a configured Gemini key, then an OpenAI key, otherwise
stays in evidence-only mode. Explicit selection never silently switches providers
after errors. The model is configurable; `gemini-flash-latest` is a moving alias.
Generated reasoning sends the current customer's context and source excerpts to
the selected API provider. Gemini SDK paths are mock-tested; live Gemini calls
were not run without credentials. API failures preserve retrieved evidence.

For optional OpenAI reasoning, set `LLM_PROVIDER=openai` and `OPENAI_API_KEY`
in `.env`, or in the current PowerShell 7 session:

```powershell
$env:OPENAI_API_KEY = Read-Host 'OpenAI API key' -MaskInput
$env:OPENAI_MODEL = 'gpt-4.1-mini'
```

Windows PowerShell 5 users should edit `.env` in Notepad instead of `-MaskInput`.
Never commit `.env`. Model names are configurable; unavailable models produce a
visible API-error state. Generated reasoning sends the selected customer's context
and retrieved excerpts to OpenAI with `store=False`.

## Extract, inspect and index real resources

```powershell
python scripts/inspect_resources.py
python -m rag.ingestion --extract
python -m rag.public_sources
python -m rag.ingestion --index
```

Fetching is optional for offline PDFs, but needed for the technology and Agilent
manufacturer collections. It accesses only the 19 exact HTTPS URLs listed by the
professor. No crawling, archive execution or redirects. Failures appear in
`data/public_source_report.json`. Extraction validates every path before writing
and rejects traversal, absolute paths, symlinks and oversized archives.

The default `EMBEDDING_BACKEND=local` uses reproducible 2,048-dimensional lexical
hashing embeddings and Chroma cosine search, without downloads or a key. This is
limited offline retrieval, not semantic understanding. To build semantic vectors:

```powershell
$env:EMBEDDING_BACKEND = 'openai'
$env:OPENAI_EMBEDDING_MODEL = 'text-embedding-3-small'
python -m rag.ingestion --index
```

This makes paid embedding requests and transmits chunks to OpenAI. Each
model/backend uses separate Chroma collections. Rebuild when switching and keep
the environment setting when starting Streamlit. The semantic API path is
implemented and contract-tested, but was not run here because no key was available.

## Analyze, test and run

```powershell
python -m evaluation.evaluate_retail --support 0.005 --confidence 0.08 --lift 1.0
python -m evaluation.evaluate_agents --retrieval
python -m pytest -q --junitxml=artifacts/pytest.xml
python -m streamlit run app.py
```

Open `http://localhost:8501`. The consulting page opens immediately in Guest / Demo
chat; no customer creation is required. Type into the pinned bottom chat input or
click an evidence-grounded follow-up beneath the latest response. Participating
agents and citations appear for each answer. Public sources have clickable links;
local professor documents have download buttons and PDF page references.

Create or select a named customer through the optional profile controls to keep
a saved customer conversation. Guest history stays in the browser session across
reruns and is separate from every named customer. Clear Chat resets only the
selected conversation. Without a key, leave reasoning off to inspect excerpts.
The UI supports indexing, exact public URL fetching, shared uploads and
customer-private PDF/TXT uploads. Trial CSV previews are on the Knowledge Base page.

Demonstration questions:

- “What financial and operational risks did Cisco disclose in fiscal 2025 SEC filings?”
- “How do food prices affect food security in the 2024 report?”
- “Evaluate Cisco networking infrastructure, financial risk and sustainability.”
- “Which Agilent instrument meets our laboratory throughput and assay requirements?”

In retail, add an actual SKU, then a recommended item and observe the revised
antecedents and recommendation explanations.

## Architecture and behavior

`agents/manager.py` contains one stateless manager shared across customers. Its
transparent deterministic multi-label intent router selects domain subtasks and
uses only that customer's preceding question for underspecified follow-ups.
Specialists retrieve independently, analyze evidence with Gemini or OpenAI when enabled,
and contribute findings to a manager synthesis. Unknown intent asks for
clarification; missing evidence remains explicit.

`rag/` preserves PDF pages, paths, organizations, URLs, detected years and customer
ownership. Chunks stay within pages and have stable IDs. Repeat ingestion skips
unchanged embeddings; modifications replace stale chunks; duplicate public files
are skipped. Domain collections and customer filters prevent cross-domain/private
retrieval. Company/year filters handle explicit comparisons separately.

Claim source IDs must exist in retrieved evidence; quotes must match verbatim
after whitespace normalization. Invalid claims are withheld. This checks identity
and excerpts, **not logical entailment**. Generated analysis requires review.
Equipment specs and clinical outcomes cannot be inferred from unrelated papers.
Historical filings are not live market data. Food reports cannot establish an
individual supplier's sustainability.

`recommendations/consulting_ranker.py` is independent from Apriori. It implements
configurable weights and hard constraints: false or unknown mandatory checks
exclude procurement candidates. Unknown numeric factors remain unknown. Current
generated proposals have no numeric scores. Scores are comparable only with the
same known factors. Proposals awaiting verification appear with next steps.

`customer/context.py` stores separate UUID profiles/histories. Private uploads
stay outside public ingestion directories; retrieval includes public plus selected
customer evidence. Selection is **not authentication or production security**.
Concurrent multi-process editing and enterprise access control are out of scope.

`recommendations/apriori.py` verifies the CSV schema, preserves transaction IDs,
one-hot encodes with mlxtend and mines Apriori itemsets/rules. Recommendations
prefer full-cart antecedents, then explicitly labeled satisfied-subset fallback.
They exclude cart products and rank by coverage, confidence, lift and support,
with deterministic ties. Empty carts and unmatched rules produce no suggestions.
Associations do not establish causation or hardware compatibility.

## Measured results and limits

Saved results in `artifacts/` contain exact parameters and per-case outcomes.

| Check | Measured result |
|---|---|
| Automated tests | 54 passed, including Gemini/OpenAI contracts, guest/named chat, follow-ups, citations, page rendering and cart interactions |
| Labeled routing | 10/10 exact route sets; micro F1 1.0 |
| Document retrieval | Mean source Recall@5 1.0 on six cases, local backend |
| Retail split | 800 training / 200 test transactions; seed 256 |
| Retail Precision@5 | 0.0500 |
| Retail Recall@5 | 0.1142 |
| Retail coverage | 1.0000 |
| Retail hit rate | 0.2200 |
| Useful training rules | 459 at support .005, confidence .08, lift 1.0 |

Retail evaluation groups identical baskets before an 80/20 split, mines training
baskets only and hides half of each test basket. Precision@5 divides by five,
counting empty slots as misses. Recall uses hidden items. Coverage measures carts
receiving at least one suggestion. High coverage does not imply relevance; the
measured precision is low. Thresholds demonstrate sparse associations and were
not tuned against test results. Analytics demo rules use all transactions;
evaluation retrains independently. Fixtures never replace the real dataset.

Routing labels are a small developer-authored suite, not an independent benchmark.
Retrieval labels identify documents rather than relevant passages; K applies per
requested company/year. Live OpenAI reasoning, semantic retrieval quality,
recommendation relevance, groundedness and completeness are **not measured**.
The Evaluation page supplies a human review protocol instead of invented scores.
Tests include mocked API contracts and failure handling. mlxtend emits a harmless
warning for an unused certainty metric on a degenerate fixture.

Limits: no OCR; unknown publication years remain blank; trial CSVs are previewed,
not embedded; keyword routing has limited language coverage; fetched pages may
be incomplete or stale; redirects are intentionally rejected. Additional evidence
is required for instrument selection, clinical outcomes, component compatibility
and specific supplier sustainability when sources do not establish them.

API integration follows the official
[Responses API](https://developers.openai.com/api/reference/python/resources/responses/methods/create)
and [Embeddings API](https://developers.openai.com/api/reference/resources/embeddings/methods/create),
plus the [Google Gen AI SDK](https://googleapis.github.io/python-genai/).
