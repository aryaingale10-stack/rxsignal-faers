"""Step 5: analysis questions answered with the cleaned, normalized data.

All counts are distinct reports (after de-duplication). 'Suspect' = the drug the reporter
named as the primary suspect (role_cod = 'PS').
"""
from __future__ import annotations
import sqlite3

import pandas as pd

from .config import TABLEAU_DIR

OUTCOME_LABELS = {"DE": "Death", "LT": "Life-threatening", "HO": "Hospitalization",
                  "DS": "Disability", "CA": "Congenital anomaly", "RI": "Required intervention",
                  "OT": "Other serious"}
REPORTER_LABELS = {"MD": "Physician", "PH": "Pharmacist", "OT": "Other health professional", "HP": "Health professional",
                   "LW": "Lawyer", "CN": "Consumer"}


def q(con, sql) -> pd.DataFrame:
    return pd.read_sql(sql, con)


def run_analysis(con: sqlite3.Connection, top_n: int = 20) -> dict:
    top = q(con, f"""
        SELECT ingredient, COUNT(DISTINCT primaryid) AS reports
        FROM drug_clean WHERE role_cod = 'PS' AND ingredient IS NOT NULL
        GROUP BY ingredient ORDER BY reports DESC LIMIT {top_n}""")
    top_list = top["ingredient"].tolist()
    in_list = ",".join("'" + i.replace("'", "''") + "'" for i in top_list) or "''"

    # Why normalization matters: counting by the most common raw spelling misses reports.
    spell = q(con, f"""
        WITH s AS (
            SELECT ingredient, UPPER(TRIM(drugname)) AS spelling, COUNT(DISTINCT primaryid) AS reports
            FROM drug_clean WHERE role_cod = 'PS' AND ingredient IN ({in_list})
            GROUP BY ingredient, spelling
        ), r AS (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY ingredient ORDER BY reports DESC) AS rn,
                   COUNT(*) OVER (PARTITION BY ingredient) AS spellings
            FROM s
        )
        SELECT ingredient, spelling AS top_spelling, reports AS reports_top_spelling, spellings
        FROM r WHERE rn = 1""")
    under = top.merge(spell, on="ingredient")
    under["reports_missed"] = under["reports"] - under["reports_top_spelling"]
    under["pct_missed"] = (100 * under["reports_missed"] / under["reports"]).round(1)

    top5 = top_list[:5]
    reac_frames = []
    for ing in top5:
        safe = ing.replace("'", "''")
        df = q(con, f"""
            WITH rep AS (SELECT DISTINCT primaryid FROM drug_clean
                         WHERE role_cod = 'PS' AND ingredient = '{safe}')
            SELECT r.pt AS reaction, COUNT(DISTINCT r.primaryid) AS reports
            FROM reac_clean r JOIN rep USING (primaryid)
            GROUP BY r.pt ORDER BY reports DESC LIMIT 10""")
        total = int(top.loc[top["ingredient"] == ing, "reports"].iloc[0])
        df["pct_of_drug_reports"] = (100 * df["reports"] / total).round(1)
        df.insert(0, "ingredient", ing)
        reac_frames.append(df)
    reactions = pd.concat(reac_frames) if reac_frames else pd.DataFrame()

    outcomes = q(con, f"""
        WITH rep AS (SELECT DISTINCT ingredient, primaryid FROM drug_clean
                     WHERE role_cod = 'PS' AND ingredient IN ({in_list})),
        o AS (SELECT primaryid,
                     MAX(outc_cod = 'DE') AS death,
                     MAX(outc_cod = 'HO') AS hosp,
                     MAX(outc_cod = 'LT') AS life_threat,
                     1 AS any_serious
              FROM outc_clean GROUP BY primaryid)
        SELECT rep.ingredient,
               COUNT(*) AS reports,
               ROUND(100.0 * SUM(COALESCE(o.death, 0)) / COUNT(*), 1)       AS pct_death,
               ROUND(100.0 * SUM(COALESCE(o.hosp, 0)) / COUNT(*), 1)        AS pct_hospitalization,
               ROUND(100.0 * SUM(COALESCE(o.life_threat, 0)) / COUNT(*), 1) AS pct_life_threatening,
               ROUND(100.0 * SUM(COALESCE(o.any_serious, 0)) / COUNT(*), 1) AS pct_any_serious
        FROM rep LEFT JOIN o USING (primaryid)
        GROUP BY rep.ingredient ORDER BY reports DESC""")

    demo = q(con, """
        SELECT COALESCE(sex, 'Unknown') AS sex, age_group, COUNT(*) AS reports
        FROM demo_clean GROUP BY 1, 2""")
    reporters = q(con, """
        SELECT COALESCE(occp_cod, 'Unknown') AS code, COUNT(*) AS reports
        FROM demo_clean GROUP BY 1 ORDER BY reports DESC""")
    reporters["reporter"] = reporters["code"].map(REPORTER_LABELS).fillna(reporters["code"])
    countries = q(con, """
        SELECT COALESCE(reporter_country, 'Unknown') AS country, COUNT(*) AS reports
        FROM demo_clean GROUP BY 1 ORDER BY reports DESC LIMIT 10""")

    # Tidy CSVs for Tableau / Power BI.
    top.to_csv(TABLEAU_DIR / "top_suspect_drugs.csv", index=False)
    under.to_csv(TABLEAU_DIR / "undercount_without_normalization.csv", index=False)
    reactions.to_csv(TABLEAU_DIR / "top_reactions_top5_drugs.csv", index=False)
    outcomes.to_csv(TABLEAU_DIR / "serious_outcomes_top_drugs.csv", index=False)
    demo.to_csv(TABLEAU_DIR / "reports_by_sex_age.csv", index=False)
    reporters.to_csv(TABLEAU_DIR / "reports_by_reporter_type.csv", index=False)
    countries.to_csv(TABLEAU_DIR / "reports_by_country.csv", index=False)
    q(con, """
        SELECT d.primaryid, d.ingredient, d.drugname AS raw_drug_name, d.norm_method,
               m.sex, m.age_years, m.age_group, m.weight_kg, m.reporter_country, m.occp_cod,
               m.fda_dt
        FROM drug_clean d JOIN demo_clean m USING (primaryid)
        WHERE d.role_cod = 'PS'""").to_csv(TABLEAU_DIR / "suspect_drug_reports_fact.csv", index=False)

    rec = lambda df: df.to_dict(orient="records")
    return {
        "top_drugs": rec(top),
        "undercount": rec(under),
        "reactions": rec(reactions),
        "outcomes": rec(outcomes),
        "demographics": rec(demo),
        "reporters": rec(reporters),
        "countries": rec(countries),
    }
