"""
Data-quality regression tests for finsight.db and the evaluation set.
Requires the DB to be built: .venv/bin/python scripts/extract_tables.py
"""

import json
import sqlite3
from pathlib import Path

import pytest

PROJECT = Path(__file__).parent.parent
DB = PROJECT / "data" / "finsight.db"
QUESTIONS = PROJECT / "data" / "evaluation" / "seed_questions.json"


@pytest.fixture(scope="module")
def conn():
    if not DB.exists():
        pytest.skip("finsight.db not built")
    c = sqlite3.connect(DB)
    yield c
    c.close()


@pytest.fixture(scope="module")
def questions():
    return json.loads(QUESTIONS.read_text())


def test_one_fact_per_company_metric_year(conn):
    """fiscal_year must label the period, not the filing, so each year maps to one value."""
    dupes = conn.execute("""
        SELECT ticker, concept, fiscal_year, COUNT(*) FROM financial_facts
        GROUP BY ticker, concept, fiscal_year HAVING COUNT(*) > 1
    """).fetchall()
    assert dupes == []


def test_restated_values_win(conn):
    """NVDA's 10:1 split (June 2024): later 10-Ks restate FY2024 diluted EPS from 11.93 to 1.19."""
    eps = conn.execute("""
        SELECT value FROM financial_facts
        WHERE ticker = 'NVDA' AND metric_label = 'EPS Diluted' AND fiscal_year = '2024'
    """).fetchone()[0]
    assert eps == pytest.approx(1.19)


def test_known_revenue_figures(conn):
    expected = {("MSFT", "2026"): 331839, ("AAPL", "2026"): 478834, ("NVDA", "2026"): 215938}
    for (ticker, fy), value in expected.items():
        got = conn.execute("""
            SELECT value FROM financial_facts
            WHERE ticker = ? AND metric_label = 'Revenue' AND fiscal_year = ?
        """, (ticker, fy)).fetchone()[0]
        assert got == value, (ticker, fy)


def test_question_set_shape(questions):
    assert len(questions) >= 30
    ids = [q["id"] for q in questions]
    assert len(ids) == len(set(ids))
    assert all(q["verified"] for q in questions)


def test_retrieval_questions_have_ground_truth(questions):
    for q in questions:
        if q["requires_retrieval"]:
            assert q["evidence"], f"{q['id']} needs evidence phrases"
            assert q["expected_chunks"], f"{q['id']} needs expected_chunks"


def test_expected_chunks_match_evidence(conn, questions):
    """expected_chunks must equal every chunk containing an evidence phrase.
    If this fails after re-chunking: uv run scripts/label_evidence.py"""
    from finsight.evaluation.labels import resolve_evidence

    for q in questions:
        if q.get("evidence"):
            keys, missing = resolve_evidence(conn, q["evidence"])
            assert not missing, f"{q['id']}: phrases not found {missing}"
            assert keys == q["expected_chunks"], q["id"]


def test_expected_chunks_exist(conn, questions):
    for q in questions:
        for key in q.get("expected_chunks", []):
            acc, section, idx = key.split("|")
            row = conn.execute("""
                SELECT 1 FROM filing_chunks
                WHERE accession_number = ? AND section_id = ? AND chunk_idx = ?
            """, (acc, section, int(idx))).fetchone()
            assert row, f"{q['id']}: chunk {key} not in DB"
