"""End-to-end question answering.

    question -> parse (companies, years, metrics)
             -> financial facts computed in Python  [F1], [F2], ...
             -> hybrid retrieval of filing passages  [C1], [C2], ...
             -> LLM writes a cited answer from that evidence only (or abstains)
             -> citations checked against what was actually provided
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from finsight.reasoning.financial_tools import Fact, FinancialData, compute_facts
from finsight.reasoning.llm import LLMClient, LLMResponse
from finsight.reasoning.query_parser import ALL_TICKERS, ParsedQuery, parse_question
from finsight.retrieval.common import SECTION_NAMES, SearchResult

ABSTAIN_MARKER = "INSUFFICIENT EVIDENCE"
# Matches [C1], and grouped forms the model also writes: [C1, C3], [F2; F1], [C1-C3] is not expanded.
CITATION_GROUP = re.compile(r"\[((?:[FC]\d+)(?:\s*[,;]\s*[FC]\d+)*)\]")
CITATION = re.compile(r"([FC])(\d+)")


def extract_citations(text: str) -> list[tuple[str, str]]:
    return [m for group in CITATION_GROUP.findall(text) for m in CITATION.findall(group)]

SYSTEM_PROMPT = f"""You are FinSight, a financial research assistant. You answer questions about public \
companies using ONLY the evidence provided: computed financial facts [F#] and passages from SEC 10-K filings [C#].

Rules:
1. Use only the provided evidence. Do not use outside knowledge, and do not guess or forecast.
2. Never do arithmetic. Every number you state must appear in the evidence exactly as written, \
either in a fact [F#] or in a passage [C#]. Numbers quoted from passages are valid evidence: \
cite the passage. If a needed calculation appears nowhere, say it is not available.
3. Cite every claim with the tag of its source, e.g. [F2] or [C1]. Cite at least once.
4. If the specific thing asked for is in neither the facts nor the passages (for example, a future \
period, or a figure the company does not disclose), begin with "{ABSTAIN_MARKER}:" and say what is \
missing. You may then add closely related information that IS in the evidence, with citations. \
If any fact or passage states what was asked (including figures for a segment, product, or region), \
the question IS answered: answer it directly and do not use "{ABSTAIN_MARKER}".
5. Facts are company-wide totals. For segment or product questions (e.g. one product line or \
region), answer from the passages and do not present a company total as the segment figure.
6. Answer for the fiscal year(s) asked about; if none is specified, use the most recent year provided. \
When comparing companies, mention that their fiscal years end in different months.
7. Be concise: 2-5 sentences, no headings."""


@dataclass
class Answer:
    question: str
    text: str
    parsed: ParsedQuery
    facts: list[Fact]
    passages: list[SearchResult]
    notes: list[str]
    citations: list[str] = field(default_factory=list)          # valid tags used, e.g. ["F1", "C2"]
    invalid_citations: list[str] = field(default_factory=list)  # tags that point at nothing
    llm: LLMResponse | None = None
    seconds: float = 0.0

    @property
    def abstained(self) -> bool:
        return self.text.upper().startswith(ABSTAIN_MARKER)

    @property
    def cited_chunks(self) -> list[str]:
        return [self.passages[int(t[1:]) - 1].chunk.key for t in self.citations if t[0] == "C"]

    def sources(self) -> list[str]:
        """Human-readable list of the sources the answer actually cited."""
        out = []
        for tag in self.citations:
            i = int(tag[1:]) - 1
            if tag[0] == "F":
                out.append(f"[{tag}] {self.facts[i].statement} (filings: {', '.join(self.facts[i].sources) or 'computed'})")
            else:
                c = self.passages[i].chunk
                acc, sec, idx = c.key.split("|")
                out.append(f"[{tag}] {c.company} FY{c.fiscal_year} 10-K, Item {sec} "
                           f"{SECTION_NAMES.get(sec, '')} (accession {acc}, chunk {idx})")
        return out


class Answerer:
    def __init__(self, retriever=None, llm: LLMClient | None = None, data: FinancialData | None = None,
                 n_passages: int = 5):
        if retriever is None:
            from finsight.retrieval.hybrid_retriever import HybridRetriever
            retriever = HybridRetriever()
        self.retriever = retriever
        self.llm = llm or LLMClient()
        self.data = data or FinancialData()
        self.n_passages = n_passages

    def retrieve(self, parsed: ParsedQuery) -> list[SearchResult]:
        tickers = parsed.tickers or None
        # Passages come from the years asked about (or the latest). Unlike compute_facts, no prior
        # year is added: it let a FY2025 10-K passage answer a FY2026 question (eval sq_006).
        years = sorted(set(parsed.fiscal_years) or {self.data.latest_year(t) for t in (parsed.tickers or ALL_TICKERS)})
        # Filings exist for FY2024-2026 only; drop years with no filing so filters don't empty the results.
        years = [y for y in years if any(c.fiscal_year == y for c in self.retriever.bm25.chunks)] or None
        return self.retriever.search(parsed.question, k=self.n_passages, ticker=tickers, fiscal_year=years)

    def build_prompt(self, question: str, facts: list[Fact], passages: list[SearchResult], notes: list[str]) -> str:
        parts = [f"Question: {question}", "", "Financial facts (computed from XBRL data in the filings):"]
        parts += [f"[F{i}] {f.statement}" for i, f in enumerate(facts, 1)] or ["(none relevant)"]
        if notes:
            parts += ["", "Data notes:"] + [f"- {n}" for n in notes]
        parts += ["", "Filing passages:"]
        for i, r in enumerate(passages, 1):
            c = r.chunk
            parts += [f"[C{i}] {c.company} ({c.ticker}) FY{c.fiscal_year} 10-K, "
                      f"{SECTION_NAMES.get(c.section_id, c.section_id)}:", c.text, ""]
        valid = [f"F1-F{len(facts)}" if facts else None, f"C1-C{len(passages)}" if passages else None]
        parts += [f"Answer the question following the rules. The only valid citation tags are "
                  f"{' and '.join(v for v in valid if v) or 'none'}; never cite any other tag."]
        return "\n".join(parts)

    def ask(self, question: str) -> Answer:
        t0 = time.time()
        parsed = parse_question(question)
        facts, notes = compute_facts(parsed, self.data)
        passages = self.retrieve(parsed)
        response = self.llm.chat(self.build_prompt(question, facts, passages, notes), system=SYSTEM_PROMPT)

        valid, invalid = [], []
        for kind, num in extract_citations(response.text):
            tag, n = f"{kind}{num}", int(num)
            ok = 1 <= n <= (len(facts) if kind == "F" else len(passages))
            (valid if ok else invalid).append(tag)
        return Answer(question, response.text, parsed, facts, passages, notes,
                      citations=list(dict.fromkeys(valid)), invalid_citations=list(dict.fromkeys(invalid)),
                      llm=response, seconds=time.time() - t0)
