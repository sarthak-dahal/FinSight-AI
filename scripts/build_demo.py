"""Pre-generate answers for demo mode (no live model needed to view them).

Runs the real pipeline on every question in seed_questions.json and saves the complete
results, plus each answer's evaluation verdict, to data/demo/answers.json.
Needs Ollama; ~9 min with gemma3:27b.

Usage:
  uv run scripts/build_demo.py [--model gemma3:27b]
  uv run scripts/build_demo.py --rescore      # re-grade the saved answers only (no LLM)
"""

import argparse
import json
import time
from datetime import date

from finsight.demo import DEMO_FILE, answer_from_dict, answer_to_dict, save_demo
from finsight.evaluation.answer_scoring import score_answer
from finsight.retrieval.common import PROJECT_DIR, load_config

QUESTIONS = PROJECT_DIR / "data" / "evaluation" / "seed_questions.json"


def verdict(question: dict, answer) -> dict:
    """Short, human-readable evaluation result shown next to each demo answer."""
    s = score_answer(question, answer)
    if s["passed"]:
        return {"passed": True, "reason": "Passed all automatic checks"}
    if not s["abstain_ok"]:
        reason = ("Declined to answer although the retrieved passages contain the answer"
                  if answer.abstained else "Answered a question that should have been declined")
    elif s["figures"] is not None and s["figures"] < 1:
        reason = f"Missing key figures: {', '.join(map(str, s['missing_figures']))}"
    else:
        reason = "No valid citation"
    return {"passed": False, "reason": reason}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model")
    ap.add_argument("--rescore", action="store_true", help="re-grade saved answers without the LLM")
    args = ap.parse_args()

    questions = {q["id"]: q for q in json.loads(QUESTIONS.read_text())}

    if args.rescore:
        saved = json.loads(DEMO_FILE.read_text())
        for e in saved["answers"]:
            e["evaluation"] = verdict(questions[e["id"]], answer_from_dict(e))
        saved["info"]["passed"] = sum(e["evaluation"]["passed"] for e in saved["answers"])
        save_demo(saved["answers"], saved["info"])
        print(f"Re-scored: {saved['info']['passed']}/{len(saved['answers'])} passed")
        return

    from finsight.reasoning.answerer import Answerer
    from finsight.reasoning.llm import LLMClient

    answerer = Answerer(llm=LLMClient(model=args.model))
    answerer.llm.check()
    entries, t0 = [], time.time()
    for i, q in enumerate(questions.values(), 1):
        a = answerer.ask(q["question"])
        entries.append(answer_to_dict(a, {"id": q["id"], "answer_type": q["answer_type"],
                                          "evaluation": verdict(q, a)}))
        print(f"[{i:>2}/{len(questions)}] {a.seconds:5.1f}s {q['id']} {q['question'][:70]}", flush=True)

    save_demo(entries, {
        "model": answerer.llm.model,
        "generated": date.today().isoformat(),
        "embedding_model": load_config()["embedding_model"],
        "questions": len(entries),
        "passed": sum(e["evaluation"]["passed"] for e in entries),
        "avg_seconds": round(sum(e["seconds"] for e in entries) / len(entries), 1),
    })
    print(f"\nSaved {len(entries)} answers to {DEMO_FILE.relative_to(PROJECT_DIR)} in {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()
