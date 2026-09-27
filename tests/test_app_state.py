# tests/test_app_state.py
"""The pure helpers behind the pages. Streamlit itself is not exercised here;
the privacy smoke test in Step 6 covers the running app."""

import pytest

from app.state import STATUS_ICON, VERIFICATION_MARK, mask_identifier, summarize_run


@pytest.mark.parametrize(
    "value,expected",
    [
        ("PK00TEST0000000000003474", "…3474"),
        ("03001234567", "…4567"),
        ("1234", "…1234"),
        ("12", "…12"),
        ("", ""),
    ],
)
def test_identifiers_are_masked_for_display(value, expected):
    assert mask_identifier(value) == expected


def test_masking_never_shows_a_full_iban():
    full = "PK00TEST0000000000003474"
    assert full not in mask_identifier(full)


def test_status_icons_cover_every_account_status():
    assert set(STATUS_ICON) == {"complete", "incomplete", "failed"}


def test_verification_marks_cover_every_state():
    assert set(VERIFICATION_MARK) == {
        "iris_verified", "form_text", "form_scan", "prior_year_assumed", "unknown"
    }
    assert VERIFICATION_MARK["iris_verified"] == "✓"
    assert VERIFICATION_MARK["unknown"] == "✗"


def test_summarize_counts_outcomes_and_checks():
    from fbr.model import Check
    from fbr.pipeline import FileOutcome, RunResult

    run = RunResult(
        outcomes=(
            FileOutcome("a.csv", "h1", "ok", "meezan.csv.v1", "meezan-main", "", 12),
            FileOutcome("b.csv", "h2", "unknown_layout", None, None, "no match", 0),
        ),
        ledgers={},
        account_status={"meezan-main": "complete"},
        all_checks=(
            Check("c1", "document", "running_balance", "pass", "", "", ""),
            Check("c2", "account", "gap", "warn", "", "", ""),
            Check("c3", "document", "unresolved_rows", "fail", "", "", ""),
        ),
    )
    s = summarize_run(run)
    assert s["files_ok"] == 1
    assert s["files_problem"] == 1
    assert s["transactions"] == 12
    assert s["checks_failed"] == 1
    assert s["checks_warned"] == 1


def test_summarize_handles_an_empty_run():
    from fbr.pipeline import RunResult

    s = summarize_run(RunResult(outcomes=()))
    assert s["files_ok"] == 0 and s["transactions"] == 0
