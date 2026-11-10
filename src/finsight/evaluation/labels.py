"""Evidence-based retrieval labels.

Each retrieval question in seed_questions.json lists `evidence`: exact phrases from a
specific filing, e.g. {"filing": "0001045810-26-000021", "text": "approximately 42,000 employees"}.
`expected_chunks` is derived: every chunk of that filing containing any phrase.

Why: chunks overlap (80 words), so one answer can live in two chunks, and filings repeat
key facts across sections. Labelling by phrase catches every copy and survives
re-chunking — rerun scripts/label_evidence.py after changing the chunker.
"""

from __future__ import annotations

import sqlite3


def resolve_evidence(conn: sqlite3.Connection, evidence: list[dict]) -> tuple[list[str], list[dict]]:
    """Return (sorted chunk keys containing any phrase, evidence items found nowhere)."""
    keys, missing = set(), []
    for item in evidence:
        rows = conn.execute(
            "SELECT section_id, chunk_idx, text FROM filing_chunks WHERE accession_number = ?",
            (item["filing"],),
        ).fetchall()
        hits = {f"{item['filing']}|{sec}|{idx}" for sec, idx, text in rows if item["text"] in text}
        if not hits:
            missing.append(item)
        keys |= hits
    return sorted(keys), missing
