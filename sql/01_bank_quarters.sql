-- 01_bank_quarters.sql
-- One clean row per bank per quarter, with a size-based peer group.
CREATE OR REPLACE TABLE bank_quarters AS
SELECT
    f.cert                                                 AS cert,
    COALESCE(i.name, 'CERT ' || CAST(f.cert AS VARCHAR))   AS bank_name,
    i.city                                                 AS city,
    i.stalp                                                AS state,
    i.active                                               AS active,
    CAST(strptime(CAST(f.repdte AS VARCHAR), '%Y%m%d') AS DATE) AS report_date,
    f.asset / 1e6                                          AS assets_bn,
    f.dep   / 1e6                                          AS deposits_bn,
    f.roa     AS roa,        -- return on assets %
    f.roe     AS roe,        -- return on equity %
    f.nimy    AS nimy,       -- net interest margin %
    f.nclnlsr AS nclnlsr,    -- noncurrent loans / total loans %
    f.eeffr   AS eeffr,      -- efficiency ratio % (lower is better)
    f.rbc1aaj AS rbc1aaj,    -- tier 1 leverage ratio %
    CASE WHEN f.asset < 10000000  THEN '1: $1-10B Community/Regional'
         WHEN f.asset < 100000000 THEN '2: $10-100B Regional'
         ELSE '3: $100B+ Large' END                        AS peer_group
FROM fin f
LEFT JOIN inst i ON f.cert = i.cert;
