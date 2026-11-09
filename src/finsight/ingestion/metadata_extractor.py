"""
Metadata Extraction Module for FinSight AI
Extracts key metadata from SEC filings.
"""

import os
import json
import re
import logging
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class MetadataExtractor:
    """
    Extracts and processes metadata from SEC filings.

    Parses HTML filings to extract structured information for the research assistant.
    """

    def __init__(self):
        """Initialize the metadata extractor."""
        pass

    def extract_metadata(self, html_content: str, company_name: str, ticker: str,
                        cik: str, accession_number: str, filing_date: str,
                        form_type: str, source_url: str) -> Dict[str, Any]:
        """
        Extract metadata from a filing's HTML content.

        Args:
            html_content (str): Raw HTML content of the filing
            company_name (str): Company name
            ticker (str): Stock ticker symbol
            cik (str): Central Index Key
            accession_number (str): SEC accession number
            filing_date (str): Filing date (YYYY-MM-DD)
            form_type (str): Form type (e.g., '10-K')
            source_url (str): Original SEC URL

        Returns:
            dict: Extracted metadata
        """
        # Basic metadata
        metadata = {
            'company': company_name,
            'ticker': ticker,
            'cik': cik,
            'accession_number': accession_number,
            'filing_date': filing_date,
            'form_type': form_type,
            'source_url': source_url,
            'primary_document': self._extract_primary_document(html_content),
            'report_period': self._extract_report_period(html_content, filing_date),
            'fiscal_year': self._extract_fiscal_year(filing_date)
        }

        # Add file information
        metadata['file_size'] = len(html_content) if html_content else 0

        logger.info(f"Extracted metadata for {company_name} filing {accession_number}")
        return metadata

    def _extract_primary_document(self, html_content: str) -> str:
        """
        Extract the primary document filename from HTML.

        Args:
            html_content (str): Raw HTML content

        Returns:
            str: Primary document filename or empty string
        """
        # Look for primary document in the HTML
        # This is a simplified extraction - real implementation would parse properly
        if not html_content:
            return ""

        # Look for document references in common patterns
        patterns = [
            r'primarydocument">([^<]+)</',
            r'primary-document">([^<]+)</',
            r'<a[^>]*href="[^"]*/([^"]+)"[^>]*class="[^"]*primary[^"]*"[^>]*>',
            r'filename="([^"]+)"'
        ]

        for pattern in patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        # If no specific document found, return empty string
        return ""

    def _extract_report_period(self, html_content: str, filing_date: str) -> Optional[str]:
        """
        Extract the report period from filing content.

        Args:
            html_content (str): Raw HTML content
            filing_date (str): Filing date

        Returns:
            str or None: Report period if found
        """
        # Parse the filing date to get year
        try:
            filing_dt = datetime.strptime(filing_date, '%Y-%m-%d')
            return f"{filing_dt.year}"
        except ValueError:
            return None

    def _extract_fiscal_year(self, filing_date: str) -> Optional[str]:
        """
        Extract fiscal year from filing date.

        Args:
            filing_date (str): Filing date (YYYY-MM-DD)

        Returns:
            str or None: Fiscal year if found
        """
        try:
            filing_dt = datetime.strptime(filing_date, '%Y-%m-%d')
            return str(filing_dt.year)
        except ValueError:
            return None

    def save_manifest(self, metadata: Dict[str, Any], manifest_dir: str = "data/manifests") -> bool:
        """
        Save extracted metadata to a JSON manifest file.

        Args:
            metadata (dict): Extracted metadata
            manifest_dir (str): Directory to save manifest

        Returns:
            bool: True if successful, False otherwise
        """
        os.makedirs(manifest_dir, exist_ok=True)

        # Create filename based on accession number
        filename = f"{metadata['accession_number']}.json"
        filepath = os.path.join(manifest_dir, filename)

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

            logger.info(f"Manifest saved to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Error saving manifest: {str(e)}")
            return False