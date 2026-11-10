---
name: session-wrap
description: End-of-session wrap-up for FinSight AI. Runs the tests, updates PROGRESS.md with what changed this session, and drafts a commit message. Use when the user says they're done for the day, wants to wrap up, or asks to update progress notes.
---

# Session wrap-up

1. **Tests.** Run `.venv/bin/python -m pytest tests/ -q`. If anything fails, report it and stop; do not mark work complete.

2. **What changed.** Run `git status --short` and `git diff --stat HEAD`. Combine with what was done in this conversation.

3. **DB snapshot** (if `data/finsight.db` exists):
   `sqlite3 data/finsight.db "select count(*) from filing_chunks; select count(*) from financial_facts;"`
   Update any counts in PROGRESS.md that no longer match.

4. **Update PROGRESS.md.**
   - Mark finished items done in the "What's next" plan; move newly completed work into the matching "Week N" section, with files built and key decisions (the *why*, not just the *what*).
   - Update the "Current state" line.
   - Add any new gotchas (parser quirks, data issues) where a future session would need them.
   - Keep it concise; it is loaded into every session via CLAUDE.md.

5. **Commit message.** Draft one (summary line + bullets) and show it. Do not commit or push unless the user says so. If on `main`, suggest a branch first.

6. **Report** in a few lines: tests result, what PROGRESS.md now says is next, and the drafted commit message.
