"""Dense vector retriever: Sentence Transformers embeddings + FAISS inner-product index.

Embeddings are L2-normalised, so inner product == cosine similarity.
Each model gets its own index folder (written by scripts/build_index.py):
    data/index/<model-slug>/faiss.index   — FAISS IndexFlatIP
    data/index/<model-slug>/chunks.json   — chunk keys in index order + model settings
"""

from __future__ import annotations

import json
from pathlib import Path

# torch MUST be imported before faiss: both bundle an OpenMP runtime, and on macOS
# loading faiss's first makes torch segfault (exit 139) during model.encode().
import torch  # noqa: F401
import faiss
import numpy as np

from finsight.retrieval.common import Chunk, SearchResult, load_chunks, load_config, matches

INDEX_FILE = "faiss.index"
META_FILE = "chunks.json"

# Some retrieval models are trained with an instruction prepended to queries (not passages).
QUERY_PREFIXES = {
    "BAAI/bge-small-en-v1.5": "Represent this sentence for searching relevant passages: ",
    "BAAI/bge-base-en-v1.5": "Represent this sentence for searching relevant passages: ",
}


def index_dir_for(model_name: str, cfg: dict | None = None) -> Path:
    cfg = cfg or load_config()
    return cfg["index_dir"] / model_name.replace("/", "__")


def load_model(model_name: str):
    from sentence_transformers import SentenceTransformer  # slow import; only when needed
    return SentenceTransformer(model_name, device="cpu")


def embed(model, texts: list[str], batch_size: int = 32) -> np.ndarray:
    vecs = model.encode(texts, batch_size=batch_size, normalize_embeddings=True,
                        convert_to_numpy=True, show_progress_bar=len(texts) > 100)
    return vecs.astype("float32")


def build_index(chunks: list[Chunk], model, model_name: str, index_dir: Path, batch_size: int = 32) -> np.ndarray:
    """Embed all chunks, write the FAISS index + metadata. Returns the embedding matrix."""
    vecs = embed(model, [c.indexed_text for c in chunks], batch_size)
    index = faiss.IndexFlatIP(vecs.shape[1])
    index.add(vecs)
    index_dir.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(index_dir / INDEX_FILE))
    (index_dir / META_FILE).write_text(json.dumps({
        "model": model_name,
        "dim": int(vecs.shape[1]),
        "max_seq_length": int(model.max_seq_length),
        "query_prefix": QUERY_PREFIXES.get(model_name, ""),
        "keys": [c.key for c in chunks],
    }))
    return vecs


class VectorRetriever:
    def __init__(self, model_name: str | None = None, model=None):
        cfg = load_config()
        model_name = model_name or cfg["embedding_model"]
        index_dir = index_dir_for(model_name, cfg)
        if not (index_dir / INDEX_FILE).exists():
            raise FileNotFoundError(
                f"No index for {model_name} in {index_dir}. Run: uv run scripts/build_index.py --model {model_name}"
            )

        meta = json.loads((index_dir / META_FILE).read_text())
        self.model_name = meta["model"]
        self.query_prefix = meta.get("query_prefix", "")
        self.index = faiss.read_index(str(index_dir / INDEX_FILE))
        by_key = {c.key: c for c in load_chunks(cfg["db_path"])}
        missing = [k for k in meta["keys"] if k not in by_key]
        if missing or len(by_key) != len(meta["keys"]):
            raise RuntimeError("Index is out of sync with the DB; rebuild it with scripts/build_index.py.")
        self.chunks = [by_key[k] for k in meta["keys"]]
        self.model = model or load_model(self.model_name)

    def search(self, query: str, k: int = 10, ticker=None, fiscal_year=None, section_id=None) -> list[SearchResult]:
        qvec = embed(self.model, [self.query_prefix + query])
        # Flat index over ~1k vectors: score everything, then filter. Exact and fast.
        scores, ids = self.index.search(qvec, self.index.ntotal)
        results = []
        for score, i in zip(scores[0], ids[0]):
            chunk = self.chunks[i]
            if matches(chunk, ticker, fiscal_year, section_id):
                results.append(SearchResult(chunk, float(score), len(results) + 1))
                if len(results) == k:
                    break
        return results
