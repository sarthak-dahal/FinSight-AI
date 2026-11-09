# FinSight AI --- Project Blueprint

**Project type:** Applied AI / Data Science / Machine Learning
Engineering\
**Target roles:** Data Scientist, Machine Learning Engineer\
**Difficulty:** Advanced\
**Development environment:** VS Code, Python, SQL\
**Cost:** \$0 required for APIs, datasets, and hosting; run the system
locally

------------------------------------------------------------------------

## 1. Project goal

Build **FinSight AI**, a local financial research assistant that can
analyze public-company filings, answer questions using source evidence,
perform financial calculations, and compare companies across reporting
periods.

The goal is to demonstrate that you can build an end-to-end applied AI
system---not simply connect an LLM to a PDF.

The project should demonstrate:

-   Data acquisition and engineering.
-   Document and financial-table extraction.
-   SQL and structured data management.
-   Natural-language processing and embeddings.
-   Keyword, vector, and hybrid retrieval.
-   LLM integration and tool-based reasoning.
-   Model evaluation and error analysis.
-   API development, testing, and deployment.

## 2. What the application will do

A user should be able to select a company and reporting period, ask a
question, and receive an answer supported by filing evidence.

Example questions:

-   How did Microsoft's operating margin change over the last three
    fiscal years?
-   What factors did management identify as driving revenue growth?
-   Compare R&D spending as a percentage of revenue for Apple and
    Microsoft.
-   What does Nvidia's annual report say about data-center revenue?
-   Which filing section discusses capital expenditures?
-   Does the available evidence support the claim that operating
    expenses grew faster than revenue?

For each answer, FinSight AI should show:

1.  A direct answer.
2.  The company and reporting period.
3.  Supporting filing passages and source links.
4.  The calculation and inputs, when relevant.
5.  An insufficient-evidence message when the documents do not support
    an answer.

**Core design principle:** The LLM explains and coordinates. Retrieved
filings provide evidence, SQL stores structured facts, and Python
performs calculations.

## 3. Data sources

Use public SEC information as the primary dataset.

  -------------------------------------------------------------------------------------------------------------
  Source                                                                    Purpose
  ------------------------------------------------------------------------- -----------------------------------
  [SEC EDGAR](https://www.sec.gov/edgar/search/)                            Public 10-K annual reports and
                                                                            other filings

  [SEC API documentation](https://www.sec.gov/edgar/sec-api-documentation)  Company submissions and XBRL
                                                                            financial facts

  [FinQA](https://github.com/czyssrs/FinQA)                                 Optional financial
                                                                            numerical-reasoning benchmark

  [FinanceBench](https://huggingface.co/datasets/PatronusAI/financebench)   Optional financial question-answer
                                                                            benchmark
  -------------------------------------------------------------------------------------------------------------

### Initial dataset

Start small:

-   3 companies: Microsoft, Apple, and Nvidia.
-   3 annual 10-K filings per company.
-   9 filings total.
-   30 manually verified questions.

After the first version works, expand to 8--10 companies and
approximately 150--200 evaluation questions.

SEC filings are publicly accessible. Follow SEC access policies, use a
descriptive User-Agent, cache downloads, and make requests
conservatively. Review each third-party dataset's license before using
or redistributing it; FinanceBench has non-commercial restrictions. You
can complete the project using SEC data and your own questions without
either benchmark.

## 4. Technology stack

The project uses regular Python files (`.py`) in VS Code. **No Jupyter
notebooks are required.**

  -----------------------------------------------------------------------
  Area                    Tool                    Purpose
  ----------------------- ----------------------- -----------------------
  IDE                     VS Code                 Write and manage the
                                                  project

  Programming             Python                  Pipelines, ML,
                                                  application logic

  Query language          SQL                     Query structured
                                                  financial data

  Database                SQLite                  Store company facts and
                                                  metadata

  Data processing         Pandas, NumPy           Clean and transform
                                                  data

  Filing parsing          BeautifulSoup, lxml     Extract text and tables
                                                  from HTML

  Embeddings              Sentence Transformers / Convert text into
                          BGE                     vectors

  Keyword retrieval       BM25                    Exact-term search

  Vector search           FAISS                   Semantic similarity
                                                  search

  Reranking               BGE cross-encoder       Reorder retrieved
                                                  passages

  Local LLM runtime       Ollama                  Run models locally

  LLM                     A suitable local        Generate evidence-based
                          instruction model       responses

  Coding assistant        Claude Code + local     Help write, inspect,
                          Qwen3-Coder through     and debug code
                          Ollama                  

  API                     FastAPI                 Serve application
                                                  endpoints

  User interface          Streamlit               Provide a simple
                                                  research interface

  Evaluation              Python metrics;         Evaluate retrieval and
                          optional Ragas          answers

  Testing                 pytest                  Unit and integration
                                                  tests

  Version control         Git and GitHub          Track and publish code

  Packaging               Docker (optional)       Reproducible local
                                                  setup
  -----------------------------------------------------------------------

All core components can run locally. No paid OpenAI or Anthropic API,
cloud database, or paid hosting is required. Model downloads and local
inference use disk space, memory, electricity, and processing time.
Check individual model licenses and hardware requirements.

### Keep the first version simple

Start with Python, SQLite, Pandas, BM25, Sentence Transformers, FAISS,
Ollama, and Streamlit. Add reranking, FastAPI, Docker, and advanced
orchestration after the basic pipeline works.

## 5. How the system works

``` text
                 SEC EDGAR filings / XBRL
                            |
                            v
                     Python ingestion
                            |
                  +---------+---------+
                  |                   |
                  v                   v
            Filing parser       Table / XBRL parser
                  |                   |
                  v                   v
          Text and sections     Structured financial facts
                  |                   |
                  v                   v
          Chunking + metadata        SQLite
                  |
          +-------+-------+
          |               |
          v               v
       BM25 search    Embeddings + FAISS
          |               |
          +-------+-------+
                  |
             User question
                  |
             Query routing
                  |
          +-------+-------+
          |               |
          v               v
      Text retrieval   SQL metric lookup
          |               |
          v               v
    Hybrid search      Python calculations
    + reranking
          |               |
          +-------+-------+
                  |
             Evidence package
                  |
              Local LLM
                  |
       Citation / support checks
                  |
          Answer or abstention
                  |
             Streamlit UI
```

There are two main data paths:

-   **Narrative data:** explanations, risks, management commentary, and
    other filing text are searched through BM25 and vector retrieval.
-   **Structured data:** revenue, operating income, expenses, and other
    financial facts are stored in SQL and used for deterministic
    calculations.

Some questions need both paths. For example, a question about why
operating margin changed may need a calculated margin and narrative
evidence explaining the change.

## 6. Main project components

### A. Data ingestion and processing

Build Python scripts to:

-   Download selected SEC filings.
-   Save source files locally and avoid downloading duplicates.
-   Record company, CIK, filing date, fiscal year, accession number, and
    source URL.
-   Parse filing sections and paragraphs.
-   Extract financial tables.
-   Retrieve selected XBRL facts.
-   Preserve source references for every extracted record.

Start with HTML filings. Add PDF parsing only if you have a clear need.

### B. SQL database

Use SQLite initially. Store structured financial facts and filing
metadata.

Useful fields include:

``` text
company
cik
concept
metric_label
value
unit
period_start
period_end
filing_date
form_type
accession_number
source_url
```

Preserve units, reporting periods, and source information. Do not
compare values until you have checked that their units and periods are
compatible.

### C. Retrieval system

Build and compare:

1.  BM25 keyword search.
2.  Dense-vector search using local embeddings.
3.  Hybrid search combining keyword and vector results.
4.  Hybrid search with a cross-encoder reranker.

Start with section-aware text chunks and preserve company, year, filing
type, section, and source metadata. Apply company and year filters when
the question specifies them.

### D. LLM and financial reasoning

Run a local instruction model through Ollama. Build Python tools for:

-   Searching filing passages.
-   Looking up financial metrics from SQL.
-   Calculating percentage change.
-   Calculating operating margin.
-   Comparing companies and years.
-   Checking whether citations point to retrieved evidence.

Do not ask the LLM to invent figures or perform important arithmetic.
Let it select the operation, then use deterministic Python functions for
calculations.

### E. Evidence and citation validation

Every answer should cite the filing and evidence used. Check that:

-   Each evidence ID exists.
-   The evidence belongs to the requested company and period.
-   The citation points to content actually retrieved.
-   Numerical claims match the stored data or calculation.
-   Unsupported questions receive an insufficient-evidence response.

## 7. Evaluation

Evaluation is a major part of the project. A working chatbot alone is
not enough.

Create a verified test set. A later target is 150--200 questions:

  Question type              Suggested count
  ------------------------ -----------------
  Factual                                 40
  Numerical                               40
  Comparative                             35
  Multi-step / multi-hop                  25
  Unanswerable                            20
  **Total**                          **160**

Keep a development set separate from the final test set.

Measure:

  -----------------------------------------------------------------------
  Metric                              What it tells you
  ----------------------------------- -----------------------------------
  Recall@5                            Whether relevant evidence appears
                                      in the top five results

  MRR / NDCG                          Whether relevant evidence is ranked
                                      highly

  Answer correctness                  Whether the generated answer is
                                      correct

  Citation precision                  Whether cited evidence supports the
                                      claims

  Faithfulness                        Whether the answer stays grounded
                                      in retrieved evidence

  Abstention precision / recall       Whether the system handles
                                      unanswerable questions

  Latency                             How long a query takes
  -----------------------------------------------------------------------

Run experiments comparing:

-   BM25 vs. dense vs. hybrid retrieval.
-   Fixed-size vs. section-aware chunks.
-   Reranking vs. no reranking.
-   Different local LLMs.
-   LLM-only numerical responses vs. deterministic Python calculation
    tools.

Record actual results. Do not invent accuracy or performance numbers.
Review failures and classify them: parsing, retrieval, wrong
company/year, incorrect metric, calculation, unsupported generation, or
citation mismatch.

## 8. Application and how to use it

The finished application should let a user:

1.  Launch FinSight AI locally.
2.  Select a company and filing year.
3.  Enter a natural-language research question.
4.  View the generated answer.
5.  Inspect supporting filing passages and source links.
6.  Review calculations for numerical questions.
7.  Compare companies or reporting periods.

Use Streamlit for the first interface. FastAPI can be added later if you
want a separate backend.

Example local workflow:

``` bash
# Activate your environment
source .venv/bin/activate

# Download and process filings
python scripts/ingest_filings.py

# Build the retrieval index
python scripts/build_index.py

# Launch the application
streamlit run app/streamlit_app.py
```

These are planned script names; create them as you implement the
corresponding components.

## 9. Development setup: VS Code and Python

On macOS:

``` bash
# Create the project folder and enter it
mkdir financial-research-ai
cd financial-research-ai

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Upgrade pip
python -m pip install --upgrade pip

# Open the folder in VS Code
code .
```

In VS Code:

-   Install or enable the Python extension.
-   Select `.venv` as the Python interpreter.
-   Use the integrated terminal to run scripts.
-   Keep reusable application code in `src/`.
-   Keep runnable command-line tasks in `scripts/`.
-   Use SQL files for database queries and schema definitions.
-   Use `pytest` to run tests.

Do not put the entire project in one Python file. Separate ingestion,
parsing, retrieval, reasoning, evaluation, and application code into
modules.

## 10. Suggested GitHub structure

``` text
finsight-ai/
├── README.md
├── requirements.txt
├── .gitignore
├── configs/
│   ├── ingestion.yaml
│   └── retrieval.yaml
├── data/
│   ├── manifests/
│   └── evaluation/
├── scripts/
│   ├── ingest_filings.py
│   ├── extract_tables.py
│   ├── build_index.py
│   └── run_evaluation.py
├── src/
│   └── finsight/
│       ├── ingestion/
│       ├── parsing/
│       ├── database/
│       ├── retrieval/
│       ├── reasoning/
│       ├── validation/
│       └── evaluation/
├── app/
│   └── streamlit_app.py
├── sql/
│   ├── schema.sql
│   └── queries.sql
├── tests/
├── experiments/
└── reports/
    ├── architecture.md
    └── evaluation_report.md
```

Do not commit API keys, raw filing collections, model weights, large
vector indexes, or generated caches. Include scripts and instructions to
recreate them.

## 11. Local coding assistant: Qwen3-Coder through Ollama

You can use your local Qwen3-Coder model to help develop the project.
This is separate from the LLM that FinSight AI uses to answer financial
questions.

Example setup:

``` bash
ollama pull qwen3-coder:30b
```

If your installed Claude Code and Ollama versions support the
Anthropic-compatible integration, launch it with:

``` bash
OLLAMA_NUM_CTX=65536 \
ANTHROPIC_AUTH_TOKEN=ollama \
ANTHROPIC_BASE_URL=http://localhost:11434 \
ANTHROPIC_API_KEY="" \
claude --model qwen3-coder:30b
```

This directs the coding assistant's model requests to your local Ollama
server. Qwen3-Coder can help inspect files, write code, refactor
modules, and debug. It is not an Anthropic Claude model, and it is not
automatically the best model for financial question answering.

A 30B model with a 65K context can use substantial memory. Start with a
smaller context if performance or memory use is an issue. Local
inference has no per-token API charge, but it uses your computer's
resources.

## 12. Six-week implementation roadmap

  -----------------------------------------------------------------------
  Week                    Work                    Deliverable
  ----------------------- ----------------------- -----------------------
  1                       Select companies,       Small source dataset
                          download filings,       
                          verify 30 questions     

  2                       Parse filing text and   Ingestion pipeline
                          tables; store facts in  
                          SQLite                  

  3                       Implement BM25 and      Search baseline
                          dense retrieval         

  4                       Add hybrid retrieval,   Working research
                          local LLM,              assistant
                          calculations, and       
                          citations               

  5                       Evaluate retrieval and  Evaluation report
                          answers; analyze        
                          failures                

  6                       Build Streamlit UI,     Portfolio-ready project
                          tests, documentation,   
                          and demo                
  -----------------------------------------------------------------------

### First milestone

Start with only:

-   One company.
-   One 10-K filing.
-   Ten verified questions.
-   A Python ingestion script.
-   A basic BM25 search script.

Once this works, add SQL facts, embeddings, hybrid retrieval, LLM
reasoning, and evaluation. Do not begin with agents or a complex
deployment.

## 13. Final deliverables

The finished portfolio project should include:

-   A working local research application.
-   Reproducible Python ingestion and indexing scripts.
-   A SQL database schema and example queries.
-   BM25, dense, and hybrid retrieval experiments.
-   Evidence-linked answers and deterministic calculations.
-   A held-out evaluation report with actual measurements.
-   Failure analysis and documented limitations.
-   GitHub setup instructions, screenshots, and a short demo.

### Resume description --- update after completing the work

**FinSight AI \| Python, SQL, RAG, Sentence Transformers, FAISS, Ollama,
FastAPI**

-   Built a local financial research assistant ingesting SEC filings and
    structured XBRL data, preserving source metadata for evidence
    retrieval.
-   Implemented and evaluated BM25, dense-vector, and hybrid retrieval
    with reranking across multi-year company filings.
-   Developed deterministic financial calculation tools and
    evidence-grounded LLM responses with citation validation and
    insufficient-evidence handling.
-   Evaluated retrieval quality, answer correctness, citation support,
    abstention, and local inference latency.

Only add measured performance improvements and numerical results after
running the experiments.

------------------------------------------------------------------------

**Guiding principle:** Build a smaller system that works, can be tested,
and has measurable results. Prioritize data quality, retrieval,
calculation correctness, and evaluation over unnecessary complexity.
