"""Hybrid retriever: Reciprocal Rank Fusion (RRF) of BM25 and vector results.

RRF score(chunk) = sum over retrievers of weight / (k_rrf + rank). It uses only ranks,
so BM25 scores (unbounded) and cosine similarities (0..1) never need normalising.
A chunk ranked well by both retrievers beats one ranked first by only one.
"""

from __future__ import annotations

from finsight.retrieval.bm25_retriever import BM25Retriever
from finsight.retrieval.common import SearchResult, load_config
from finsight.retrieval.vector_retriever import VectorRetriever


class HybridRetriever:
    def __init__(self, bm25: BM25Retriever | None = None, vector: VectorRetriever | None = None,
                 k_rrf: int | None = None, bm25_weight: float | None = None, vector_weight: float | None = None,
                 candidates: int | None = None):
        cfg = load_config().get("hybrid", {})
        self.bm25 = bm25 or BM25Retriever()
        self.vector = vector or VectorRetriever()
        self.k_rrf = k_rrf if k_rrf is not None else cfg.get("k_rrf", 60)
        self.weights = (bm25_weight if bm25_weight is not None else cfg.get("bm25_weight", 1.0),
                        vector_weight if vector_weight is not None else cfg.get("vector_weight", 1.0))
        self.candidates = candidates if candidates is not None else cfg.get("candidates", 50)

    def search(self, query: str, k: int = 10, ticker=None, fiscal_year=None, section_id=None) -> list[SearchResult]:
        filters = dict(ticker=ticker, fiscal_year=fiscal_year, section_id=section_id)
        fused: dict[str, float] = {}
        chunks = {}
        for retriever, weight in zip((self.bm25, self.vector), self.weights):
            for r in retriever.search(query, k=self.candidates, **filters):
                fused[r.chunk.key] = fused.get(r.chunk.key, 0.0) + weight / (self.k_rrf + r.rank)
                chunks[r.chunk.key] = r.chunk
        ranked = sorted(fused.items(), key=lambda kv: (-kv[1], kv[0]))[:k]
        return [SearchResult(chunks[key], score, rank) for rank, (key, score) in enumerate(ranked, start=1)]
