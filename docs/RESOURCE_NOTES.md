# Professor resource inspection

All eight original files remain unchanged in `professor_resources/`. Full archive
member paths, PDF page counts, first-page excerpts, CSV schemas and SHA-256 hashes
are recorded in `artifacts/resource_inventory.json`. The complete 11-page
assignment transcript is `artifacts/assignment_text.txt`. Assignment diagrams and
example interfaces were also inspected visually before implementation.

| Resource | Actual contents | Application use |
|---|---|---|
| Clinical.zip | 20 research PDFs in Covid, Diabetes, Heart_attack and KneeInjuries; four `ctg-studies_*.csv` tables | Clinical paper retrieval; first-100-row trial table previews |
| SEC archive | Five PDFs under Agilent, Alphabet and Cisco | Company/year-filtered financial disclosure retrieval |
| FoodSecurity.zip | `FoodSecurity/SOFI-2023.pdf`, `SOFI-2024.pdf` | Separate report years in CSR retrieval |
| Retail.zip | `Retail/CMPE256_Hackathon_market_basket_analysis_Release.csv` | Apriori training and held-out evaluation |
| Cisco TXT | Five router product pages and five datasheets | Exact public-source fetch allowlist |
| Google TXT | Three MCP/RAG documentation links | Technology documentation ingestion |
| Agilent TXT | Six instrument/pathology links | Manufacturer documentation ingestion |
| Assignment PDF | 11 pages; manager/four specialists, RAG and iterative checkout examples | Implementation requirements |

The retail CSV contains 1,000 transactions, 40 distinct products and columns
`transaction_id,item_1,item_2,item_3,item_4,item_5`. Products contain actual names and
SKUs. Missing items are omitted; repeated IDs merge; duplicate products collapse;
empty baskets are excluded. Missing IDs are rejected.

Trial CSVs have 30 columns including NCT Number, Study Title, Study URL, Study
Status, Brief Summary, Conditions, Interventions, Outcome Measures and Enrollment.
They are preserved and previewable, not converted into claims about effectiveness.
No synthetic replacement dataset is used.

Filing cover years: Agilent fiscal 2025; Alphabet fiscal 2024 and 2025; Cisco fiscal
2025 and 2026. Filenames are opaque identifiers, so years come from cover text.
The assignment's final page has a legacy November 2025 footer; the title page and
project request establish October 17, 2026 as the hackathon date.

Public fetch measured in this workspace: 9 of 19 references downloaded—five Cisco
PDF datasheets, three Google Cloud pages, and Agilent's short digital-pathology
overview. Ten references failed (403, redirects or insufficient text). The overview
does not establish instrument throughput or compatibility. No IBM documents were
provided. Access can change; rerun fetching to inspect current availability.
Exact failures are in `data/public_source_report.json`. No access bypasses,
replacement URLs, inferred specifications or fabricated content are used.

Index: technology 288 chunks; clinical 562; SEC 2,806; CSR 1,968. Counts apply to
the local hashing backend and this public-source snapshot. Clinical equipment
queries retrieve Agilent manufacturer content; papers are not equipment specs.
