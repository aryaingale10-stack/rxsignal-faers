# RxSignal: Cleaning & Standardizing FDA Adverse Event Drug Data

A data quality and standardization pipeline for the FDA Adverse Event Reporting System (FAERS), built with Python, SQL and the NLM RxNorm API.

The FDA's Adverse Event Reporting System (FAERS) is a public database of millions of reports of
side effects. Drug names in it are typed by hand, so the same drug shows up dozens of ways
(`HUMIRA`, `HUMIRA PEN`, `HUMIRA (ADALIMUMAB)`, `humira 40mg/0.4ml`, ...). The data also has
duplicate case versions, impossible ages and weights, and placeholder names like `UNKNOWN`.

This project:

1. **Audits data quality** of one FAERS quarter with SQL (duplication, completeness, validity, consistency).
2. **Cleans** it: de-duplicates cases using FDA's rule, and nulls out impossible values.
3. **Normalizes drug names** to standard active ingredients (NLM RxNorm) with a layered pipeline:
   rules → RxNorm exact match → RxNorm fuzzy match (verified) → optional LLM suggestion (verified by RxNorm).
4. **Measures accuracy** against the FDA's own coded ingredient field, plus a hand-labeled sample (accuracy + Cohen's kappa).
5. **Re-runs the audit** to show before vs. after, and answers analysis questions
   (top drugs, reports missed without normalization, serious outcomes, top reactions, demographics).
6. **Builds an interactive dashboard** and exports tidy CSVs for Tableau / Power BI.

---

## Results (FAERS Q3 2026)

| Metric | Value |
|---|---|
| Reports analyzed | 421,404 |
| Drug records standardized | 1.58M, of which **92.4%** mapped to an RxNorm ingredient |
| Raw drug spellings → ingredients | **36,003 → 1,536** |
| Reports missing patient weight / event date / age | 82.1% / 56.0% / 36.0% |
| Reports missed when counting a drug by its most common spelling | up to **67%** (e.g. adalimumab: 13 spellings) |

## Run it (about 20–40 minutes, mostly RxNorm lookups)

Needs Python 3.9 or newer and an internet connection.

```bash
cd rxsignal-faers
python -m venv .venv
# Windows: .venv\Scripts\activate     Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt

python run_all.py --quarter 2026q3
```

Then open `output/dashboard.html` in your browser.

Options:

| Option | What it does |
|---|---|
| `--quarter 2026q2` | Choose another quarter (list: https://fis.fda.gov/extensions/FPD-QDE-FAERS/FPD-QDE-FAERS.html) |
| `--zip-path file.zip` | Use a FAERS ASCII zip you downloaded yourself |
| `--max-names 5000` | Look up more drug names (higher coverage, longer run). Default 3000. |
| `--llm` | Turn on the LLM layer. Set `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` first (optional `LLM_MODEL`). |
| `--skip-load` | Reuse the database from the last run |

RxNorm lookups are cached in `data/rxnav_cache.db`, so a second run is fast.

## What you get (`output/`)

| File | Use |
|---|---|
| `dashboard.html` | Interactive dashboard (portfolio piece) |
| `results.json` | Every number behind the dashboard |
| `tableau/*.csv` | Tidy tables to rebuild the dashboard in Tableau Public or Power BI |
| `manual_review_sample.csv` | ~300 names to label Y/N by hand → `python evaluate_labels.py` |
| `top_disagreements_with_fda_prod_ai.csv` | Where our ingredient and FDA's differ - good for error analysis |

## How it works

```
FDA zip ─► SQLite (raw) ─► SQL quality audit (BEFORE)
                │
                ▼
     clean: de-dup cases, fix invalid ages/weights/dates
                │
                ▼
     normalize drug names:
       1 rules          'TYLENOL EXTRA STRENGTH 500MG TABS' → 'tylenol'
       2 RxNorm exact   'tylenol' → acetaminophen
       3 RxNorm fuzzy   'lisinipril' → lisinopril  (accepted only if ≥80% similar)
       4 LLM (optional) 'norco' → suggests 'hydrocodone/acetaminophen' → confirmed in RxNorm
                │
                ▼
     SQL quality audit (AFTER) + accuracy checks + analysis ─► dashboard + CSVs
```

| Folder / file | What's in it |
|---|---|
| `sql/` | The data-quality checks, written as plain SQL |
| `src/load.py` | Loads the `$`-delimited FDA files into SQLite, counts malformed rows |
| `src/clean.py` | De-duplication and validity cleaning (SQL) |
| `src/clean_names.py` | Rule-based drug-name cleaning |
| `src/rxnorm.py` | RxNav API client: rate limit (15/sec, NLM allows 20), retries, cache |
| `src/llm.py` | Optional LLM suggestions (never trusted without RxNorm confirmation) |
| `src/normalize.py` | Runs the layers, writes `ingredient` back to the drug table |
| `src/evaluate.py` | Agreement with FDA `prod_ai` field; manual review sample |
| `src/analysis.py` | Analysis queries + Tableau exports |
| `src/dashboard.py` | Generates the HTML dashboard |
| `tests/` | Synthetic FDA-format data + a mock RxNorm server for offline testing |

### Test without internet

```bash
python tests/make_test_data.py                # synthetic data - NOT real numbers
python tests/mock_rxnav.py 8765 &             # fake RxNorm API
RXNAV_BASE=http://127.0.0.1:8765/REST python run_all.py --zip-path tests/faers_ascii_test26q3.zip
```

## Limitations (say these in interviews - it shows maturity)

* FAERS is voluntary reporting. Report counts show what gets **reported**, not how often a reaction **happens**, and a report does not prove the drug caused it.
* Only the most frequent `--max-names` cleaned names are looked up; rare names are left as "not looked up". The dashboard reports the exact coverage.
* The FDA `prod_ai` field is itself imperfect, so agreement with it is a sanity check, not ground truth. The hand-labeled sample is the real accuracy measure.
* Fuzzy matching can still be wrong for look-alike names (e.g. brand names one letter apart); check `top_disagreements_with_fda_prod_ai.csv`.

## Ideas to extend it

* Run several quarters and chart trends over time.
* Rebuild the dashboard in Tableau Public and link it on your resume.
* Add a disproportionality measure (reporting odds ratio) to flag drug–reaction pairs reported more than expected.
* Normalize reactions too (MedDRA preferred terms are already coded, so group them into body systems).

## Data sources

* U.S. FDA, FAERS Quarterly Data Extract Files: https://fis.fda.gov/extensions/FPD-QDE-FAERS/FPD-QDE-FAERS.html
* U.S. National Library of Medicine, RxNorm / RxNav API: https://lhncbc.nlm.nih.gov/RxNav/APIs/RxNormAPIs.html
