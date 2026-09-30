-- 02_peer_medians.sql
-- Peer-group medians every quarter: the benchmark each bank is compared against.
CREATE OR REPLACE TABLE peer_medians AS
SELECT
    report_date,
    peer_group,
    COUNT(*)                      AS banks,
    ROUND(SUM(assets_bn), 1)      AS total_assets_bn,
    ROUND(MEDIAN(roa), 3)         AS roa,
    ROUND(MEDIAN(roe), 3)         AS roe,
    ROUND(MEDIAN(nimy), 3)        AS nim,
    ROUND(MEDIAN(nclnlsr), 3)     AS noncurrent_loans,
    ROUND(MEDIAN(eeffr), 2)       AS efficiency_ratio,
    ROUND(MEDIAN(rbc1aaj), 2)     AS leverage_ratio
FROM bank_quarters
GROUP BY report_date, peer_group
ORDER BY report_date, peer_group;
