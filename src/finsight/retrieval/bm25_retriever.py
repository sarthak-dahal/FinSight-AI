"""BM25 keyword retriever over filing chunks.

Built in memory from SQLite on construction (milliseconds for ~1k chunks), so there
is no on-disk index to go stale.
"""

from __future__ import annotations

import numpy as np
from rank_bm25 import BM25Okapi

from finsight.retrieval.common import Chunk, SearchResult, load_chunks, load_config, matches, tokenize


class BM25Retriever:
    def __init__(self, chunks: list[Chunk] | None = None, k1: float | None = None, b: float | None = None):
        cfg = load_config()
        self.chunks = chunks if chunks is not None else load_chunks(cfg["db_path"])
        self.bm25 = BM25Okapi(
            [tokenize(c.indexed_text) for c in self.chunks],
            k1=k1 if k1 is not None else cfg["bm25"]["k1"],
            b=b if b is not None else cfg["bm25"]["b"],
        )

    def search(self, query: str, k: int = 10, ticker=None, fiscal_year=None, section_id=None) -> list[SearchResult]:
        scores = self.bm25.get_scores(tokenize(query))
        allowed = np.array([matches(c, ticker, fiscal_year, section_id) for c in self.chunks])
        scores = np.where(allowed, scores, -np.inf)
        order = np.argsort(-scores, kind="stable")[:k]
        return [
            SearchResult(self.chunks[i], float(scores[i]), rank)
            for rank, i in enumerate(order, start=1)
            if np.isfinite(scores[i])
        ]
