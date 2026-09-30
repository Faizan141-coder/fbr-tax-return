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
from fbr.engines.tabular import ParseError, parse_row
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


# Column x-positions shared with tests/fixtures/synth_pdf.py: Credit's right
# edge at 400, Debit's at 470, Available Balance's at 555.
_CREDIT_X, _DEBIT_X, _BALANCE_X = 400, 470, 555
_MIDWAY_X = (_CREDIT_X + _DEBIT_X) // 2      # equally close to two columns


def _meezan_page(lines, *, opening="1,000.00", closing=None, cover=False):
    """Draw one Meezan-style page from explicit line specs.

    Each line is a dict of what to place where: `date`, `desc`, `credit`,
    `debit`, `balance`, and `midway` for an amount drawn deliberately between
    the Credit and Debit columns. Omitting a key leaves that cell blank, which
    is how a dateless line is expressed.

    `cover=True` puts a header-less page in front, to prove the engine still
    tolerates a cover page before the first header row.
    """
    import io

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 8)
    if cover:
        c.drawString(40, A4[1] - 60, "Meezan Bank  Account Statement")
        c.drawString(40, A4[1] - 76, "This cover page carries no column header.")
        c.showPage()
        c.setFont("Helvetica", 8)
    y = A4[1] - 60
    c.drawString(40, y, f"OPENING BALANCE  PKR {opening}")
    if closing is not None:
        y -= 16
        c.drawString(40, y, f"CLOSING BALANCE  PKR {closing}")
    y -= 24
    c.setFont("Helvetica-Bold", 8)
    c.drawString(40, y, "Booking Date")
    c.drawString(130, y, "Description")
    c.drawRightString(_CREDIT_X, y, "Credit")
    c.drawRightString(_DEBIT_X, y, "Debit")
    c.drawRightString(_BALANCE_X, y, "Available Balance")
    c.setFont("Helvetica", 8)
    for line in lines:
        y -= 16
        if line.get("date"):
            c.drawString(40, y, line["date"])
        if line.get("desc"):
            c.drawString(130, y, line["desc"])
        if line.get("credit"):
            c.drawRightString(_CREDIT_X, y, line["credit"])
        if line.get("debit"):
            c.drawRightString(_DEBIT_X, y, line["debit"])
        if line.get("midway"):
            c.drawRightString(_MIDWAY_X, y, line["midway"])
        if line.get("balance"):
            c.drawRightString(_BALANCE_X, y, line["balance"])
    c.save()
    return buf.getvalue()


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
    stmt = build_statement(seed=17, count=4)
    res = _parse(write_wrapped_description_pdf(stmt), MEEZAN_PDF)
    assert res.unresolved == ()
    # Assert every row's EXACT description, not `any(...)`. The fixture puts the
    # LAST row's continuation on page 2, and `any(...)` still passed when that
    # one row silently truncated to "ATM Cash Withdrawal STAN 654321" - which is
    # precisely how the page-break bug hid. Only the exact final string fails a
    # regression.
    assert [t.description for t in res.transactions] == [
        "Withholding Tax Debit CONTINUATION STAN 100000",
        "POS Transaction STAN 222333 CONTINUATION STAN 100001",
        "IBFT In from THUNES STAN 123456 CONTINUATION STAN 100002",
        "ATM Cash Withdrawal STAN 654321 CONTINUATION STAN 100003",
    ]
    # The continuation line must not become its own transaction.
    assert len(res.transactions) == len(stmt.txns)
    assert not any(t.description.startswith("CONTINUATION") for t in res.transactions)


def test_a_dateless_line_carrying_an_amount_is_unresolved_not_swallowed():
    # The worst outcome this engine can produce. A bank that does not reprint
    # the date on a same-day second row used to have that row absorbed as a
    # description continuation, which DISCARDED its amount and its balance. The
    # balance vanished with the row, so the running-balance chain still
    # verified over what was left, `unresolved` was empty, and
    # statement_usable() returned True: Rs 700.00 gone with every check green.
    res = _parse(_meezan_page([
        {"date": "02 Jul 2025", "desc": "Money Received",
         "credit": "500.00", "balance": "1,500.00"},
        {"desc": "Second Same Day Credit",
         "credit": "700.00", "balance": "2,200.00"},
    ]), MEEZAN_PDF)

    assert [t.amount for t in res.transactions] == [50000]
    assert len(res.unresolved) == 1
    reason = res.unresolved[0].reason
    assert "no date" in reason
    # The reason must name the money it refused, so the owner can find the row.
    assert "700.00" in reason and "2,200.00" in reason
    checks = check_statement(res, MEEZAN_PDF)
    assert not statement_usable(checks)
    assert any(c.kind == "unresolved_rows" and c.status == "fail" for c in checks)


def test_a_dateless_line_of_description_text_still_joins_its_row():
    res = _parse(_meezan_page([
        {"date": "02 Jul 2025", "desc": "IBFT In from THUNES",
         "credit": "500.00", "balance": "1,500.00"},
        {"desc": "STAN 123456 REF ABCDEF"},
    ]), MEEZAN_PDF)

    assert res.unresolved == ()
    assert len(res.transactions) == 1
    assert res.transactions[0].description == "IBFT In from THUNES STAN 123456 REF ABCDEF"
    assert res.transactions[0].amount == 50000
    assert res.transactions[0].balance_after == 150000


def test_a_dateless_line_with_an_ambiguous_token_is_unresolved():
    # No amount lands in a band at all here, so nothing is "carried" - but a
    # token sitting equally close to Credit and Debit is exactly the case this
    # engine must never guess at, dateless or not.
    res = _parse(_meezan_page([
        {"date": "02 Jul 2025", "desc": "Money Received",
         "credit": "500.00", "balance": "1,500.00"},
        {"desc": "Same Day", "midway": "700.00"},
    ]), MEEZAN_PDF)

    assert [t.amount for t in res.transactions] == [50000]
    assert len(res.unresolved) == 1
    reason = res.unresolved[0].reason
    assert "no date" in reason and "outside every column band" in reason
    assert "700.00" in reason
    assert not statement_usable(check_statement(res, MEEZAN_PDF))


def test_a_pdf_whose_header_is_never_found_is_refused():
    # tabular.py raises ParseError in this situation; this engine used to
    # return 0 transactions, 0 unresolved rows and statement_usable() == True,
    # so reading a SadaPay PDF with the Meezan profile looked like a clean
    # empty statement. The two engines must not disagree about failing open.
    data = write_sadapay_pdf(build_statement(seed=24))
    with pytest.raises(ParseError) as exc:
        _parse(data, MEEZAN_PDF)
    message = str(exc.value)
    assert "header row not found" in message
    # It must name the labels it looked for, so the owner can see the mismatch.
    for label in MEEZAN_PDF.detect.header_contains:
        assert label in message
    assert not isinstance(exc.value, (PdfNotTextual, PdfPasswordError))


def test_a_cover_page_before_the_first_header_is_still_parsed():
    # The header-never-found refusal must not break the legitimate case it
    # sits next to: page 1 carries text but no header, page 2 carries both.
    res = _parse(_meezan_page([
        {"date": "02 Jul 2025", "desc": "Money Received",
         "credit": "500.00", "balance": "1,500.00"},
    ], cover=True), MEEZAN_PDF)

    assert res.unresolved == ()
    assert [t.amount for t in res.transactions] == [50000]


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
