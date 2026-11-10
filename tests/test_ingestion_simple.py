"""
Smoke tests for FinSight AI — checks that key files and DB output exist.
"""

import unittest
import sqlite3
from pathlib import Path

PROJECT = Path(__file__).parent.parent


class TestProjectStructure(unittest.TestCase):

    def test_scripts_exist(self):
        for f in [
            "scripts/ingest_filings.py",
            "scripts/extract_tables.py",
        ]:
            self.assertTrue((PROJECT / f).exists(), f"{f} missing")

    def test_parsing_modules_exist(self):
        for f in [
            "src/finsight/parsing/section_extractor.py",
            "src/finsight/parsing/xbrl_extractor.py",
            "src/finsight/parsing/chunker.py",
        ]:
            self.assertTrue((PROJECT / f).exists(), f"{f} missing")

    def test_sql_files_exist(self):
        for f in ["sql/schema.sql", "sql/queries.sql"]:
            self.assertTrue((PROJECT / f).exists(), f"{f} missing")

    def test_manifests_exist(self):
        manifests = list((PROJECT / "data" / "manifests").glob("*.json"))
        self.assertEqual(len(manifests), 9, f"Expected 9 manifests, found {len(manifests)}")

    def test_database_has_chunks(self):
        db = PROJECT / "data" / "finsight.db"
        self.assertTrue(db.exists(), "finsight.db missing")
        conn = sqlite3.connect(db)
        count = conn.execute("SELECT COUNT(*) FROM filing_chunks").fetchone()[0]
        conn.close()
        self.assertGreater(count, 0, "filing_chunks table is empty")

    def test_database_has_facts(self):
        db = PROJECT / "data" / "finsight.db"
        conn = sqlite3.connect(db)
        count = conn.execute("SELECT COUNT(*) FROM financial_facts").fetchone()[0]
        conn.close()
        self.assertGreater(count, 0, "financial_facts table is empty")


if __name__ == "__main__":
    unittest.main()
