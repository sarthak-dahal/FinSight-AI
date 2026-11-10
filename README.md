# FinSight AI
A local financial research assistant that can analyze public-company filings, answer questions using source evidence, perform financial calculations, and compare companies across reporting periods.

The goal of FinSight AI is to build a local AI-powered financial research assistant that analyzes public companies using their SEC filings.

A user should be able to ask questions like:
- Why did Microsoft's revenue increase?
- How does Apple's profitability compare to Microsoft?
- How has Nvidia's R&D spending changed?
- What risks does a company identify in its annual report?
FinSight AI will:
1. Download and process SEC financial filings.
2. Extract financial data and business information.
3. Use SQL, Python, and machine learning to analyze the data.
4. Use RAG and a local LLM to answer questions.
5. Provide calculations, supporting evidence, and citations.
Ultimately: Build an end-to-end Data Science and AI application that can research companies, analyze financial performance, and explain its findings with verifiable evidence.



## Project Overview

FinSight AI is designed to demonstrate an end-to-end applied AI system for financial research. The system ingests SEC filings, processes the data, builds retrieval indexes, and provides a user interface for asking questions about public companies.

## Architecture

The system follows a modular architecture with the following components:

1. **Data Ingestion** - Download and process SEC filings
2. **Data Processing** - Parse text and extract financial tables
3. **Database** - Store structured financial facts in SQLite
4. **Retrieval System** - Search both narrative and structured data
5. **Reasoning Engine** - Use local LLMs to generate evidence-based answers
6. **Validation** - Ensure citations point to actual evidence
7. **User Interface** - Streamlit-based research interface

## Getting Started

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync                                  # create .venv and install locked dependencies
cp .env.example .env                     # then set SEC_EMAIL (SEC requires a contact email)

uv run scripts/ingest_filings.py         # download 10-K filings
uv run scripts/extract_tables.py         # parse into data/finsight.db
uv run scripts/build_index.py            # build the vector index
uv run scripts/eval_retrieval.py         # score retrieval on the labelled questions
uv run pytest                            # run tests
```

## Project Structure

```
.
├── README.md
├── pyproject.toml / uv.lock
├── .gitignore
├── configs/                 # Configuration files
├── data/                    # Data storage
│   ├── manifests/
│   └── evaluation/
├── scripts/                 # Executable scripts
├── src/                     # Source code packages
│   └── finsight/
│       ├── ingestion/
│       ├── parsing/
│       ├── database/
│       ├── retrieval/
│       ├── reasoning/
│       ├── validation/
│       └── evaluation/
├── app/                     # Application files
│   └── streamlit_app.py
├── sql/                     # SQL schema and queries
├── tests/                   # Test files
├── experiments/             # Experimental results
└── reports/                 # Project reports
```

## Development Roadmap

1. **Week 1**: Select companies, download filings, verify questions
2. **Week 2**: Parse filing text and tables; store facts in SQLite  
3. **Week 3**: Implement BM25 and dense retrieval
4. **Week 4**: Add hybrid retrieval, local LLM, calculations, and citations
5. **Week 5**: Evaluate retrieval and answers; analyze failures
6. **Week 6**: Build Streamlit UI, tests, documentation, and demo

## License

This project is for educational purposes only.