-- 03_bank_vs_peer.sql
-- Every bank vs its peer median, with a rank within its peer group each quarter.
CREATE OR REPLACE TABLE bank_vs_peer AS
SELECT
    b.*,
    ROUND(b.roa     - p.roa, 3)               AS roa_vs_peer,
    ROUND(b.nimy    - p.nim, 3)               AS nim_vs_peer,
    ROUND(b.nclnlsr - p.noncurrent_loans, 3)  AS noncurrent_vs_peer,
    ROUND(b.eeffr   - p.efficiency_ratio, 2)  AS efficiency_vs_peer,
    p.noncurrent_loans                        AS peer_noncurrent_loans,
    RANK() OVER (PARTITION BY b.report_date, b.peer_group ORDER BY b.roa DESC NULLS LAST) AS roa_rank_in_peer
FROM bank_quarters b
JOIN peer_medians p USING (report_date, peer_group);
