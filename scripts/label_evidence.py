"""Regenerate `expected_chunks` in seed_questions.json from each question's `evidence`.

Run after rebuilding the DB with a different chunker. Fails if a phrase is not found.

Usage: uv run scripts/label_evidence.py [--check]
"""

import argparse
import json
import sqlite3
import sys

from finsight.evaluation.labels import resolve_evidence
from finsight.retrieval.common import PROJECT_DIR, load_config

QUESTIONS = PROJECT_DIR / "data" / "evaluation" / "seed_questions.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report differences without writing")
    args = ap.parse_args()

    questions = json.loads(QUESTIONS.read_text())
    conn = sqlite3.connect(load_config()["db_path"])
    changed, errors = 0, 0
    for q in questions:
        if not q.get("evidence"):
            continue
        keys, missing = resolve_evidence(conn, q["evidence"])
        for item in missing:
            print(f"ERROR {q['id']}: phrase not found in {item['filing']}: {item['text']!r}")
            errors += 1
        if keys != q.get("expected_chunks"):
            print(f"{q['id']}: {q.get('expected_chunks')} -> {keys}")
            q["expected_chunks"] = keys
            changed += 1

    print(f"{changed} questions changed, {errors} missing phrases")
    if errors:
        sys.exit(1)
    if changed and not args.check:
        QUESTIONS.write_text(json.dumps(questions, indent=2, ensure_ascii=False) + "\n")
        print(f"Wrote {QUESTIONS.name}")
    elif changed:
        sys.exit(1)


if __name__ == "__main__":
    main()
