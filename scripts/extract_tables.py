"""
Parse all downloaded 10-K filings and populate the SQLite database.

For each filing this script:
  1. Extracts text sections (Item 1, 1A, 7, 7A) and writes chunks to filing_chunks.
  2. Extracts inline XBRL financial facts and writes them to financial_facts.

Run after ingest_filings.py:
    python scripts/extract_tables.py
"""

import json
import logging
import sqlite3
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "src"))

from finsight.parsing.section_extractor import extract_sections
from finsight.parsing.xbrl_extractor import extract_xbrl_facts
from finsight.parsing.chunker import chunk_section

MANIFEST_DIR = PROJECT_DIR / "data" / "manifests"
RAW_BASE = PROJECT_DIR / "data" / "raw" / "sec"
DB_PATH = PROJECT_DIR / "data" / "finsight.db"

LOG_DIR = PROJECT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "extraction.log"),
    ],
)
logger = logging.getLogger(__name__)

COMPANY_SLUG = {
    "MSFT": "microsoft",
    "AAPL": "apple",
    "NVDA": "nvidia",
}


def init_db(db_path: Path) -> sqlite3.Connection:
    schema = (PROJECT_DIR / "sql" / "schema.sql").read_text()
    conn = sqlite3.connect(db_path)
    conn.executescript(schema)
    conn.commit()
    return conn


def load_manifests() -> list:
    manifests = []
    for path in sorted(MANIFEST_DIR.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            manifests.append(json.load(f))
    return manifests


def html_path_for(manifest: dict) -> Path:
    ticker = manifest["ticker"]
    slug = COMPANY_SLUG.get(ticker, ticker.lower())
    accession = manifest["accession_number"]
    return RAW_BASE / slug / "10-k" / f"{accession}.html"


def insert_chunks(conn: sqlite3.Connection, chunks: list):
    sql = """
        INSERT OR IGNORE INTO filing_chunks
            (company, ticker, cik, fiscal_year, filing_date, report_period,
             form_type, accession_number, source_url,
             section_id, section_title, chunk_idx, text)
        VALUES
            (:company, :ticker, :cik, :fiscal_year, :filing_date, :report_period,
             :form_type, :accession_number, :source_url,
             :section_id, :section_title, :chunk_idx, :text)
    """
    conn.executemany(sql, chunks)
    conn.commit()


def insert_facts(conn: sqlite3.Connection, facts: list):
    sql = """
        INSERT INTO financial_facts
            (company, ticker, cik, concept, metric_label,
             value, unit, period_start, period_end,
             fiscal_year, filing_date, form_type,
             accession_number, source_url)
        VALUES
            (:company, :ticker, :cik, :concept, :metric_label,
             :value, :unit, :period_start, :period_end,
             :fiscal_year, :filing_date, :form_type,
             :accession_number, :source_url)
        -- Later filings restate prior periods (e.g. NVDA's 10:1 split in 2024 restated
        -- EPS), so the most recently filed value wins regardless of processing order.
        ON CONFLICT (concept, cik, period_start, period_end) DO UPDATE SET
            value = excluded.value,
            unit = excluded.unit,
            filing_date = excluded.filing_date,
            form_type = excluded.form_type,
            accession_number = excluded.accession_number,
            source_url = excluded.source_url
        WHERE excluded.filing_date > financial_facts.filing_date
    """
    conn.executemany(sql, facts)
    conn.commit()


def process_filing(manifest: dict, conn: sqlite3.Connection) -> dict:
    html = html_path_for(manifest)
    if not html.exists():
        logger.warning(f"HTML not found: {html}")
        return {"chunks": 0, "facts": 0, "skipped": True}

    ticker = manifest["ticker"]
    fy = manifest["fiscal_year"]
    accession = manifest["accession_number"]
    logger.info(f"  Parsing {ticker} FY{fy} ({accession})")

    # --- Section text → chunks ---
    sections = extract_sections(html)
    all_chunks = []
    for section_id, section_data in sections.items():
        for chunk in chunk_section(
            section_data["text"],
            section_id,
            section_data["title"],
            manifest,
        ):
            all_chunks.append(chunk)

    insert_chunks(conn, all_chunks)

    # --- Inline XBRL → financial facts ---
    facts = extract_xbrl_facts(html, manifest)
    insert_facts(conn, facts)

    logger.info(f"    {len(all_chunks)} chunks, {len(facts)} facts")
    return {"chunks": len(all_chunks), "facts": len(facts), "skipped": False}


def print_summary(results: list):
    total_chunks = sum(r["chunks"] for r in results)
    total_facts = sum(r["facts"] for r in results)
    skipped = sum(1 for r in results if r["skipped"])

    print(f"\n{'='*55}")
    print(f"  FinSight AI — Extraction Complete")
    print(f"{'='*55}")
    print(f"  Filings processed : {len(results) - skipped}")
    print(f"  Filings skipped   : {skipped}")
    print(f"  Text chunks       : {total_chunks:,}")
    print(f"  Financial facts   : {total_facts:,}")
    print(f"  Database          : {DB_PATH}")
    print()


def main():
    logger.info("Starting FinSight AI extraction pipeline")

    conn = init_db(DB_PATH)
    manifests = load_manifests()
    logger.info(f"Found {len(manifests)} manifest(s)")

    results = []
    for manifest in manifests:
        result = process_filing(manifest, conn)
        results.append(result)

    conn.close()
    print_summary(results)
    logger.info("Extraction pipeline finished")


if __name__ == "__main__":
    main()
