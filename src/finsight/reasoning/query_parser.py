"""Rule-based question parser: which companies, fiscal years, and metrics a question asks about.

Deterministic on purpose: with three companies and a fixed metric list, rules are instant,
testable, and can't hallucinate. The parse becomes retrieval filters and SQL lookups.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

COMPANY_ALIASES = {
    "MSFT": ["microsoft", "msft"],
    "AAPL": ["apple", "aapl"],
    "NVDA": ["nvidia", "nvda"],
}
ALL_TICKERS = list(COMPANY_ALIASES)

# Phrase -> metric. Longest phrases are matched first, and matched text is consumed,
# so "operating margin" never also counts as "operating income"-ish noise.
# Bare "sales" is deliberately absent: "iPhone sales" / "Greater China sales" are segment
# questions, not total revenue.
METRIC_PHRASES = {
    "operating margin": "operating_margin",
    "gross margin": "gross_margin",
    "net income margin": "net_margin",
    "net margin": "net_margin",
    "profit margin": "net_margin",
    "operating income": "Operating Income",
    "net income": "Net Income",
    "gross profit": "Gross Profit",
    "research and development": "R&D Expense",
    "r&d": "R&D Expense",
    "selling, general and administrative": "SG&A Expense",
    "sg&a": "SG&A Expense",
    "capital expenditures": "Capital Expenditures",
    "capital expenditure": "Capital Expenditures",
    "capex": "Capital Expenditures",
    "diluted earnings per share": "EPS Diluted",
    "diluted eps": "EPS Diluted",
    "earnings per share": "EPS Diluted",
    "eps": "EPS Diluted",
    "depreciation": "D&A",
    "cost of revenue": "Cost of Revenue",
    "total revenue": "Revenue",
    "net sales": "Revenue",
    "revenue": "Revenue",
}
# Ratios computed from two stored metrics: numerator / Revenue.
DERIVED_METRICS = {
    "operating_margin": ("Operating Income", "Operating margin"),
    "gross_margin": ("Gross Profit", "Gross margin"),
    "net_margin": ("Net Income", "Net income margin"),
}

NARRATIVE_CUES = re.compile(
    r"\b(why|drove|driv\w*|factor\w*|risk\w*|describe\w*|explain\w*|segment\w*|strateg\w*|"
    r"oversee\w*|affect\w*|impact\w*|perform\w*|employees|compet\w*|business|product lines?)\b"
)
LATEST_CUES = re.compile(r"\b(most recent|latest|current|this year)\b")
YEAR = re.compile(r"\b(?:fiscal(?: year)?|fy)\s*'?(\d{4}|\d{2})\b|\b(20\d{2})\b", re.IGNORECASE)


@dataclass
class ParsedQuery:
    question: str
    tickers: list[str]                       # empty = not specified
    fiscal_years: list[str]                  # empty = not specified (caller decides default)
    metrics: list[str] = field(default_factory=list)  # stored labels or derived keys
    wants_latest: bool = False
    is_numeric: bool = False
    is_narrative: bool = False

    @property
    def stored_metrics(self) -> list[str]:
        """Metrics to fetch from SQL, expanding derived ratios into their inputs."""
        out = []
        for m in self.metrics:
            needed = [DERIVED_METRICS[m][0], "Revenue"] if m in DERIVED_METRICS else [m]
            out += [n for n in needed if n not in out]
        return out


# "Azure and other cloud services revenue" / "data center revenue" ask about a segment, not the
# company total. Feeding total-revenue facts to those questions confused the LLM (eval sq_021).
SEGMENT_SENSITIVE = {"revenue", "net sales"}
_TOTAL_QUALIFIERS = {"total", "net", "overall", "annual", "consolidated", "its", "their", "of", "in", "and", "the"}
_COMPANY_WORDS = {a for aliases in COMPANY_ALIASES.values() for a in aliases}


def _is_segment_qualified(text: str, pattern: str) -> bool:
    """True if the word right before the metric names something other than the company/total."""
    m = re.search(pattern, text)
    if m is None:
        return False
    before = re.findall(r"[a-z0-9&']+", text[:m.start()])
    if not before:
        return False
    prev = before[-1].removesuffix("'s")
    return prev not in _TOTAL_QUALIFIERS and prev not in _COMPANY_WORDS


def parse_question(question: str) -> ParsedQuery:
    q = question.lower().replace("’", "'")

    tickers = [t for t, aliases in COMPANY_ALIASES.items()
               if any(re.search(rf"\b{re.escape(a)}\b", q) for a in aliases)]

    years = []
    for m in YEAR.finditer(question):
        y = m.group(1) or m.group(2)
        y = f"20{y}" if len(y) == 2 else y
        if y not in years:
            years.append(y)
    years.sort()

    metrics, rest = [], q
    for phrase in sorted(METRIC_PHRASES, key=len, reverse=True):
        pattern = rf"(?<![a-z]){re.escape(phrase)}s?(?![a-z])"  # allow plurals: "margins"
        if re.search(pattern, rest):
            metric = METRIC_PHRASES[phrase]
            if phrase in SEGMENT_SENSITIVE and _is_segment_qualified(rest, pattern):
                rest = re.sub(pattern, " ", rest)
                continue
            if metric not in metrics:
                metrics.append(metric)
            rest = re.sub(pattern, " ", rest)

    # "...what percentage of revenue does that represent" asks for a ratio, not revenue itself
    if "Revenue" in metrics and len(metrics) > 1 and re.search(r"(percent\w*|share|%) of (its )?revenue", q):
        metrics.remove("Revenue")

    return ParsedQuery(
        question=question,
        tickers=tickers,
        fiscal_years=years,
        metrics=metrics,
        wants_latest=bool(LATEST_CUES.search(q)),
        is_numeric=bool(metrics),
        is_narrative=bool(NARRATIVE_CUES.search(q)) or not metrics,
    )
