"""Step 4: check accuracy two ways.

1. Automatic: compare our ingredient with the FDA's own coded active-ingredient field
   (prod_ai) on rows where the FDA filled it in. prod_ai is not perfect, so this is a
   sanity check / agreement rate, not absolute truth.
2. Manual: export a random sample (stratified by method) for a human to label correct /
   incorrect. Score it later with evaluate_labels.py (accuracy + Cohen's kappa).
"""
from __future__ import annotations
import re
import sqlite3

import pandas as pd
from rapidfuzz import fuzz

from .config import OUTPUT_DIR

SALT_WORDS = {
    "hydrochloride", "hcl", "dihydrochloride", "sodium", "potassium", "calcium", "magnesium",
    "sulfate", "sulphate", "mesylate", "maleate", "tartrate", "bitartrate", "succinate",
    "besylate", "acetate", "citrate", "phosphate", "bromide", "fumarate", "hydrobromide",
    "monohydrate", "dihydrate", "trihydrate", "hyclate", "propionate", "dipropionate",
    "valerate", "furoate", "xinafoate", "disodium", "anhydrous", "medoxomil", "pegol",
    "mofetil", "monosodium", "hemifumarate", "lysine", "trometamol", "tromethamine",
    "oxalate", "bisulfate", "trifenatate", "acetonide", "human", "nos", "pancrelipase",
}

# Same substance, different standard names (RxNorm name -> FDA prod_ai style).
SYNONYMS = {
    "cholecalciferol": "vitamin d3", "cyanocobalamin": "vitamin b12",
    "onabotulinumtoxina": "botulinum toxin type a", "immunoglobulin g": "immunoglobulin g",
    "ascorbic acid": "vitamin c", "ergocalciferol": "vitamin d2",
}
# FDA adds a 4-letter suffix to biologic names (risankizumab-rzaa); RxNorm usually drops it.
BIOLOGIC_SUFFIX = re.compile(r"-[a-z]{4}$")


def _one(name: str) -> str:
    raw = " ".join(re.sub(r"[^a-z\s\-]", " ", name).split())
    words = [w for w in raw.split() if w not in SALT_WORDS]
    text = " ".join(words) or raw          # 'magnesium' alone is the ingredient, keep it
    text = BIOLOGIC_SUFFIX.sub("", text)
    return SYNONYMS.get(text, text)


def _ingredient_set(text) -> frozenset:
    if not isinstance(text, str) or not text.strip():
        return frozenset()
    text = text.lower()
    inner = re.findall(r"\(([^)]*)\)", text)   # 'TYLENOL (ACETAMINOPHEN)' -> 'acetaminophen'
    if inner:
        text = inner[0]
    parts = re.split(r"\\| / |/|,|\band\b", text)
    return frozenset(o for o in (_one(p) for p in parts) if o and o not in {"human", "nos"})


def _agrees(ours: frozenset, fda: frozenset) -> bool:
    if not ours or not fda:
        return False
    if ours == fda:
        return True
    if len(ours) != len(fda):
        return False
    a, b = " ".join(sorted(ours)), " ".join(sorted(fda))
    return fuzz.token_sort_ratio(a, b) >= 90


def prod_ai_agreement(con: sqlite3.Connection) -> dict:
    df = pd.read_sql(
        "SELECT ingredient, prod_ai, norm_method FROM drug_clean "
        "WHERE ingredient IS NOT NULL AND prod_ai IS NOT NULL", con)
    if df.empty:
        return {"rows_compared": 0, "pct_agree": None, "by_method": {}}
    pairs = df[["ingredient", "prod_ai"]].drop_duplicates()
    pairs["agree"] = [_agrees(_ingredient_set(a), _ingredient_set(b))
                      for a, b in zip(pairs["ingredient"], pairs["prod_ai"])]
    df = df.merge(pairs, on=["ingredient", "prod_ai"])
    by_method = df.groupby("norm_method")["agree"].agg(["mean", "size"])
    disagreements = (df[~df["agree"]].groupby(["ingredient", "prod_ai"]).size()
                     .sort_values(ascending=False).head(25).reset_index(name="rows"))
    disagreements.to_csv(OUTPUT_DIR / "top_disagreements_with_fda_prod_ai.csv", index=False)
    return {
        "rows_compared": int(len(df)),
        "pct_agree": round(100 * df["agree"].mean(), 2),
        "by_method": {m: {"pct_agree": round(100 * r["mean"], 2), "rows": int(r["size"])}
                      for m, r in by_method.iterrows()},
    }


def export_manual_sample(con: sqlite3.Connection, n: int = 300, seed: int = 42) -> int:
    df = pd.read_sql(
        "SELECT drugname AS raw_name, cleaned_name, norm_method AS method, ingredient, "
        "MIN(prod_ai) AS fda_prod_ai_example, COUNT(*) AS drug_rows "
        "FROM drug_clean WHERE norm_method IN ('rxnorm_exact','rxnorm_approx','llm_verified','unresolved') "
        "GROUP BY drugname", con)
    if df.empty:
        return 0
    per = max(n // df["method"].nunique(), 1)
    sample = pd.concat([g.sample(min(len(g), per), random_state=seed)
                        for _, g in df.groupby("method")])
    sample = sample.sample(frac=1, random_state=seed)
    sample["reviewer1_correct (Y/N)"] = ""
    sample["reviewer2_correct (Y/N)"] = ""
    sample.to_csv(OUTPUT_DIR / "manual_review_sample.csv", index=False)
    return int(len(sample))
