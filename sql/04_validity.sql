-- Validity: values that are present but impossible.
-- Age is converted to years from its unit code; weight to kg.
WITH conv AS (
    SELECT
        CASE age_cod
            WHEN 'YR'  THEN CAST(age AS REAL)
            WHEN 'DEC' THEN CAST(age AS REAL) * 10
            WHEN 'MON' THEN CAST(age AS REAL) / 12
            WHEN 'WK'  THEN CAST(age AS REAL) / 52.18
            WHEN 'DY'  THEN CAST(age AS REAL) / 365.25
            WHEN 'HR'  THEN CAST(age AS REAL) / 8766
        END AS age_years,
        age, age_cod,
        CASE UPPER(wt_cod)
            WHEN 'KG'  THEN CAST(wt AS REAL)
            WHEN 'LBS' THEN CAST(wt AS REAL) * 0.4536
        END AS weight_kg,
        wt, event_dt, fda_dt
    FROM {demo}
)
SELECT
    SUM(age IS NOT NULL)                                                     AS ages_reported,
    SUM(age IS NOT NULL AND (age_years IS NULL OR age_years < 0 OR age_years > 120)) AS invalid_ages,
    SUM(wt IS NOT NULL)                                                      AS weights_reported,
    SUM(wt IS NOT NULL AND (weight_kg IS NULL OR weight_kg < 0.2 OR weight_kg > 400)) AS invalid_weights,
    SUM(event_dt IS NOT NULL)                                                AS event_dates_reported,
    SUM(event_dt IS NOT NULL AND (
          LENGTH(event_dt) NOT IN (4, 6, 8)
       OR SUBSTR(event_dt, 1, 4) < '1900'
       OR (fda_dt IS NOT NULL AND SUBSTR(event_dt || '0101', 1, 8) > fda_dt)
    ))                                                                       AS invalid_event_dates
FROM conv;
