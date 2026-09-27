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


# --- fix round 1 regressions -------------------------------------------------
#
# Three defects that all produced a confidently-labelled WRONG figure on the
# wealth statement rather than an obvious failure, which is the one outcome
# this tool must not have. Each test below fails against the behaviour that
# preceded the fix; the before/after figures are recorded in the comments.

# An account whose layout changed mid-year - one statement a running-balance
# CSV, the next an export without a balance column - needs two DISTINCT
# layout ids, since `profiles` is keyed by layout id. The no-balance variant
# above deliberately shares MEEZAN's id (so its own tests stay single-layout),
# so mixed-layout cases get their own.
NO_BALANCE_LAYOUT = NO_BALANCE_PROFILE.model_copy(update={"id": "meezan.csv.nb.v1"})
PROFILES_MIXED = {"meezan.csv.v1": MEEZAN, "meezan.csv.nb.v1": NO_BALANCE_LAYOUT}


def test_a_tax_year_dormant_account_ignores_activity_before_the_year(ty):
    # Finding 1. The statement runs a month early, and its only row predates
    # the tax year. The printed opening (300000) is the balance on 1 June, not
    # on 1 July: the 15 June credit has already landed by the time the tax
    # year starts. Both boundaries are therefore 310000.
    # Before: 300000/310000, both labelled "printed", status "complete".
    stmt = build_statement(
        opening=300000, start=date(2025, 6, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2025, 6, 15), "Before TY", 10000, None)],
    )
    led = merge_account([_result(stmt)], _account(), ty, profiles=PROFILES)
    assert led.transactions == ()
    assert led.opening == 310000 and led.opening_source == "computed"
    assert led.closing == 310000 and led.closing_source == "computed"
    # Not "printed": neither printed figure is a tax-year boundary, and a
    # derived number must never claim the statement printed it.
    assert led.status == "complete"


def test_a_tax_year_dormant_account_ignores_activity_after_the_year(ty):
    # Finding 1, mirrored. The statement runs a month late and its only row
    # falls after 30 June, so it has not moved the balance by either boundary:
    # the printed closing (310000) belongs to 31 July, not to 30 June.
    # Before: 300000/310000, both labelled "printed", status "complete".
    stmt = build_statement(
        opening=300000, start=date(2025, 7, 1), end=date(2026, 7, 31),
        rows=[SynthTxn(date(2026, 7, 15), "After TY", 10000, None)],
    )
    led = merge_account([_result(stmt)], _account(), ty, profiles=PROFILES)
    assert led.transactions == ()
    assert led.opening == 300000 and led.opening_source == "computed"
    assert led.closing == 300000 and led.closing_source == "computed"
    assert led.status == "complete"


def test_partially_overlapping_statements_keep_each_real_row_exactly_once(ty):
    # Finding 2. Jul-Dec and Nov-Jun both print November. Overlap detection
    # used to require full containment, so neither statement contained the
    # other, no overlap check fired, and November's single real transaction
    # was counted twice - 4 rows where 3 are real, overstating income, and
    # reported as "complete".
    first = build_statement(
        opening=100000, start=date(2025, 7, 1), end=date(2025, 12, 31),
        rows=[SynthTxn(date(2025, 8, 1), "A", 50000, None),
              SynthTxn(date(2025, 11, 15), "N", 20000, None)],
    )
    second = build_statement(
        opening=150000, start=date(2025, 11, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2025, 11, 15), "N", 20000, None),
              SynthTxn(date(2026, 2, 1), "B", -30000, None)],
    )
    led = merge_account([_result(first), _result(second, sha="b" * 64)],
                        _account(), ty, profiles=PROFILES)
    assert [t.description for t in led.transactions] == ["A", "N", "B"]
    assert len(led.transactions) == 3          # was 4: November counted twice
    assert "overlap" in _kinds(led)            # the shared window is reported
    assert "overlap" not in _kinds(led, "fail")   # ... and the two agree
    # February survives: only the intersecting slice is resolved, never the
    # whole of the later statement.
    assert led.opening == 100000
    assert led.closing == 140000
    assert led.status == "complete"


def test_mixed_profiles_recover_the_opening_when_the_early_half_has_no_balances(ty):
    # Finding 3. The Jul-Dec export carries no balance column; the Jan-Jun one
    # does. `has_balance` is true for the account as a whole, so the opening
    # was read off the first in-year row - which has no balance - and came
    # back None, while the warning claimed no anchor had been supplied when
    # one had. Before: opening None/"unknown", a false "no anchor" warning,
    # status "incomplete".
    early = build_statement(
        opening=500000, start=date(2025, 7, 1), end=date(2025, 12, 31),
        rows=[SynthTxn(date(2025, 8, 1), "A", 50000, None)],
    )
    late = build_statement(
        opening=550000, start=date(2026, 1, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2026, 2, 1), "B", -20000, None)],
    )
    led = merge_account(
        [_result(early, NO_BALANCE_LAYOUT), _result(late, MEEZAN, sha="b" * 64)],
        _account(), ty, anchor=500000, profiles=PROFILES_MIXED,
    )
    assert len(led.transactions) == 2
    # The half that does carry balances, plus the year's net movement, fixes
    # the 1 July figure exactly - and it agrees with the anchor the owner gave.
    assert led.opening == 500000 and led.opening_source == "computed"
    assert led.closing == 530000 and led.closing_source == "printed"
    assert "anchor_missing" not in _kinds(led, "warn")   # an anchor WAS supplied
    assert led.status == "complete"


def test_mixed_profiles_recover_the_closing_when_the_late_half_has_no_balances(ty):
    # Finding 3, mirrored, and the dangerous half: the 30 June figure - the
    # one the owner types onto the wealth statement - came back None with NO
    # warning at all and status "complete". A missing 30 June figure must
    # never ship as complete. Before: closing None/"unknown", status
    # "complete", no warning.
    early = build_statement(
        opening=500000, start=date(2025, 7, 1), end=date(2025, 12, 31),
        rows=[SynthTxn(date(2025, 8, 1), "A", 50000, None)],
    )
    late = build_statement(
        opening=550000, start=date(2026, 1, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2026, 2, 1), "B", -20000, None)],
    )
    led = merge_account(
        [_result(early, MEEZAN), _result(late, NO_BALANCE_LAYOUT, sha="b" * 64)],
        _account(), ty, profiles=PROFILES_MIXED,
    )
    assert len(led.transactions) == 2
    assert led.opening == 500000 and led.opening_source == "printed"
    assert led.closing == 530000 and led.closing_source == "computed"
    assert led.closing_source != "unknown"
    # Complete is only honest because the figure is now determined, not
    # because a hole went unreported - see the next test for the other case.
    assert led.status == "complete"


# --- spec §6.2 continuity chain (final fix round, Finding 4) ----------------


def test_a_break_in_the_balance_chain_between_statements_fails(ty):
    # Only date gaps were checked. These two meet perfectly in time and each
    # reconciles on its own, so nothing fired: the merged ledger reported
    # closing 9,100.00 and status "complete" over a 7,500.00 discontinuity.
    first = build_statement(
        opening=100000, start=date(2025, 7, 1), end=date(2025, 12, 31),
        rows=[SynthTxn(date(2025, 8, 1), "A", 50000, None)],
    )                                   # closes at 1,500.00
    second = build_statement(
        opening=900000, start=date(2026, 1, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2026, 2, 1), "B", 10000, None)],
    )                                   # opens at 9,000.00
    led = merge_account([_result(first), _result(second, sha="b" * 64)],
                        _account(), ty, profiles=PROFILES)

    assert "continuity" in _kinds(led, "fail")
    broken = next(c for c in led.checks if c.kind == "continuity")
    assert broken.expected == "1,500.00" and broken.actual == "9,000.00"
    assert "7,500.00" in broken.detail
    assert "gap" not in _kinds(led, "warn")      # the dates really are contiguous
    # Fail closed: the account contributes nothing until the cause is fixed.
    assert led.status == "failed"
    assert led.transactions == ()


def test_an_unbroken_balance_chain_passes(ty):
    first = build_statement(
        opening=100000, start=date(2025, 7, 1), end=date(2025, 12, 31),
        rows=[SynthTxn(date(2025, 8, 1), "A", 50000, None)],
    )
    second = build_statement(
        opening=first.closing, start=date(2026, 1, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2026, 2, 1), "B", -20000, None)],
    )
    led = merge_account([_result(first), _result(second, sha="b" * 64)],
                        _account(), ty, profiles=PROFILES)
    assert "continuity" in _kinds(led, "pass")
    assert led.status == "complete"


def test_the_chain_is_ordered_by_period_not_by_file_order(ty):
    # The same two statements handed over newest-first must produce the same
    # verdict, or the check would depend on the order the owner's folder
    # happened to list the files in.
    first = build_statement(
        opening=100000, start=date(2025, 7, 1), end=date(2025, 12, 31),
        rows=[SynthTxn(date(2025, 8, 1), "A", 50000, None)],
    )
    second = build_statement(
        opening=first.closing, start=date(2026, 1, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2026, 2, 1), "B", -20000, None)],
    )
    led = merge_account([_result(second, sha="b" * 64), _result(first)],
                        _account(), ty, profiles=PROFILES)
    assert "continuity" in _kinds(led, "pass")
    assert "continuity" not in _kinds(led, "fail")


def test_a_gap_between_statements_does_not_also_fail_continuity(ty):
    # With days missing between them, the balance legitimately moved in
    # between. The gap warning is the right report; failing the balance
    # chain as well would turn every incomplete account into a failed one.
    first = build_statement(
        opening=100000, start=date(2025, 7, 1), end=date(2025, 9, 30),
        rows=[SynthTxn(date(2025, 8, 1), "A", 50000, None)],
    )
    later = build_statement(
        opening=999999, start=date(2026, 1, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2026, 2, 1), "B", -20000, None)],
    )
    led = merge_account([_result(first), _result(later, sha="b" * 64)],
                        _account(), ty, profiles=PROFILES)
    assert "gap" in _kinds(led, "warn")
    assert "continuity" not in _kinds(led)
    assert led.status == "incomplete"


def test_overlapping_statements_do_not_also_fail_continuity(ty):
    # Overlapping periods are the overlap check's business; their printed
    # opening/closing pairs are not a chain and must not be read as one.
    stmt = build_statement(
        opening=100000, start=date(2025, 7, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2025, 8, 1), "A", 50000, None)],
    )
    led = merge_account([_result(stmt), _result(stmt, sha="b" * 64)],
                        _account(), ty, profiles=PROFILES)
    assert "continuity" not in _kinds(led)
    assert led.status == "complete"


def test_an_undeterminable_closing_balance_is_named_in_the_warning(ty):
    # Finding 3, the invariant behind both halves: when nothing - statement
    # or anchor - determines a boundary, the warning must say which boundary,
    # and the account must not be complete. The warning used to speak only of
    # the 1 July balance and only fired when the OPENING was unknown, so an
    # unknown 30 June figure could pass silently.
    stmt = build_statement(
        opening=0, start=date(2025, 7, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2025, 8, 1), "A", 50000, None)],
    )
    res = parse_tabular(write_meezan_csv(stmt), NO_BALANCE_PROFILE, sha256="a" * 64,
                        filename="x.csv", account_id="meezan-main")
    led = merge_account([res], _account(), ty, profiles=PROFILES_NB)
    assert led.closing is None and led.closing_source == "unknown"
    warning = next(c for c in led.checks if c.kind == "anchor_missing")
    assert "30 June" in warning.expected and "30 June" in warning.detail
    assert led.status != "complete"
