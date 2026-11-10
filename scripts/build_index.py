"""Build the dense retrieval index.

Embeds every chunk in data/finsight.db with the model in configs/retrieval.yaml,
writes data/index/faiss.index + chunks.json, and stores each embedding in
filing_chunks.embedding (float32 bytes).

Usage: .venv/bin/python scripts/build_index.py
"""

import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from finsight.retrieval.common import load_chunks, load_config  # noqa: E402
from finsight.retrieval.vector_retriever import build_index, load_model  # noqa: E402


def main():
    cfg = load_config()
    chunks = load_chunks(cfg["db_path"])
    print(f"Loaded {len(chunks)} chunks from {cfg['db_path'].name}")

    t0 = time.time()
    model = load_model(cfg["embedding_model"])
    print(f"Model: {cfg['embedding_model']} (max {model.max_seq_length} tokens per chunk)")

    vecs = build_index(chunks, model, cfg["embedding_model"], cfg["index_dir"], cfg["embedding_batch_size"])
    print(f"Embedded {len(chunks)} chunks -> {vecs.shape} in {time.time() - t0:.1f}s")

    conn = sqlite3.connect(cfg["db_path"])
    for chunk, vec in zip(chunks, vecs):
        acc, sec, idx = chunk.key.split("|")
        conn.execute(
            "UPDATE filing_chunks SET embedding = ? WHERE accession_number = ? AND section_id = ? AND chunk_idx = ?",
            (vec.tobytes(), acc, sec, int(idx)),
        )
    conn.commit()
    conn.close()
    print(f"Index written to {cfg['index_dir']}; embeddings stored in SQLite")


if __name__ == "__main__":
    main()
