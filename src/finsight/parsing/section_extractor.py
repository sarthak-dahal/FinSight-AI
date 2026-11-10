"""
Extract named 10-K sections (Item 1, 7, etc.) from SEC HTML filings.

Returns a dict keyed by normalised section id (e.g. "1", "1A", "7")
with the full cleaned text for that section.
"""

import re
import warnings
from pathlib import Path
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

TARGET_SECTIONS = {"1", "1A", "1C", "7", "7A"}

_ITEM_RE = re.compile(r"^item\s+(\d+[A-Z]?)[\.\s]", re.IGNORECASE)
_NBSP = re.compile(r"[\xa0 ]+")


def _normalise(text: str) -> str:
    return _NBSP.sub(" ", text).strip()


def _section_id(raw_text: str):
    m = _ITEM_RE.match(_normalise(raw_text))
    return m.group(1).upper() if m else None


def _body_child(tag, body):
    """Return the ancestor of tag that is a direct child of <body>."""
    current = tag
    while current.parent and current.parent is not body:
        current = current.parent
    return current


def extract_sections(html_path: Path) -> dict:
    """
    Parse an SEC 10-K HTML filing and return:
        {section_id: {"title": str, "text": str}}

    Handles both div-based (NVDA/AAPL) and p-in-div (MSFT) header styles
    by anchoring content traversal at the body-level container for each header.
    """
    content = html_path.read_bytes().decode("utf-8", errors="replace")
    soup = BeautifulSoup(content, "lxml")
    body = soup.find("body")
    if body is None:
        return {}

    # Find all div/p tags that look like Item headers
    raw_items = []
    for tag in soup.find_all(["div", "p"]):
        raw = _normalise(tag.get_text(strip=True))
        sid = _section_id(raw)
        if sid and len(raw) < 300:
            anchor = _body_child(tag, body)
            raw_items.append((tag, anchor, sid, raw))

    if not raw_items:
        return {}

    # Deduplicate by section_id: keep the last occurrence so TOC anchors
    # (which appear first) are discarded in favour of the real section header.
    seen: dict = {}
    for i, item in enumerate(raw_items):
        seen[item[2]] = i   # section_id → last index
    raw_items = [raw_items[i] for i in sorted(seen.values())]

    # Build the list of (anchor_element, section_id, title) in document order
    anchors = [(anchor, sid, title) for (_tag, anchor, sid, title) in raw_items]

    sections = {}

    for idx, (anchor, sid, title) in enumerate(anchors):
        if sid not in TARGET_SECTIONS:
            continue

        next_anchor = anchors[idx + 1][0] if idx + 1 < len(anchors) else None

        texts = []
        for sibling in anchor.find_next_siblings():
            if sibling is next_anchor:
                break
            sibling_text = _normalise(sibling.get_text(separator=" ", strip=True))
            if sibling_text:
                texts.append(sibling_text)

        full_text = re.sub(r"\s{3,}", "  ", " ".join(texts))
        sections[sid] = {"title": title, "text": full_text}

    return sections
