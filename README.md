# FinSight AI

A local financial research assistant that can analyze public-company filings, answer questions using source evidence, perform financial calculations, and compare companies across reporting periods.

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

1. Create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
streamlit run app/streamlit_app.py
```

## Project Structure

```
.
├── README.md
├── requirements.txt
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