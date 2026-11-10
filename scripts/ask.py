"""Ask FinSight a question from the command line.

Usage: uv run scripts/ask.py "What drove Microsoft's revenue growth in fiscal year 2026?" [--show-prompt]
"""

import argparse
import textwrap

from finsight.reasoning.answerer import Answerer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--model", help="override configs/llm.yaml model, e.g. gemma3:12b")
    ap.add_argument("--show-prompt", action="store_true")
    args = ap.parse_args()

    from finsight.reasoning.llm import LLMClient
    answerer = Answerer(llm=LLMClient(model=args.model))
    answerer.llm.check()
    a = answerer.ask(args.question)

    p = a.parsed
    print(f"Parsed: companies={p.tickers or 'any'} years={p.fiscal_years or 'latest'} metrics={p.metrics or '-'}\n")
    if args.show_prompt:
        print(answerer.build_prompt(a.question, a.facts, a.passages, a.notes), "\n" + "-" * 80)
    print(textwrap.fill(a.text, 100, replace_whitespace=False), "\n")
    print("Sources:")
    for s in a.sources():
        print("  " + s)
    if a.invalid_citations:
        print(f"  WARNING: answer cited sources that don't exist: {a.invalid_citations}")
    print(f"\n{a.llm.model} | {a.llm.prompt_tokens} prompt tokens | {a.seconds:.1f}s")


if __name__ == "__main__":
    main()
