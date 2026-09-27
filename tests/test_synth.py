import csv
import io
from datetime import date

import pytest

from tests.fixtures.synth import (
    SynthTxn,
    build_statement,
    corrupt,
    write_meezan_csv,
    write_mcb_csv,
    write_nayapay_csv,
    write_xlsx,
)


def test_balances_are_computed_from_transactions():
    stmt = build_statement(
        opening=100000,
        rows=[
            SynthTxn(date(2025, 7, 2), "Top-up", 50000, None),
            SynthTxn(date(2025, 7, 3), "ATM withdrawal", -20000, None),
        ],
    )
    assert [t.balance_after for t in stmt.txns] == [150000, 130000]
    assert stmt.closing == 130000
    assert stmt.total_credit == 50000
    assert stmt.total_debit == 20000


def test_generated_statement_is_reproducible_from_a_seed():
    a = build_statement(seed=7)
    b = build_statement(seed=7)
    assert [(t.date, t.amount, t.description) for t in a.txns] == [
        (t.date, t.amount, t.description) for t in b.txns
    ]


def test_meezan_csv_has_preamble_then_header_then_rows():
    stmt = build_statement(seed=1)
    rows = list(csv.reader(io.StringIO(write_meezan_csv(stmt).decode("utf-8"))))
    joined = "\n".join(",".join(r) for r in rows[:6])
    assert "OPENING BALANCE" in joined and "CLOSING BALANCE" in joined
    header = next(r for r in rows if r and r[0] == "Booking Date")
    # Meezan's CSV puts Debit BEFORE Credit - the reverse of its PDF.
    assert header.index("Debit") < header.index("Credit")


def test_meezan_csv_leaves_the_unused_side_blank():
    # Review Focus #1: a credit row must leave Debit empty, not "0.00".
    stmt = build_statement(
        opening=0, rows=[SynthTxn(date(2025, 7, 2), "Top-up", 50000, None)]
    )
    rows = list(csv.reader(io.StringIO(write_meezan_csv(stmt).decode("utf-8"))))
    header = next(r for r in rows if r and r[0] == "Booking Date")
    body = rows[rows.index(header) + 1]
    assert body[header.index("Debit")] == ""
    assert body[header.index("Credit")] == "500.00"


def test_mcb_csv_uses_a_dr_cr_suffix():
    stmt = build_statement(
        opening=100000, rows=[SynthTxn(date(2025, 7, 2), "Cash withdrawal", -20000, None)]
    )
    text = write_mcb_csv(stmt).decode("utf-8")
    assert "200.00Dr" in text


def test_nayapay_csv_uses_signed_amounts():
    # Fix round 1, Finding 2: the original assertion ("+500.00" in text or
    # "500.00" in text) is satisfied by "-500.00" too, since "500.00" is a
    # substring of it - it would pass even with every sign backwards. Pin
    # the sign on both a credit and a debit row instead.
    stmt = build_statement(
        opening=100000,
        rows=[
            SynthTxn(date(2025, 7, 2), "IBFT In", 50000, None),
            SynthTxn(date(2025, 7, 3), "IBFT Out", -20000, None),
        ],
    )
    rows = list(csv.reader(io.StringIO(write_nayapay_csv(stmt).decode("utf-8"))))
    header = next(r for r in rows if r and r[0] == "Date")
    body = rows[rows.index(header) + 1:]
    credit_amount = body[0][header.index("Amount")]
    debit_amount = body[1][header.index("Amount")]
    assert credit_amount.startswith("+") and "500.00" in credit_amount
    assert debit_amount.startswith("-") and "200.00" in debit_amount


def test_xlsx_is_a_zip_container():
    stmt = build_statement(seed=2)
    assert write_xlsx(stmt).startswith(b"PK\x03\x04")


def test_fake_ibans_use_the_reserved_prefix():
    # Global Constraints: only PK00TEST may appear in the repo.
    stmt = build_statement(seed=3)
    assert stmt.account_id.startswith("PK00TEST")


def test_corrupt_produces_different_bytes_for_each_mode():
    stmt = build_statement(seed=4)
    clean = write_meezan_csv(stmt)
    for how in ("drop_row", "flip_sign", "wrong_total", "bad_amount",
                "blank_debit_and_credit", "unsorted_dates"):
        assert corrupt(clean, how) != clean, how


# Fix round 1, Finding 1: the above test only ever exercises the Meezan
# writer, so it never noticed that corrupt(..., "flip_sign") silently
# returned NayaPay's CSV unchanged (NayaPay's signed amounts have no Dr/Cr
# token for the old code to find and swap). The tests below cover every
# writer against every mode, and pin down the two combinations that
# legitimately cannot apply to a given fixture.

_CORRUPT_WRITERS = {
    "meezan": write_meezan_csv,
    "mcb": write_mcb_csv,
    "nayapay": write_nayapay_csv,
}
_CORRUPT_MODES = (
    "drop_row", "flip_sign", "wrong_total", "bad_amount",
    "blank_debit_and_credit", "unsorted_dates",
)


def test_corrupt_covers_every_writer_and_every_mode():
    # A statement with >= 2 transaction rows, including both a credit and
    # a debit, so every mode has something to act on for every layout
    # (in particular, unsorted_dates has a second row to swap with, and
    # flip_sign has both a "+"-led and a "-"-led amount to try on NayaPay).
    # Given that, none of these 18 (writer, mode) combinations is expected
    # to raise - the one combination that genuinely cannot apply
    # (unsorted_dates on a single-row statement) is exercised on its own in
    # test_corrupt_raises_when_unsorted_dates_has_too_few_rows below.
    stmt = build_statement(
        opening=100000,
        rows=[
            SynthTxn(date(2025, 7, 2), "Top-up", 50000, None),
            SynthTxn(date(2025, 7, 3), "Cash withdrawal", -20000, None),
            SynthTxn(date(2025, 7, 5), "Payment of Profit", 15000, None),
        ],
    )
    for name, writer in _CORRUPT_WRITERS.items():
        clean = writer(stmt)
        for how in _CORRUPT_MODES:
            assert corrupt(clean, how) != clean, (name, how)


def test_corrupt_flip_sign_handles_nayapay_signed_amounts():
    # The exact case from Finding 1: NayaPay carries a leading "+"/"-"
    # rather than a Dr/Cr suffix, so flip_sign must flip that sign instead
    # of matching nothing and handing back the clean bytes.
    stmt = build_statement(
        opening=100000, rows=[SynthTxn(date(2025, 7, 2), "IBFT In", 50000, None)]
    )
    clean = write_nayapay_csv(stmt)
    dirty = corrupt(clean, "flip_sign").decode("utf-8")
    assert "-Rs. 500.00" in dirty
    assert "+Rs. 500.00" not in dirty


def test_corrupt_raises_when_unsorted_dates_has_too_few_rows():
    # unsorted_dates needs a second transaction row to swap with. Against a
    # single-row statement it must fail loudly rather than hand back the
    # clean bytes, which a caller could mistake for "the check did not
    # fire".
    stmt = build_statement(
        opening=100000, rows=[SynthTxn(date(2025, 7, 2), "Top-up", 50000, None)]
    )
    clean = write_meezan_csv(stmt)
    with pytest.raises(ValueError, match="unsorted_dates"):
        corrupt(clean, "unsorted_dates")
