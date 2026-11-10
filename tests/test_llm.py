"""LLM client tests. Live tests skip when Ollama isn't running or the model isn't pulled."""

import pytest

from finsight.reasoning.llm import LLMClient, LLMUnavailable, load_llm_config


def test_config_has_safe_defaults():
    cfg = load_llm_config()
    assert cfg["num_ctx"] >= 8192, "Ollama's small default context silently truncates RAG prompts"
    assert cfg["temperature"] <= 0.3, "factual answers need a low temperature"


def test_missing_model_gives_actionable_error():
    client = LLMClient(model="definitely-not-a-model:1b")
    with pytest.raises(LLMUnavailable, match="ollama"):
        client.check()


@pytest.fixture(scope="module")
def llm():
    client = LLMClient()
    try:
        client.check()
    except LLMUnavailable as e:
        pytest.skip(str(e))
    return client


def test_live_chat(llm):
    r = llm.chat("What is 2+2? Answer with just the number.")
    assert "4" in r.text
    assert r.prompt_tokens > 0 and r.completion_tokens > 0
    assert r.model == llm.model
