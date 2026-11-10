# FinSight AI

Local RAG assistant over SEC 10-K filings (MSFT, AAPL, NVDA). No paid APIs: SQLite, BM25, FAISS, Sentence Transformers, Ollama, Streamlit.

Current status and next steps live in PROGRESS.md:
@PROGRESS.md

## Commands

- Environment is managed by **uv** (`~/.local/bin/uv`; Python 3.14, `.venv/`). Run everything with `uv run ...`. Add deps with `uv add <pkg>` (dev: `uv add --dev`), never pip; `pyproject.toml` + `uv.lock` are the source of truth.
- Tests: `uv run pytest -q`
- Rebuild DB from raw filings: `rm -f data/finsight.db && uv run scripts/extract_tables.py`
- Rebuild retrieval index (after DB rebuild or model change): `uv run scripts/build_index.py`
- Score retrieval: `uv run scripts/eval_retrieval.py --details`
- LLM: Ollama must be running (Ollama.app or `ollama serve`); model + settings in `configs/llm.yaml`. Never let the LLM do arithmetic — compute in Python and pass results in.
- Re-ingest filings (network, slow, needs `SEC_EMAIL` in `.env`): `uv run scripts/ingest_filings.py`

## Rules

- Never modify or delete `data/raw/`. It is the downloaded SEC source of truth and slow to re-fetch.
- `data/finsight.db` is a build artifact; it can always be regenerated from `data/raw/` + `data/manifests/`.
- Never hardcode emails, keys, or personal info. Config goes in `.env` (gitignored); document new vars in `.env.example`.
- Library code goes in `src/finsight/<module>/`; runnable entry points go in `scripts/`. `finsight` is installed in editable mode, so import as `finsight.*` with no path hacks.
- In any module that uses both, `import torch` before `faiss` (macOS OpenMP clash → segfault).
- Financial numbers must be traceable: every fact/chunk keeps its accession number, ticker, fiscal year, and section.
- `financial_facts` holds consolidated (non-dimensioned) annual XBRL values only; check the `unit` column (`USD_millions` or `USD_per_share`). Fiscal years differ by company (MSFT ends June, AAPL Sept, NVDA late Jan).
- Run the tests before calling work done. Update PROGRESS.md at the end of a session (`/session-wrap`).
