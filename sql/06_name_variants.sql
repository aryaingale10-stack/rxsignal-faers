-- Consistency: how many different raw spellings map to the same ingredient.
-- Run after normalization (needs drug_clean.ingredient).
SELECT
    ingredient,
    COUNT(DISTINCT UPPER(TRIM(drugname))) AS raw_spellings,
    COUNT(*)                              AS drug_rows
FROM drug_clean
WHERE ingredient IS NOT NULL
GROUP BY ingredient
ORDER BY drug_rows DESC
LIMIT 50;
