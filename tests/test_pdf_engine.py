# tests/test_pdf_engine.py
"""The PDF engine, exercised against PDFs whose geometry we chose.

Two behaviours carry the weight: an unsigned amount is assigned to Credit or
Debit by position and never by guess, and anything unclear becomes an
UnresolvedRow so the statement fails rather than reporting a wrong figure.
"""
from datetime import date

import pytest

from fbr.config.schema_profile import Profile
from fbr.engines.pdf import PdfNotTextual, PdfPasswordError, parse_pdf, pdf_row_samples
from fbr.engines.tabular import parse_row
from fbr.reconcile import check_statement, statement_usable
from tests.fixtures.synth import SynthTxn, build_statement
from tests.fixtures.synth_pdf import (
    encrypt_pdf,
    write_meezan_pdf,
    write_sadapay_pdf,
    write_wrapped_description_pdf,
)

SADAPAY = Profile.model_validate({
    "id": "sadapay.pdf.v1", "institution": "SadaPay", "container": "pdf",
    "valid_from": date(2025, 7, 1),
    "detect": {"header_contains": ["Date", "Description", "Debit/Credit"]},
    "columns": {"date": "Date", "description": "Description",
                "amount": "Debit/Credit",
                "align": {"amount": "right"}},
    "formats": {"dates": ["%d %b, %Y"], "sign": "signed"},
    "rows": {"footer": [r"(?i)system generated"], "row_anchor": "date"},
    "summary": {
        "total_debit": r"(?i)Total\s+debit[^\d\n]+?(?P<value>-?[\d,]+\.\d{2})",
        "total_credit": r"(?i)Total\s+credit[^\d\n]+?(?P<value>-?[\d,]+\.\d{2})",
        "period_from": r"(?i)Statement\s+Period[^\d\n]+?(?P<value>\d{2} \w{3}, \d{4})",
        "period_to": r"(?i)to\s+(?P<value>\d{2} \w{3}, \d{4})",
    },
    "balance": {"semantics": "none"},
    "selftest": {"cases": [{
        "row": {"Date": "01 Jul, 2025", "Description": "Top-up",
                "Debit/Credit": "+1,000.00"},
        "expect_date": date(2025, 7, 1), "expect_amount": 100000}]},
})

MEEZAN_PDF = Profile.model_validate({
    "id": "meezan.pdf.v1", "institution": "Meezan Bank Limited", "container": "pdf",
    "valid_from": date(2025, 7, 1),
    "detect": {"header_contains": ["Booking Date", "Credit", "Debit"]},
    "columns": {"date": "Booking Date", "description": "Description",
                "credit": "Credit", "debit": "Debit",
                "balance": "Available Balance",
                "align": {"credit": "right", "debit": "right", "balance": "right"}},
    "formats": {"dates": ["%d %b %Y"], "sign": "columns"},
    "rows": {"row_anchor": "date", "continuation": "below"},
    "summary": {
        "opening": r"(?i)OPENING\s+BALANCE[^\d\n]+?(?P<value>-?[\d,]+\.\d{2})",
        "closing": r"(?i)CLOSING\s+BALANCE[^\d\n]+?(?P<value>-?[\d,]+\.\d{2})",
        "period_from": r"(?i)From\s+Date[^\d\n]+?(?P<value>\d{2} \w{3} \d{4})",
        "period_to": r"(?i)To\s+Date[^\d\n]+?(?P<value>\d{2} \w{3} \d{4})",
    },
    "balance": {"semantics": "running", "kind": "available"},
    "selftest": {"cases": [{
        "row": {"Booking Date": "01 Jul 2025", "Description": "Top-up",
                "Credit": "1,000.00", "Debit": "", "Available Balance": "1,000.00"},
        "expect_date": date(2025, 7, 1), "expect_amount": 100000}]},
})


def _parse(data, profile, password=None, account_id="acct"):
    return parse_pdf(data, profile, sha256="a" * 64, filename="x.pdf",
                     account_id=account_id, password=password)


def test_parses_a_sadapay_statement():
    stmt = build_statement(seed=11)
    res = _parse(write_sadapay_pdf(stmt), SADAPAY)
    assert res.unresolved == ()
    assert [t.amount for t in res.transactions] == [t.amount for t in stmt.txns]


def test_reads_sadapay_printed_totals_and_period():
    stmt = build_statement(seed=12)
    res = _parse(write_sadapay_pdf(stmt), SADAPAY)
    assert res.document.summary.total_credit == stmt.total_credit
    assert res.document.summary.total_debit == stmt.total_debit
    assert res.document.summary.period_start == stmt.period_start


def test_sadapay_reconciles_against_its_printed_totals():
    stmt = build_statement(seed=13)
    res = _parse(write_sadapay_pdf(stmt), SADAPAY)
    checks = check_statement(res, SADAPAY)
    assert statement_usable(checks)
    assert any(c.kind == "printed_totals" and c.status == "pass" for c in checks)


def test_meezan_unsigned_columns_get_the_right_sign_from_position():
    # The core risk: a positional mistake here inverts every sign while the
    # statement still reconciles against itself.
    stmt = build_statement(
        opening=100000,
        rows=[SynthTxn(date(2025, 7, 2), "Money Received", 50000, None),
              SynthTxn(date(2025, 7, 3), "ATM Cash Withdrawal", -20000, None)],
    )
    res = _parse(write_meezan_pdf(stmt), MEEZAN_PDF)
    assert [t.amount for t in res.transactions] == [50000, -20000]
    assert {t.provenance.sign_source for t in res.transactions} == {"column"}


def test_meezan_pdf_running_balance_reconciles():
    stmt = build_statement(seed=14, opening=500000)
    res = _parse(write_meezan_pdf(stmt), MEEZAN_PDF)
    checks = check_statement(res, MEEZAN_PDF)
    assert statement_usable(checks), [c for c in checks if c.status == "fail"]
    assert any(c.kind == "running_balance" and c.status == "pass" for c in checks)


def test_a_repeated_header_on_later_pages_is_not_a_transaction():
    stmt = build_statement(seed=15, count=60)
    res = _parse(write_sadapay_pdf(stmt), SADAPAY)
    assert len(res.transactions) == len(stmt.txns)


def test_a_footer_line_is_not_a_transaction():
    stmt = build_statement(seed=16)
    res = _parse(write_sadapay_pdf(stmt), SADAPAY)
    assert not any("system generated" in t.description.lower()
                   for t in res.transactions)


def test_a_wrapped_description_is_joined_onto_its_row():
    res = _parse(write_wrapped_description_pdf(build_statement(seed=17, count=4)),
                 MEEZAN_PDF)
    assert res.unresolved == ()
    assert any("CONTINUATION" in t.description for t in res.transactions)
    # The continuation line must not become its own transaction.
    assert len([t for t in res.transactions if t.description.startswith("CONTINUATION")]) == 0


def test_rows_stay_in_printed_order():
    stmt = build_statement(
        opening=100000,
        rows=[SynthTxn(date(2025, 7, 9), "Later first", 50000, None),
              SynthTxn(date(2025, 7, 5), "Earlier second", -20000, None)],
    )
    res = _parse(write_meezan_pdf(stmt), MEEZAN_PDF)
    assert [t.date for t in res.transactions] == [date(2025, 7, 9), date(2025, 7, 5)]


def test_an_encrypted_pdf_opens_with_its_password():
    stmt = build_statement(seed=18)
    data = encrypt_pdf(write_sadapay_pdf(stmt), "s3cret")
    res = _parse(data, SADAPAY, password="s3cret")
    assert len(res.transactions) == len(stmt.txns)


def test_wrong_password_reprompts_without_leaking_it():
    # Review Focus #1: the password must not reach the exception text.
    data = encrypt_pdf(write_sadapay_pdf(build_statement(seed=19)), "s3cret")
    with pytest.raises(PdfPasswordError) as exc:
        _parse(data, SADAPAY, password="wrong-pass-9999")
    message = str(exc.value)
    assert "wrong-pass-9999" not in message
    assert "s3cret" not in message
    assert "password" in message.lower()


def test_missing_password_on_an_encrypted_pdf_raises_password_error():
    data = encrypt_pdf(write_sadapay_pdf(build_statement(seed=20)), "s3cret")
    with pytest.raises(PdfPasswordError):
        _parse(data, SADAPAY, password=None)


def test_password_on_unencrypted_pdf_is_harmless():
    # Review Focus #1: an owner who types a password for a file that needs none
    # must not be punished for it.
    stmt = build_statement(seed=21)
    res = _parse(write_sadapay_pdf(stmt), SADAPAY, password="irrelevant")
    assert len(res.transactions) == len(stmt.txns)


def test_a_pdf_with_no_text_layer_is_refused():
    minimal = (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
               b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
               b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
               b"trailer<</Root 1 0 R>>")
    with pytest.raises((PdfNotTextual, Exception)):
        _parse(minimal, SADAPAY)


def test_an_amount_between_two_columns_is_unresolved_not_guessed():
    # Draw an amount deliberately midway between Credit and Debit.
    import io
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 8)
    y = A4[1] - 60
    c.drawString(40, y, "OPENING BALANCE  PKR 1,000.00")
    y -= 24
    c.setFont("Helvetica-Bold", 8)
    c.drawString(40, y, "Booking Date"); c.drawString(130, y, "Description")
    c.drawRightString(400, y, "Credit"); c.drawRightString(470, y, "Debit")
    c.drawRightString(555, y, "Available Balance")
    c.setFont("Helvetica", 8)
    y -= 16
    c.drawString(40, y, "02 Jul 2025"); c.drawString(130, y, "Ambiguous")
    c.drawRightString(435, y, "500.00")          # midway between 400 and 470
    c.drawRightString(555, y, "1,500.00")
    c.save()
    res = _parse(buf.getvalue(), MEEZAN_PDF)
    assert res.transactions == ()
    assert len(res.unresolved) == 1
    assert "ambiguous" in res.unresolved[0].reason.lower()


def test_pdf_row_samples_feed_parse_row_for_a_selftest():
    stmt = build_statement(seed=22)
    samples = pdf_row_samples(write_sadapay_pdf(stmt), SADAPAY, limit=3)
    assert samples and set(samples[0]) >= {"Date", "Description", "Debit/Credit"}
    d, amount = parse_row(SADAPAY, samples[0])
    assert d == stmt.txns[0].date
    assert amount == stmt.txns[0].amount


def test_transactions_carry_page_and_position_provenance():
    res = _parse(write_sadapay_pdf(build_statement(seed=23)), SADAPAY)
    loc = res.transactions[0].provenance.locator
    assert loc.startswith("page:") and ",y:" in loc
