"""
SEC EDGAR API Client for FinSight AI
Handles communication with SEC EDGAR APIs following fair access policies.
"""

import time
import json
import logging
from typing import Optional, Dict, List
import requests
from requests.adapters import HTTPAdapter
from urllib.parse import quote

logger = logging.getLogger(__name__)

class EdgarClient:
    """
    Client for accessing SEC EDGAR data following fair access requirements.

    Uses official SEC endpoints and proper User-Agent headers.
    Implements rate limiting and retry logic.
    """

    def __init__(self, user_agent: str = "FinSight AI Research Project sardahal@github.com - For educational purposes",
                 rate_limit: float = 1.0):
        """
        Initialize the SEC EDGAR client.

        Args:
            user_agent (str): User-Agent string following SEC requirements
            rate_limit (float): Minimum seconds between requests (default: 1.0)
        """
        self.user_agent = user_agent
        self.rate_limit = rate_limit

        # Create session with retry strategy
        self.session = requests.Session()
        adapter = HTTPAdapter(max_retries=3)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

        # Track last request time for rate limiting
        self._last_request_time = 0

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time

        if time_since_last < self.rate_limit:
            sleep_time = self.rate_limit - time_since_last
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)

        self._last_request_time = time.time()

    def _make_request(self, url: str, params: Optional[Dict] = None) -> requests.Response:
        """
        Make a request to SEC EDGAR API with rate limiting and error handling.

        Args:
            url (str): The URL to request
            params (dict, optional): Query parameters

        Returns:
            requests.Response: The HTTP response

        Raises:
            requests.RequestException: If the request fails
        """
        self._rate_limit()

        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'application/json'
        }

        try:
            response = self.session.get(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            logger.error(f"Request failed for {url}: {str(e)}")
            raise

    def get_company_cik(self, ticker: str) -> Optional[str]:
        """
        Resolve company ticker to CIK using SEC's company search API.

        Args:
            ticker (str): Company ticker symbol

        Returns:
            str or None: CIK number if found, otherwise None
        """
        # SEC company search endpoint
        url = "https://www.sec.gov/cgi-bin/browse-edgar"

        params = {
            'action': 'getcompany',
            'CIK': ticker,
            'output': 'xml'
        }

        try:
            response = self._make_request(url, params)

            # Parse XML to extract CIK (simplified approach for now)
            # In a production environment, we'd use xml.etree.ElementTree or lxml
            if response.status_code == 200 and 'CIK' in response.text:
                # This is a simplified extraction - real implementation would parse XML properly
                logger.info(f"Found company information for ticker {ticker}")
                return self._extract_cik_from_response(response.text)
            else:
                logger.warning(f"No CIK found for ticker {ticker}")
                return None

        except Exception as e:
            logger.error(f"Error resolving CIK for ticker {ticker}: {str(e)}")
            return None

    def get_company_cik_by_name(self, company_name: str) -> Optional[str]:
        """
        Resolve company name to CIK using SEC's company search API.

        Args:
            company_name (str): Company name

        Returns:
            str or None: CIK number if found, otherwise None
        """
        url = "https://www.sec.gov/cgi-bin/browse-edgar"

        params = {
            'action': 'getcompany',
            'company': company_name,
            'output': 'xml'
        }

        try:
            response = self._make_request(url, params)

            if response.status_code == 200 and 'CIK' in response.text:
                logger.info(f"Found company information for name {company_name}")
                return self._extract_cik_from_response(response.text)
            else:
                logger.warning(f"No CIK found for company name {company_name}")
                return None

        except Exception as e:
            logger.error(f"Error resolving CIK for company {company_name}: {str(e)}")
            return None

    def _extract_cik_from_response(self, response_text: str) -> Optional[str]:
        """
        Extract CIK from SEC response (simplified implementation).

        Args:
            response_text (str): Response text from SEC

        Returns:
            str or None: CIK number if found
        """
        # This is a placeholder for proper XML parsing
        # In practice, we'd parse the XML properly to extract CIK
        import re

        cik_match = re.search(r'CIK>(\d+)<', response_text)
        if cik_match:
            return cik_match.group(1)

        return None

    def get_company_filing_history(self, cik: str) -> Optional[List[Dict]]:
        """
        Get filing history for a company using SEC submissions API.

        Args:
            cik (str): Company CIK

        Returns:
            list of dict: Filing information or None if error
        """
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"

        try:
            response = self._make_request(url)
            data = response.json()

            # Extract relevant filing information
            filings = []
            if 'filings' in data and 'recent' in data['filings']:
                for filing in data['filings']['recent']:
                    # Only include 10-K filings, excluding amendments (10-K/A)
                    if filing.get('form') == '10-K' and not filing.get('fileNumber', '').endswith('/A'):
                        filings.append({
                            'accession_number': filing.get('accessionNumber'),
                            'filing_date': filing.get('filingDate'),
                            'form': filing.get('form'),
                            'primary_document': filing.get('primaryDocument'),
                            'url': f"https://www.sec.gov/Archives/edgar/data/{cik}/{filing['accessionNumber'].replace('-', '')}/{filing.get('primaryDocument')}"
                        })

            return filings

        except Exception as e:
            logger.error(f"Error fetching filing history for CIK {cik}: {str(e)}")
            return None

    def download_filing(self, url: str, filename: str) -> bool:
        """
        Download a filing HTML document from SEC EDGAR.

        Args:
            url (str): URL of the filing to download
            filename (str): Local filename to save the filing

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            response = self._make_request(url)

            # Save the raw HTML content
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(response.text)

            logger.info(f"Filing downloaded successfully to {filename}")
            return True

        except Exception as e:
            logger.error(f"Error downloading filing from {url}: {str(e)}")
            return False