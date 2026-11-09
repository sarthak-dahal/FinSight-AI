# FinSight AI — Project Progress & Development Log

**Last updated:** November 9, 2026  
**Status:** Phase 1 complete; Phase 2 in progress

---

## 1. Project Overview

FinSight AI is a local AI-powered financial research assistant designed to analyze public company filings and answer financial questions using evidence from SEC documents.

The goal is to build a practical end-to-end data science and machine learning project demonstrating:

- Data ingestion and ETL pipelines
- SEC filing extraction and document processing
- Structured financial data storage using SQL
- Natural language processing and information retrieval
- Retrieval-Augmented Generation (RAG)
- Local LLM integration
- Financial calculations and analysis using Python and SQL
- Response validation, source citations, and evaluation

Example questions the application should eventually answer:

- Why did Microsoft's revenue change compared with the previous year?
- How much does Microsoft spend on research and development relative to revenue?
- What risks does the company disclose in its annual filing?
- Compare revenue growth and operating margins across companies.
- What factors contributed to changes in operating income?

**Core design principle:**

The LLM should explain and interpret information, not invent financial figures. SQL and Python will handle structured data retrieval and calculations, while SEC filings provide the supporting evidence.

---

## 2. Development Environment

### Hardware and software

- Computer: MacBook Pro M5 Pro
- Memory: 48 GB unified memory
- IDE: Visual Studio Code
- Language: Python
- Database: SQL (planned)
- Local model runtime: Ollama
- Version control: Git (planned/being configured)

### Local LLM setup

Ollama is installed and running locally.

Models currently available:

| Model | Purpose |
|---|---|
| GPT-OSS 20B | General-purpose local model |
| Qwen 3.8 27B | General-purpose local model |
| Qwen3-Coder 30B | Coding assistant |
| Gemma 4 26B | General-purpose local model |

Qwen3-Coder 30B was used through Claude Code.

Claude Code was configured to connect to the local Ollama endpoint:

```bash
cd "/Users/sardahal/Desktop/FinSight AI"

ANTHROPIC_AUTH_TOKEN=ollama \
ANTHROPIC_BASE_URL=http://localhost:11434 \
ANTHROPIC_API_KEY="" \
claude --model qwen3-coder:30b
```

This allowed us to use Claude Code as an interface while running Qwen locally instead of relying on a hosted model.

**Development decision:** Qwen was useful for initial scaffolding and code generation, but some generated code required debugging. We decided to work directly with ChatGPT on implementation, review, and troubleshooting instead of delegating every development task to Qwen.

---

## 3. Project Structure

The initial project structure was created under:

`/Users/sardahal/Desktop/FinSight AI`

```text
FinSight AI/
│
├── finsight_ai_blueprint.md
├── README.md
├── PROJECT_PROGRESS.md
├── requirements.txt
├── .gitignore
│
├── configs/
│   ├── ingestion.yaml
│   └── retrieval.yaml
│
├── data/
│   ├── raw/
│   │   └── sec/
│   │       └── microsoft/
│   │           └── 10-k/
│   ├── processed/
│   ├── manifests/
│   └── evaluation/
│
├── scripts/
│   ├── ingest_filings.py
│   ├── inspect_filing.py
│   ├── extract_tables.py
│   ├── build_index.py
│   └── run_evaluation.py
│
├── src/
│   └── finsight/
│       ├── ingestion/
│       ├── parsing/
│       ├── database/
│       ├── retrieval/
│       ├── reasoning/
│       ├── validation/
│       └── evaluation/
│
├── app/
│   └── streamlit_app.py
│
├── sql/
│   ├── schema.sql
│   └── queries.sql
│
├── tests/
│
├── experiments/
│
└── reports/
    ├── architecture.md
    └── evaluation_report.md
```

The project is organized into separate modules so ingestion, parsing, database operations, retrieval, reasoning, and evaluation can be developed independently.

The original `finsight_ai_blueprint.md` is being retained as the master project blueprint.

---

## 4. Work Completed So Far

### Phase 0 — Environment and project setup

**Status: Completed**

- Created the FinSight AI project directory.
- Established the initial directory structure.
- Created the README, requirements file, and `.gitignore`.
- Initialized the Python package structure.
- Installed and configured Ollama.
- Downloaded local LLMs.
- Configured Claude Code to use Qwen through Ollama.
- Installed the document-processing dependencies.

Python dependencies installed for the current parsing work:

```bash
python -m pip install beautifulsoup4 lxml
```

Verified:

```bash
python -c "import bs4, lxml; print('BeautifulSoup and lxml ready')"
```

Output:

```text
BeautifulSoup and lxml ready
```

### Phase 1 — SEC filing ingestion

**Status: Completed for Microsoft**

This was our first actual data pipeline.

#### Initial work with Qwen

We initially used Qwen3-Coder through Claude Code to scaffold the SEC ingestion modules.

The initial generated files included:

- `edgar_client.py`
- `company_resolver.py`
- `filing_downloader.py`
- `metadata_extractor.py`

However, the generated implementation had problems:

- Some metadata was hardcoded rather than retrieved from the SEC.
- There was an error involving `.get()` on the filing metadata.
- Some variables and sample metadata were not properly defined.
- The modules did not form a reliable end-to-end ingestion pipeline.

We inspected the code and identified the issues instead of continuing to build on an unreliable implementation.

#### Rebuilding the ingestion script

We decided to simplify the first ingestion milestone and create a self-contained implementation in:

`scripts/ingest_filings.py`

ChatGPT helped write the replacement script, and we tested and debugged it together.

The script performs the following operations:

1. Connects to the SEC company ticker mapping endpoint.
2. Resolves Microsoft's ticker to its CIK.
3. Retrieves Microsoft's SEC filing history.
4. Identifies the latest 10-K filing.
5. Retrieves the accession number and primary document.
6. Constructs the SEC filing archive URL.
7. Downloads the original HTML filing.
8. Creates a JSON manifest containing filing metadata.
9. Caches downloaded files to avoid unnecessary repeat downloads.

#### SEC endpoints used

Company ticker mapping:

```text
https://www.sec.gov/files/company_tickers.json
```

Company submissions:

```text
https://data.sec.gov/submissions/CIK0000789019.json
```

The script uses the SEC's public data endpoints and an identifying User-Agent.

#### Debugging the SEC request

During development, we encountered an HTTP 404 error.

We identified that the request included an explicit `Host: www.sec.gov` header while accessing `data.sec.gov`.

Removing that conflicting header resolved the problem.

We also implemented caching and verified that running the script a second time reused the existing files instead of downloading the filing again.

#### Successful ingestion result

The pipeline successfully retrieved Microsoft's filing:

| Field | Result |
|---|---|
| Company | Microsoft Corporation |
| Ticker | MSFT |
| CIK | 0000789019 |
| Filing type | 10-K |
| Filing date | July 29, 2026 |
| Report period | June 30, 2026 |
| Accession number | 0001193125-26-323660 |
| HTML file size | 8,585,609 bytes |

Downloaded filing:

```text
data/raw/sec/microsoft/10-k/0001193125-26-323660.html
```

Generated manifest:

```text
data/manifests/0001193125-26-323660.json
```

We also ran the ingestion script again and confirmed that the existing filing was recognized and reused from the cache.

**Phase 1 result:** We have a working SEC ingestion pipeline that resolves a company, retrieves filing metadata, downloads an actual 10-K, and saves a manifest.

---

### Phase 2 — SEC document parsing

**Status: In progress**

The next objective is to turn the downloaded HTML filing into structured, usable information.

We installed BeautifulSoup and lxml and began inspecting the actual Microsoft filing.

#### Initial HTML inspection

We created a temporary diagnostic script:

```text
scripts/inspect_filing.py
```

It was used to examine:

- Document title
- Number of HTML tables
- Number of headings
- Presence of major filing sections
- HTML structure around section headings

Initial findings:

| Observation | Result |
|---|---:|
| HTML tables | 88 |
| Standard H1/H2/H3 headings | 0 |
| Elements with IDs | 2,424 |
| Named anchors | 0 |

The filing uses an XHTML-style structure rather than conventional HTML headings.

BeautifulSoup initially produced an XML parsing warning when we used the `lxml` HTML parser. We switched to:

```python
soup = BeautifulSoup(file, "xml")
```

This is more appropriate for the XML-style structure observed in this particular document.

#### Identifying major filing sections

We inspected the actual HTML and identified the section IDs:

| Section | HTML ID |
|---|---|
| Item 1 — Business | `item_1_business` |
| Item 1A — Risk Factors | `item_1a_risk_factors` |
| Item 7 — MD&A | `item_7_managements_discussion_analysis_f` |
| Item 8 — Financial Statements | `item_8_financial_statements_and_supplem` |

These IDs were verified directly against the downloaded filing.

We also discovered that section headings are stored inside `<p>` elements, with their IDs attached to the parent paragraph.

This matters because relying on standard heading tags or exact text searches would not reliably identify the filing sections.

#### Current parsing status

We have successfully:

- Opened the actual downloaded 10-K.
- Parsed its XHTML-style structure with BeautifulSoup.
- Identified its 88 tables.
- Located the four major sections we want to extract.
- Confirmed the HTML IDs used to identify those sections.

We have **not yet implemented the actual section or table extraction pipeline**.

The next implementation should use the existing:

```text
scripts/extract_tables.py
```

We will extract narrative sections and financial tables separately, preserve their source information, and save structured JSON outputs.

---

## 5. Current Working Files

| File | Purpose | Status |
|---|---|---|
| `scripts/ingest_filings.py` | SEC ingestion and download | Working |
| `scripts/inspect_filing.py` | Temporary HTML inspection | Used for diagnostics |
| `scripts/extract_tables.py` | Actual filing extraction | Not implemented yet |
| `requirements.txt` | Python dependencies | Created |
| `README.md` | Project documentation | Created |
| `finsight_ai_blueprint.md` | Original master blueprint | Preserved |

The initial Qwen-generated ingestion modules should be treated as experimental until reviewed. The self-contained ingestion script is currently the verified implementation.

---

## 6. Planned Data Outputs

After parsing, we intend to generate:

```text
data/
│
├── raw/
│   └── sec/
│       └── microsoft/
│           └── 10-k/
│               └── 0001193125-26-323660.html
│
├── processed/
│   ├── filings/
│   │   └── microsoft/
│   │       └── 0001193125-26-323660.json
│   │
│   └── tables/
│       └── microsoft/
│           └── 0001193125-26-323660.json
│
├── manifests/
│   └── 0001193125-26-323660.json
│
└── evaluation/
```

The original SEC filing will remain unchanged.

The processed filing JSON will contain the extracted narrative sections and filing metadata.

The table JSON will preserve table content in a structured format, including rows and cells, so financial information can be processed later.

---

## 7. Remaining Development Phases

| Phase | Work | Status |
|---|---|---|
| 0 | Environment and project setup | Complete |
| 1 | SEC filing ingestion | Complete for MSFT |
| 2 | HTML parsing and table extraction | In progress |
| 3 | Structured financial database and SQL queries | Not started |
| 4 | Text chunking and document indexing | Not started |
| 5 | BM25, dense, and hybrid retrieval | Not started |
| 6 | Local LLM integration and RAG | Not started |
| 7 | Financial calculations and answer validation | Not started |
| 8 | Streamlit interface | Not started |
| 9 | Evaluation and documentation | Not started |

### Planned final MVP

The initial MVP will focus on:

- Three public companies.
- Two annual filings per company where available.
- A limited set of important financial metrics.
- SQL-based financial calculations.
- BM25 and dense/hybrid document retrieval.
- One local LLM.
- Source-grounded responses with citations.
- A Streamlit interface.
- A small but meaningful evaluation dataset.

Advanced features such as reranking, FastAPI, Docker deployment, and more complex agent workflows can be postponed.

---

## 8. Development Approach and Responsibilities

The project has been developed collaboratively.

**Qwen3-Coder / Claude Code:**
- Assisted with initial project scaffolding.
- Generated initial SEC ingestion modules.
- Helped explore the project structure.
- The generated ingestion implementation required debugging and was replaced with a simpler verified script.

**ChatGPT:**
- Helped review and troubleshoot the initial code.
- Wrote the replacement SEC ingestion implementation.
- Helped debug the SEC request issue.
- Guided dependency installation and HTML inspection.
- Helped identify the actual section IDs and parsing approach.
- Will assist with implementation, testing, and explanation of the remaining pipeline.

**Developer:**
- Set up the local development environment.
- Installed and configured Ollama and local models.
- Used VS Code and Terminal to execute and test scripts.
- Reviewed generated code and identified implementation problems.
- Ran the ingestion pipeline and verified the downloaded SEC filing.
- Executed the HTML inspection scripts and shared their results.
- Made implementation decisions and will continue building and validating the application.

The priority is to understand and own the implementation rather than simply generate a large amount of code.

---

## 9. Immediate Next Steps

The next development session should begin with actual implementation, not more diagnostic scripts.

1. Implement section extraction in the existing parsing workflow.
2. Extract Item 1, Item 1A, Item 7, and Item 8.
3. Extract and preserve the 88 HTML tables in structured form.
4. Save the processed sections and tables as JSON.
5. Validate that extracted content is complete and readable.
6. Move to structured financial data and SQL.

**Current milestone:** Microsoft SEC ingestion is working. The actual 10-K is downloaded locally, its metadata is saved, and the four target sections have been identified. We are ready to build the parsing pipeline.