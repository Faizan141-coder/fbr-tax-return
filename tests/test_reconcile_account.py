from datetime import date

import pytest

from fbr.config.loader import load_tax_year
from fbr.engines.tabular import parse_tabular
from fbr.model import Account
from fbr.reconcile import merge_account
from tests.fixtures.synth import SynthTxn, build_statement, write_meezan_csv
from tests.test_loader import TAXYEAR_TOML
from tests.test_tabular import MEEZAN


@pytest.fixture
def ty(tmp_path):
    (tmp_path / "TY2026.toml").write_text(TAXYEAR_TOML)
    return load_tax_year("TY2026", tmp_path)


def _account(**over):
    base = dict(
        id="meezan-main", institution="Meezan Bank Limited", kind="bank",
        iban="PK00TEST0000000000000000", account_number="", wallet_number="",
        title="ACCOUNT TITLE", type="Saving", ownership="Self", currency="PKR",
        statement_expected=True, match_hints=("MEEZAN",), opened_on=None, closed_on=None,
    )
    return Account(**{**base, **over})


# merge_account requires the profile that parsed each statement, so the
# per-statement checks can run. Both variants keep the same layout id.
NO_BALANCE_PROFILE = MEEZAN.model_copy(update={
    "balance": MEEZAN.balance.model_copy(update={"semantics": "none"})
})
PROFILES = {"meezan.csv.v1": MEEZAN}
PROFILES_NB = {"meezan.csv.v1": NO_BALANCE_PROFILE}


def _result(stmt, profile=MEEZAN, sha="a" * 64):
    return parse_tabular(write_meezan_csv(stmt), profile, sha256=sha,
                         filename="x.csv", account_id="meezan-main")


def _kinds(ledger, status=None):
    return {c.kind for c in ledger.checks if status is None or c.status == status}


def test_single_full_year_statement_yields_printed_boundaries(ty):
    stmt = build_statement(
        opening=100000, start=date(2025, 7, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2025, 7, 2), "Top-up", 50000, None),
              SynthTxn(date(2026, 6, 29), "Withdrawal", -20000, None)],
    )
    led = merge_account([_result(stmt)], _account(), ty, profiles=PROFILES)
    assert led.opening == 100000 and led.opening_source == "printed"
    assert led.closing == 130000 and led.closing_source == "printed"
    assert led.status == "complete"


def test_two_contiguous_statements_merge(ty):
    first = build_statement(
        opening=100000, start=date(2025, 7, 1), end=date(2025, 12, 31),
        rows=[SynthTxn(date(2025, 8, 1), "A", 50000, None)],
    )
    second = build_statement(
        opening=first.closing, start=date(2026, 1, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2026, 2, 1), "B", -20000, None)],
    )
    led = merge_account([_result(first), _result(second, sha="b" * 64)], _account(), ty, profiles=PROFILES)
    assert len(led.transactions) == 2
    assert led.opening == 100000
    assert led.closing == 130000
    assert "gap" not in _kinds(led, "warn")


def test_a_gap_between_statements_warns_and_marks_incomplete(ty):
    first = build_statement(
        opening=100000, start=date(2025, 7, 1), end=date(2025, 9, 30),
        rows=[SynthTxn(date(2025, 8, 1), "A", 50000, None)],
    )
    third = build_statement(
        opening=999999, start=date(2026, 1, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2026, 2, 1), "B", -20000, None)],
    )
    led = merge_account([_result(first), _result(third, sha="b" * 64)], _account(), ty, profiles=PROFILES)
    assert "gap" in _kinds(led, "warn")
    assert led.status == "incomplete"


def test_a_missing_start_of_year_counts_as_a_gap(ty):
    stmt = build_statement(
        opening=100000, start=date(2025, 10, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2025, 10, 5), "A", 50000, None)],
    )
    led = merge_account([_result(stmt)], _account(), ty, profiles=PROFILES)
    assert "gap" in _kinds(led, "warn")


def test_an_account_opened_mid_year_has_no_false_gap(ty):
    stmt = build_statement(
        opening=0, start=date(2025, 10, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2025, 10, 5), "First ever credit", 50000, None)],
    )
    led = merge_account([_result(stmt)], _account(opened_on=date(2025, 10, 1)), ty, profiles=PROFILES)
    assert "gap" not in _kinds(led, "warn")
    assert led.status == "complete"


def test_identical_overlapping_statements_deduplicate_by_period(ty):
    stmt = build_statement(
        opening=100000, start=date(2025, 7, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2025, 8, 1), "A", 50000, None)],
    )
    led = merge_account([_result(stmt), _result(stmt, sha="b" * 64)], _account(), ty, profiles=PROFILES)
    assert len(led.transactions) == 1
    assert "overlap" not in _kinds(led, "fail")


def test_disagreeing_overlapping_statements_fail(ty):
    a = build_statement(
        opening=100000, start=date(2025, 7, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2025, 8, 1), "A", 50000, None)],
    )
    b = build_statement(
        opening=100000, start=date(2025, 7, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2025, 8, 1), "A", 60000, None)],
    )
    led = merge_account([_result(a), _result(b, sha="b" * 64)], _account(), ty, profiles=PROFILES)
    assert "overlap" in _kinds(led, "fail")
    assert led.status == "failed"


def test_two_identical_same_day_transactions_are_both_kept(ty):
    # Not duplicates: two genuine Rs 1,000 top-ups on one day.
    stmt = build_statement(
        opening=0, start=date(2025, 7, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2025, 8, 1), "TOPUP", 100000, None),
              SynthTxn(date(2025, 8, 1), "TOPUP", 100000, None)],
    )
    led = merge_account([_result(stmt)], _account(), ty, profiles=PROFILES)
    assert len(led.transactions) == 2
    assert led.closing == 200000


def test_transactions_outside_the_tax_year_are_excluded_from_boundaries(ty):
    stmt = build_statement(
        opening=100000, start=date(2025, 6, 1), end=date(2026, 7, 31),
        rows=[SynthTxn(date(2025, 6, 15), "Before TY", 10000, None),
              SynthTxn(date(2025, 8, 1), "In TY", 50000, None),
              SynthTxn(date(2026, 7, 15), "After TY", 70000, None)],
    )
    led = merge_account([_result(stmt)], _account(), ty, profiles=PROFILES)
    assert [t.description for t in led.transactions] == ["In TY"]
    assert led.opening == 110000          # balance after the pre-TY row
    assert led.opening_source == "computed"
    assert led.closing == 160000          # balance after the last in-TY row
    assert led.closing_source == "computed"


def test_a_dormant_account_still_reports_boundaries(ty):
    # Review Focus #5: no transactions in the year, but printed balances exist.
    stmt = build_statement(
        opening=250000, start=date(2025, 7, 1), end=date(2026, 6, 30), rows=[]
    )
    led = merge_account([_result(stmt)], _account(), ty, profiles=PROFILES)
    assert led.transactions == ()
    assert led.opening == 250000 and led.closing == 250000
    assert led.status == "complete"


def test_no_balance_column_uses_the_anchor(ty):
    stmt = build_statement(
        opening=0, start=date(2025, 7, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2025, 8, 1), "A", 50000, None),
              SynthTxn(date(2025, 9, 1), "B", -20000, None)],
    )
    res = parse_tabular(write_meezan_csv(stmt), NO_BALANCE_PROFILE, sha256="a" * 64,
                        filename="x.csv", account_id="meezan-main")
    led = merge_account([res], _account(), ty, anchor=500000, profiles=PROFILES_NB)
    assert led.opening == 500000 and led.opening_source == "anchor"
    assert led.closing == 530000 and led.closing_source == "computed"


def test_no_balance_column_and_no_anchor_yields_unknown_never_zero(ty):
    stmt = build_statement(
        opening=0, start=date(2025, 7, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2025, 8, 1), "A", 50000, None)],
    )
    res = parse_tabular(write_meezan_csv(stmt), NO_BALANCE_PROFILE, sha256="a" * 64,
                        filename="x.csv", account_id="meezan-main")
    led = merge_account([res], _account(), ty, profiles=PROFILES_NB)
    assert led.opening is None and led.opening_source == "unknown"
    assert led.closing is None and led.closing_source == "unknown"
    assert "anchor_missing" in _kinds(led, "warn")


def test_prior_year_mismatch_warns(ty):
    stmt = build_statement(
        opening=100000, start=date(2025, 7, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2025, 8, 1), "A", 50000, None)],
    )
    led = merge_account([_result(stmt)], _account(), ty, prior_year_closing=999999, profiles=PROFILES)
    assert "prior_year_mismatch" in _kinds(led, "warn")


def test_a_missing_profile_raises_rather_than_skipping_the_checks(ty):
    # Fail closed: silently skipping per-statement checks would let a broken
    # statement through.
    stmt = build_statement(seed=52, start=date(2025, 7, 1), end=date(2026, 6, 30))
    with pytest.raises(KeyError, match="no profile supplied"):
        merge_account([_result(stmt)], _account(), ty, profiles={})


def test_a_failed_statement_makes_the_account_failed(ty):
    from tests.fixtures.synth import corrupt
    stmt = build_statement(seed=51, start=date(2025, 7, 1), end=date(2026, 6, 30))
    bad = parse_tabular(corrupt(write_meezan_csv(stmt), "drop_row"), MEEZAN,
                        sha256="a" * 64, filename="x.csv", account_id="meezan-main")
    led = merge_account([bad], _account(), ty, profiles=PROFILES)
    assert led.status == "failed"
    assert led.transactions == ()      # fail closed: contributes nothing
