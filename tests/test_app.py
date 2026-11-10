"""Headless tests for the Streamlit app (no LLM call: a prepared answer is injected)."""

import pytest

from finsight.reasoning.answerer import Answer
from finsight.reasoning.financial_tools import Fact
from finsight.reasoning.llm import LLMResponse
from finsight.reasoning.query_parser import parse_question
from finsight.retrieval.common import PROJECT_DIR, Chunk, SearchResult, load_config

APP = str(PROJECT_DIR / "app" / "streamlit_app.py")


@pytest.fixture(autouse=True)
def needs_index():
    from finsight.retrieval.vector_retriever import index_dir_for

    if not (index_dir_for(load_config()["embedding_model"]) / "faiss.index").exists():
        pytest.skip("index not built")


def fake_answer(text, abstain=False):
    chunk = Chunk("0001193125-26-323660|7|3", "MICROSOFT CORP", "MSFT", "2026", "7",
                  "Revenue increased $50.1 billion or 18% driven by growth in Microsoft Cloud.")
    q = "What drove Microsoft's revenue growth in fiscal year 2026?"
    return Answer(
        question=q, text=text, parsed=parse_question(q),
        facts=[Fact("MSFT FY2026 Revenue: $331,839 million", 331839, "usd_millions", ["0001193125-26-323660"])],
        passages=[SearchResult(chunk, 0.03, 1)], notes=[],
        citations=[] if abstain else ["C1", "F1"],
        llm=LLMResponse(text, "gemma3:27b", 3800, 80, 30.0), seconds=31.0,
    )


def run_with(history):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["history"] = history
    return at.run()


def test_empty_page_shows_examples():
    at = run_with([])
    assert not at.exception
    assert at.title[0].value.endswith("FinSight AI")
    assert len([b for b in at.button if b.key and b.key.startswith("ex")]) == 4


def test_answer_renders_with_sources_and_escaped_dollars():
    text = "Revenue rose $50.1 billion or 18% [C1] to $331,839 million [F1]."
    at = run_with([{"question": "What drove Microsoft's revenue growth?", "answer": fake_answer(text)}])
    assert not at.exception
    rendered = " ".join(m.value for m in at.markdown)
    assert r"\$50.1 billion" in rendered          # escaped, so not rendered as LaTeX
    assert "**[C1]**" in rendered                 # citation tags highlighted
    assert any("Sources cited (2)" in e.label for e in at.expander)


def test_abstention_renders_as_warning():
    at = run_with([{"question": "Revenue in FY2027?",
                    "answer": fake_answer("INSUFFICIENT EVIDENCE: no FY2027 data.", abstain=True)}])
    assert not at.exception
    assert at.warning and "INSUFFICIENT EVIDENCE" in at.warning[0].value
