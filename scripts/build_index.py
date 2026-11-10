"""Build the dense retrieval index for one embedding model.

Embeds every chunk in data/finsight.db, writes data/index/<model-slug>/, and — for
the model set in configs/retrieval.yaml — stores each embedding in
filing_chunks.embedding (float32 bytes).

Usage: uv run scripts/build_index.py [--model BAAI/bge-small-en-v1.5]
"""

import argparse
import sqlite3
import time

from finsight.retrieval.common import load_chunks, load_config
from finsight.retrieval.vector_retriever import build_index, index_dir_for, load_model


def main():
    cfg = load_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=cfg["embedding_model"], help="defaults to configs/retrieval.yaml")
    model_name = ap.parse_args().model

    chunks = load_chunks(cfg["db_path"])
    print(f"Loaded {len(chunks)} chunks from {cfg['db_path'].name}")

    t0 = time.time()
    model = load_model(model_name)
    print(f"Model: {model_name} (max {model.max_seq_length} tokens per chunk)")

    index_dir = index_dir_for(model_name, cfg)
    vecs = build_index(chunks, model, model_name, index_dir, cfg["embedding_batch_size"])
    print(f"Embedded {len(chunks)} chunks -> {vecs.shape} in {time.time() - t0:.1f}s")
    print(f"Index written to {index_dir}")

    if model_name != cfg["embedding_model"]:
        print("Not the configured model: SQLite embeddings left unchanged")
        return
    conn = sqlite3.connect(cfg["db_path"])
    for chunk, vec in zip(chunks, vecs):
        acc, sec, idx = chunk.key.split("|")
        conn.execute(
            "UPDATE filing_chunks SET embedding = ? WHERE accession_number = ? AND section_id = ? AND chunk_idx = ?",
            (vec.tobytes(), acc, sec, int(idx)),
        )
    conn.commit()
    conn.close()
    print("Embeddings stored in SQLite")


if __name__ == "__main__":
    main()
