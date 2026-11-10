"""
Extract structured financial facts from inline XBRL tags in SEC 10-K filings.

Produces a list of dicts suitable for inserting into the financial_facts table.
Only annual (full-year) contexts are retained; quarterly and instant contexts
are skipped so we don't double-count.
"""

import re
import warnings
from pathlib import Path
from datetime import date
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# GAAP concepts to keep (income statement + key balance sheet items)
CONCEPTS_OF_INTEREST = {
    "us-gaap:Revenues",
    "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
    "us-gaap:GrossProfit",
    "us-gaap:CostOfRevenue",
    "us-gaap:OperatingIncomeLoss",
    "us-gaap:NetIncomeLoss",
    "us-gaap:ResearchAndDevelopmentExpense",
    "us-gaap:SellingGeneralAndAdministrativeExpense",
    "us-gaap:EarningsPerShareBasic",
    "us-gaap:EarningsPerShareDiluted",
    "us-gaap:Assets",
    "us-gaap:CashAndCashEquivalentsAtCarryingValue",
    "us-gaap:LongTermDebt",
    "us-gaap:StockholdersEquity",
    "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment",
    "us-gaap:DepreciationDepletionAndAmortization",
}

HUMAN_LABELS = {
    "us-gaap:Revenues": "Revenue",
    "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax": "Revenue",
    "us-gaap:GrossProfit": "Gross Profit",
    "us-gaap:CostOfRevenue": "Cost of Revenue",
    "us-gaap:OperatingIncomeLoss": "Operating Income",
    "us-gaap:NetIncomeLoss": "Net Income",
    "us-gaap:ResearchAndDevelopmentExpense": "R&D Expense",
    "us-gaap:SellingGeneralAndAdministrativeExpense": "SG&A Expense",
    "us-gaap:EarningsPerShareBasic": "EPS Basic",
    "us-gaap:EarningsPerShareDiluted": "EPS Diluted",
    "us-gaap:Assets": "Total Assets",
    "us-gaap:CashAndCashEquivalentsAtCarryingValue": "Cash and Equivalents",
    "us-gaap:LongTermDebt": "Long-term Debt",
    "us-gaap:StockholdersEquity": "Stockholders Equity",
    "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment": "Capital Expenditures",
    "us-gaap:DepreciationDepletionAndAmortization": "D&A",
}

_COMMA_NUM = re.compile(r"^-?[\d,]+$")


def _parse_value(text: str, decimals: str):
    """Return (numeric_value, unit_str) or (None, None) if unparseable."""
    clean = text.replace(",", "").strip()
    try:
        raw = float(clean)
    except ValueError:
        return None, None

    try:
        dec = int(decimals)
    except (ValueError, TypeError):
        dec = 0

    # decimals=-6 → reported in millions; store as reported
    unit = "USD"
    if dec == -6:
        unit = "USD_millions"
    elif dec == -3:
        unit = "USD_thousands"
    elif dec in (0, 2):
        unit = "USD_per_share" if abs(raw) < 10000 and "." in clean else "USD"

    return raw, unit


def _build_context_map(soup) -> dict:
    """Return {context_id: {period_start, period_end, is_annual}}."""
    contexts = {}
    for ctx in soup.find_all("xbrli:context"):
        cid = ctx.get("id", "")
        instant = ctx.find("xbrli:instant")
        start = ctx.find("xbrli:startdate")
        end = ctx.find("xbrli:enddate")

        # Contexts with explicit segment/member dimensions represent sub-totals,
        # not consolidated company-wide figures — skip them for financial_facts.
        has_dimensions = (
            ctx.find("xbrli:segment") is not None
            or ctx.find("xbrldi:explicitmember") is not None
            or ctx.find("xbrldi:typedmember") is not None
        )

        if instant:
            d = instant.get_text(strip=True)
            contexts[cid] = {
                "period_start": d, "period_end": d,
                "is_annual": False, "has_dimensions": has_dimensions,
            }
        elif start and end:
            ps = start.get_text(strip=True)
            pe = end.get_text(strip=True)
            try:
                d1 = date.fromisoformat(ps)
                d2 = date.fromisoformat(pe)
                days = (d2 - d1).days
                is_annual = 340 <= days <= 380
            except ValueError:
                is_annual = False
            contexts[cid] = {
                "period_start": ps, "period_end": pe,
                "is_annual": is_annual, "has_dimensions": has_dimensions,
            }

    return contexts


def extract_xbrl_facts(html_path: Path, manifest: dict) -> list:
    """
    Return a list of financial fact dicts for annual contexts only.
    Deduplicates by (concept, period_start, period_end).
    """
    content = html_path.read_bytes().decode("utf-8", errors="replace")
    soup = BeautifulSoup(content, "lxml")

    context_map = _build_context_map(soup)

    seen = set()
    facts = []

    for el in soup.find_all(attrs={"name": True}):
        concept = el.get("name", "")
        if concept not in CONCEPTS_OF_INTEREST:
            continue

        ctx_id = el.get("contextref", "")
        ctx = context_map.get(ctx_id)
        if not ctx or not ctx["is_annual"] or ctx["has_dimensions"]:
            continue

        raw_text = el.get_text(strip=True).replace(",", "")
        decimals = el.get("decimals", "0")
        value, unit = _parse_value(raw_text, decimals)
        if value is None:
            continue

        key = (concept, ctx["period_start"], ctx["period_end"])
        if key in seen:
            continue
        seen.add(key)

        facts.append({
            "company": manifest["company"],
            "ticker": manifest["ticker"],
            "cik": manifest["cik"],
            "concept": concept,
            "metric_label": HUMAN_LABELS.get(concept, concept.split(":")[-1]),
            "value": value,
            "unit": unit,
            "period_start": ctx["period_start"],
            "period_end": ctx["period_end"],
            # Fiscal year of the *period*, not the filing: each 10-K restates 2-3 prior
            # years. Labelled by the calendar year the period ends in, which matches how
            # MSFT (Jun), AAPL (Sep) and NVDA (late Jan) name their fiscal years.
            # Revisit for companies whose FY ends in early January (e.g. retailers).
            "fiscal_year": ctx["period_end"][:4],
            "filing_date": manifest["filing_date"],
            "form_type": manifest["form_type"],
            "accession_number": manifest["accession_number"],
            "source_url": manifest.get("source_url", ""),
        })

    return facts
