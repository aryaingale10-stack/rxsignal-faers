"""Run the whole project end to end.

    python run_all.py --quarter 2026q3
    python run_all.py --quarter 2026q3 --max-names 5000 --llm   # bigger run + LLM layer

Outputs (in output/):
    dashboard.html               interactive dashboard - open in a browser
    results.json                 every number in the dashboard
    tableau/*.csv                tidy tables for Tableau / Power BI
    manual_review_sample.csv     sample to label by hand (then: python evaluate_labels.py)
    top_disagreements_with_fda_prod_ai.csv
"""
import argparse
import json
import sqlite3
import time
from datetime import date
from pathlib import Path

import pandas as pd

from src.analysis import run_analysis
from src.clean import build_clean_tables
from src.config import DB_PATH, OUTPUT_DIR, TABLEAU_DIR
from src.dashboard import write_dashboard
from src.download import download_quarter
from src.evaluate import export_manual_sample, prod_ai_agreement
from src.load import load_zip
from src.normalize import normalize
from src.quality import audit, name_variants


def step(n, text):
    print(f"\n[{n}/7] {text}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quarter", default="2026q3", help="FAERS quarter, e.g. 2026q3")
    ap.add_argument("--zip-path", help="use an already-downloaded faers_ascii_*.zip instead of downloading")
    ap.add_argument("--max-names", type=int, default=3000,
                    help="how many of the most frequent cleaned drug names to look up in RxNorm (default 3000)")
    ap.add_argument("--llm", action="store_true", help="enable the optional LLM layer (needs an API key)")
    ap.add_argument("--skip-load", action="store_true", help="reuse data/faers.db from a previous run")
    args = ap.parse_args()
    t0 = time.time()

    if not args.skip_load:
        step(1, "Get the FDA data")
        zip_path = Path(args.zip_path) if args.zip_path else download_quarter(args.quarter)
        print("  Loading into SQLite ...")
        load_stats = load_zip(zip_path, DB_PATH)
    else:
        step(1, "Reusing existing database")
        load_stats = None

    con = sqlite3.connect(DB_PATH)

    step(2, "Data quality audit: BEFORE (raw tables)")
    before = audit(con, "demo_raw", "drug_raw")
    print(f"  duplicate case versions: {before['duplication']['pct_duplicate_rows']}%  |  "
          f"invalid ages: {before['validity']['pct_invalid_ages']}%  |  "
          f"unique raw drug names: {before['unique_raw_drug_names']:,}")

    step(3, "Clean: de-duplicate cases, fix invalid ages/weights/dates")
    build_clean_tables(con)

    step(4, "Normalize drug names (rules -> RxNorm exact -> RxNorm fuzzy -> optional LLM)")
    norm = normalize(con, max_names=args.max_names, use_llm=args.llm)
    print(f"  {norm['pct_rows_normalized']}% of drug rows mapped to an RxNorm ingredient")

    step(5, "Data quality audit: AFTER (clean tables) + accuracy checks")
    after = audit(con, "demo_clean", "drug_clean")
    variants = name_variants(con)
    agreement = prod_ai_agreement(con)
    n_sample = export_manual_sample(con)
    unique_ingredients = con.execute(
        "SELECT COUNT(DISTINCT ingredient) FROM drug_clean WHERE ingredient IS NOT NULL").fetchone()[0]
    print(f"  agreement with FDA-coded ingredient: {agreement['pct_agree']}% "
          f"on {agreement['rows_compared']:,} rows; {n_sample} names exported for manual review")

    step(6, "Analysis")
    analysis = run_analysis(con)
    con.close()

    step(7, "Write results, Tableau CSVs and dashboard")
    results = {
        "quarter": args.quarter if not args.zip_path else Path(args.zip_path).stem.replace("faers_ascii_", ""),
        "generated": date.today().isoformat(),
        "load": load_stats,
        "quality_before": before,
        "quality_after": after,
        "normalization": norm,
        "unique_ingredients": unique_ingredients,
        "name_variants": variants,
        "agreement": agreement,
        "analysis": analysis,
    }
    (OUTPUT_DIR / "results.json").write_text(json.dumps(results, indent=2, default=str))
    qa = [
        ("duplicate_case_versions_pct", before["duplication"]["pct_duplicate_rows"], after["duplication"]["pct_duplicate_rows"]),
        ("invalid_age_pct", before["validity"]["pct_invalid_ages"], after["validity"]["pct_invalid_ages"]),
        ("invalid_weight_pct", before["validity"]["pct_invalid_weights"], after["validity"]["pct_invalid_weights"]),
        ("invalid_event_date_pct", before["validity"]["pct_invalid_event_dates"], after["validity"]["pct_invalid_event_dates"]),
        ("age_complete_pct", before["completeness_demo"]["pct_age"], after["completeness_demo"]["pct_age"]),
        ("sex_complete_pct", before["completeness_demo"]["pct_sex"], after["completeness_demo"]["pct_sex"]),
        ("distinct_drug_identifiers", before["unique_raw_drug_names"], unique_ingredients),
        ("drug_rows_on_standard_vocab_pct", 0, norm["pct_rows_normalized"]),
    ]
    pd.DataFrame(qa, columns=["metric", "before", "after"]).to_csv(TABLEAU_DIR / "quality_before_after.csv", index=False)
    pd.DataFrame(variants).to_csv(TABLEAU_DIR / "spellings_per_ingredient.csv", index=False)
    pd.DataFrame([{"method": k, "drug_rows": v} for k, v in norm["rows_by_method"].items()]).to_csv(
        TABLEAU_DIR / "normalization_methods.csv", index=False)
    write_dashboard(results, OUTPUT_DIR / "dashboard.html")
    print(f"\nDone in {(time.time() - t0) / 60:.1f} min. Open {OUTPUT_DIR / 'dashboard.html'}")


if __name__ == "__main__":
    main()
