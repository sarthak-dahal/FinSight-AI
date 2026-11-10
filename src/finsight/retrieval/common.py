"""Shared pieces for the retrievers: config, chunk loading, filters, results."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import yaml

PROJECT_DIR = Path(__file__).resolve().parents[3]
CONFIG_PATH = PROJECT_DIR / "configs" / "retrieval.yaml"

SECTION_NAMES = {
    "1": "Business",
    "1A": "Risk Factors",
    "1C": "Cybersecurity",
    "7": "Management's Discussion and Analysis",
    "7A": "Market Risk",
}


def load_config() -> dict:
    cfg = yaml.safe_load(CONFIG_PATH.read_text())
    cfg["db_path"] = PROJECT_DIR / cfg["db_path"]
    cfg["index_dir"] = PROJECT_DIR / cfg["index_dir"]
    return cfg


@dataclass(frozen=True)
class Chunk:
    key: str            # "accession|section_id|chunk_idx" — stable across DB rebuilds
    company: str
    ticker: str
    fiscal_year: str
    section_id: str
    text: str

    @property
    def header(self) -> str:
        """Context line prepended before indexing. Filings rarely name the company in
        the body ("The Company", "we"), so without this a query like "Apple iPhone
        sales" has nothing to match the company name against."""
        section = SECTION_NAMES.get(self.section_id, self.section_id)
        return f"{self.company} ({self.ticker}) fiscal year {self.fiscal_year} 10-K, {section}."

    @property
    def indexed_text(self) -> str:
        return f"{self.header}\n{self.text}"


@dataclass
class SearchResult:
    chunk: Chunk
    score: float
    rank: int


def load_chunks(db_path: Path) -> list[Chunk]:
    """All chunks in a fixed order (by key), so index positions are reproducible."""
    conn = sqlite3.connect(db_path)
    rows = conn.execute("""
        SELECT accession_number, section_id, chunk_idx, company, ticker, fiscal_year, text
        FROM filing_chunks
        ORDER BY accession_number, section_id, chunk_idx
    """).fetchall()
    conn.close()
    return [
        Chunk(f"{acc}|{sec}|{idx}", company, ticker, fy, sec, text)
        for acc, sec, idx, company, ticker, fy, text in rows
    ]


def matches(chunk: Chunk, ticker=None, fiscal_year=None, section_id=None) -> bool:
    """Metadata filter. Each argument may be None (no filter), a value, or a list of values."""
    for value, wanted in ((chunk.ticker, ticker), (chunk.fiscal_year, fiscal_year),
                          (chunk.section_id, section_id)):
        if wanted is None:
            continue
        allowed = {str(w) for w in wanted} if isinstance(wanted, (list, tuple, set)) else {str(wanted)}
        if value not in allowed:
            return False
    return True


_STOPWORDS = frozenset(
    "a an and are as at be by for from has have in is it its of on or that the this to was were "
    "will with we our us which what how did does do".split()
)
_TOKEN = re.compile(r"[a-z0-9]+(?:[.&][a-z0-9]+)*")
_POSSESSIVE = re.compile(r"['’]s\b")


def tokenize(text: str) -> list[str]:
    """Lowercase word/number tokens without stopwords. Keeps tokens like 'm&a', '3.5'.
    Strips possessives so "Microsoft's" (straight or curly apostrophe) matches "microsoft"."""
    text = _POSSESSIVE.sub("", text.lower())
    return [t for t in _TOKEN.findall(text) if t not in _STOPWORDS]
