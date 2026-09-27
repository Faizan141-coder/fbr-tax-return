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
    from typing import get_args

    from fbr.reconcile import AccountStatus

    # Every status an AccountLedger can carry, plus "missing" - an expected
    # account that produced no ledger at all, which has nothing to reconcile
    # but still needs a row on the Checks page (final fix round, Finding 5).
    assert set(STATUS_ICON) == set(get_args(AccountStatus)) | {"missing"}
    assert set(STATUS_ICON) == {"complete", "incomplete", "failed", "missing"}


def test_every_status_the_pipeline_reports_has_an_icon():
    # The Checks page indexes STATUS_ICON directly, so a status the pipeline
    # can produce but the map does not hold is a KeyError in the owner's face.
    from datetime import date
    from pathlib import Path

    from fbr.config.loader import load_profiles, load_tax_year
    from fbr.model import Account, Owner, Registry
    from fbr.pipeline import InputFile, load_files
    from tests.fixtures.synth import SynthTxn, build_statement, write_meezan_csv

    root = Path(__file__).resolve().parents[1]
    registry = Registry(
        owner=Owner(name="OWNER NAME"),
        accounts=(
            Account(id="meezan-main", institution="Meezan Bank Limited", kind="bank",
                    iban="PK00TEST0000000000000000", account_number="", wallet_number="",
                    title="T", type="Saving", ownership="Self", currency="PKR",
                    statement_expected=True),
            Account(id="mcb-main", institution="MCB Bank Limited", kind="bank",
                    iban="PK00TEST1111111111111111", account_number="", wallet_number="",
                    title="T", type="Current", ownership="Self", currency="PKR",
                    statement_expected=True),
        ),
    )
    stmt = build_statement(
        opening=100000, start=date(2025, 7, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2025, 8, 1), "Top-up", 50000, None)],
        account_id="PK00TEST0000000000000000",
    )
    run = load_files(
        [InputFile("meezan.csv", write_meezan_csv(stmt))],
        registry=registry,
        profiles=load_profiles(root / "profiles"),
        tax_year=load_tax_year("TY2026", root / "taxyears"),
    )
    assert set(run.account_status.values()) == {"complete", "missing"}
    for status in run.account_status.values():
        assert status in STATUS_ICON


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
