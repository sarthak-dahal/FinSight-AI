"""Financial lookups and calculations over `financial_facts`.

The LLM never does arithmetic: every number it may state is fetched or computed here,
labelled, and carries its source filing so it can be cited.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from finsight.reasoning.query_parser import ALL_TICKERS, DERIVED_METRICS, ParsedQuery
from finsight.retrieval.common import load_config


@dataclass
class Fact:
    statement: str      # human-readable, e.g. "NVDA FY2026 Revenue: $215,938 million"
    value: float
    kind: str           # "usd_millions" | "usd_per_share" | "percent"
    sources: list[str]  # accession numbers the inputs came from


def fmt_value(value: float, kind: str) -> str:
    if kind == "usd_millions":
        return f"${value:,.0f} million"
    if kind == "usd_per_share":
        return f"${value:,.2f} per share"
    return f"{value:.1f}%"


class FinancialData:
    def __init__(self, db_path=None):
        # Read-only use; check_same_thread=False lets one cached instance serve Streamlit's threads.
        self.conn = sqlite3.connect(db_path or load_config()["db_path"], check_same_thread=False)
        self.years = {
            t: sorted(y for (y,) in self.conn.execute(
                "SELECT DISTINCT fiscal_year FROM financial_facts WHERE ticker = ?", (t,)))
            for t in ALL_TICKERS
        }
        self.company = dict(self.conn.execute("SELECT DISTINCT ticker, company FROM financial_facts"))

    def latest_year(self, ticker: str) -> str:
        return self.years[ticker][-1]

    def get(self, ticker: str, metric: str, year: str):
        """(value, unit, accession, period_start, period_end) or None."""
        return self.conn.execute("""
            SELECT value, unit, accession_number, period_start, period_end FROM financial_facts
            WHERE ticker = ? AND metric_label = ? AND fiscal_year = ?
        """, (ticker, metric, str(year))).fetchone()


def resolve_years(parsed: ParsedQuery, data: FinancialData, ticker: str) -> list[str]:
    """Requested years; else the latest. A single year also pulls the prior year for YoY context,
    except for "most recent" questions, where a second year only invites picking the wrong one."""
    years = list(parsed.fiscal_years) or [data.latest_year(ticker)]
    if len(years) == 1 and not parsed.wants_latest:
        prior = str(int(years[0]) - 1)
        if prior in data.years[ticker]:
            years = [prior, years[0]]
    return years


def compute_facts(parsed: ParsedQuery, data: FinancialData) -> tuple[list[Fact], list[str]]:
    """All stored + derived facts relevant to the question, and notes about missing data."""
    facts, notes = [], []
    tickers = parsed.tickers or (ALL_TICKERS if parsed.metrics else [])
    for ticker in tickers:
        years = resolve_years(parsed, data, ticker)
        unavailable = [y for y in years if y not in data.years[ticker]]
        if unavailable:
            notes.append(f"No {ticker} financial data exists for fiscal year(s) {', '.join(unavailable)}; "
                         f"the dataset covers FY{data.years[ticker][0]}–FY{data.years[ticker][-1]}.")
        years = [y for y in years if y in data.years[ticker]]

        for metric in parsed.metrics:
            if metric in DERIVED_METRICS:
                facts += _ratio_facts(data, ticker, years, *DERIVED_METRICS[metric])
            else:
                facts += _metric_facts(data, ticker, years, metric, notes)
    return facts, notes


def _label(ticker: str, year: str, data: FinancialData) -> str:
    row = data.get(ticker, "Revenue", year)
    period = f" (period {row[3]} to {row[4]})" if row else ""
    return f"{ticker} FY{year}{period}"


def _metric_facts(data, ticker, years, metric, notes) -> list[Fact]:
    out, values = [], {}
    for y in years:
        row = data.get(ticker, metric, y)
        if row is None:
            notes.append(f"{metric} is not in the dataset for {ticker} FY{y}.")
            continue
        value, unit, acc = row[0], row[1], row[2]
        kind = "usd_per_share" if unit == "USD_per_share" else "usd_millions"
        values[y] = (value, kind, acc)
        out.append(Fact(f"{_label(ticker, y, data)} {metric}: {fmt_value(value, kind)}", value, kind, [acc]))
        if metric != "Revenue" and kind == "usd_millions":
            rev = data.get(ticker, "Revenue", y)
            if rev:
                pct = value / rev[0] * 100
                out.append(Fact(f"{ticker} FY{y} {metric} as a share of revenue: {fmt_value(pct, 'percent')} "
                                f"({fmt_value(value, kind)} / {fmt_value(rev[0], 'usd_millions')})",
                                pct, "percent", sorted({acc, rev[2]})))
    if len(values) >= 2:
        y0, y1 = min(values), max(values)
        (v0, kind, a0), (v1, _, a1) = values[y0], values[y1]
        growth = (v1 - v0) / abs(v0) * 100
        out.append(Fact(f"{ticker} {metric} change FY{y0} to FY{y1}: {growth:+.1f}% "
                        f"({fmt_value(v0, kind)} to {fmt_value(v1, kind)}; {v1 / v0:.2f}x)",
                        growth, "percent", sorted({a0, a1})))
    return out


def _ratio_facts(data, ticker, years, numerator, name) -> list[Fact]:
    out, ratios = [], {}
    for y in years:
        num, rev = data.get(ticker, numerator, y), data.get(ticker, "Revenue", y)
        if not (num and rev):
            continue
        pct = num[0] / rev[0] * 100
        ratios[y] = pct
        out.append(Fact(f"{_label(ticker, y, data)} {name}: {fmt_value(pct, 'percent')} "
                        f"({numerator} {fmt_value(num[0], 'usd_millions')} / Revenue {fmt_value(rev[0], 'usd_millions')})",
                        pct, "percent", sorted({num[2], rev[2]})))
    if len(ratios) >= 2:
        y0, y1 = min(ratios), max(ratios)
        diff = ratios[y1] - ratios[y0]
        out.append(Fact(f"{ticker} {name} change FY{y0} to FY{y1}: {diff:+.1f} percentage points",
                        diff, "percent", []))
    return out
