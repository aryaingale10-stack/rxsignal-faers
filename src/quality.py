"""Step 2 & 5: data-quality audit. The checks live in sql/*.sql so they are easy to read.

The same SQL runs on the raw tables ("before") and the cleaned tables ("after").
"""
import sqlite3

from .config import SQL_DIR

CHECKS = {
    "duplication": "01_duplicate_versions.sql",
    "completeness_demo": "02_completeness_demo.sql",
    "completeness_drug": "03_completeness_drug.sql",
    "validity": "04_validity.sql",
    "uninformative_names": "05_uninformative_drug_names.sql",
}

UNINFORMATIVE = {
    "UNKNOWN", "UNK", "UNKNOWN DRUG", "UNSPECIFIED", "NOT REPORTED", "NOT SPECIFIED", "OTHER",
    "OTHERS", "NONE", "N/A", "NA", "-", "?", "OTHER MEDICATIONS", "OTHER MEDICATION",
    "CONCOMITANT DRUGS", "CONCOMITANT DRUG",
}


def _run(con: sqlite3.Connection, sql_file: str, demo: str, drug: str) -> dict:
    sql = (SQL_DIR / sql_file).read_text().format(demo=demo, drug=drug)
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    row = cur.fetchone()
    return {c: (row[i] if row[i] is not None else 0) for i, c in enumerate(cols)}


def audit(con: sqlite3.Connection, demo: str, drug: str) -> dict:
    out = {name: _run(con, f, demo, drug) for name, f in CHECKS.items()}
    v = out["validity"]
    v["pct_invalid_ages"] = round(100 * v["invalid_ages"] / v["ages_reported"], 2) if v["ages_reported"] else 0
    v["pct_invalid_weights"] = round(100 * v["invalid_weights"] / v["weights_reported"], 2) if v["weights_reported"] else 0
    v["pct_invalid_event_dates"] = (
        round(100 * v["invalid_event_dates"] / v["event_dates_reported"], 2) if v["event_dates_reported"] else 0
    )
    u = out["uninformative_names"]
    u["pct_uninformative"] = round(100 * u["uninformative_rows"] / u["drug_rows"], 2) if u["drug_rows"] else 0
    out["unique_raw_drug_names"] = con.execute(
        f"SELECT COUNT(DISTINCT UPPER(TRIM(drugname))) FROM {drug}"
    ).fetchone()[0]
    return out


def name_variants(con: sqlite3.Connection) -> list[dict]:
    cur = con.execute((SQL_DIR / "06_name_variants.sql").read_text())
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]
