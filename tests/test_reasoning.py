"""Tests for the deterministic parts of answering: parser, financial tools, citations, scoring.
No LLM needed."""

from types import SimpleNamespace

import pytest

from finsight.evaluation.answer_scoring import extract_numbers, figure_found, score_answer
from finsight.reasoning.answerer import extract_citations
from finsight.reasoning.query_parser import parse_question


# --- query parser ---------------------------------------------------------------------------

@pytest.mark.parametrize("question, tickers, years, metrics", [
    ("What was Nvidia's operating margin in fiscal year 2026?", ["NVDA"], ["2026"], ["operating_margin"]),
    ("How did Microsoft's capital expenditures change from fiscal year 2024 to fiscal year 2026?",
     ["MSFT"], ["2024", "2026"], ["Capital Expenditures"]),
    ("Compare the operating margins of Nvidia, Microsoft, and Apple", ["MSFT", "AAPL", "NVDA"], [], ["operating_margin"]),
    ("How much did Nvidia spend on research and development in FY26, and what percentage of revenue does that represent?",
     ["NVDA"], ["2026"], ["R&D Expense"]),
    ("How did Apple's iPhone sales perform in fiscal year 2026?", ["AAPL"], ["2026"], []),
])
def test_parse_question(question, tickers, years, metrics):
    p = parse_question(question)
    assert p.tickers == tickers
    assert p.fiscal_years == years
    assert p.metrics == metrics


def test_parse_latest_and_narrative():
    p = parse_question("What risks does Apple describe in its most recent annual report?")
    assert p.wants_latest and p.is_narrative and not p.is_numeric


def test_derived_metrics_expand_to_inputs():
    assert parse_question("Nvidia gross margin").stored_metrics == ["Gross Profit", "Revenue"]


# --- financial tools ------------------------------------------------------------------------

@pytest.fixture(scope="module")
def data():
    from finsight.reasoning.financial_tools import FinancialData
    from finsight.retrieval.common import load_config

    if not load_config()["db_path"].exists():
        pytest.skip("finsight.db not built")
    return FinancialData()


def facts_for(question, data):
    from finsight.reasoning.financial_tools import compute_facts
    return compute_facts(parse_question(question), data)


def test_margin_is_computed_not_stored(data):
    facts, _ = facts_for("What was Nvidia's operating margin in fiscal year 2026?", data)
    fy26 = next(f for f in facts if "FY2026" in f.statement and "Operating margin:" in f.statement)
    assert fy26.value == pytest.approx(60.38, abs=0.01)
    assert fy26.sources == ["0001045810-26-000021"]


def test_growth_between_requested_years(data):
    facts, _ = facts_for("How did Nvidia's revenue change between fiscal year 2024 and fiscal year 2026?", data)
    growth = next(f for f in facts if "change FY2024 to FY2026" in f.statement)
    assert growth.value == pytest.approx(254.45, abs=0.01)


def test_single_year_includes_prior_year(data):
    facts, _ = facts_for("What was Apple's R&D in fiscal year 2026?", data)
    assert any("FY2025" in f.statement for f in facts)
    assert any("change FY2025 to FY2026" in f.statement for f in facts)


def test_future_year_produces_note(data):
    _, notes = facts_for("What will Nvidia's revenue be in fiscal year 2027?", data)
    assert any("2027" in n for n in notes)


# --- citations & scoring --------------------------------------------------------------------

def test_extract_citations_handles_groups():
    text = "Revenue rose [C1, C3] to $331,839 million [F2; F1]. Margin [F4]."
    assert extract_citations(text) == [("C", "1"), ("C", "3"), ("F", "2"), ("F", "1"), ("F", "4")]


@pytest.mark.parametrize("text, target, found", [
    ("Revenue was $215.9 billion", {"value": 215938, "kind": "usd_millions"}, True),
    ("Revenue was $215,938 million", {"value": 215938, "kind": "usd_millions"}, True),
    ("a margin of 60.4%", {"value": 60.4, "kind": "percent"}, True),
    ("a margin of 61.0%", {"value": 60.4, "kind": "percent"}, False),
    ("up 6.3 percentage points", {"value": 6.3, "kind": "number"}, True),
    ("diluted EPS of $1.19", {"value": 1.19, "kind": "number"}, True),
    ("revenue grew 60.4 million", {"value": 60.4, "kind": "percent"}, False),
])
def test_figure_matching(text, target, found):
    assert figure_found(target, extract_numbers(text)) is found


def fake_answer(text, citations=(), cited_chunks=(), passages=()):
    return SimpleNamespace(text=text, citations=list(citations), invalid_citations=[],
                           cited_chunks=list(cited_chunks), passages=list(passages),
                           abstained=text.upper().startswith("INSUFFICIENT EVIDENCE"))


def test_scoring_unanswerable_requires_abstention():
    q = {"unanswerable": True, "key_figures": []}
    assert score_answer(q, fake_answer("INSUFFICIENT EVIDENCE: no FY2027 data."))["passed"]
    assert not score_answer(q, fake_answer("Revenue will be $300 billion [F1].", ["F1"]))["passed"]


def test_scoring_requires_all_figures_and_citation():
    q = {"key_figures": [{"value": 60.4, "kind": "percent"}]}
    assert score_answer(q, fake_answer("Margin was 60.4% [F2].", ["F2"]))["passed"]
    assert not score_answer(q, fake_answer("Margin was 60.4%."))["passed"]           # no citation
    assert not score_answer(q, fake_answer("Margin was 58.0% [F2].", ["F2"]))["passed"]  # wrong figure


def test_most_recent_uses_only_latest_year(data):
    """Regression (eval sq_017): with the prior year also present, the LLM quoted FY2025 margins."""
    facts, _ = facts_for("Compare the operating margins of Nvidia, Microsoft, and Apple in their most recent fiscal year.", data)
    assert facts and all("FY2025" not in f.statement for f in facts)
    assert {f.statement.split()[0] for f in facts} == {"NVDA", "MSFT", "AAPL"}


@pytest.mark.parametrize("question, has_revenue", [
    ("How fast did Microsoft's Azure and other cloud services revenue grow?", False),  # eval sq_021
    ("How did Nvidia's data center revenue grow?", False),
    ("How much did iPhone net sales grow?", False),
    ("What was Apple's revenue in FY2026?", True),
    ("What was Nvidia's total revenue?", True),
    ("Revenue of Microsoft in 2025?", True),
    ("What was Microsoft and Apple revenue?", True),
])
def test_segment_revenue_is_not_company_revenue(question, has_revenue):
    assert ("Revenue" in parse_question(question).metrics) is has_revenue


def test_figure_accepts_filing_rounding():
    target = {"value": 32.5, "kind": "percent", "accept": [32]}
    assert figure_found(target, extract_numbers("R&D grew 32% [C1]"))
    assert not figure_found(target, extract_numbers("R&D grew 30% [C1]"))
