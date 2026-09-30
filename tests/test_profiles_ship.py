"""The shipped config must load, self-test, and detect the layouts it claims."""

from datetime import date
from pathlib import Path

import pytest

from fbr.config.loader import load_profiles, load_tax_year, run_selftest
from fbr.engines.tabular import parse_row, parse_tabular
from fbr.ingest import detect_layout
from fbr.reconcile import check_statement, statement_usable
from tests.fixtures.synth import (
    build_statement,
    corrupt,
    write_mcb_csv,
    write_meezan_csv,
    write_nayapay_csv,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def shipped():
    return load_profiles(ROOT / "profiles")


def test_shipped_profiles_load(shipped):
    assert {p.id for p in shipped.profiles} >= {
        "meezan.csv.v1", "mcb.csv.v1", "nayapay.csv.v1", "sadapay.pdf.v1"
    }


def test_every_shipped_profile_passes_its_own_selftest(shipped):
    for profile in shipped.profiles:
        status = run_selftest(profile, parse_row,
                              summary_text=profile.selftest.summary_sample or None)
        assert status.ok, f"{profile.id}: {status.message}"
        if profile.summary.compiled():
            # The message names the patterns only when they were exercised.
            assert "summary pattern" in status.message, profile.id


@pytest.mark.parametrize(
    "writer,expected_id",
    [
        (write_meezan_csv, "meezan.csv.v1"),
        (write_mcb_csv, "mcb.csv.v1"),
        (write_nayapay_csv, "nayapay.csv.v1"),
    ],
)
def test_each_profile_detects_and_reconciles_its_own_layout(shipped, writer, expected_id):
    stmt = build_statement(seed=81, start=date(2025, 7, 1), end=date(2026, 6, 30))
    data = writer(stmt)
    profile = detect_layout(data, shipped, "csv")
    assert profile.id == expected_id
    result = parse_tabular(data, profile, sha256="a" * 64, filename="x.csv",
                           account_id="acct")
    assert len(result.transactions) == len(stmt.txns)
    checks = check_statement(result, profile)
    assert statement_usable(checks), [c for c in checks if c.status == "fail"]

    # Fix round 1, Finding 2: every shipped profile now defines total_credit/
    # total_debit patterns, so printed_totals must actually run - not sit
    # absent (None, filtered out of `checks`) - and pass, for every layout.
    printed_totals = next((c for c in checks if c.kind == "printed_totals"), None)
    assert printed_totals is not None, f"{expected_id}: printed_totals did not run"
    assert printed_totals.status == "pass", printed_totals.detail


@pytest.mark.parametrize(
    "writer,expected_id",
    [
        (write_meezan_csv, "meezan.csv.v1"),
        (write_mcb_csv, "mcb.csv.v1"),
        (write_nayapay_csv, "nayapay.csv.v1"),
    ],
)
def test_printed_totals_fails_closed_when_a_bank_total_is_wrong(shipped, writer, expected_id):
    # Fix round 1, Finding 2: printed_totals is not just wired up, it is
    # load-bearing - a statement whose own declared total disagrees with
    # what was actually parsed must fail closed, for every shipped profile.
    stmt = build_statement(seed=90, start=date(2025, 7, 1), end=date(2026, 6, 30))
    data = corrupt(writer(stmt), "wrong_total")
    profile = shipped.by_id(expected_id)
    result = parse_tabular(data, profile, sha256="c" * 64, filename="x.csv",
                           account_id="acct")
    checks = check_statement(result, profile)
    printed_totals = next((c for c in checks if c.kind == "printed_totals"), None)
    assert printed_totals is not None, f"{expected_id}: printed_totals did not run"
    assert printed_totals.status == "fail"
    assert not statement_usable(checks)


def test_no_two_shipped_profiles_match_the_same_file(shipped):
    # Review Focus #3, at the level of the config that actually ships.
    stmt = build_statement(seed=82)
    for writer in (write_meezan_csv, write_mcb_csv, write_nayapay_csv):
        detect_layout(writer(stmt), shipped, "csv")   # raises if ambiguous


def test_ty2026_config_loads_with_the_verified_export_code():
    ty = load_tax_year("TY2026", ROOT / "taxyears")
    assert ty.name == "TY2026"
    assert ty.period_start == date(2025, 7, 1)
    assert ty.period_end == date(2026, 6, 30)
    # 64060285 is the 1% export line, verified against FBR's TY2024 form text.
    assert ty.codes["export_receipts"].code == "64060285"
    assert ty.codes["profit_final"].code == "64040052"
    assert ty.codes["salary_149"].code == "64020004"
    assert ty.codes["tax_236y"].code == "64151905"


def test_the_ty2026_wealth_bank_code_is_blank_and_flagged_unknown():
    # Unreadable in FBR's scanned SRO; the owner reads it off IRIS (open question A1).
    ty = load_tax_year("TY2026", ROOT / "taxyears")
    entry = ty.codes["wealth_bank_accounts"]
    assert entry.code == ""
    assert entry.verification == "unknown"


def test_thresholds_are_in_paisa():
    ty = load_tax_year("TY2026", ROOT / "taxyears")
    assert ty.thresholds.review_threshold == 1_000_000            # Rs 10,000
    assert ty.thresholds.profit_final_regime_max == 500_000_000   # Rs 5,000,000


def test_profiles_mark_values_that_a_real_dump_must_confirm():
    for name in ("meezan.csv.v1", "mcb.csv.v1", "nayapay.csv.v1"):
        text = (ROOT / "profiles" / f"{name}.toml").read_text()
        assert "VERIFY" in text, f"{name} must flag values awaiting a real dump"
