"""
Unit tests for FinSight AI SEC ingestion components.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import os
import json
from pathlib import Path

# Add src to Python path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from finsight.ingestion.edgar_client import EdgarClient
from finsight.ingestion.company_resolver import CompanyResolver
from finsight.ingestion.filing_downloader import FilingDownloader
from finsight.ingestion.metadata_extractor import MetadataExtractor

class TestEdgarClient(unittest.TestCase):
    """Test the EdgarClient component."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = EdgarClient(user_agent="Test Agent", rate_limit=0.1)

    @patch('requests.Session.get')
    def test_get_company_cik_success(self, mock_get):
        """Test successful CIK resolution."""
        # Mock a response that contains CIK
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '<CIK>0000789019</CIK>'
        mock_get.return_value = mock_response

        cik = self.client.get_company_cik("MSFT")

        self.assertEqual(cik, "0000789019")

    @patch('requests.Session.get')
    def test_get_company_cik_failure(self, mock_get):
        """Test CIK resolution failure."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        cik = self.client.get_company_cik("INVALID")

        self.assertIsNone(cik)

    def test_rate_limiting(self):
        """Test that rate limiting works."""
        # This test just verifies the method exists and doesn't crash
        self.client._rate_limit()
        # No assertion needed as we're just testing it doesn't crash

class TestCompanyResolver(unittest.TestCase):
    """Test the CompanyResolver component."""

    def setUp(self):
        """Set up test fixtures."""
        mock_client = Mock(spec=EdgarClient)
        self.resolver = CompanyResolver(mock_client)

    @patch.object(EdgarClient, 'get_company_cik')
    def test_resolve_cik_success(self, mock_get_cik):
        """Test successful CIK resolution."""
        mock_get_cik.return_value = "0000789019"

        cik = self.resolver.resolve_cik("MSFT")

        self.assertEqual(cik, "0000789019")

    @patch.object(EdgarClient, 'get_company_cik')
    def test_resolve_cik_failure(self, mock_get_cik):
        """Test CIK resolution failure."""
        mock_get_cik.return_value = None

        cik = self.resolver.resolve_cik("INVALID")

        self.assertIsNone(cik)

class TestFilingDownloader(unittest.TestCase):
    """Test the FilingDownloader component."""

    def setUp(self):
        """Set up test fixtures."""
        mock_client = Mock(spec=EdgarClient)
        self.downloader = FilingDownloader(mock_client, cache_dir="test_cache")

    def test_is_cached(self):
        """Test caching logic - we'll just verify the method exists."""
        # This is a placeholder since we don't have actual files to check
        # But we can at least verify it doesn't crash with expected parameters
        result = self.downloader._is_cached("0000123456", "http://example.com")
        # Method should return boolean, but we're not testing file existence here

    def test_get_cache_filename(self):
        """Test cache filename generation."""
        filename = self.downloader._get_cache_filename("0000123456", "Microsoft Corporation")
        self.assertIsInstance(filename, str)

class TestMetadataExtractor(unittest.TestCase):
    """Test the MetadataExtractor component."""

    def setUp(self):
        """Set up test fixtures."""
        self.extractor = MetadataExtractor()

    def test_extract_metadata(self):
        """Test metadata extraction."""
        # Create sample HTML content (minimal for testing)
        html_content = "<html><body>Sample filing content</body></html>"

        metadata = self.extractor.extract_metadata(
            html_content=html_content,
            company_name="Microsoft Corporation",
            ticker="MSFT",
            cik="0000789019",
            accession_number="0000789019-23-000001",
            filing_date="2023-06-30",
            form_type="10-K",
            source_url="https://www.sec.gov/Archives/edgar/data/789019/000078901923000001/msft-2023-10-k.htm"
        )

        # Verify required fields are present
        self.assertEqual(metadata['company'], "Microsoft Corporation")
        self.assertEqual(metadata['ticker'], "MSFT")
        self.assertEqual(metadata['cik'], "0000789019")
        self.assertEqual(metadata['accession_number'], "0000789019-23-000001")
        self.assertEqual(metadata['filing_date'], "2023-06-30")
        self.assertEqual(metadata['form_type'], "10-K")
        self.assertIn('source_url', metadata)
        self.assertIsInstance(metadata['file_size'], int)

    @patch('builtins.open', new_callable=Mock)
    def test_save_manifest_success(self, mock_open):
        """Test successful manifest saving."""
        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file

        metadata = {
            'company': 'Microsoft Corporation',
            'accession_number': '0000789019-23-000001'
        }

        result = self.extractor.save_manifest(metadata, "test_dir")

        # Should return True for successful save
        self.assertTrue(result)

    @patch('builtins.open', side_effect=Exception("Test error"))
    def test_save_manifest_failure(self, mock_open):
        """Test manifest saving failure."""
        metadata = {
            'company': 'Microsoft Corporation',
            'accession_number': '0000789019-23-000001'
        }

        result = self.extractor.save_manifest(metadata, "test_dir")

        # Should return False for failed save
        self.assertFalse(result)

if __name__ == '__main__':
    unittest.main()