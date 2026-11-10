-- FinSight AI — common analytical queries

-- Revenue for all companies across years
SELECT ticker, fiscal_year, metric_label, value, unit
FROM financial_facts
WHERE metric_label = 'Revenue'
ORDER BY ticker, fiscal_year;

-- Year-over-year revenue change for a specific company
SELECT
    a.ticker,
    a.fiscal_year AS year,
    a.value       AS revenue,
    b.value       AS prev_revenue,
    ROUND((a.value - b.value) / b.value * 100, 1) AS pct_change
FROM financial_facts a
JOIN financial_facts b
    ON a.ticker = b.ticker
    AND a.concept = b.concept
    AND CAST(a.fiscal_year AS INTEGER) = CAST(b.fiscal_year AS INTEGER) + 1
WHERE a.metric_label = 'Revenue'
ORDER BY a.ticker, a.fiscal_year;

-- Operating margin by company and year
SELECT
    r.ticker,
    r.fiscal_year,
    r.value           AS revenue,
    o.value           AS operating_income,
    ROUND(o.value / r.value * 100, 1) AS operating_margin_pct
FROM financial_facts r
JOIN financial_facts o
    ON r.ticker = o.ticker
    AND r.fiscal_year = o.fiscal_year
    AND r.period_start = o.period_start
WHERE r.metric_label = 'Revenue'
  AND o.metric_label = 'Operating Income'
ORDER BY r.ticker, r.fiscal_year;

-- R&D as % of revenue
SELECT
    r.ticker,
    r.fiscal_year,
    rd.value          AS rd_expense,
    r.value           AS revenue,
    ROUND(rd.value / r.value * 100, 1) AS rd_pct
FROM financial_facts r
JOIN financial_facts rd
    ON r.ticker = rd.ticker
    AND r.fiscal_year = rd.fiscal_year
    AND r.period_start = rd.period_start
WHERE r.metric_label  = 'Revenue'
  AND rd.metric_label = 'R&D Expense'
ORDER BY r.ticker, r.fiscal_year;

-- Full metrics table for one company / year
SELECT metric_label, value, unit, period_start, period_end
FROM financial_facts
WHERE ticker = 'NVDA' AND fiscal_year = '2026'
ORDER BY metric_label;

-- Chunk search by company and section
SELECT company, fiscal_year, section_title, chunk_idx, SUBSTR(text, 1, 300) AS preview
FROM filing_chunks
WHERE ticker = 'MSFT' AND section_id = '7'
ORDER BY fiscal_year DESC, chunk_idx
LIMIT 5;
