# FinSight AI

Local RAG assistant over SEC 10-K filings (MSFT, AAPL, NVDA). No paid APIs: SQLite, BM25, FAISS, Sentence Transformers, Ollama, Streamlit.

Current status and next steps live in PROGRESS.md:
@PROGRESS.md

## Commands

- Python: always `.venv/bin/python` (Python 3.14). Install packages with `.venv/bin/python -m pip install ...` and pin them in `requirements.txt`.
- Tests: `.venv/bin/python -m pytest tests/ -q`
- Rebuild DB from raw filings: `rm -f data/finsight.db && .venv/bin/python scripts/extract_tables.py`
- Re-ingest filings (network, slow, needs `SEC_EMAIL` in `.env`): `.venv/bin/python scripts/ingest_filings.py`

## Rules

- Never modify or delete `data/raw/`. It is the downloaded SEC source of truth and slow to re-fetch.
- `data/finsight.db` is a build artifact; it can always be regenerated from `data/raw/` + `data/manifests/`.
- Never hardcode emails, keys, or personal info. Config goes in `.env` (gitignored); document new vars in `.env.example`.
- Library code goes in `src/finsight/<module>/`; runnable entry points go in `scripts/`. Import as `finsight.*` (PYTHONPATH=src).
- Financial numbers must be traceable: every fact/chunk keeps its accession number, ticker, fiscal year, and section.
- `financial_facts` holds consolidated (non-dimensioned) annual XBRL values only; check the `unit` column (`USD_millions` or `USD_per_share`). Fiscal years differ by company (MSFT ends June, AAPL Sept, NVDA late Jan).
- Run the tests before calling work done. Update PROGRESS.md at the end of a session (`/session-wrap`).
