"""
Split section text into overlapping word-window chunks with filing metadata.

Each chunk carries enough context for retrieval:
  company, ticker, fiscal_year, filing_date, section_id, section_title,
  chunk_idx, text
"""

import re
from typing import Iterator


def _sentences(text: str) -> list:
    """Split text into rough sentences on period / newline boundaries."""
    parts = re.split(r"(?<=[.!?])\s+|\n{2,}", text)
    return [p.strip() for p in parts if p.strip()]


def chunk_section(
    section_text: str,
    section_id: str,
    section_title: str,
    manifest: dict,
    chunk_words: int = 400,
    overlap_words: int = 80,
) -> Iterator[dict]:
    """
    Yield chunk dicts for a single section.

    Chunks are formed by accumulating sentences until chunk_words is reached,
    then stepping back overlap_words worth of words for the next chunk.
    """
    words = section_text.split()
    if not words:
        return

    base = {
        "company": manifest["company"],
        "ticker": manifest["ticker"],
        "cik": manifest["cik"],
        "fiscal_year": manifest["fiscal_year"],
        "filing_date": manifest["filing_date"],
        "report_period": manifest["report_period"],
        "form_type": manifest["form_type"],
        "accession_number": manifest["accession_number"],
        "source_url": manifest.get("source_url", ""),
        "section_id": section_id,
        "section_title": section_title,
    }

    start = 0
    chunk_idx = 0

    while start < len(words):
        end = min(start + chunk_words, len(words))
        chunk_text = " ".join(words[start:end])

        yield {**base, "chunk_idx": chunk_idx, "text": chunk_text}

        chunk_idx += 1
        # Step forward by (chunk_words - overlap_words) so chunks overlap
        step = chunk_words - overlap_words
        start += step

        # Stop if the remaining text is shorter than overlap (would duplicate)
        if len(words) - start <= overlap_words:
            break
