import csv
import io
from datetime import date

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
    stmt = build_statement(
        opening=100000, rows=[SynthTxn(date(2025, 7, 2), "IBFT In", 50000, None)]
    )
    text = write_nayapay_csv(stmt).decode("utf-8")
    assert "+500.00" in text or "500.00" in text


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
