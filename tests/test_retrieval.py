"""
Tests for the BM25 and vector retrievers.
Needs the DB (scripts/extract_tables.py); vector tests also need the index (scripts/build_index.py).
"""

import pytest

from finsight.retrieval.common import CONFIG_PATH, load_config, tokenize


def test_tokenize_strips_possessives_and_stopwords():
    assert tokenize("Microsoft's Azure revenue") == ["microsoft", "azure", "revenue"]
    assert tokenize("NVIDIA’s growth was 41%") == ["nvidia", "growth", "41"]


def test_config_loads():
    cfg = load_config()
    assert CONFIG_PATH.exists()
    assert cfg["embedding_model"]
    assert cfg["db_path"].name == "finsight.db"


@pytest.fixture(scope="module")
def bm25():
    if not load_config()["db_path"].exists():
        pytest.skip("finsight.db not built")
    from finsight.retrieval.bm25_retriever import BM25Retriever
    return BM25Retriever()


@pytest.fixture(scope="module")
def vector():
    from finsight.retrieval.vector_retriever import VectorRetriever, index_dir_for

    if not (index_dir_for(load_config()["embedding_model"]) / "faiss.index").exists():
        pytest.skip("index not built (uv run scripts/build_index.py)")
    return VectorRetriever()


@pytest.fixture(scope="module")
def hybrid(bm25, vector):
    from finsight.retrieval.hybrid_retriever import HybridRetriever
    return HybridRetriever(bm25, vector)


@pytest.mark.parametrize("name", ["bm25", "vector", "hybrid"])
def test_filters_are_respected(name, request):
    retriever = request.getfixturevalue(name)
    results = retriever.search("revenue growth drivers", k=10, ticker="AAPL", fiscal_year="2025", section_id="7")
    assert results
    assert all(r.chunk.ticker == "AAPL" and r.chunk.fiscal_year == "2025" and r.chunk.section_id == "7"
               for r in results)


@pytest.mark.parametrize("name", ["bm25", "vector", "hybrid"])
def test_list_filters(name, request):
    retriever = request.getfixturevalue(name)
    results = retriever.search("operating margin", k=30, ticker=["NVDA", "MSFT"])
    assert {r.chunk.ticker for r in results} <= {"NVDA", "MSFT"}


@pytest.mark.parametrize("name", ["bm25", "vector", "hybrid"])
def test_ranks_and_scores_are_ordered(name, request):
    results = request.getfixturevalue(name).search("cybersecurity governance board", k=5)
    assert [r.rank for r in results] == [1, 2, 3, 4, 5]
    assert all(a.score >= b.score for a, b in zip(results, results[1:]))


def test_bm25_known_answer(bm25):
    """sq_027: the Greater China figure lives in AAPL FY2026 MD&A chunk 2."""
    results = bm25.search("How did Apple's Greater China sales change?", k=3, ticker="AAPL", fiscal_year="2026")
    assert "0000320193-26-000026|7|2" in [r.chunk.key for r in results]


def test_vector_index_matches_db(vector, bm25):
    assert vector.index.ntotal == len(bm25.chunks)


def test_vector_known_answer(vector):
    """sq_025: MSFT board cybersecurity oversight, Item 1C."""
    results = vector.search("How does Microsoft's board oversee cybersecurity risk?", k=3,
                            ticker="MSFT", fiscal_year="2026")
    assert "0001193125-26-323660|1C|0" in [r.chunk.key for r in results]


def test_hybrid_fuses_both_retrievers(hybrid):
    """A chunk found by both retrievers should outrank one found by only one."""
    results = hybrid.search("How does Microsoft's board oversee cybersecurity risk?", k=5,
                            ticker="MSFT", fiscal_year="2026")
    assert results[0].chunk.key in {"0001193125-26-323660|1C|0", "0001193125-26-323660|1C|1"}  # sq_025 labels
    assert results[0].score > 1 / 61  # more than a single first-place vote


def test_vector_refuses_missing_index():
    from finsight.retrieval.vector_retriever import VectorRetriever

    with pytest.raises(FileNotFoundError):
        VectorRetriever("not-a-real/model")
