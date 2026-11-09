"""
Company Resolution Module for FinSight AI
Resolves company names and tickers to SEC CIKs.
"""

import logging
from typing import Optional
from .edgar_client import EdgarClient

logger = logging.getLogger(__name__)

class CompanyResolver:
    """
    Resolves company information to SEC CIKs using EDGAR APIs.

    Follows SEC fair access requirements and handles edge cases.
    """

    def __init__(self, edgar_client: EdgarClient):
        """
        Initialize the company resolver.

        Args:
            edgar_client (EdgarClient): SEC EDGAR client instance
        """
        self.edgar_client = edgar_client

    def resolve_cik(self, company_identifier: str) -> Optional[str]:
        """
        Resolve a company identifier (ticker or name) to CIK.

        Args:
            company_identifier (str): Company ticker symbol or full name

        Returns:
            str or None: CIK number if found, otherwise None
        """
        # Try resolving as ticker first
        cik = self.edgar_client.get_company_cik(company_identifier)

        if not cik:
            # Try resolving as company name
            cik = self.edgar_client.get_company_cik_by_name(company_identifier)

        return cik

    def get_company_info(self, company_identifier: str) -> Optional[dict]:
        """
        Get comprehensive company information including CIK.

        Args:
            company_identifier (str): Company ticker symbol or full name

        Returns:
            dict or None: Company information with CIK
        """
        cik = self.resolve_cik(company_identifier)

        if not cik:
            logger.warning(f"Could not resolve CIK for {company_identifier}")
            return None

        # For now, we'll just return the CIK - in a more advanced version
        # we might fetch full company information
        return {
            'ticker': company_identifier,
            'cik': cik
        }