# FinSight AI — Session Notes

> Read this at the start of each session to get up to speed instantly.

---

## What this project is

A local financial research assistant that answers questions about public companies using their SEC 10-K filings. No paid APIs — everything runs locally.

**Stack:** Python, SQLite, BeautifulSoup, Sentence Transformers, FAISS, BM25, Ollama (local LLM), Streamlit  
**Blueprint:** `finsight_ai_blueprint.md` — full 6-week roadmap  
**Environment:** uv (`pyproject.toml` + `uv.lock`), Python 3.14 in `.venv/`; run things with `uv run ...`  
**Hardware:** MacBook M5 Pro, 48 GB unified memory — can run 27B+ Ollama models comfortably

---

## Current state: Week 3 baseline done (Phases 0–3) → next is Phase 4 / Week 4

### Roadmap (agreed 2026-11-10)

- [x] **Phase 0 — Stabilize:** tests fixed, requirements pinned, email moved to `.env`, clutter removed, venv rebuilt on Python 3.14
- [x] **Phase 1 — Claude Code setup:** `CLAUDE.md`, `.claude/settings.json`, `/session-wrap` skill; migrated to uv (`pyproject.toml` + `uv.lock`)
- [x] **Phase 2 — Finish Week 1 gap:** 30 verified questions across all 3 companies, retrieval questions labelled with `expected_chunks`; fixed two fact-table bugs found along the way (see Week 2 → "Fact table fixes")
- [x] **Phase 3 — Week 3 retrieval baseline:** install retrieval packages → `bm25_retriever.py` → `vector_retriever.py` (MiniLM, model name in `configs/retrieval.yaml`) → `build_index.py` → recall@5/@10 eval for both → retriever unit tests
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

### Week 3 — Retrieval baseline ✅ (Phase 3)

**Modules in `src/finsight/retrieval/`** (settings in `configs/retrieval.yaml`):
- `common.py` — config, `Chunk` (key `accession|section_id|chunk_idx`), metadata filters (value or list), tokenizer
- `bm25_retriever.py` — `BM25Retriever().search(q, k, ticker=, fiscal_year=, section_id=)`. Built in memory from SQLite (ms), so no pickle to go stale
- `vector_retriever.py` — `VectorRetriever()` same API; MiniLM embeddings, FAISS `IndexFlatIP`, refuses to load if index model ≠ config model
- Every chunk is indexed with a header line ("NVIDIA CORP (NVDA) fiscal year 2026 10-K, Risk Factors.") because filing text rarely names the company

**Scripts:** `scripts/build_index.py` (8 s: writes `data/index/` + `filing_chunks.embedding`), `scripts/eval_retrieval.py [--details]`

**Baseline** — 16 labelled questions; hit@k = an expected chunk is in the top k:

| Retriever | Mode | hit@1 | hit@3 | hit@5 | hit@10 | MRR |
|---|---|---|---|---|---|---|
| BM25 | unfiltered | 0.12 | 0.12 | 0.50 | 0.94 | 0.27 |
| BM25 | filtered (ticker+year) | 0.31 | 0.69 | **0.94** | 0.94 | 0.51 |
| Vector (MiniLM) | unfiltered | 0.19 | 0.44 | 0.56 | 0.69 | 0.33 |
| Vector (MiniLM) | filtered | 0.44 | 0.62 | 0.62 | 0.75 | 0.53 |

**What we learned**
- **Filters matter most.** Unfiltered search often returns the same passage from another year's 10-K. Week 4's query parser must extract ticker + fiscal year.
- **MiniLM truncation is the vector retriever's main failure.** It reads 256 tokens; chunks are ~470–550 tokens. All 5 NVDA vector misses have the answer past token 256 → Phase 4: a 512-token model (bge-small/base) and/or smaller chunks.
- hit@1 is harsh: chunks ranked above the expected one are usually overlapping neighbours from the same section.
- sq_028 (NVDA headcount) fails everywhere: "employees" appears all over the risk factors.
- Gotchas fixed: tokenizer kept possessives ("microsoft's" ≠ "microsoft"); **`torch` must be imported before `faiss`** on macOS or `encode()` segfaults (exit 139).

---

## What's next: Phase 4 (optional stretch) → Week 4

1. Fix truncation: try `BAAI/bge-small-en-v1.5` (512 tokens) and/or ~200-word chunks; compare with `eval_retrieval.py`
2. Hybrid search (reciprocal rank fusion of BM25 + vector)
3. Week 4: query parser (ticker/year), reranker, Ollama LLM, calculation tools, citations

## Dependencies

Managed by uv (migrated 2026-11-10): dependencies in `pyproject.toml`, exact versions in `uv.lock`. `uv sync` installs; `uv add <pkg>` adds. `finsight` is installed editable, so no PYTHONPATH needed.

## Environment

`ingest_filings.py` reads `SEC_EMAIL` from `.env` (gitignored). Copy `.env.example` to `.env` and fill it in.

---

## How to re-run everything from scratch

```bash
cd "/Users/sardahal/Desktop/Personal Project/FinSight AI"
uv sync

# Re-ingest (skips cached files)
uv run scripts/ingest_filings.py

# Re-extract (drops and recreates DB)
rm -f data/finsight.db
uv run scripts/extract_tables.py

# Rebuild retrieval index, then score it
uv run scripts/build_index.py
uv run scripts/eval_retrieval.py --details

# Run tests
uv run pytest
```

---

## Tests

23 passing (`uv run pytest`):
- `test_ingestion_simple.py` — 6 smoke tests (files, manifests, DB populated)
- `test_data_quality.py` — 6 data tests (one fact per year, restated EPS, known revenues, eval-set labels exist in DB)
- `test_retrieval.py` — 11 retriever tests (tokenizer, filters, ordering, known answers, index ↔ DB alignment); vector tests skip if the index isn't built
