"""FinSight AI — web interface.

Run: uv run streamlit run app/streamlit_app.py

Live mode needs Ollama running and the index built (scripts/build_index.py).
Demo mode shows pre-generated answers (data/demo/answers.json, from scripts/build_demo.py) and
needs neither. It turns on automatically when live mode is unavailable, via the sidebar toggle,
or with FINSIGHT_DEMO=1. Demo mode never imports torch/faiss or opens the database.
"""

from __future__ import annotations

import os
from typing import Any
import re

import streamlit as st

st.set_page_config(page_title="FinSight AI", page_icon=":material/query_stats:", layout="wide")

# These imports are light; torch/faiss load only inside load_shared() (live mode).
from finsight.reasoning.answerer import Answer, Answerer  # noqa: E402
from finsight.reasoning.financial_tools import FinancialData  # noqa: E402
from finsight.reasoning.llm import LLMClient, LLMUnavailable, load_llm_config  # noqa: E402
from finsight.retrieval.common import SECTION_NAMES  # noqa: E402

# Suggestion chip label -> question sent.
EXAMPLES = {
    ":material/trending_up: What drove Microsoft's FY2026 revenue growth?":
        "What drove Microsoft's revenue growth in fiscal year 2026?",
    ":material/compare_arrows: Compare operating margins":
        "Compare the operating margins of Nvidia, Microsoft, and Apple in their most recent fiscal year.",
    ":material/warning: Nvidia's customer concentration risk":
        "What risk factors does Nvidia identify related to its dependence on a small number of customers?",
    ":material/public: Apple's Greater China sales":
        "How did Apple's Greater China sales change in fiscal year 2026?",
}


# --- cached resources ------------------------------------------------------------------------

@st.cache_resource(show_spinner="Loading search indexes and embedding model…")
def load_shared():
    from finsight.retrieval.hybrid_retriever import HybridRetriever
    return HybridRetriever(), FinancialData()


@st.cache_data(ttl=30, show_spinner=False)
def ollama_status(model: str) -> tuple[bool, str, list[str]]:
    try:
        models = LLMClient(model=model).available_models()
    except LLMUnavailable:
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
        st.warning(md_safe(a.text), icon=":material/report:")
    else:
        st.markdown(highlight_tags(a.text))
    if a.invalid_citations:
        st.error(f"The answer cited {', '.join(a.invalid_citations)}, which weren't provided. "
                 "Treat those claims with caution.", title="Invalid citations", icon=":material/error:")

    cited = set(a.citations)
    with st.expander(f"Sources cited ({len(cited)})", expanded=not a.abstained):
        if not cited:
            st.caption("No sources cited.")
        for tag in a.citations:
            i = int(tag[1:]) - 1
            if tag[0] == "F":
                f = a.facts[i]
                st.markdown(f"**[{tag}]** {md_safe(f.statement)}")
                st.caption(f"Computed from XBRL data · filing {', '.join(f.sources) or '—'}")
            else:
                c = a.passages[i].chunk
                acc, sec, idx = c.key.split("|")
                st.markdown(f"**[{tag}]** {c.company} · FY{c.fiscal_year} 10-K · Item {sec} "
                            f"{SECTION_NAMES.get(sec, '')}")
                st.caption(f"Accession {acc} · chunk {idx}")
                st.text(c.text[:1500] + ("…" if len(c.text) > 1500 else ""))

    if a.facts:
        with st.expander(f"Computed figures ({len(a.facts)})"):
            st.dataframe(
                [{"tag": f"F{i}", "cited": "✓" if f"F{i}" in cited else "", "figure": f.statement,
                  "filings": ", ".join(f.sources)} for i, f in enumerate(a.facts, 1)],
                hide_index=True, width="stretch", alt="Financial figures computed for this answer",
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
        if a.llm:
            st.caption(f"{a.llm.model} · {a.llm.prompt_tokens:,} prompt tokens · "
                       f"{a.llm.completion_tokens} answer tokens · {a.seconds:.1f}s")


# --- mode: live (Ollama + local index) or demo (pre-generated answers) ------------------------

DATA_COVERAGE = {
    "MSFT": "Microsoft · fiscal year ends June",
    "AAPL": "Apple · fiscal year ends September",
    "NVDA": "Nvidia · fiscal year ends late January",
}
TYPE_LABELS = {"factual": "Fact", "numerical": "Numbers", "comparative": "Comparison", "multi_step": "Multi-step",
               "narrative": "Narrative", "unanswerable": "Can't be answered"}


def index_built() -> bool:
    """Checked without importing torch/faiss, so demo-only deployments stay light."""
    from finsight.retrieval.common import load_config

    cfg = load_config()
    return (cfg["index_dir"] / cfg["embedding_model"].replace("/", "__") / "faiss.index").exists() \
        and cfg["db_path"].exists()


@st.cache_data(show_spinner=False)
def load_demo_entries():
    from finsight.demo import load_demo
    return load_demo()


cfg = load_llm_config()
forced_demo = os.environ.get("FINSIGHT_DEMO", "").lower() in ("1", "true", "yes")
demo_info, demo_entries = load_demo_entries()

with st.sidebar:
    st.header("Settings")
    if forced_demo:
        ok, status, models = False, "Demo mode (FINSIGHT_DEMO is set).", []
    elif not index_built():
        ok, status, models = False, "Search index not built: run scripts/extract_tables.py and scripts/build_index.py.", []
    else:
        ok, status, models = ollama_status(cfg["model"])

    live_possible = ok
    demo_mode = (not live_possible) or st.toggle(
        "Demo mode", value=False, disabled=not demo_entries,
        help="Browse pre-generated answers instead of asking the live model.")
    if demo_mode and not demo_entries:
        st.error("No demo answers found. Generate them with `uv run scripts/build_demo.py`.")

    if not demo_mode:
        model = st.selectbox("Model", models or [cfg["model"]],
                             index=(models.index(cfg["model"]) if cfg["model"] in models else 0),
                             help="Any model from `ollama list`. Default comes from configs/llm.yaml.")
        if model != cfg["model"]:
            ok, status, _ = ollama_status(model)
        st.success(status) if ok else st.error(status)
        n_passages = st.slider("Passages per answer", 3, 8, 5,
                               help="How many filing passages the model reads. More = more context, slower.")
    elif not forced_demo and not live_possible:
        st.info(f"Live mode unavailable: {status}")

    st.divider()
    st.subheader("Data")
    for t, desc in DATA_COVERAGE.items():
        st.markdown(f"**{t}** · {desc}")
    st.caption("SEC EDGAR 10-K filings for FY2024–FY2026 (financial data back to FY2022). "
               "Answers use only these filings; numbers are computed in Python, not by the model.")
    if not demo_mode and st.button("Clear conversation", icon=":material/delete:"):
        st.session_state.history = []
        st.rerun()


# --- main ------------------------------------------------------------------------------------

st.title(":material/query_stats: FinSight AI")
st.caption("Questions about Microsoft, Apple, and Nvidia, answered from their SEC 10-K filings with citations.")

if demo_mode and not demo_entries:
    st.error("Live mode is unavailable and no demo answers exist. See the sidebar.")

elif demo_mode:
    st.info(
        f"Real answers pre-generated by `{demo_info.get('model', '?')}` on {demo_info.get('generated', '?')} "
        f"(about {demo_info.get('avg_seconds', '?')} s each when live), shown unedited. "
        f"{demo_info.get('passed', '?')} of {demo_info.get('questions', '?')} pass the automatic evaluation "
        "checks; each answer shows its result. Run FinSight locally with Ollama to ask your own questions.",
        title="Demo mode", icon=":material/play_circle:")
    types = sorted({e["answer_type"] for e in demo_entries}, key=list(TYPE_LABELS).index)
    picked_types = st.pills("Question type", types, selection_mode="multi", key="demo_types",
                            format_func=lambda t: TYPE_LABELS.get(t, t), default=types)
    shown = [e for e in demo_entries if e["answer_type"] in (picked_types or types)]
    entry = st.selectbox(f"Pick a question ({len(shown)})", shown, key="demo_question",
                         format_func=lambda e: f"{e['question']}  ·  {TYPE_LABELS.get(e['answer_type'], '')}")
    if entry:
        with st.chat_message("user"):
            st.markdown(md_safe(entry["question"]))
        with st.chat_message("assistant"):
            if verdict := entry.get("evaluation"):
                if verdict["passed"]:
                    st.badge(verdict["reason"], icon=":material/check_circle:", color="green")
                else:
                    st.badge(f"Evaluation: {verdict['reason']}", icon=":material/cancel:", color="red")
            render_answer(entry["answer"])

else:
    if "history" not in st.session_state:
        st.session_state.history = []

    for item in st.session_state.history:
        with st.chat_message("user"):
            st.markdown(md_safe(item["question"]))
        with st.chat_message("assistant"):
            if item.get("error"):
                st.error(item["error"], icon=":material/error:")
            else:
                render_answer(item["answer"])

    question = st.chat_input("Ask a question about MSFT, AAPL, or NVDA…", key="question",
                             disabled=not ok, submit_mode="disable")

    # Suggestion chips before the first question; a pick goes through the same path as typed input.
    if not st.session_state.history:
        suggestions = st.empty()
        picked = suggestions.pills("Try asking", list(EXAMPLES), key="suggestion", label_visibility="collapsed")
        if picked and not question:
            question = EXAMPLES[picked]
        if question:
            suggestions.empty()

    if question:
        with st.chat_message("user"):
            st.markdown(md_safe(question))
        with st.chat_message("assistant"):
            item: dict[str, Any] = {"question": question}
            with st.status(":shimmer[Researching the filings]", type="compact") as progress:
                try:
                    item["answer"] = get_answerer(model, n_passages).ask(
                        question, step=lambda label: st.status(label, type="step"))
                    progress.update(label=f"Answered in {item['answer'].seconds:.0f} s", state="complete")
                except LLMUnavailable as e:
                    item["error"] = str(e)
                    progress.update(label="Couldn't reach the model", state="error")
            if item.get("error"):
                st.error(item["error"], icon=":material/error:")
            else:
                render_answer(item["answer"])
        st.session_state.history.append(item)
