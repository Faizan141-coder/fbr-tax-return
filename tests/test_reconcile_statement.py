from datetime import date

from fbr.engines.tabular import parse_tabular
from fbr.reconcile import check_statement, statement_usable, worst_status
from tests.fixtures.synth import SynthTxn, build_statement, corrupt, write_meezan_csv
from tests.test_tabular import MEEZAN


def _checks(data, profile=MEEZAN):
    res = parse_tabular(data, profile, sha256="a" * 64, filename="x.csv",
                        account_id="meezan-main")
    return res, check_statement(res, profile)


def _kinds(checks, status=None):
    return {c.kind for c in checks if status is None or c.status == status}


def test_a_clean_statement_passes_every_check():
    _, checks = _checks(write_meezan_csv(build_statement(seed=31)))
    assert _kinds(checks, "fail") == set()
    assert statement_usable(checks) is True
    assert worst_status(checks) == "pass"


def test_all_five_checks_are_reported():
    _, checks = _checks(write_meezan_csv(build_statement(seed=32)))
    assert _kinds(checks) == {
        "running_balance", "opening_closing", "printed_totals",
        "unresolved_rows", "date_range",
    }


def test_a_wrong_printed_total_fails_printed_totals():
    # Fix round 1, Finding 1: printed_totals is the only check available for
    # a statement that prints no balances at all (the SadaPay case), so it
    # must actually be exercised rather than sit unverified because MEEZAN
    # never printed a total for any test to corrupt.
    _, checks = _checks(corrupt(write_meezan_csv(build_statement(seed=42)), "wrong_total"))
    assert "printed_totals" in _kinds(checks, "fail")


def test_a_correctly_printed_total_passes():
    _, checks = _checks(write_meezan_csv(build_statement(seed=43)))
    assert "printed_totals" in _kinds(checks, "pass")


def test_a_dropped_row_breaks_the_running_balance():
    _, checks = _checks(corrupt(write_meezan_csv(build_statement(seed=33)), "drop_row"))
    assert "running_balance" in _kinds(checks, "fail")
    assert statement_usable(checks) is False


def test_a_flipped_sign_breaks_the_running_balance():
    _, checks = _checks(corrupt(write_meezan_csv(build_statement(seed=34)), "flip_sign"))
    assert "running_balance" in _kinds(checks, "fail")


def test_a_wrong_printed_closing_breaks_opening_closing():
    _, checks = _checks(corrupt(write_meezan_csv(build_statement(seed=35)), "wrong_total"))
    assert "opening_closing" in _kinds(checks, "fail")


def test_an_unresolved_row_fails_the_statement():
    _, checks = _checks(corrupt(write_meezan_csv(build_statement(seed=36)), "bad_amount"))
    assert "unresolved_rows" in _kinds(checks, "fail")
    assert statement_usable(checks) is False


def test_the_failing_check_locates_the_row():
    _, checks = _checks(corrupt(write_meezan_csv(build_statement(seed=37)), "drop_row"))
    failure = next(c for c in checks if c.kind == "running_balance" and c.status == "fail")
    assert failure.locator and failure.locator.startswith("row:")
    assert failure.expected != failure.actual


def test_running_balance_walks_printed_order_not_date_order():
    # Review Focus #2: a statement sorted by value date still reconciles,
    # because the balance chain follows the printed sequence.
    stmt = build_statement(
        opening=100000,
        rows=[SynthTxn(date(2025, 7, 9), "Later date first", 50000, None),
              SynthTxn(date(2025, 7, 5), "Earlier date second", -20000, None)],
    )
    _, checks = _checks(write_meezan_csv(stmt))
    assert "running_balance" not in _kinds(checks, "fail")
    # Fix round 1, Finding 3: this statement's printed period must be wide
    # enough to cover both rows even though the later date is printed first;
    # a period fixture that quietly excluded the first row would fail the
    # whole statement for a reason this test never intended to exercise.
    assert statement_usable(checks) is True


def test_a_date_outside_the_printed_period_fails():
    stmt = build_statement(
        opening=0, start=date(2025, 7, 1), end=date(2025, 7, 31),
        rows=[SynthTxn(date(2025, 7, 2), "In period", 50000, None),
              SynthTxn(date(2026, 3, 1), "Out of period", 10000, None)],
    )
    _, checks = _checks(write_meezan_csv(stmt))
    assert "date_range" in _kinds(checks, "fail")


def test_period_regex_does_not_cross_a_line_into_an_unrelated_row():
    # Fix round 1, Finding 2: `\D+?` matches a newline as readily as a
    # space, so a lazy non-digit separator could walk straight past an
    # unparseable "Statement Period" value and harvest a fabricated period
    # out of two unrelated rows below it. The fixed separator must refuse
    # to cross that line boundary, leaving the period simply unprinted
    # rather than wrong.
    stmt = build_statement(seed=45)
    period_line = (
        f"Statement Period,{stmt.period_start.strftime('%d %b %Y')} to "
        f"{stmt.period_end.strftime('%d %b %Y')}\r\n"
    ).encode()
    decoy = (b"Statement Period,not available\r\n"
             b"Printed,05 Aug 2025\r\n"
             b"Due,14 Sep 2025\r\n")
    data = write_meezan_csv(stmt).replace(period_line, decoy)
    res, checks = _checks(data)
    assert res.document.summary.period_start is None
    assert res.document.summary.period_end is None
    assert "date_range" in _kinds(checks, "warn")


def test_missing_opening_balance_warns_rather_than_fails():
    data = write_meezan_csv(build_statement(seed=38)).replace(b"OPENING BALANCE", b"NOT PRINTED")
    _, checks = _checks(data)
    assert "running_balance" in _kinds(checks, "warn")
    assert statement_usable(checks) is True


def test_no_balance_column_skips_the_balance_checks_without_failing():
    no_balance = MEEZAN.model_copy(update={
        "balance": MEEZAN.balance.model_copy(update={"semantics": "none"})
    })
    _, checks = _checks(write_meezan_csv(build_statement(seed=39)), no_balance)
    assert "running_balance" not in _kinds(checks, "fail")


def test_worst_status_prefers_fail_over_warn():
    _, clean = _checks(write_meezan_csv(build_statement(seed=40)))
    _, broken = _checks(corrupt(write_meezan_csv(build_statement(seed=40)), "drop_row"))
    assert worst_status(clean) in ("pass", "warn")
    assert worst_status(broken) == "fail"
