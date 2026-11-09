-- Duplication: FAERS keeps every follow-up version of a case as a separate report.
-- Counting all rows double-counts cases. FDA guidance: keep the latest version per caseid.
SELECT
    COUNT(*)                              AS report_rows,
    COUNT(DISTINCT caseid)                AS unique_cases,
    COUNT(*) - COUNT(DISTINCT caseid)     AS superseded_versions,
    ROUND(100.0 * (COUNT(*) - COUNT(DISTINCT caseid)) / COUNT(*), 2) AS pct_duplicate_rows
FROM {demo};
