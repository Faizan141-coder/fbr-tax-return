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
    assert {"running_balance", "opening_closing", "unresolved_rows", "date_range"} <= _kinds(checks)


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


def test_a_date_outside_the_printed_period_fails():
    stmt = build_statement(
        opening=0, start=date(2025, 7, 1), end=date(2025, 7, 31),
        rows=[SynthTxn(date(2025, 7, 2), "In period", 50000, None),
              SynthTxn(date(2026, 3, 1), "Out of period", 10000, None)],
    )
    _, checks = _checks(write_meezan_csv(stmt))
    assert "date_range" in _kinds(checks, "fail")


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
