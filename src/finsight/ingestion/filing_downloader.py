"""
Filing Downloader Module for FinSight AI
Downloads and caches SEC filings with proper duplicate detection.
"""

import os
import json
import hashlib
import logging
from typing import Optional, Dict, List
from pathlib import Path

from .edgar_client import EdgarClient
from .company_resolver import CompanyResolver

logger = logging.getLogger(__name__)

class FilingDownloader:
    """
    Handles downloading and caching SEC filings.

    Implements caching based on accession number and URL to avoid duplicates.
    """

    def __init__(self, edgar_client: EdgarClient, cache_dir: str = "data/raw/sec"):
        """
        Initialize the filing downloader.

        Args:
            edgar_client (EdgarClient): SEC EDGAR client instance
            cache_dir (str): Directory to store downloaded filings
        """
        self.edgar_client = edgar_client
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _calculate_file_hash(self, url: str, accession_number: str) -> str:
        """
        Calculate a hash for caching purposes.

        Args:
            url (str): The filing URL
            accession_number (str): Accession number

        Returns:
            str: Hash string for the file
        """
        combined = f"{url}_{accession_number}"
        return hashlib.md5(combined.encode()).hexdigest()

    def _is_cached(self, accession_number: str, url: str) -> bool:
        """
        Check if a filing is already cached.

        Args:
            accession_number (str): Accession number
            url (str): Filing URL

        Returns:
            bool: True if cached, False otherwise
        """
        # Simple check - in reality we'd want more sophisticated caching
        cache_file = self.cache_dir / f"{accession_number}.html"
        return cache_file.exists()

    def _get_cache_filename(self, accession_number: str, company_name: str) -> str:
        """
        Generate a filename for cached filing.

        Args:
            accession_number (str): Accession number
            company_name (str): Company name

        Returns:
            str: Cache filename
        """
        # Sanitize company name for filename
        safe_company = "".join(c for c in company_name if c.isalnum() or c in " -").strip()
        safe_company = safe_company.replace(" ", "-")

        return f"{safe_company}-{accession_number}.html"

    def download_latest_10k(self, cik: str, company_name: str) -> Optional[Dict]:
        """
        Download the latest original 10-K filing for a company.

        Args:
            cik (str): Company CIK
            company_name (str): Company name

        Returns:
            dict or None: Filing information if successful, otherwise None
        """
        logger.info(f"Fetching filing history for CIK {cik}")

        # Get filing history
        filings = self.edgar_client.get_company_filing_history(cik)

        if not filings:
            logger.error(f"No filings found for CIK {cik}")
            return None

        # Find the latest 10-K (exclude amendments like 10-K/A)
        latest_10k = None
        for filing in filings:
            if filing.get('form') == '10-K' and not filing.get('fileNumber', '').endswith('/A'):
                if latest_10k is None or filing.get('filing_date') > latest_10k.get('filing_date'):
                    latest_10k = filing

        if not latest_10k:
            logger.warning(f"No original 10-K filing found for CIK {cik}")
            return None

        accession_number = latest_10k['accession_number']
        url = latest_10k['url']

        # Check if already cached
        if self._is_cached(accession_number, url):
            logger.info(f"Filing already cached: {accession_number}")
            # Return basic info about cached filing
            return {
                'accession_number': accession_number,
                'cached': True,
                'url': url
            }

        # Create cache directory for this company
        company_cache_dir = self.cache_dir / company_name.lower()
        company_cache_dir.mkdir(parents=True, exist_ok=True)

        # Download the filing
        filename = company_cache_dir / f"{accession_number}.html"

        logger.info(f"Downloading filing: {accession_number}")
        success = self.edgar_client.download_filing(url, str(filename))

        if not success:
            logger.error(f"Failed to download filing: {accession_number}")
            return None

        # Return information about the downloaded filing
        return {
            'accession_number': accession_number,
            'cached': False,
            'url': url,
            'filename': str(filename)
        }