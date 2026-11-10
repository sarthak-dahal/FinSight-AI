"""FinSight AI — web interface.

Run: uv run streamlit run app/streamlit_app.py
Needs Ollama running (Ollama.app or `ollama serve`) and the index built (scripts/build_index.py).
"""

from __future__ import annotations

import re

import streamlit as st

st.set_page_config(page_title="FinSight AI", page_icon="📊", layout="wide")

# Heavy imports after set_page_config (torch/faiss load here).
from finsight.reasoning.answerer import Answer, Answerer  # noqa: E402
from finsight.reasoning.financial_tools import FinancialData  # noqa: E402
from finsight.reasoning.llm import LLMClient, LLMUnavailable, load_llm_config  # noqa: E402
from finsight.retrieval.common import SECTION_NAMES  # noqa: E402

EXAMPLES = [
    "What drove Microsoft's revenue growth in fiscal year 2026?",
    "Compare the operating margins of Nvidia, Microsoft, and Apple in their most recent fiscal year.",
    "What risk factors does Nvidia identify related to its dependence on a small number of customers?",
    "How did Apple's Greater China sales change in fiscal year 2026?",
]


# --- cached resources ------------------------------------------------------------------------

@st.cache_resource(show_spinner="Loading search indexes and embedding model…")
def load_shared():
    from finsight.retrieval.hybrid_retriever import HybridRetriever
    return HybridRetriever(), FinancialData()


@st.cache_data(ttl=30, show_spinner=False)
def ollama_status(model: str) -> tuple[bool, str, list[str]]:
    client = LLMClient(model=model)
    try:
        models = sorted(m.model for m in client._client.list().models)
    except Exception:
        return False, "Ollama isn't running. Open the Ollama app (or run `ollama serve`), then reload.", []
    if model not in models:
        return False, f"Model `{model}` isn't downloaded. Run `ollama pull {model}`.", models
    return True, "Ollama is running.", models


def get_answerer(model: str, n_passages: int) -> Answerer:
    retriever, data = load_shared()
    return Answerer(retriever=retriever, llm=LLMClient(model=model), data=data, n_passages=n_passages)


# --- rendering helpers -----------------------------------------------------------------------

def md_safe(text: str) -> str:
    """Escape $ so Streamlit doesn't render '$215 ... $130' as LaTeX math."""
    return text.replace("$", r"\$")


def highlight_tags(text: str) -> str:
    return re.sub(r"\[((?:[FC]\d+)(?:\s*[,;]\s*[FC]\d+)*)\]", r"**[\1]**", md_safe(text))


def render_answer(a: Answer) -> None:
    if a.abstained:
        st.warning(md_safe(a.text), icon="⚠️")
    else:
        st.markdown(highlight_tags(a.text))
    if a.invalid_citations:
        st.error(f"The answer cited sources that weren't provided: {', '.join(a.invalid_citations)}. "
                 "Treat those claims with caution.")

    cited = set(a.citations)
    with st.expander(f"Sources cited ({len(cited)})", expanded=not a.abstained):
        if not cited:
            st.caption("No sources cited.")
        for tag in a.citations:
            i = int(tag[1:]) - 1
            if tag[0] == "F":
                f = a.facts[i]
                st.markdown(f"**[{tag}]** {md_safe(f.statement)}  \n"
                            f"<small>Computed from XBRL data · filing {', '.join(f.sources) or '—'}</small>",
                            unsafe_allow_html=True)
            else:
                c = a.passages[i].chunk
                acc, sec, idx = c.key.split("|")
                st.markdown(f"**[{tag}]** {c.company} · FY{c.fiscal_year} 10-K · Item {sec} "
                            f"{SECTION_NAMES.get(sec, '')}  \n<small>Accession {acc} · chunk {idx}</small>",
                            unsafe_allow_html=True)
                st.text(c.text[:1500] + ("…" if len(c.text) > 1500 else ""))

    if a.facts:
        with st.expander(f"Computed figures ({len(a.facts)})"):
            st.dataframe(
                [{"tag": f"F{i}", "cited": "✓" if f"F{i}" in cited else "", "figure": f.statement,
                  "filings": ", ".join(f.sources)} for i, f in enumerate(a.facts, 1)],
                hide_index=True, width="stretch",
            )

    with st.expander("How this was answered"):
        p = a.parsed
        st.markdown(
            f"- **Companies:** {', '.join(p.tickers) or 'not specified'}\n"
            f"- **Fiscal years:** {', '.join(p.fiscal_years) or ('most recent' if p.wants_latest else 'not specified → latest')}\n"
            f"- **Metrics:** {', '.join(p.metrics) or 'none (narrative question)'}\n"
            f"- **Passages retrieved** (hybrid BM25 + vector search):"
        )
        for r in a.passages:
            c = r.chunk
            tag = f"C{r.rank}"
            st.markdown(f"  {'✓' if tag in cited else '·'} **[{tag}]** {c.ticker} FY{c.fiscal_year} · "
                        f"{SECTION_NAMES.get(c.section_id, c.section_id)} · `{c.key}`")
        for note in a.notes:
            st.caption(f"Note: {note}")
        st.caption(f"{a.llm.model} · {a.llm.prompt_tokens:,} prompt tokens · "
                   f"{a.llm.completion_tokens} answer tokens · {a.seconds:.1f}s")


# --- sidebar ---------------------------------------------------------------------------------

cfg = load_llm_config()
with st.sidebar:
    st.header("Settings")
    ok, status, models = ollama_status(cfg["model"])
    model = st.selectbox("Model", models or [cfg["model"]],
                         index=(models.index(cfg["model"]) if cfg["model"] in models else 0),
                         help="Any model from `ollama list`. Default comes from configs/llm.yaml.")
    if model != cfg["model"]:
        ok, status, _ = ollama_status(model)
    (st.success if ok else st.error)(status)
    n_passages = st.slider("Passages per answer", 3, 8, 5,
                           help="How many filing passages the model reads. More = more context, slower.")

    st.divider()
    st.subheader("Data")
    _, data = load_shared()
    for t in ("MSFT", "AAPL", "NVDA"):
        st.markdown(f"**{t}** · {data.company.get(t, t).title()}  \nFacts FY{data.years[t][0]}–FY{data.years[t][-1]} "
                    f"· 10-K text FY2024–FY2026")
    st.caption("Source: SEC EDGAR 10-K filings. Answers use only these filings; "
               "numbers are computed in Python, not by the model.")
    if st.button("Clear conversation"):
        st.session_state.history = []
        st.rerun()


# --- main ------------------------------------------------------------------------------------

st.title("📊 FinSight AI")
st.caption("Ask about Microsoft, Apple, or Nvidia. Answers come from their SEC 10-K filings, with citations.")

if "history" not in st.session_state:
    st.session_state.history = []

if not st.session_state.history:
    st.markdown("**Try an example:**")
    cols = st.columns(2)
    for i, example in enumerate(EXAMPLES):
        if cols[i % 2].button(example, key=f"ex{i}", width="stretch"):
            st.session_state.pending = example
            st.rerun()

for item in st.session_state.history:
    with st.chat_message("user"):
        st.markdown(md_safe(item["question"]))
    with st.chat_message("assistant"):
        if item.get("error"):
            st.error(item["error"])
        else:
            render_answer(item["answer"])

question = st.chat_input("Ask a question about MSFT, AAPL, or NVDA…", disabled=not ok)
question = question or st.session_state.pop("pending", None)
if question:
    with st.chat_message("user"):
        st.markdown(md_safe(question))
    with st.chat_message("assistant"):
        item = {"question": question}
        with st.spinner(f"Searching filings and asking {model}… (about 20–40 seconds)"):
            try:
                item["answer"] = get_answerer(model, n_passages).ask(question)
            except LLMUnavailable as e:
                item["error"] = str(e)
        if item.get("error"):
            st.error(item["error"])
        else:
            render_answer(item["answer"])
    st.session_state.history.append(item)
