"""Automatic checks for generated answers.

Per question:
  figures   — share of `key_figures` stated in the answer (unit-aware, small tolerance)
  abstain   — abstained iff the question is unanswerable
  cited     — at least one valid citation, and no citations pointing at nothing
  grounded  — for retrieval questions: a cited passage is one of the labelled answer chunks
A question passes when figures == 1.0, abstain is right, and it is cited. Narrative quality
beyond these checks is left to human review of the report.
"""

from __future__ import annotations

import re

NUMBER = re.compile(
    r"(\$)?\s?(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*"
    r"(%|percent(?:age points?)?|percentage points?|pp\b|trillion|billion|million|bn\b|b\b|m\b)?",
    re.IGNORECASE,
)


def extract_numbers(text: str) -> list[tuple[float, str]]:
    """(value, kind) pairs; money normalised to USD millions."""
    out = []
    for dollar, raw, unit in NUMBER.findall(text):
        value = float(raw.replace(",", ""))
        unit = (unit or "").lower()
        if unit.startswith("percent") and "point" not in unit or unit == "%":
            out.append((value, "percent"))
        elif "point" in unit or unit == "pp":
            out.append((value, "number"))
        elif unit in ("trillion",):
            out.append((value * 1_000_000, "usd_millions"))
        elif unit in ("billion", "bn", "b"):
            out.append((value * 1_000, "usd_millions"))
        elif unit in ("million", "m"):
            out.append((value, "usd_millions"))
        else:
            out.append((value, "usd_millions" if dollar and value >= 1000 else "number"))
    return out


def figure_found(target: dict, numbers: list[tuple[float, str]]) -> bool:
    """`accept` lists other correct forms, e.g. the filing's own rounding (32% for 32.5%)."""
    return any(_matches(v, target["kind"], numbers) for v in [target["value"], *target.get("accept", [])])


def _matches(v: float, kind: str, numbers: list[tuple[float, str]]) -> bool:
    for value, k in numbers:
        if kind == "percent" and k == "percent" and abs(value - v) <= 0.15:
            return True
        if kind == "usd_millions" and k in ("usd_millions", "number") and abs(value - v) <= max(0.005 * abs(v), 0.5):
            return True
        if kind == "number" and abs(value - v) <= max(0.005 * abs(v), 0.005):
            return True
    return False


def score_answer(question: dict, answer) -> dict:
    numbers = extract_numbers(answer.text)
    figures = question.get("key_figures", [])
    found = [f for f in figures if figure_found(f, numbers)]
    expected_chunks = set(question.get("expected_chunks", []))
    retrieved = {r.chunk.key for r in answer.passages}

    result = {
        "figures": len(found) / len(figures) if figures else None,
        "missing_figures": [f["value"] for f in figures if f not in found],
        "abstain_ok": answer.abstained == question.get("unanswerable", False),
        "cited": bool(answer.citations) and not answer.invalid_citations,
        "retrieved_answer": bool(expected_chunks & retrieved) if expected_chunks else None,
        "grounded": bool(expected_chunks & set(answer.cited_chunks)) if expected_chunks else None,
    }
    result["passed"] = (
        result["abstain_ok"]
        and (result["figures"] in (None, 1.0) or question.get("unanswerable"))
        and (result["cited"] or answer.abstained)
    )
    return result
