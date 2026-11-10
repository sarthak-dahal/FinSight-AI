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

## Current state: Weeks 1–4 done + web app with demo mode → next: Week 5 (harder eval, model comparison) or hosting the demo

### Roadmap (agreed 2026-11-10)

- [x] **Phase 0 — Stabilize:** tests fixed, requirements pinned, email moved to `.env`, clutter removed, venv rebuilt on Python 3.14
- [x] **Phase 1 — Claude Code setup:** `CLAUDE.md`, `.claude/settings.json`, `/session-wrap` skill; migrated to uv (`pyproject.toml` + `uv.lock`)
- [x] **Phase 2 — Finish Week 1 gap:** 30 verified questions across all 3 companies, retrieval questions labelled with `expected_chunks`; fixed two fact-table bugs found along the way (see Week 2 → "Fact table fixes")
- [x] **Phase 3 — Week 3 retrieval baseline:** install retrieval packages → `bm25_retriever.py` → `vector_retriever.py` (MiniLM, model name in `configs/retrieval.yaml`) → `build_index.py` → recall@5/@10 eval for both → retriever unit tests
- [x] **Phase 4 — Better retrieval:** bge-base replaces MiniLM; hybrid RRF retriever; evidence-based labels
- [x] **Week 4 — Assistant:** parser, financial tools, cited answers with Gemma 3, end-to-end eval (28–29/30)
- [x] **Week 6 (UI part, done early):** Streamlit app
- [ ] **Week 5 — Honest evaluation:** ~25 harder questions, model comparison, reranker, failure analysis
- [ ] **Week 6 (rest):** README/architecture docs, demo, merge to main

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

**Scripts:** `scripts/build_index.py` (writes `data/index/<model>/` + `filing_chunks.embedding`; ~80 s for bge-base), `scripts/eval_retrieval.py [--details]`

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

### Phase 4 — Better retrieval ✅

- **Embedding model → `BAAI/bge-base-en-v1.5`** (512 tokens, 768-dim). Indexes now live per model in `data/index/<model-slug>/`; `build_index.py --model X` and `eval_retrieval.py --models A B` compare models side by side. BGE needs a query instruction prefix (handled in `vector_retriever.QUERY_PREFIXES`).
- **`hybrid_retriever.py`** — Reciprocal Rank Fusion of BM25 + vector (k=60, equal weights, 50 candidates each; deliberately untuned).
- **Evidence-based labels.** Questions now store exact `evidence` phrases; `scripts/label_evidence.py` derives `expected_chunks` = every chunk containing them. Fixed 4 under-labelled questions (overlapping chunks and repeated facts held the answer too — sq_028 was never really failing). Rerun after any re-chunking; a test enforces sync.

**Results** (16 labelled questions, corrected labels):

| Retriever | Filtered hit@1 | hit@3 | hit@5 | MRR | Unfiltered hit@3 | Unfiltered hit@5 |
|---|---|---|---|---|---|---|
| BM25 | 0.38 | 0.88 | 1.00 | 0.59 | 0.19 | 0.56 |
| MiniLM | 0.44 | 0.69 | 0.75 | 0.56 | 0.44 | 0.56 |
| bge-small | 0.75 | 0.81 | 0.94 | 0.80 | 0.75 | 0.75 |
| bge-base | **0.69** | 0.88 | 1.00 | **0.79** | 0.75 | 0.88 |
| **Hybrid (BM25 + bge-base)** — default | 0.50 | **1.00** | 1.00 | 0.72 | **0.94** | **1.00** |

**Takeaways**
- Hybrid is the most robust (right passage in top 3 for every question, even unfiltered); bge-base alone ranks the answer *first* more often → a cross-encoder reranker over hybrid's top ~20 should get both (Week 4).
- **The eval set is now saturated and optimistic.** 16 questions, written after reading the passages, so wording overlaps the text. Differences of 0.06 = one question. Before tuning further, add ~25 harder retrieval questions (paraphrased, older years, risk factors, AAPL/MSFT FY2024–25).
- Chunk size (400 words) left unchanged: with 512-token models it fits, and changing it would need re-labelling (now automatic via evidence phrases).

---

### Week 4 — LLM setup ✅ (started 2026-11-10)

- **Model: `gemma3:27b` via Ollama** (Q4_K_M, 17.4 GB; Ollama 0.32.13). Settings in `configs/llm.yaml`; client in `src/finsight/reasoning/llm.py` (`LLMClient().chat(user, system)`).
- `num_ctx: 16384` — Ollama's default context silently truncates; verified a 9.8k-token prompt is read in full. `temperature: 0.1` (model default 1.0).
- Gemma 3 has **no tool-calling** capability → Python orchestrates (parse → SQL/calc → retrieve) and Gemma only writes the cited answer.
- Speed: ~180 prompt tokens/s → expect ~20–30 s per answer at 27B. Use `gemma3:12b` for fast dev loops.
- Also installed for later comparison: `gemma4:26b`, `gpt-oss:20b`, `qwen3.8:27b`, `qwen3-coder:30b`.

### Week 4 — The assistant ✅

Pipeline (`src/finsight/reasoning/`): **parse → compute facts → retrieve → Gemma writes cited answer → validate citations**
- `query_parser.py` — rule-based: tickers, fiscal years (incl. "FY26", "most recent"), metrics (plurals, derived margins); segment phrases like "cloud services revenue" are *not* company revenue
- `financial_tools.py` — every number computed in Python from `financial_facts` with source accession: values, % of revenue, growth, margin changes; prior year added for YoY context; notes for years with no data
- `answerer.py` — prompt with facts `[F#]` + 5 hybrid-retrieved passages `[C#]`; rules: evidence only, no arithmetic, cite everything, `INSUFFICIENT EVIDENCE:` prefix to abstain, valid tags listed explicitly. Parses grouped citations (`[C1, C3]`) and flags tags pointing at nothing
- `scripts/ask.py "question"` — CLI

**Answer evaluation** — `scripts/run_evaluation.py` → `reports/evaluation_report.md` (every answer, for human review). Automatic checks in `src/finsight/evaluation/answer_scoring.py`: key figures stated (unit-aware; `key_figures` per question, `accept` for a filing's own rounding), correct abstention, valid citations, answer passage retrieved & cited.

| Run | Passed | Fixed after |
|---|---|---|
| 1 | 28/30 | "most recent" pulled prior year → wrong year; prompt read "numbers must be in evidence" as facts-only → abstained despite finding 41% |
| 2 | 29/30 | missing abstain marker on partial answers; prior year leaked into passage retrieval (FY2025 passage for FY2026 question) |
| 3 | 29/30 | segment questions got company-total revenue facts; model cited non-existent [C6] → valid tags now listed |
| 4 (final) | 28/30 → **29/30** after grader fix | sq_013 was correct ("32%" is the filing's own rounding); **sq_021 is a known failure** |

Final run: key figures 24/24 (after grader fix), abstention 29/30, valid citations 100%, answer passage retrieved and cited 16/16. ~18 s/question with gemma3:27b.

**Lessons**
- Most failures were noisy or ambiguous *inputs* to the model (extra years, irrelevant facts), not model limits. Fix the context before adding prompt rules.
- Prompt changes shift boundary cases both ways — always re-run the full set, never just the failing question.
- **Known failure sq_021:** Gemma writes "not directly stated" then quotes "Azure and other cloud services revenue grew 41%" in the next sentence. Three prompt angles tried; stopped to avoid overfitting. Check whether other models get it right (Week 5).
- 30 questions written by us are too easy to trust these scores — see Week 5.

### Week 6 (early) — Web app ✅

`uv run streamlit run app/streamlit_app.py` → http://localhost:8501
- Chat interface with example questions; answers with highlighted citations; **Sources cited** (opens the exact passage), **Computed figures** table, **How this was answered** (parse, retrieved passages, model, tokens, time); abstentions shown as warnings
- Sidebar: model picker (anything in `ollama list`), Ollama status with fix-it messages, passages slider, data coverage
- Gotchas handled: `$` escaped (Streamlit renders `$…$` as LaTeX); SQLite connection shared across Streamlit threads (`check_same_thread=False`)
- `tests/test_app.py` — headless AppTest with an injected answer (no LLM); verified a live question end to end

### Demo mode + app polish ✅

- **Demo mode** — `data/demo/answers.json` holds 30 complete pipeline outputs (answer, facts, passage text, parse, model info) plus each answer's evaluation verdict. Built by `scripts/build_demo.py` (~9 min; `--rescore` re-grades without the LLM). Loader in `src/finsight/demo.py`.
  - Turns on automatically when Ollama or the index is unavailable; sidebar toggle; `FINSIGHT_DEMO=1` forces it
  - Question picker filtered by type; each answer shows a pass/fail badge with the reason (honest: 29/30, sq_021 shown as a failure)
  - **Never imports torch/faiss/sentence-transformers** (enforced by a fresh-process test) → can be hosted on free tiers
- **App polish (developing-with-streamlit skill):** suggestion chips routed through the same path as typed input; live progress timeline (`st.status` compact + steps) via `Answerer.ask(step=...)`; input disabled while answering; Material icons; alerts with `title=`; `alt=` on tables; page code as a direct script; `ty` type check clean (fixed 5 None-safety gaps, added `LLMClient.available_models()`)
- Verified in the running app with the agent API (demo selection + red badge; live question → step timeline, citations); `tests/test_app.py` now 6 tests (3 live, 3 demo)

---

## What's next: Week 5 — honest evaluation

1. ~25 harder questions: paraphrased (not copied from filing text), FY2024–25, risk factors, cross-company, tricky unanswerables
2. Model comparison on the same set: `uv run scripts/run_evaluation.py --model gemma4:26b` (also gemma3:12b, gpt-oss:20b) — speed vs quality; does anyone fix sq_021?
3. Reranker experiment (cross-encoder over hybrid top 20) — keep only if it helps
4. Balance-sheet facts (instant XBRL contexts): assets, cash, debt, equity
5. Failure analysis write-up in `reports/`; then Week 6 docs + demo, merge to main

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

68 passing (`uv run pytest`):
- `test_ingestion_simple.py` — 6 smoke tests (files, manifests, DB populated)
- `test_data_quality.py` — 7 data tests (one fact per year, restated EPS, known revenues, labels exist in DB and match evidence phrases)
- `test_retrieval.py` — 17 retriever tests (tokenizer, filters, ordering, known answers, hybrid fusion, index ↔ DB alignment); vector/hybrid tests skip if the index isn't built
- `test_llm.py` — 3 LLM tests (safe config, actionable errors, live chat); live test skips if Ollama is down
- `test_reasoning.py` — 30 tests: parser (incl. segment revenue, most recent), financial calculations, citation parsing, answer scoring
- `test_app.py` — 6 headless Streamlit tests: live (suggestion chips, cited answer with escaped `$`, abstention warning) and demo (picker, type filter, no heavy imports)
