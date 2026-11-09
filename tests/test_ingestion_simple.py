"""
Simple unit tests for FinSight AI SEC ingestion components.
"""

import unittest
from pathlib import Path
import sys

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

class TestIngestionStructure(unittest.TestCase):
    """Test that all required files exist."""

    def test_module_files_exist(self):
        """Test that all ingestion module files exist."""
        expected_files = [
            'src/finsight/ingestion/__init__.py',
            'src/finsight/ingestion/edgar_client.py',
            'src/finsight/ingestion/company_resolver.py',
            'src/finsight/ingestion/filing_downloader.py',
            'src/finsight/ingestion/metadata_extractor.py'
        ]

        for file_path in expected_files:
            self.assertTrue(Path(file_path).exists(), f"File {file_path} does not exist")

    def test_script_exists(self):
        """Test that the main script exists."""
        script_path = 'scripts/ingest_filings.py'
        self.assertTrue(Path(script_path).exists(), "Main ingestion script does not exist")

if __name__ == '__main__':
    unittest.main()