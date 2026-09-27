# app/state.py
"""Display helpers shared by the pages.

Pure functions only: everything here is testable without Streamlit, which
keeps the pages free of logic that could otherwise drift away from the rules
the rest of the codebase enforces.
"""

from __future__ import annotations

from fbr.pipeline import RunResult

STATUS_ICON = {"complete": "✅", "incomplete": "⚠️", "failed": "❌"}

VERIFICATION_MARK = {
    "iris_verified": "✓",
    "form_text": "⚠",
    "form_scan": "⚠",
    "prior_year_assumed": "⚠",
    "unknown": "✗",
}

VERIFICATION_HELP = {
    "iris_verified": "confirmed on the live IRIS screen",
    "form_text": "read from an FBR form's text layer; confirm in IRIS",
    "form_scan": "read by OCR from a scanned FBR form; confirm in IRIS",
    "prior_year_assumed": "carried over from last year; confirm in IRIS",
    "unknown": "not known; read it off IRIS before filing",
}


def mask_identifier(value: str) -> str:
    """Show only the last four characters of an account identifier."""
    if not value:
        return ""
    return f"…{value[-4:]}"


def summarize_run(run: RunResult) -> dict[str, int]:
    """Counts for the header strip."""
    return {
        "files_ok": sum(1 for o in run.outcomes if o.status == "ok"),
        "files_problem": sum(1 for o in run.outcomes if o.status != "ok"),
        "transactions": sum(o.transactions_parsed for o in run.outcomes),
        "accounts": len(run.ledgers),
        "checks_failed": sum(1 for c in run.all_checks if c.status == "fail"),
        "checks_warned": sum(1 for c in run.all_checks if c.status == "warn"),
    }
