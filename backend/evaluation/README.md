# Evaluation protocol

Run from `backend`:

```powershell
.\.venv\Scripts\python.exe -m evaluation.run --tests
.\.venv\Scripts\python.exe -m evaluation.run --live --tests
.\.venv\Scripts\python.exe -m evaluation.judge
```

The first command measures retrieval and ranking without Gemini calls. The second
also runs the labeled routing cases and two full answer cases (including
cross-domain synthesis). It makes paid/quota-limited Gemini calls. The third
optionally grades saved completed answers using a model rubric; it does not
regenerate them. All results contain real outputs or explicit failure statuses.
Copy `results.json` before a new run if you need to retain an earlier report.

Source labels and one-based PDF page sets were manually selected from available
reports and datasheets. Page labels are not exhaustive, so page Recall@5 is a
small diagnostic, not a comprehensive relevance benchmark. The two ranking
scenarios use fixed, labeled candidate actions; they do not evaluate arbitrary
live proposals or prove business impact. Thresholds/weights were not fitted using
the reported cases. Routing labels are developer-authored and not held out.

Citation checks validate identifiers, including grouped citations, against
retrieved metadata; they do not prove entailment. Automated response ratings use
a 1–5 rubric for groundedness, relevance, completeness and clarity and preserve
rationales/source IDs. Model judgments, especially from the same model being
evaluated, can be biased and require human review. Do not label them human scores.

Complete `human_review.csv` independently, recording reviewer and source-based
rationale. A 1 means unsupported/off-topic/incomplete; 3 means partially supported
or incomplete; 5 means supported and complete relative to available evidence.
Unknown equipment compatibility, costs, regulatory status and clinical outcomes
must remain unknown. Never replace failed API calls with successful ratings.
