"""Step 3a: build cleaned tables.

  * De-duplicate: keep only the latest version of each case (FDA's recommended rule:
    highest fda_dt, then highest primaryid, per caseid).
  * Validity: convert age to years and weight to kg; impossible values become NULL
    (so they are counted as missing instead of silently skewing averages).
  * Keep drug / reaction / outcome rows only for the surviving reports.
"""
import sqlite3

DEDUP_SQL = """
DROP TABLE IF EXISTS demo_clean;
CREATE TABLE demo_clean AS
WITH ranked AS (
    SELECT d.*,
           ROW_NUMBER() OVER (
               PARTITION BY caseid
               ORDER BY fda_dt DESC, CAST(primaryid AS INTEGER) DESC
           ) AS rn
    FROM demo_raw d
),
latest AS (SELECT * FROM ranked WHERE rn = 1),
conv AS (
    SELECT latest.*,
        CASE age_cod
            WHEN 'YR'  THEN CAST(age AS REAL)
            WHEN 'DEC' THEN CAST(age AS REAL) * 10
            WHEN 'MON' THEN CAST(age AS REAL) / 12
            WHEN 'WK'  THEN CAST(age AS REAL) / 52.18
            WHEN 'DY'  THEN CAST(age AS REAL) / 365.25
            WHEN 'HR'  THEN CAST(age AS REAL) / 8766
        END AS age_years_raw,
        CASE UPPER(wt_cod)
            WHEN 'KG'  THEN CAST(wt AS REAL)
            WHEN 'LBS' THEN CAST(wt AS REAL) * 0.4536
        END AS weight_kg_raw
    FROM latest
),
flags AS (
    SELECT conv.*,
        (age_years_raw BETWEEN 0 AND 120) AS age_ok,
        (weight_kg_raw BETWEEN 0.2 AND 400) AS wt_ok,
        (event_dt IS NOT NULL
         AND LENGTH(event_dt) IN (4, 6, 8)
         AND SUBSTR(event_dt, 1, 4) >= '1900'
         AND (fda_dt IS NULL OR SUBSTR(event_dt || '0101', 1, 8) <= fda_dt)) AS evt_ok
    FROM conv
)
SELECT
    primaryid, caseid, caseversion, fda_dt, init_fda_dt, rept_cod, occp_cod,
    reporter_country, occr_country,
    CASE WHEN sex IN ('F', 'M') THEN sex END              AS sex,
    CASE WHEN age_ok THEN age END                          AS age,
    CASE WHEN age_ok THEN age_cod END                      AS age_cod,
    CASE WHEN age_ok THEN ROUND(age_years_raw, 1) END      AS age_years,
    CASE WHEN wt_ok THEN wt END                            AS wt,
    CASE WHEN wt_ok THEN wt_cod END                        AS wt_cod,
    CASE WHEN wt_ok THEN ROUND(weight_kg_raw, 1) END       AS weight_kg,
    CASE WHEN evt_ok THEN event_dt END                     AS event_dt,
    CASE
        WHEN NOT age_ok OR age_ok IS NULL THEN 'Unknown'
        WHEN age_years_raw < 18 THEN '0-17'
        WHEN age_years_raw < 45 THEN '18-44'
        WHEN age_years_raw < 65 THEN '45-64'
        WHEN age_years_raw < 75 THEN '65-74'
        ELSE '75+'
    END AS age_group
FROM flags;
CREATE INDEX ix_demo_clean_pid ON demo_clean(primaryid);

DROP TABLE IF EXISTS drug_clean;
CREATE TABLE drug_clean AS
SELECT dr.* FROM drug_raw dr JOIN demo_clean dc ON dr.primaryid = dc.primaryid;
CREATE INDEX ix_drug_clean_pid ON drug_clean(primaryid);

DROP TABLE IF EXISTS reac_clean;
CREATE TABLE reac_clean AS
SELECT DISTINCT r.primaryid, r.pt FROM reac_raw r JOIN demo_clean dc ON r.primaryid = dc.primaryid;
CREATE INDEX ix_reac_clean_pid ON reac_clean(primaryid);

DROP TABLE IF EXISTS outc_clean;
CREATE TABLE outc_clean AS
SELECT DISTINCT o.primaryid, o.outc_cod FROM outc_raw o JOIN demo_clean dc ON o.primaryid = dc.primaryid;
"""


def build_clean_tables(con: sqlite3.Connection) -> None:
    con.executescript(DEDUP_SQL)
    con.commit()
