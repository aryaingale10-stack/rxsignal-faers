"""Step 3c: normalize drug names to RxNorm active ingredients with a layered pipeline.

  layer 1  rules          clean_names.py (lowercase, strip doses/forms/punctuation)
  layer 2  rxnorm_exact   exact normalized-string match in RxNorm
  layer 3  rxnorm_approx  RxNorm fuzzy match, accepted only if it resembles the input
  layer 4  llm_verified   optional LLM suggestion, accepted only if RxNorm confirms it

Each unique cleaned name is looked up once; results are cached, so re-runs are fast.
"""
import sqlite3
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from .clean_names import candidate_names, clean_name
from .llm import llm_available, suggest_generics
from .rxnorm import RxNormClient


def _lookup(client: RxNormClient, key: str, alts: list[str]) -> dict:
    for name in [key] + alts:
        hit = client.exact(name)
        if hit:
            return {**hit, "method": "rxnorm_exact"}
    for name in [key] + alts:
        hit = client.approximate(name)
        if hit:
            return {**hit, "method": "rxnorm_approx"}
    return {"method": "unresolved"}


def normalize(con: sqlite3.Connection, max_names: int, use_llm: bool, workers: int = 8,
              llm_max: int = 2000) -> dict:
    drug = pd.read_sql("SELECT rowid AS rid, primaryid, drugname, prod_ai, role_cod FROM drug_clean", con)
    print(f"  {len(drug):,} drug rows, {drug['drugname'].nunique():,} unique raw names")

    raw_unique = drug["drugname"].dropna().unique()
    raw_to_clean = {r: clean_name(r) for r in raw_unique}
    drug["cleaned_name"] = drug["drugname"].map(raw_to_clean)

    # Alternate candidates (e.g. generic name in parentheses) grouped by cleaned key.
    alts = defaultdict(set)
    for r in raw_unique:
        c = raw_to_clean[r]
        if c:
            for a in candidate_names(r)[1:]:
                alts[c].add(a)

    freq = drug["cleaned_name"].value_counts()
    keys = list(freq.index[:max_names])
    rows_covered = int(freq.iloc[:max_names].sum())
    print(f"  {len(freq):,} unique cleaned names; looking up the top {len(keys):,} "
          f"(they cover {100 * rows_covered / max(freq.sum(), 1):.1f}% of informative drug rows)")

    client = RxNormClient()
    results = {}
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_lookup, client, k, sorted(alts.get(k, []))[:3]): k for k in keys}
        for i, f in enumerate(as_completed(futs), 1):
            results[futs[f]] = f.result()
            if i % 250 == 0 or i == len(keys):
                print(f"    RxNorm lookups: {i:,}/{len(keys):,} ({time.time() - t0:.0f}s, "
                      f"{client.calls:,} API calls)")

    # Optional LLM layer for whatever RxNorm could not match.
    unresolved = [k for k in keys if results[k]["method"] == "unresolved"][:llm_max]
    llm_used = False
    if use_llm and unresolved:
        if not llm_available():
            print("  --llm given but no ANTHROPIC_API_KEY / OPENAI_API_KEY set; skipping LLM layer")
        else:
            llm_used = True
            print(f"  Asking the LLM about {len(unresolved):,} unresolved names ...")
            suggestions = suggest_generics(unresolved)
            for k, generic in suggestions.items():
                if generic:
                    hit = client.exact(generic)  # verify: hallucinations fail here
                    if hit:
                        results[k] = {**hit, "method": "llm_verified", "llm_suggestion": generic}
                    else:
                        results[k]["llm_suggestion"] = generic

    name_map = pd.DataFrame(
        [{"cleaned_name": k, **v} for k, v in results.items()]
    ).reindex(columns=["cleaned_name", "method", "ingredient", "rxcui", "matched_name",
                       "similarity", "llm_suggestion"])
    name_map.to_sql("name_map", con, if_exists="replace", index=False)

    m = name_map.set_index("cleaned_name")
    drug["ingredient"] = drug["cleaned_name"].map(m["ingredient"])
    drug["rxcui"] = drug["cleaned_name"].map(m["rxcui"])
    drug["norm_method"] = drug["cleaned_name"].map(m["method"])
    drug.loc[drug["cleaned_name"].isna(), "norm_method"] = "uninformative"
    drug["norm_method"] = drug["norm_method"].fillna("not_looked_up")

    # Write the new columns back onto drug_clean.
    full = pd.read_sql("SELECT rowid AS rid, * FROM drug_clean", con)
    full = full.drop(columns=["cleaned_name", "ingredient", "rxcui", "norm_method"], errors="ignore")
    full = full.merge(drug[["rid", "cleaned_name", "ingredient", "rxcui", "norm_method"]], on="rid")
    full.drop(columns="rid").to_sql("drug_clean", con, if_exists="replace", index=False, chunksize=50_000)
    con.execute("CREATE INDEX IF NOT EXISTS ix_drug_clean_pid ON drug_clean(primaryid)")
    con.execute("CREATE INDEX IF NOT EXISTS ix_drug_clean_ing ON drug_clean(ingredient)")
    con.commit()

    by_rows = drug["norm_method"].value_counts().to_dict()
    by_names = name_map["method"].value_counts().to_dict()
    total = len(drug)
    resolved = sum(by_rows.get(k, 0) for k in ("rxnorm_exact", "rxnorm_approx", "llm_verified"))
    return {
        "drug_rows": total,
        "unique_raw_names": int(len(raw_unique)),
        "unique_cleaned_names": int(len(freq)),
        "names_looked_up": len(keys),
        "rows_by_method": {k: int(v) for k, v in by_rows.items()},
        "names_by_method": {k: int(v) for k, v in by_names.items()},
        "pct_rows_normalized": round(100 * resolved / max(total, 1), 2),
        "llm_used": llm_used,
        "rxnav_api_calls": client.calls,
        "seconds": round(time.time() - t0, 1),
    }
