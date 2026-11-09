-- Completeness of the drug table.
SELECT
    COUNT(*) AS drug_rows,
    ROUND(100.0 * SUM(drugname IS NOT NULL) / COUNT(*), 2)  AS pct_drugname,
    ROUND(100.0 * SUM(prod_ai IS NOT NULL) / COUNT(*), 2)   AS pct_active_ingredient,
    ROUND(100.0 * SUM(route IS NOT NULL AND UPPER(route) NOT IN ('UNKNOWN')) / COUNT(*), 2) AS pct_route,
    ROUND(100.0 * SUM(dose_amt IS NOT NULL) / COUNT(*), 2)  AS pct_dose_amount
FROM {drug};
