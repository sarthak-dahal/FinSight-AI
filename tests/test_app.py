"""Headless tests for the Streamlit app. No LLM call is made: live-mode tests inject a prepared
answer into the chat history; demo-mode tests use data/demo/answers.json."""

import json
import subprocess
import sys

import pytest

from finsight.reasoning.answerer import Answer
from finsight.reasoning.financial_tools import Fact
from finsight.reasoning.llm import LLMClient, LLMResponse, LLMUnavailable
from finsight.reasoning.query_parser import parse_question
from finsight.retrieval.common import PROJECT_DIR, Chunk, SearchResult, load_config

APP = str(PROJECT_DIR / "app" / "streamlit_app.py")
DEMO_FILE = PROJECT_DIR / "data" / "demo" / "answers.json"


def live_available() -> bool:
    cfg = load_config()
    index = cfg["index_dir"] / cfg["embedding_model"].replace("/", "__") / "faiss.index"
    if not index.exists():
        return False
    try:
        LLMClient().check()
        return True
    except LLMUnavailable:
        return False


live = pytest.mark.skipif(not live_available(), reason="live mode needs the index and Ollama")
demo = pytest.mark.skipif(not DEMO_FILE.exists(), reason="no demo answers (scripts/build_demo.py)")


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


# --- live mode ---------------------------------------------------------------------------------

@live
def test_empty_page_shows_suggestion_chips():
    at = run_with([])
    assert not at.exception
    assert at.title[0].value.endswith("FinSight AI")
    chips = [p for p in at.pills if p.key == "suggestion"]
    assert chips and len(chips[0].options) == 4


@live
def test_answer_renders_with_sources_and_escaped_dollars():
    text = "Revenue rose $50.1 billion or 18% [C1] to $331,839 million [F1]."
    at = run_with([{"question": "What drove Microsoft's revenue growth?", "answer": fake_answer(text)}])
    assert not at.exception
    rendered = " ".join(m.value for m in at.markdown)
    assert r"\$50.1 billion" in rendered          # escaped, so not rendered as LaTeX
    assert "**[C1]**" in rendered                 # citation tags highlighted
    assert any("Sources cited (2)" in e.label for e in at.expander)
    assert not [p for p in at.pills if p.key == "suggestion"]  # chips hidden once chatting


@live
def test_abstention_renders_as_warning():
    at = run_with([{"question": "Revenue in FY2027?",
                    "answer": fake_answer("INSUFFICIENT EVIDENCE: no FY2027 data.", abstain=True)}])
    assert not at.exception
    assert at.warning and "INSUFFICIENT EVIDENCE" in at.warning[0].value


# --- demo mode ---------------------------------------------------------------------------------

@demo
def test_demo_mode_shows_pregenerated_answers(monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("FINSIGHT_DEMO", "1")
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception
    assert any("Demo mode" in (i.proto.title or "") for i in at.info)
    picker = at.selectbox(key="demo_question")
    assert len(picker.options) == len(json.loads(DEMO_FILE.read_text())["answers"])
    assert any(e.label.startswith("How this was answered") for e in at.expander)

    # Switching question renders that answer
    picker.select_index(len(picker.options) - 1).run()
    assert not at.exception
    last_question = json.loads(DEMO_FILE.read_text())["answers"][-1]["question"]
    assert any(m.value == last_question.replace("$", r"\$") for m in at.markdown)


@demo
def test_demo_mode_filters_by_question_type(monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("FINSIGHT_DEMO", "1")
    at = AppTest.from_file(APP, default_timeout=120).run()
    at.pills(key="demo_types").set_value(["unanswerable"]).run()
    assert not at.exception
    assert len(at.selectbox(key="demo_question").options) == 2


@demo
def test_demo_mode_never_loads_heavy_dependencies():
    """Demo mode must run without torch/faiss/the DB so it can be hosted cheaply.
    Run in a fresh process: other tests in this session have already imported torch."""
    code = f"""
import os, sys
os.environ["FINSIGHT_DEMO"] = "1"
from streamlit.testing.v1 import AppTest
at = AppTest.from_file({APP!r}, default_timeout=120).run()
assert not at.exception, at.exception
heavy = [m for m in ("torch", "faiss", "sentence_transformers", "rank_bm25") if m in sys.modules]
print("HEAVY:", heavy)
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stderr[-2000:]
    assert "HEAVY: []" in out.stdout, out.stdout
