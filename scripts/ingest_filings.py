import json
import os
import time
import logging
from pathlib import Path

import requests
from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_DIR / ".env")
MANIFEST_DIR = PROJECT_DIR / "data" / "manifests"

COMPANIES = [
    {"ticker": "MSFT", "slug": "microsoft"},
    {"ticker": "AAPL", "slug": "apple"},
    {"ticker": "NVDA", "slug": "nvidia"},
]

FILINGS_PER_COMPANY = 3

# SEC requires a contact email in the User-Agent. Set SEC_EMAIL in .env (see .env.example).
EMAIL = os.getenv("SEC_EMAIL")
if not EMAIL:
    raise SystemExit("SEC_EMAIL is not set. Copy .env.example to .env and add your email.")
USER_AGENT = f"FinSight AI Research Project {EMAIL}"
HEADERS = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"}

LOG_DIR = PROJECT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "ingestion.log"),
    ],
)
logger = logging.getLogger(__name__)

session = requests.Session()
session.headers.update(HEADERS)

_last_request_time = 0


def sec_get(url):
    """Rate-limited SEC request with exponential-backoff retries."""
    global _last_request_time

    for attempt in range(5):
        elapsed = time.time() - _last_request_time
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)

        try:
            response = session.get(url, timeout=30)
            _last_request_time = time.time()

            if response.status_code == 429 or response.status_code >= 500:
                wait = 2 ** attempt
                logger.warning(f"SEC returned {response.status_code}. Retrying in {wait}s.")
                time.sleep(wait)
                continue

            response.raise_for_status()
            return response

        except requests.RequestException as error:
            if attempt == 4:
                raise
            wait = 2 ** attempt
            logger.warning(f"Request failed: {error}. Retrying in {wait}s.")
            time.sleep(wait)

    raise RuntimeError(f"Unable to retrieve: {url}")


def resolve_cik(ticker):
    """Return zero-padded CIK for a ticker using SEC's company_tickers.json."""
    data = sec_get("https://www.sec.gov/files/company_tickers.json").json()
    for entry in data.values():
        if entry["ticker"].upper() == ticker.upper():
            return str(entry["cik_str"]).zfill(10)
    raise ValueError(f"Ticker not found in SEC data: {ticker}")


def get_recent_10ks(cik, n=3):
    """Return the n most recent original 10-K filings for a CIK."""
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    data = sec_get(url).json()
    company_name = data["name"]

    recent = data["filings"]["recent"]
    filings = []

    for i, form in enumerate(recent["form"]):
        if form == "10-K":
            filings.append({
                "accession_number": recent["accessionNumber"][i],
                "filing_date": recent["filingDate"][i],
                "report_date": recent["reportDate"][i],
                "primary_document": recent["primaryDocument"][i],
                "form_type": form,
            })

    if not filings:
        raise ValueError(f"No 10-K filings found for CIK {cik}")

    filings.sort(key=lambda x: x["filing_date"], reverse=True)
    return filings[:n], company_name


def download_filing(cik, filing, raw_dir):
    """Download one filing HTML to raw_dir; skip if already cached."""
    accession = filing["accession_number"]
    accession_clean = accession.replace("-", "")
    cik_int = str(int(cik))
    document = filing["primary_document"]

    url = (
        f"https://www.sec.gov/Archives/edgar/data/"
        f"{cik_int}/{accession_clean}/{document}"
    )

    raw_dir.mkdir(parents=True, exist_ok=True)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)

    html_path = raw_dir / f"{accession}.html"
    manifest_path = MANIFEST_DIR / f"{accession}.json"

    if html_path.exists() and html_path.stat().st_size > 0 and manifest_path.exists():
        logger.info(f"  Cached: {accession}")
        return html_path, manifest_path, None

    logger.info(f"  Downloading: {url}")
    response = sec_get(url)
    content = response.content

    if len(content) == 0:
        raise ValueError(f"Empty response for {url}")

    preview = content[:1000].lower()
    if b"<html" not in preview and b"<!doctype html" not in preview:
        raise ValueError(f"Response is not HTML for {url}")

    html_path.write_bytes(content)
    logger.info(f"  Saved {len(content):,} bytes → {html_path.name}")

    return html_path, manifest_path, url


def save_manifest(ticker, cik, company_name, filing, html_path, manifest_path, url):
    """Write provenance metadata for one filing."""
    report_date = filing["report_date"]
    metadata = {
        "company": company_name,
        "ticker": ticker,
        "cik": cik,
        "accession_number": filing["accession_number"],
        "filing_date": filing["filing_date"],
        "report_period": report_date,
        "fiscal_year": report_date[:4] if report_date else None,
        "form_type": filing["form_type"],
        "primary_document": filing["primary_document"],
        "source_url": url,
        "file_size": html_path.stat().st_size,
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4)

    logger.info(f"  Manifest: {manifest_path.name}")
    return metadata


def ingest_company(ticker, slug):
    """Download the 3 most recent 10-Ks for one company."""
    logger.info(f"=== {ticker} ===")

    cik = resolve_cik(ticker)
    logger.info(f"  CIK: {cik}")

    filings, company_name = get_recent_10ks(cik, n=FILINGS_PER_COMPANY)
    logger.info(f"  Found {len(filings)} 10-K filing(s) for {company_name}")

    raw_dir = PROJECT_DIR / "data" / "raw" / "sec" / slug / "10-k"
    results = []

    for filing in filings:
        logger.info(f"  Filing: {filing['filing_date']} (period {filing['report_date']})")

        html_path, manifest_path, url = download_filing(cik, filing, raw_dir)

        if url is None:
            with open(manifest_path, encoding="utf-8") as f:
                metadata = json.load(f)
        else:
            metadata = save_manifest(
                ticker, cik, company_name, filing, html_path, manifest_path, url
            )

        results.append(metadata)

    return results


def print_summary(all_results):
    total = sum(len(r) for r in all_results.values())
    print(f"\n{'='*55}")
    print(f"  FinSight AI — Ingestion Complete  ({total} filings)")
    print(f"{'='*55}")
    for ticker, filings in all_results.items():
        print(f"\n  {ticker}")
        for m in filings:
            cached = "" if m.get("source_url") else " [cached]"
            print(f"    FY{m['fiscal_year']}  {m['filing_date']}  {m['file_size']:>10,} bytes{cached}")
    print()


def main():
    logger.info("Starting FinSight AI multi-company SEC ingestion")

    all_results = {}
    errors = []

    for company in COMPANIES:
        try:
            results = ingest_company(company["ticker"], company["slug"])
            all_results[company["ticker"]] = results
        except Exception as e:
            logger.error(f"Failed to ingest {company['ticker']}: {e}")
            errors.append((company["ticker"], str(e)))

    print_summary(all_results)

    if errors:
        print("Errors:")
        for ticker, msg in errors:
            print(f"  {ticker}: {msg}")

    logger.info("Multi-company ingestion finished")


if __name__ == "__main__":
    main()
