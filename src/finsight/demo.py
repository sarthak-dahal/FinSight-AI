"""Demo mode: save fully rendered answers to JSON and load them back.

data/demo/answers.json is self-contained (answer text, facts, passage text, parse, model info),
so the app can show real pipeline output with no Ollama, database, or search index.
Build it with: uv run scripts/build_demo.py

This module deliberately imports nothing heavy (no torch/faiss/DB) so a demo-only deployment stays small.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from finsight.reasoning.answerer import Answer
from finsight.reasoning.financial_tools import Fact
from finsight.reasoning.llm import LLMResponse
from finsight.reasoning.query_parser import ParsedQuery
from finsight.retrieval.common import PROJECT_DIR, Chunk, SearchResult

DEMO_FILE = PROJECT_DIR / "data" / "demo" / "answers.json"


def answer_to_dict(a: Answer, meta: dict | None = None) -> dict:
    return {
        **(meta or {}),
        "question": a.question,
        "text": a.text,
        "parsed": asdict(a.parsed),
        "facts": [asdict(f) for f in a.facts],
        "passages": [{"chunk": asdict(r.chunk), "score": r.score, "rank": r.rank} for r in a.passages],
        "notes": a.notes,
        "citations": a.citations,
        "invalid_citations": a.invalid_citations,
        "llm": asdict(a.llm) if a.llm else None,
        "seconds": a.seconds,
    }


def answer_from_dict(d: dict) -> Answer:
    return Answer(
        question=d["question"],
        text=d["text"],
        parsed=ParsedQuery(**d["parsed"]),
        facts=[Fact(**f) for f in d["facts"]],
        passages=[SearchResult(Chunk(**p["chunk"]), p["score"], p["rank"]) for p in d["passages"]],
        notes=d["notes"],
        citations=d["citations"],
        invalid_citations=d["invalid_citations"],
        llm=LLMResponse(**d["llm"]) if d.get("llm") else None,
        seconds=d["seconds"],
    )


def save_demo(entries: list[dict], info: dict, path: Path = DEMO_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"info": info, "answers": entries}, indent=1, ensure_ascii=False) + "\n")


def load_demo(path: Path = DEMO_FILE) -> tuple[dict, list[dict]]:
    """(info, entries) where each entry has 'id', 'question', 'answer_type', 'answer' (an Answer)."""
    if not path.exists():
        return {}, []
    raw = json.loads(path.read_text())
    entries = [{"id": d.get("id"), "answer_type": d.get("answer_type"), "question": d["question"],
                "evaluation": d.get("evaluation"), "answer": answer_from_dict(d)} for d in raw["answers"]]
    return raw["info"], entries
