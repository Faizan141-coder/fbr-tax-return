# tests/test_model.py
from datetime import date

import pytest

from fbr.model import (
    Account,
    Check,
    Document,
    DocumentSummary,
    Owner,
    Provenance,
    Registry,
    Transaction,
    assign_occurrences,
    make_txn_id,
    normalize_description,
    tax_year_for,
)


@pytest.mark.parametrize(
    "d,expected",
    [
        (date(2025, 7, 1), "TY2026"),    # first day of TY2026
        (date(2026, 6, 30), "TY2026"),   # last day
        (date(2025, 6, 30), "TY2025"),   # day before
        (date(2026, 7, 1), "TY2027"),    # day after
        (date(2026, 1, 15), "TY2026"),   # mid-year, across the calendar boundary
    ],
)
def test_tax_year_runs_july_to_june(d, expected):
    assert tax_year_for(d) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("  IBFT  In   from  Thunes ", "IBFT IN FROM THUNES"),
        ("ibft in", "IBFT IN"),
        ("IBFT In", "IBFT IN"),          # NBSP folds to a space
        ("IBFT\nIn", "IBFT IN"),              # wrapped line
    ],
)
def test_normalize_description(raw, expected):
    assert normalize_description(raw) == expected


def test_txn_id_is_stable_across_runs():
    args = ("meezan-main", date(2026, 1, 5), 123456, 500000, "Payment of Profit", 1)
    assert make_txn_id(*args) == make_txn_id(*args)


def test_txn_id_ignores_description_whitespace_and_case():
    base = ("meezan-main", date(2026, 1, 5), 123456, 500000)
    assert make_txn_id(*base, "Payment of Profit", 1) == make_txn_id(
        *base, "  payment   of  profit ", 1
    )


@pytest.mark.parametrize(
    "changed",
    [
        {"account_id": "mcb-main"},
        {"d": date(2026, 1, 6)},
        {"amount": 123457},
        {"balance_after": 500001},
        {"description": "Payment of Prof1t"},
        {"occurrence": 2},
    ],
)
def test_txn_id_changes_when_any_component_changes(changed):
    base = dict(
        account_id="meezan-main",
        d=date(2026, 1, 5),
        amount=123456,
        balance_after=500000,
        description="Payment of Profit",
        occurrence=1,
    )
    other = {**base, **changed}
    mk = lambda a: make_txn_id(
        a["account_id"], a["d"], a["amount"], a["balance_after"],
        a["description"], a["occurrence"],
    )
    assert mk(base) != mk(other)


def test_txn_id_handles_missing_balance():
    # SadaPay has no balance column; None must be distinct from 0.
    base = ("sadapay", date(2026, 1, 5), 123456)
    assert make_txn_id(*base, None, "PUR/SHOP", 1) != make_txn_id(*base, 0, "PUR/SHOP", 1)


def test_identical_same_day_rows_get_different_occurrences():
    # Two genuine Rs 1,000 top-ups on one day are both real (spec §6.2).
    rows = [
        {"date": date(2026, 1, 5), "amount": 100000, "balance_after": None, "description": "TOPUP"},
        {"date": date(2026, 1, 5), "amount": 100000, "balance_after": None, "description": "TOPUP"},
        {"date": date(2026, 1, 5), "amount": 200000, "balance_after": None, "description": "TOPUP"},
    ]
    assert assign_occurrences(rows) == [1, 2, 1]


def test_occurrence_numbering_follows_printed_order_not_sorted_order():
    rows = [
        {"date": date(2026, 1, 9), "amount": 100000, "balance_after": None, "description": "A"},
        {"date": date(2026, 1, 5), "amount": 100000, "balance_after": None, "description": "A"},
        {"date": date(2026, 1, 9), "amount": 100000, "balance_after": None, "description": "A"},
    ]
    assert assign_occurrences(rows) == [1, 1, 2]


def test_model_types_are_frozen():
    p = Provenance(sha256="a" * 64, locator="row:1", raw_text="x", sign_source="column")
    with pytest.raises(Exception):
        p.locator = "row:2"


def test_transaction_round_trips_its_fields():
    p = Provenance(sha256="a" * 64, locator="row:3", raw_text="raw", sign_source="column")
    t = Transaction(
        txn_id="deadbeefdeadbeef",
        account_id="meezan-main",
        date=date(2026, 1, 5),
        value_date=date(2026, 1, 5),
        amount=-25000,
        balance_after=475000,
        description="ATM Cash Withdrawal",
        reference="STAN 123456",
        tax_year="TY2026",
        provenance=p,
    )
    assert t.amount == -25000 and t.tax_year == "TY2026"
    assert t.provenance.sign_source == "column"


def test_check_and_document_construct():
    c = Check(
        check_id="c1", scope="document", kind="running_balance", status="fail",
        expected="500000", actual="499000", detail="row 12", locator="row:12",
    )
    assert c.status == "fail"
    d = Document(
        sha256="b" * 64, filename="x.csv", kind="statement", container="csv",
        layout_id="meezan.csv.v1", account_id="meezan-main",
        period_start=date(2025, 7, 1), period_end=date(2026, 6, 30),
        pages=1, encrypted=False,
        summary=DocumentSummary(
            opening=100000, closing=200000, total_credit=500000, total_debit=400000,
            period_start=date(2025, 7, 1), period_end=date(2026, 6, 30),
            account_identifier="PK00TEST0000000000000000",
        ),
    )
    assert d.summary.opening == 100000


def test_registry_types_construct():
    acct = Account(
        id="meezan-main", institution="Meezan Bank Limited", kind="bank",
        iban="PK00TEST0000000000000000", account_number="0000000000",
        wallet_number="", title="ACCOUNT TITLE", type="Saving", ownership="Self",
        currency="PKR", statement_expected=True, match_hints=["MEEZAN"],
        opened_on=None, closed_on=None,
    )
    reg = Registry(owner=Owner(name="OWNER NAME"), accounts=(acct,))
    assert reg.accounts[0].id == "meezan-main"
