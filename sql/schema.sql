-- FinSight AI — SQLite schema
-- Run once: sqlite3 data/finsight.db < sql/schema.sql

-- Structured financial facts extracted from inline XBRL tags
CREATE TABLE IF NOT EXISTS financial_facts (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    company          TEXT    NOT NULL,
    ticker           TEXT    NOT NULL,
    cik              TEXT    NOT NULL,
    concept          TEXT    NOT NULL,   -- e.g. us-gaap:Revenues
    metric_label     TEXT    NOT NULL,   -- e.g. Revenue
    value            REAL    NOT NULL,
    unit             TEXT    NOT NULL,   -- USD_millions / USD_thousands / USD_per_share
    period_start     TEXT    NOT NULL,   -- ISO date
    period_end       TEXT    NOT NULL,   -- ISO date
    fiscal_year      TEXT    NOT NULL,
    filing_date      TEXT    NOT NULL,
    form_type        TEXT    NOT NULL,
    accession_number TEXT    NOT NULL,
    source_url       TEXT,
    UNIQUE (concept, cik, period_start, period_end)
);

-- Text chunks for BM25 and vector retrieval
CREATE TABLE IF NOT EXISTS filing_chunks (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    company          TEXT NOT NULL,
    ticker           TEXT NOT NULL,
    cik              TEXT NOT NULL,
    fiscal_year      TEXT NOT NULL,
    filing_date      TEXT NOT NULL,
    report_period    TEXT NOT NULL,
    form_type        TEXT NOT NULL,
    accession_number TEXT NOT NULL,
    source_url       TEXT,
    section_id       TEXT NOT NULL,     -- e.g. "1", "7", "1A"
    section_title    TEXT NOT NULL,
    chunk_idx        INTEGER NOT NULL,
    text             TEXT NOT NULL,
    embedding        BLOB,              -- stored after build_index.py runs
    UNIQUE (accession_number, section_id, chunk_idx)
);

CREATE INDEX IF NOT EXISTS idx_facts_ticker_year  ON financial_facts (ticker, fiscal_year);
CREATE INDEX IF NOT EXISTS idx_facts_concept       ON financial_facts (concept);
CREATE INDEX IF NOT EXISTS idx_chunks_ticker_year  ON filing_chunks   (ticker, fiscal_year);
CREATE INDEX IF NOT EXISTS idx_chunks_section      ON filing_chunks   (section_id);
