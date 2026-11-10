# FinSight AI — Session Notes

> Read this at the start of each session to get up to speed instantly.

---

## What this project is

A local financial research assistant that answers questions about public companies using their SEC 10-K filings. No paid APIs — everything runs locally.

**Stack:** Python, SQLite, BeautifulSoup, Sentence Transformers, FAISS, BM25, Ollama (local LLM), Streamlit  
**Blueprint:** `finsight_ai_blueprint.md` — full 6-week roadmap  
**Venv:** `.venv/` in project root → Python 3.14; use `.venv/bin/python`  
**Hardware:** MacBook M5 Pro, 48 GB unified memory — can run 27B+ Ollama models comfortably

---

## Current state: Week 2 complete, Phases 0–2 done → next is Phase 3 (retrieval)

### Roadmap (agreed 2026-11-10)

- [x] **Phase 0 — Stabilize:** tests fixed, requirements pinned, email moved to `.env`, clutter removed, venv rebuilt on Python 3.14
- [x] **Phase 1 — Claude Code setup:** `CLAUDE.md`, `.claude/settings.json`, `/session-wrap` skill
- [x] **Phase 2 — Finish Week 1 gap:** 30 verified questions across all 3 companies, retrieval questions labelled with `expected_chunks`; fixed two fact-table bugs found along the way (see Week 2 → "Fact table fixes")
- [ ] **Phase 3 — Week 3 retrieval baseline:** install retrieval packages → `bm25_retriever.py` → `vector_retriever.py` (MiniLM, model name in `configs/retrieval.yaml`) → `build_index.py` → recall@5/@10 eval for both → retriever unit tests
- [ ] **Phase 4 — Stretch (optional):** compare `bge-small`/`bge-base` vs MiniLM; prototype hybrid (RRF); table-aware chunking if numeric retrieval is weak
- Later (blueprint): Week 4 reranker + Ollama + calculations + citations · Week 5 eval & failure analysis · Week 6 Streamlit, docs, demo

### Week 1 — Data Acquisition ✅

**Script:** `scripts/ingest_filings.py`

- Downloads 3 most-recent 10-K filings per company (MSFT, AAPL, NVDA) = 9 total
- Resolves tickers → CIK via SEC's `company_tickers.json`
- Saves raw HTML to `data/raw/sec/{company}/10-k/{accession}.html`
- Saves provenance manifest to `data/manifests/{accession}.json`
- Fully idempotent (skips cached files)

**Downloaded filings:**

| Ticker | FY   | Filed      | Period End | File Size |
|--------|------|------------|------------|-----------|
| MSFT   | 2026 | 2026-07-29 | 2026-06-30 | 8.2 MB    |
| MSFT   | 2025 | 2025-07-30 | 2025-06-30 | 7.8 MB    |
| MSFT   | 2024 | 2024-07-30 | 2024-06-30 | 6.5 MB    |
| AAPL   | 2026 | 2026-11-03 | 2026-09-26 | 1.6 MB    |
| AAPL   | 2025 | 2025-10-31 | 2025-09-27 | 1.4 MB    |
| AAPL   | 2024 | 2024-11-01 | 2024-09-28 | 1.4 MB    |
| NVDA   | 2026 | 2026-02-25 | 2026-01-25 | 1.9 MB    |
| NVDA   | 2025 | 2025-02-26 | 2025-01-26 | 2.0 MB    |
| NVDA   | 2024 | 2024-02-21 | 2024-01-28 | 2.0 MB    |

---

### Week 2 — Parsing & Database ✅

**Runner:** `scripts/extract_tables.py`  
**Database:** `data/finsight.db` (SQLite, ~3 MB)  
**Result:** 706 text chunks + 140 unique financial facts in the DB (252 extracted; each 10-K restates prior years, so the UNIQUE constraint dedupes them)

#### Fact table fixes (2026-11-10)

- **`fiscal_year` now labels the period, not the filing.** Previously FY2022 facts from the FY2024 10-K were tagged `fiscal_year=2024`, so year joins in `queries.sql` mixed periods. Now `fiscal_year = period_end[:4]` (works for MSFT/AAPL/NVDA; revisit for early-January fiscal year-ends).
- **Newest filing wins on conflict** (`ON CONFLICT ... WHERE excluded.filing_date > ...`). Later 10-Ks restate prior years; NVDA's June 2024 10:1 split restated FY2024 diluted EPS from $11.93 → $1.19. Only NVDA EPS FY2023/24 changed.
- Regression tests: `tests/test_data_quality.py`.

#### Known data gaps

- **No balance-sheet facts.** Total Assets, Cash, Long-term Debt, and Equity are instant (point-in-time) contexts, which the extractor skips. Needs instant-context support to answer leverage/liquidity questions.
- Cost of Revenue only for NVDA; D&A missing for MSFT (different XBRL tags; AAPL/MSFT Cost of Revenue derivable as Revenue − Gross Profit).
- NVDA FY2022 EPS ($3.85) is pre-split — no later filing in the dataset restates it.
- Financial statement notes (e.g. the split announcement, segment notes) aren't chunked; only Items 1, 1A, 1C, 7, 7A.

#### Parsing modules in `src/finsight/parsing/`

**`section_extractor.py`**
- Extracts Items 1, 1A, 1C, 7, 7A from raw HTML
- Handles two filing formats:
  - NVDA/AAPL: `<div>` headers directly in `<body>`
  - MSFT: `<p>` headers nested inside `<div>` wrappers
- Anchors sibling traversal at the body-level container for each header
- Deduplicates section IDs (Table of Contents anchors appear before the real header — keeps the last occurrence)

**`xbrl_extractor.py`**
- Reads inline XBRL tags embedded in the HTML
- Builds a context map from `xbrli:context` elements (period start/end dates)
- Keeps only annual contexts (340–380 day windows); skips quarterly, instant, and **dimensioned** contexts
- Key fix: MSFT tags revenue multiple times — once per business segment (dimensioned) and once as consolidated total. The extractor now skips any context with `xbrli:segment` or `xbrldi:explicitmember` to get consolidated figures only.
- Each filing reports 2–3 years of comparative data → multiple rows per filing, distinguished by `period_start`/`period_end`
- Tracks 16 GAAP concepts: Revenue, Gross Profit, Cost of Revenue, Operating Income, Net Income, R&D, SG&A, EPS Basic, EPS Diluted, Total Assets, Cash, Long-term Debt, Stockholders Equity, CapEx, D&A, Revenue (alt tag)

**Verified revenue figures (all correct after fix):**

| Company | Period | Revenue (USD_millions) |
|---------|--------|----------------------|
| MSFT    | FY2026 (Jul 2025–Jun 2026) | $331,839M |
| MSFT    | FY2025 (Jul 2024–Jun 2025) | $281,724M |
| MSFT    | FY2024 (Jul 2023–Jun 2024) | $245,122M |
| AAPL    | FY2026 (Oct 2025–Sep 2026) | $478,834M |
| AAPL    | FY2025 (Oct 2024–Sep 2025) | $416,161M |
| AAPL    | FY2024 (Oct 2023–Sep 2024) | $391,035M |
| NVDA    | FY2026 (Jan 2025–Jan 2026) | $215,938M |
| NVDA    | FY2025 (Jan 2024–Jan 2025) | $130,497M |
| NVDA    | FY2024 (Jan 2023–Jan 2024) | $60,922M  |

**`chunker.py`**
- 400-word windows, 80-word overlap
- Each chunk carries: company, ticker, CIK, fiscal_year, filing_date, report_period, form_type, accession_number, source_url, section_id, section_title, chunk_idx

#### Database schema (`sql/schema.sql`)

```
financial_facts   — XBRL structured facts
  UNIQUE (concept, cik, period_start, period_end)

filing_chunks     — text chunks for retrieval
  UNIQUE (accession_number, section_id, chunk_idx)
  embedding BLOB  — empty until build_index.py runs (Week 3)
```

Pre-written analytical queries are in `sql/queries.sql`.

#### Seed evaluation questions ✅

30 verified questions in `data/evaluation/seed_questions.json` (NVDA 13, MSFT 9, AAPL 6, cross-company 2):
- SQL-answerable numerical/comparative/multi-step questions, all computed from the DB
- Narrative questions verified against chunk text; each has `expected_chunks` (`accession|section_id|chunk_idx`, stable across rebuilds) — retrieval ground truth for recall@k
- Built-in traps: same question for MSFT FY2024 vs FY2026 Azure (tests year filtering); NVDA EPS across the stock split; differing fiscal year-ends in cross-company comparisons
- 2 unanswerable (NVDA FY2027 forecast; Apple iPhone unit sales — not disclosed)

---

## What's next: Week 3 — Retrieval System

### Files to build

**`src/finsight/retrieval/bm25_retriever.py`**
- BM25 keyword search over all 706 chunks
- Accepts optional filters: ticker, fiscal_year, section_id
- Uses `rank_bm25` package
- Saves/loads index as a pickle file at `data/index/bm25.pkl`

**`src/finsight/retrieval/vector_retriever.py`**
- Dense vector search using Sentence Transformers (`all-MiniLM-L6-v2`)
- FAISS flat index (IndexFlatIP with normalised vectors = cosine similarity)
- Same company/year/section filters as BM25
- Saves/loads index from `data/index/faiss.index` + `data/index/chunk_ids.pkl`

**`scripts/build_index.py`**
- Loads all 706 chunks from SQLite
- Embeds them with Sentence Transformers (CPU, ~1 min on M5 Pro)
- Builds and saves FAISS index to `data/index/`
- Saves BM25 corpus pickle
- Writes embedding blobs back to `filing_chunks.embedding` column in SQLite

### Packages still to install (for Week 3)

```bash
.venv/bin/python -m pip install sentence-transformers faiss-cpu rank_bm25
```

> Venv: recreated 2026-11-10 on Python 3.14.6 (from `/opt/anaconda3/bin/python3`). Install with `.venv/bin/python -m pip install -r requirements.txt`.

---

## Packages installed in .venv

Pinned in `requirements.txt`: requests, python-dotenv, beautifulsoup4, lxml, pytest.

## Environment

`ingest_filings.py` reads `SEC_EMAIL` from `.env` (gitignored). Copy `.env.example` to `.env` and fill it in.

---

## How to re-run everything from scratch

```bash
cd "/Users/sardahal/Desktop/Personal Project/FinSight AI"
source .venv/bin/activate    # or .venv/bin/python3 directly

# Re-ingest (skips cached files)
python scripts/ingest_filings.py

# Re-extract (drops and recreates DB)
rm -f data/finsight.db
python scripts/extract_tables.py

# Run tests
python -m pytest tests/ -v
```

---

## Tests

`tests/test_ingestion_simple.py` (6 smoke tests) + `tests/test_data_quality.py` (6 data regression tests) — 12 passing. Smoke tests check:
- Scripts and parsing modules exist
- SQL files exist
- 9 manifests exist
- DB has chunks and facts

Run with: `.venv/bin/python3 -m pytest tests/ -v`
