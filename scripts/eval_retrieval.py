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
    ap.add_argument("--retrievers", nargs="+", default=["bm25", "vector"], choices=["bm25", "vector"])
    ap.add_argument("--details", action="store_true", help="print per-question ranks")
    args = ap.parse_args()

    questions = [q for q in json.loads(QUESTIONS.read_text()) if q.get("expected_chunks")]
    print(f"{len(questions)} labelled questions\n")

    retrievers = {}
    if "bm25" in args.retrievers:
        from finsight.retrieval.bm25_retriever import BM25Retriever
        retrievers["bm25"] = BM25Retriever()
    if "vector" in args.retrievers:
        from finsight.retrieval.vector_retriever import VectorRetriever
        retrievers["vector"] = VectorRetriever()

    header = f"{'retriever':<10}{'mode':<12}" + "".join(f"{m:>9}" for m in [*(f'hit@{k}' for k in KS), "mrr@10"])
    print(header)
    print("-" * len(header))
    details = {}
    for name, retriever in retrievers.items():
        for filtered in (False, True):
            mode = "filtered" if filtered else "unfiltered"
            metrics, rows = evaluate(retriever, questions, filtered)
            print(f"{name:<10}{mode:<12}" + "".join(f"{v:>9.2f}" for v in metrics.values()))
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
