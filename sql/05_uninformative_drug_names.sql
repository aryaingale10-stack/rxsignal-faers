-- Drug names that carry no usable information (cannot ever be normalized).
SELECT
    COUNT(*) AS drug_rows,
    SUM(drugname IS NULL
        OR UPPER(TRIM(drugname)) IN ('UNKNOWN', 'UNK', 'UNKNOWN DRUG', 'UNSPECIFIED', 'NOT REPORTED',
                                     'NOT SPECIFIED', 'OTHER', 'OTHERS', 'NONE', 'N/A', 'NA', '-', '?',
                                     'OTHER MEDICATIONS', 'OTHER MEDICATION', 'CONCOMITANT DRUGS',
                                     'CONCOMITANT DRUG')
    ) AS uninformative_rows
FROM {drug};
