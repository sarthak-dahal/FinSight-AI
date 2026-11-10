"""Score retrievers against the labelled questions in data/evaluation/seed_questions.json.

For every question with `expected_chunks`, a retriever "hits" at k if any expected
chunk appears in its top k (chunks overlap by 80 words, so any one suffices).

Two modes:
  unfiltered — raw question only
  filtered   — also passes the question's ticker + fiscal_year as metadata filters
               (an upper bound on what a query parser extracting them could give)

Usage: uv run scripts/eval_retrieval.py [--retrievers bm25 vector] [--details]
"""

import argparse
import json
from pathlib import Path


PROJECT = Path(__file__).resolve().parent.parent
QUESTIONS = PROJECT / "data" / "evaluation" / "seed_questions.json"
KS = (1, 3, 5, 10)


def split(value):
    parts = [p.strip() for p in str(value).split(",") if p.strip()]
    return parts if len(parts) > 1 else (parts[0] if parts else None)


def first_hit_rank(results, expected):
    for r in results:
        if r.chunk.key in expected:
            return r.rank
    return None


def evaluate(retriever, questions, filtered):
    rows = []
    for q in questions:
        filters = {"ticker": split(q["company"]), "fiscal_year": split(q["fiscal_year"])} if filtered else {}
        results = retriever.search(q["question"], k=max(KS), **filters)
        rows.append({"id": q["id"], "rank": first_hit_rank(results, set(q["expected_chunks"])),
                     "top": results[0].chunk.key if results else None})
    n = len(rows)
    metrics = {f"hit@{k}": sum(1 for r in rows if r["rank"] and r["rank"] <= k) / n for k in KS}
    metrics["mrr@10"] = sum(1 / r["rank"] for r in rows if r["rank"]) / n
    return metrics, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--retrievers", nargs="+", default=["bm25", "vector", "hybrid"],
                    choices=["bm25", "vector", "hybrid"])
    ap.add_argument("--rrf-weights", nargs=2, type=float, metavar=("BM25", "VECTOR"), action="append",
                    help="extra hybrid variants with these weights (repeatable)")
    ap.add_argument("--models", nargs="+", default=None,
                    help="embedding models for the vector retriever (default: configs/retrieval.yaml)")
    ap.add_argument("--details", action="store_true", help="print per-question ranks")
    args = ap.parse_args()

    questions = [q for q in json.loads(QUESTIONS.read_text()) if q.get("expected_chunks")]
    print(f"{len(questions)} labelled questions\n")

    from finsight.retrieval.bm25_retriever import BM25Retriever
    from finsight.retrieval.hybrid_retriever import HybridRetriever
    from finsight.retrieval.vector_retriever import VectorRetriever

    bm25 = BM25Retriever()
    vectors = [VectorRetriever(m) for m in (args.models or [None])]
    short = lambda r: r.model_name.split("/")[-1][:18]  # noqa: E731

    retrievers = {}
    if "bm25" in args.retrievers:
        retrievers["bm25"] = bm25
    if "vector" in args.retrievers:
        for v in vectors:
            retrievers[short(v)] = v
    if "hybrid" in args.retrievers:
        for v in vectors:
            retrievers[f"hybrid+{short(v)[:9]}"] = HybridRetriever(bm25, v)
            for wb, wv in args.rrf_weights or []:
                retrievers[f"hyb{wb:g}:{wv:g}+{short(v)[:9]}"] = HybridRetriever(bm25, v, bm25_weight=wb, vector_weight=wv)

    width = max(10, *(len(n) + 2 for n in retrievers))
    header = f"{'retriever':<{width}}{'mode':<12}" + "".join(f"{m:>9}" for m in [*(f'hit@{k}' for k in KS), "mrr@10"])
    print(header)
    print("-" * len(header))
    details = {}
    for name, retriever in retrievers.items():
        for filtered in (False, True):
            mode = "filtered" if filtered else "unfiltered"
            metrics, rows = evaluate(retriever, questions, filtered)
            print(f"{name:<{width}}{mode:<12}" + "".join(f"{v:>9.2f}" for v in metrics.values()))
            details[(name, mode)] = rows

    if args.details:
        print("\nFirst rank of an expected chunk (- = not in top 10)")
        cols = list(details)
        print(f"{'id':<8}" + "".join(f"{n[:6] + '/' + m[:5]:>15}" for n, m in cols) + "  question")
        for i, q in enumerate(questions):
            ranks = "".join(f"{(details[c][i]['rank'] or '-'):>15}" for c in cols)
            print(f"{q['id']:<8}{ranks}  {q['question'][:70]}")


if __name__ == "__main__":
    main()
