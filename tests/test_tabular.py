from datetime import date

import pytest

from fbr.config.loader import run_selftest
from fbr.config.schema_profile import Profile
from fbr.engines.tabular import ParseError, parse_row, parse_tabular
from tests.fixtures.synth import (
    SynthTxn,
    build_statement,
    corrupt,
    write_meezan_csv,
    write_mcb_csv,
    write_nayapay_csv,
    write_xlsx,
)

MEEZAN = Profile.model_validate({
    "id": "meezan.csv.v1", "institution": "Meezan Bank Limited", "container": "csv",
    "valid_from": date(2025, 7, 1),
    "detect": {"header_contains": ["Booking Date", "Value Date"]},
    "columns": {"date": "Booking Date", "value_date": "Value Date",
                "description": "Description", "reference": "Doc No",
                "debit": "Debit", "credit": "Credit", "balance": "Available Balance"},
    "formats": {"dates": ["%d %b %Y"], "sign": "columns"},
    "summary": {
        # The separator between a label and its value is `[^\d\n]+?`, not
        # `\D+?`: `\D` matches a newline just as readily as a space, so a
        # lazy `\D+?` can walk straight past an unparseable value on its own
        # line and harvest a number out of a completely unrelated row below
        # it (fix round 1, Finding 2 - the same family of defect as an
        # earlier greedy-`\D+` bug in this plan, just without a sign to
        # invert). `[^\d\n]+?` cannot cross that line boundary, so a label
        # with no parseable value of its own simply fails to match, which is
        # what feeds the "not printed" warn path instead of a fabricated one.
        "opening": r"(?i)OPENING\s+BALANCE[^\d\n]+?(?P<value>-?[\d,]+\.\d{2})",
        "closing": r"(?i)CLOSING\s+BALANCE[^\d\n]+?(?P<value>-?[\d,]+\.\d{2})",
        "total_credit": r"(?i)TOTAL\s+CREDIT[^\d\n]+?(?P<value>-?[\d,]+\.\d{2})",
        "total_debit": r"(?i)TOTAL\s+DEBIT[^\d\n]+?(?P<value>-?[\d,]+\.\d{2})",
        "period_from": r"(?i)STATEMENT\s+PERIOD[^\d\n]+?(?P<value>\d{1,2}\s+[A-Za-z]{3}\s+\d{4})",
        "period_to": r"(?i)STATEMENT\s+PERIOD[^\d\n]+?\d{1,2}\s+[A-Za-z]{3}\s+\d{4}[^\d\n]+?"
                     r"(?P<value>\d{1,2}\s+[A-Za-z]{3}\s+\d{4})",
    },
    "balance": {"semantics": "running", "kind": "available"},
    "selftest": {"cases": [{
        "row": {"Booking Date": "01 Jul 2025", "Value Date": "01 Jul 2025",
                "Doc No": "D00001", "Description": "Top-up", "Debit": "",
                "Credit": "1,000.00", "Available Balance": "1,000.00"},
        "expect_date": date(2025, 7, 1), "expect_amount": 100000}]},
})

MCB = Profile.model_validate({
    "id": "mcb.csv.v1", "institution": "MCB Bank Limited", "container": "csv",
    "valid_from": date(2025, 7, 1),
    "detect": {"header_contains": ["Date", "Reference Number", "Amount"]},
    "columns": {"date": "Date", "description": "Description",
                "reference": "Reference Number", "amount": "Amount", "balance": "Balance"},
    "formats": {"dates": ["%d %b %Y"], "sign": "suffix",
                "debit_tokens": ["Dr"], "credit_tokens": ["Cr"]},
    "summary": {
        "opening": r"(?i)Opening\s+Balance\D+?(?P<value>-?[\d,]+\.\d{2})",
        "closing": r"(?i)Closing\s+Balance\D+?(?P<value>-?[\d,]+\.\d{2})",
    },
    "balance": {"semantics": "running", "kind": "ledger"},
    "selftest": {"cases": [{
        "row": {"Date": "01 Jul 2025", "Description": "Cash", "Reference Number": "1",
                "Amount": "200.00Dr", "Balance": "800.00"},
        "expect_date": date(2025, 7, 1), "expect_amount": -20000}]},
})

NAYAPAY = Profile.model_validate({
    "id": "nayapay.csv.v1", "institution": "NayaPay", "container": "csv",
    "valid_from": date(2025, 7, 1),
    "detect": {"header_contains": ["Date", "Type", "Amount", "Balance"]},
    "columns": {"date": "Date", "description": "Description", "type": "Type",
                "amount": "Amount", "balance": "Balance"},
    "formats": {"dates": ["%d %b %Y"], "sign": "signed"},
    "summary": {
        "total_credit": r"(?i)Total\s+Income\D+?(?P<value>-?[\d,]+\.\d{2})",
        "total_debit": r"(?i)Total\s+Spent\D+?(?P<value>-?[\d,]+\.\d{2})",
    },
    "balance": {"semantics": "running", "kind": "ledger"},
    "selftest": {"cases": [{
        "row": {"Date": "01 Jul 2025", "Time": "10:15 AM", "Type": "IBFT In",
                "Description": "x", "Amount": "+Rs. 500.00", "Balance": "Rs. 1,500.00"},
        "expect_date": date(2025, 7, 1), "expect_amount": 50000}]},
})


NO_BALANCE_IN_SELFTEST = Profile.model_validate({
    "id": "meezan.csv.v2-no-balance-selftest", "institution": "Meezan Bank Limited",
    "container": "csv", "valid_from": date(2025, 7, 1),
    "detect": {"header_contains": ["Booking Date", "Value Date"]},
    "columns": {"date": "Booking Date", "value_date": "Value Date",
                "description": "Description", "reference": "Doc No",
                "debit": "Debit", "credit": "Credit", "balance": "Available Balance"},
    "formats": {"dates": ["%d %b %Y"], "sign": "columns"},
    "summary": {
        "opening": r"(?i)OPENING\s+BALANCE\D+?(?P<value>-?[\d,]+\.\d{2})",
        "closing": r"(?i)CLOSING\s+BALANCE\D+?(?P<value>-?[\d,]+\.\d{2})",
    },
    "balance": {"semantics": "running", "kind": "available"},
    "selftest": {"cases": [{
        # Deliberately omits "Available Balance": a selftest case pins only
        # (date, amount), so parse_row/run_selftest must not require a
        # balance column just because the profile declares a running one.
        "row": {"Booking Date": "01 Jul 2025", "Value Date": "01 Jul 2025",
                "Doc No": "D00001", "Description": "Top-up", "Debit": "",
                "Credit": "1,000.00"},
        "expect_date": date(2025, 7, 1), "expect_amount": 100000}]},
})


def _parse(data, profile, account_id="acct"):
    return parse_tabular(data, profile, sha256="a" * 64,
                         filename="x.csv", account_id=account_id)


def test_parses_a_meezan_statement_end_to_end():
    stmt = build_statement(seed=11)
    res = _parse(write_meezan_csv(stmt), MEEZAN)
    assert len(res.transactions) == len(stmt.txns)
    assert res.unresolved == ()
    assert [t.amount for t in res.transactions] == [t.amount for t in stmt.txns]
    assert [t.balance_after for t in res.transactions] == [t.balance_after for t in stmt.txns]


def test_reads_summary_values_from_the_preamble():
    stmt = build_statement(seed=12)
    res = _parse(write_meezan_csv(stmt), MEEZAN)
    assert res.document.summary.opening == stmt.opening
    assert res.document.summary.closing == stmt.closing


def test_columns_are_mapped_by_name_not_position():
    # Meezan's CSV has Debit BEFORE Credit; a positional parser would invert
    # every sign here.
    stmt = build_statement(
        opening=0,
        rows=[SynthTxn(date(2025, 7, 2), "Top-up", 50000, None),
              SynthTxn(date(2025, 7, 3), "Withdrawal", -20000, None)],
    )
    res = _parse(write_meezan_csv(stmt), MEEZAN)
    assert [t.amount for t in res.transactions] == [50000, -20000]


def test_blank_unused_side_is_not_treated_as_zero():
    # Review Focus #1
    stmt = build_statement(opening=0, rows=[SynthTxn(date(2025, 7, 2), "Top-up", 50000, None)])
    res = _parse(write_meezan_csv(stmt), MEEZAN)
    assert res.transactions[0].amount == 50000


def test_both_sides_blank_is_unresolved_not_zero():
    # Review Focus #1: a row with no amount at all must be flagged, never
    # silently contribute 0 to a total.
    stmt = build_statement(seed=13)
    data = corrupt(write_meezan_csv(stmt), "blank_debit_and_credit")
    res = _parse(data, MEEZAN)
    assert len(res.unresolved) == 1
    assert "no amount" in res.unresolved[0].reason.lower()


def test_dash_placeholder_counts_as_no_amount():
    # Review Focus #1: some exports print "-" for the unused side.
    stmt = build_statement(opening=0, rows=[SynthTxn(date(2025, 7, 2), "Top-up", 50000, None)])
    data = write_meezan_csv(stmt).replace(b',,500.00', b',-,500.00')
    res = _parse(data, MEEZAN)
    assert res.transactions[0].amount == 50000
    assert res.unresolved == ()


def test_a_malformed_amount_is_unresolved():
    # Review Focus #4
    stmt = build_statement(seed=14)
    res = _parse(corrupt(write_meezan_csv(stmt), "bad_amount"), MEEZAN)
    assert len(res.unresolved) == 1
    assert "1,23.456" in res.unresolved[0].raw


def test_mcb_dr_cr_suffix_sets_direction():
    stmt = build_statement(
        opening=100000,
        rows=[SynthTxn(date(2025, 7, 2), "Cash", -20000, None),
              SynthTxn(date(2025, 7, 3), "Salary", 300000, None)],
    )
    res = _parse(write_mcb_csv(stmt), MCB)
    assert [t.amount for t in res.transactions] == [-20000, 300000]
    assert {t.provenance.sign_source for t in res.transactions} == {"suffix"}


def test_nayapay_signed_amounts():
    stmt = build_statement(
        opening=100000,
        rows=[SynthTxn(date(2025, 7, 2), "IBFT In", 50000, None),
              SynthTxn(date(2025, 7, 3), "IBFT Out", -30000, None)],
    )
    res = _parse(write_nayapay_csv(stmt), NAYAPAY)
    assert [t.amount for t in res.transactions] == [50000, -30000]
    assert {t.provenance.sign_source for t in res.transactions} == {"signed"}
    assert res.document.summary.total_credit == 50000


def test_xlsx_parses_identically_to_csv():
    stmt = build_statement(seed=15)
    from_csv = _parse(write_meezan_csv(stmt), MEEZAN)
    from_xlsx = parse_tabular(write_xlsx(stmt, "meezan"), MEEZAN.model_copy(
        update={"container": "xlsx"}), sha256="b" * 64, filename="x.xlsx", account_id="acct")
    assert [t.amount for t in from_xlsx.transactions] == [t.amount for t in from_csv.transactions]


def test_rows_keep_printed_order_even_when_dates_are_not_ascending():
    # Review Focus #2: the engine must not sort.
    stmt = build_statement(seed=16)
    res = _parse(corrupt(write_meezan_csv(stmt), "unsorted_dates"), MEEZAN)
    dates = [t.date for t in res.transactions]
    assert dates != sorted(dates), "engine must preserve printed order"


def test_transactions_carry_provenance_and_tax_year():
    stmt = build_statement(opening=0, rows=[SynthTxn(date(2025, 7, 2), "Top-up", 50000, None)])
    t = _parse(write_meezan_csv(stmt), MEEZAN).transactions[0]
    assert t.tax_year == "TY2026"
    assert t.provenance.sha256 == "a" * 64
    assert t.provenance.locator.startswith("row:")
    assert "Top-up" in t.provenance.raw_text


def test_identical_rows_get_distinct_ids():
    stmt = build_statement(
        opening=0,
        rows=[SynthTxn(date(2025, 7, 2), "TOPUP", 100000, None),
              SynthTxn(date(2025, 7, 2), "TOPUP", 100000, None)],
    )
    # Balances differ here, so also check the no-balance case via parse_row ids.
    res = _parse(write_meezan_csv(stmt), MEEZAN)
    assert len({t.txn_id for t in res.transactions}) == 2


def test_missing_header_raises_with_a_useful_message():
    with pytest.raises(ParseError, match="header"):
        _parse(b"nothing,useful\n1,2\n", MEEZAN)


def test_missing_mapped_column_names_the_column():
    stmt = build_statement(seed=17)
    data = write_meezan_csv(stmt).replace(b"Available Balance", b"Closing Bal")
    with pytest.raises(ParseError, match="Available Balance"):
        _parse(data, MEEZAN)


def test_parse_row_supports_profile_selftests():
    for profile in (MEEZAN, MCB, NAYAPAY):
        case = profile.selftest.cases[0]
        assert parse_row(profile, case.row) == (case.expect_date, case.expect_amount)


def test_unknown_date_format_is_unresolved():
    stmt = build_statement(seed=18)
    # NOTE: the brief hardcoded b"01 Jul 2025" here, but build_statement's row
    # dates always start strictly *after* `start` (first row is
    # start + timedelta(days=randint(1, 20))), so that literal stamp never
    # appears in a seed-generated statement and the .replace() was a silent
    # no-op that could never make this test exercise anything. Fixed by
    # deriving the actual first-row stamp the same way write_meezan_csv does.
    bad_stamp = stmt.txns[0].date.strftime("%d %b %Y").encode()
    data = write_meezan_csv(stmt).replace(bad_stamp, b"2025/07/01")
    res = _parse(data, MEEZAN)
    assert any("date" in u.reason.lower() for u in res.unresolved)


def test_selftest_case_may_omit_balance_but_a_real_statement_may_not():
    # Forward-looking fix (coordinator review, fix round 1): the "balance"
    # required-role fix must bind parse_tabular but NOT parse_row. A
    # selftest case pins (date, amount) only and has no reason to also carry
    # a balance column; if parse_row required one anyway, a profile whose
    # selftest case omitted it would raise inside run_selftest, be marked
    # ok=False, and be silently excluded from layout detection - the only
    # symptom being "unknown layout" on a file that should have parsed.
    # A real statement missing the same column must still raise ParseError:
    # that is the bug the earlier fix correctly closed, and this test must
    # not let it re-open.
    profile = NO_BALANCE_IN_SELFTEST
    case = profile.selftest.cases[0]

    assert parse_row(profile, case.row) == (case.expect_date, case.expect_amount)

    status = run_selftest(profile, parse_row)
    assert status.ok, status.message

    stmt = build_statement(seed=19)
    data = write_meezan_csv(stmt).replace(b"Available Balance", b"Closing Bal")
    with pytest.raises(ParseError, match="Available Balance"):
        _parse(data, profile)
