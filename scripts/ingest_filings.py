import json
import os
import re
import time
import logging
from pathlib import Path

import requests

# Project directories
PROJECT_DIR = Path(__file__).resolve().parent.parent

RAW_DIR = PROJECT_DIR / "data" / "raw" / "sec" / "microsoft" / "10-k"
MANIFEST_DIR = PROJECT_DIR / "data" / "manifests"

# SEC configuration
TICKER = "MSFT"
EMAIL = os.getenv(
    "SEC_EMAIL",
    "sarthak.dahal111@gmail.com"
)

USER_AGENT = f"FinSight AI Research Project {EMAIL}"

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Encoding": "gzip, deflate"
}

# Logging
LOG_DIR = PROJECT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "ingestion.log")
    ]
)

logger = logging.getLogger(__name__)

session = requests.Session()
session.headers.update(HEADERS)

last_request_time = 0


def sec_get(url):
    """Send a rate-limited SEC request with retries."""

    global last_request_time

    for attempt in range(5):
        # Conservative request rate
        elapsed = time.time() - last_request_time

        if elapsed < 1:
            time.sleep(1 - elapsed)

        try:
            response = session.get(url, timeout=30)
            last_request_time = time.time()

            if response.status_code == 429 or response.status_code >= 500:
                wait = 2 ** attempt
                logger.warning(
                    f"SEC returned {response.status_code}. "
                    f"Retrying in {wait} seconds."
                )
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

    raise RuntimeError(f"Unable to retrieve SEC resource: {url}")


def get_company_cik():
    """Find Microsoft's CIK using SEC ticker data."""

    logger.info("Looking up Microsoft's CIK...")

    url = "https://www.sec.gov/files/company_tickers.json"

    data = sec_get(url).json()

    for company in data.values():
        if company["ticker"].upper() == TICKER:
            cik = str(company["cik_str"]).zfill(10)
            logger.info(f"Found Microsoft CIK: {cik}")
            return cik

    raise ValueError("Microsoft ticker not found in SEC data.")


def get_latest_10k(cik):
    """Retrieve Microsoft's latest original 10-K."""

    logger.info("Retrieving SEC filing history...")

    url = f"https://data.sec.gov/submissions/CIK{cik}.json"

    data = sec_get(url).json()

    recent = data["filings"]["recent"]

    # SEC submissions data is column-oriented.
    # Each index represents one filing.
    filings = []

    for i, form in enumerate(recent["form"]):
        if form == "10-K":
            filings.append({
                "accession_number": recent["accessionNumber"][i],
                "filing_date": recent["filingDate"][i],
                "report_date": recent["reportDate"][i],
                "primary_document": recent["primaryDocument"][i],
                "form_type": form
            })

    if not filings:
        raise ValueError("No original 10-K filings found.")

    # Most recent filing first
    filings.sort(
        key=lambda x: x["filing_date"],
        reverse=True
    )

    filing = filings[0]

    logger.info(
        f"Selected Microsoft's 10-K filed on {filing['filing_date']}"
    )

    return filing, data["name"]


def download_filing(cik, filing):
    """Download and preserve the original SEC HTML filing."""

    accession = filing["accession_number"]
    accession_clean = accession.replace("-", "")

    cik_clean = str(int(cik))

    document = filing["primary_document"]

    url = (
        f"https://www.sec.gov/Archives/edgar/data/"
        f"{cik_clean}/{accession_clean}/{document}"
    )

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)

    html_path = RAW_DIR / f"{accession}.html"
    manifest_path = MANIFEST_DIR / f"{accession}.json"

    # Avoid downloading an existing filing again.
    if (
        html_path.exists()
        and html_path.stat().st_size > 0
        and manifest_path.exists()
    ):
        logger.info("Filing already downloaded. Using cached files.")
        return html_path, manifest_path, None

    logger.info(f"Downloading filing: {url}")

    response = sec_get(url)

    content = response.content

    if len(content) == 0:
        raise ValueError("SEC returned an empty filing.")

    # Basic HTML validation
    preview = content[:1000].lower()

    if b"<html" not in preview and b"<!doctype html" not in preview:
        raise ValueError("Downloaded document does not appear to be HTML.")

    # Save original bytes without modifying the document.
    html_path.write_bytes(content)

    logger.info(f"Saved HTML: {html_path}")
    logger.info(f"File size: {len(content):,} bytes")

    return html_path, manifest_path, url


def save_metadata(cik, company_name, filing, html_path, manifest_path, url):
    """Save actual SEC filing metadata as JSON."""

    report_date = filing["report_date"]

    metadata = {
        "company": company_name,
        "ticker": TICKER,
        "cik": cik,
        "accession_number": filing["accession_number"],
        "filing_date": filing["filing_date"],
        "report_period": report_date,
        "fiscal_year": (
            report_date[:4] if report_date else None
        ),
        "form_type": filing["form_type"],
        "primary_document": filing["primary_document"],
        "source_url": url,
        "file_size": html_path.stat().st_size
    }

    with open(manifest_path, "w", encoding="utf-8") as file:
        json.dump(metadata, file, indent=4)

    logger.info(f"Saved metadata: {manifest_path}")

    return metadata


def main():
    logger.info("Starting FinSight AI SEC ingestion")

    cik = get_company_cik()

    filing, company_name = get_latest_10k(cik)

    html_path, manifest_path, url = download_filing(cik, filing)

    if url is None:
        logger.info("Cached filing and manifest already exist.")

        with open(manifest_path, encoding="utf-8") as file:
            metadata = json.load(file)
    else:
        metadata = save_metadata(
            cik,
            company_name,
            filing,
            html_path,
            manifest_path,
            url
        )

    logger.info("SEC INGESTION COMPLETED")

    print("\n--- Download Summary ---")
    print(f"Company: {metadata['company']}")
    print(f"CIK: {metadata['cik']}")
    print(f"Filing: {metadata['form_type']}")
    print(f"Filing date: {metadata['filing_date']}")
    print(f"Reporting period: {metadata['report_period']}")
    print(f"Accession: {metadata['accession_number']}")
    print(f"HTML: {html_path}")
    print(f"JSON: {manifest_path}")
    print(f"HTML size: {metadata['file_size']:,} bytes")


if __name__ == "__main__":
    main()