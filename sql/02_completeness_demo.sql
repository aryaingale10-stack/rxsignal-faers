-- Completeness: share of reports where each key patient/report field is filled in.
-- 'UNK' / 'NS' (not specified) sex codes count as missing.
SELECT
    COUNT(*) AS reports,
    ROUND(100.0 * SUM(age IS NOT NULL AND age_cod IS NOT NULL) / COUNT(*), 2)  AS pct_age,
    ROUND(100.0 * SUM(sex IN ('F', 'M')) / COUNT(*), 2)                        AS pct_sex,
    ROUND(100.0 * SUM(wt IS NOT NULL AND wt_cod IS NOT NULL) / COUNT(*), 2)    AS pct_weight,
    ROUND(100.0 * SUM(event_dt IS NOT NULL) / COUNT(*), 2)                     AS pct_event_date,
    ROUND(100.0 * SUM(reporter_country IS NOT NULL) / COUNT(*), 2)             AS pct_reporter_country,
    ROUND(100.0 * SUM(occp_cod IS NOT NULL) / COUNT(*), 2)                     AS pct_reporter_type
FROM {demo};
