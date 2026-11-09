"""Shared settings and paths for RxSignal."""
from __future__ import annotations
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
TABLEAU_DIR = OUTPUT_DIR / "tableau"
SQL_DIR = ROOT / "sql"
DB_PATH = DATA_DIR / "faers.db"

# FDA quarterly extract files, e.g. faers_ascii_2026q3.zip
FAERS_URL = "https://fis.fda.gov/content/Exports/faers_ascii_{quarter}.zip"

# NLM RxNav REST API (free, no key). Overridable for testing.
RXNAV_BASE = os.environ.get("RXNAV_BASE", "https://rxnav.nlm.nih.gov/REST")
# NLM allows 20 requests/second per IP; stay safely under it.
RXNAV_MAX_RPS = float(os.environ.get("RXNAV_MAX_RPS", "15"))

# Minimum fuzzy similarity (0-100) to accept an approximate RxNorm match.
APPROX_MIN_SIMILARITY = 80

for d in (DATA_DIR, OUTPUT_DIR, TABLEAU_DIR):
    d.mkdir(parents=True, exist_ok=True)
