-- 04_watchlist.sql
-- Latest quarter: banks showing early-warning signs.
--   * Noncurrent loans more than 2x the peer median (asset quality)
--   * Negative return on assets (losing money)
--   * Tier 1 leverage ratio below 5% (below the "well capitalized" threshold)
WITH latest AS (
    SELECT * FROM bank_vs_peer
    WHERE report_date = (SELECT MAX(report_date) FROM bank_vs_peer)
)
SELECT
    bank_name, state, peer_group, ROUND(assets_bn, 2) AS assets_bn,
    roa, nclnlsr AS noncurrent_loans_pct, peer_noncurrent_loans, rbc1aaj AS leverage_ratio,
    (CASE WHEN nclnlsr > 2 * peer_noncurrent_loans THEN 1 ELSE 0 END)
  + (CASE WHEN roa < 0 THEN 1 ELSE 0 END)
  + (CASE WHEN rbc1aaj < 5 THEN 1 ELSE 0 END)                        AS flags,
    concat_ws('; ',
        CASE WHEN nclnlsr > 2 * peer_noncurrent_loans THEN 'Noncurrent loans >2x peers' END,
        CASE WHEN roa < 0 THEN 'Negative ROA' END,
        CASE WHEN rbc1aaj < 5 THEN 'Leverage ratio <5%' END)          AS reasons
FROM latest
WHERE nclnlsr > 2 * peer_noncurrent_loans OR roa < 0 OR rbc1aaj < 5
ORDER BY flags DESC, assets_bn DESC;
