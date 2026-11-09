"""Step 1b: load the FAERS '$'-delimited text files into a SQLite database.

Raw tables (exactly as the FDA published them):
  demo_raw  - one row per report version (patient age, sex, weight, dates, country)
  drug_raw  - one row per drug listed on a report (free-text drug name, role, route, dose)
  reac_raw  - one row per reaction (MedDRA preferred term)
  outc_raw  - one row per outcome code (death, hospitalization, ...)
"""
import csv
import io
import sqlite3
import zipfile
from pathlib import Path

import pandas as pd

TABLES = {"DEMO": "demo_raw", "DRUG": "drug_raw", "REAC": "reac_raw", "OUTC": "outc_raw"}


def _find_member(zf: zipfile.ZipFile, prefix: str) -> str:
    for name in zf.namelist():
        base = name.replace("\\", "/").split("/")[-1].upper()
        if base.startswith(prefix) and base.endswith(".TXT"):
            return name
    raise FileNotFoundError(f"No {prefix}*.txt file found in the zip")


def load_zip(zip_path: Path, db_path: Path) -> dict:
    """Load the four tables. Returns per-file row counts, including malformed rows skipped."""
    load_stats = {}
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    with zipfile.ZipFile(zip_path) as zf:
        for prefix, table in TABLES.items():
            member = _find_member(zf, prefix)
            raw_bytes = zf.read(member)
            text = raw_bytes.decode("latin-1")
            # Lines in the file minus the header = rows the FDA published.
            published_rows = max(text.count("\n") - 1 + (0 if text.endswith("\n") else 1), 0)
            df = pd.read_csv(
                io.StringIO(text),
                sep="$",
                dtype=str,
                quoting=csv.QUOTE_NONE,
                on_bad_lines="skip",
                keep_default_na=False,
                engine="c",
            )
            df.columns = [c.strip().lower() for c in df.columns]
            df = df.loc[:, [c for c in df.columns if c and not c.startswith("unnamed")]]
            # Empty strings -> NULL so completeness checks work in SQL.
            df = df.replace({"": None})
            df.to_sql(table, con, index=False, chunksize=50_000)
            load_stats[table] = {
                "source_file": member,
                "published_rows": int(published_rows),
                "loaded_rows": int(len(df)),
                "malformed_rows_skipped": int(max(published_rows - len(df), 0)),
            }
            print(f"  {table:9s} {len(df):>10,} rows loaded "
                  f"({load_stats[table]['malformed_rows_skipped']:,} malformed skipped)")
    con.execute("CREATE INDEX IF NOT EXISTS ix_demo_pid ON demo_raw(primaryid)")
    con.execute("CREATE INDEX IF NOT EXISTS ix_drug_pid ON drug_raw(primaryid)")
    con.execute("CREATE INDEX IF NOT EXISTS ix_reac_pid ON reac_raw(primaryid)")
    con.execute("CREATE INDEX IF NOT EXISTS ix_outc_pid ON outc_raw(primaryid)")
    con.commit()
    con.close()
    return load_stats
