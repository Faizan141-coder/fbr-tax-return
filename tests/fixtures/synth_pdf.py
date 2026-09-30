# tests/fixtures/synth_pdf.py
"""Draw look-alike statement PDFs at exact coordinates.

The engine under test decides whether an amount is a credit or a debit from
its x-position, so the fixtures must control x-positions precisely. reportlab's
canvas does: drawRightString places a string's right edge at a given x, which
is how a bank's right-aligned money column behaves.

No real statement ever enters this repo; every value here is invented.
"""

from __future__ import annotations

import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from fbr.money import format_paisa
from tests.fixtures.synth import SynthStatement

_W, _H = A4
_LEFT = 40
_TOP = _H - 60
_ROW_H = 16
_BOTTOM = 70

# Column right edges for the Meezan-style layout. Credit before Debit, which
# is the reverse of Meezan's CSV export - the difference the engine must not
# paper over.
_MZ_DATE_X = 40          # left-aligned
_MZ_DESC_X = 130         # left-aligned
_MZ_CREDIT_X = 400       # right-aligned
_MZ_DEBIT_X = 470        # right-aligned
_MZ_BALANCE_X = 555      # right-aligned


def _new_canvas() -> tuple[canvas.Canvas, io.BytesIO]:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 8)
    return c, buf


def _finish(c: canvas.Canvas, buf: io.BytesIO) -> bytes:
    c.save()
    return buf.getvalue()


def write_sadapay_pdf(
    stmt: SynthStatement, *, pages_hint: int = 0, summary_wording: str = "profile"
) -> bytes:
    """SadaPay: Date | Description | signed amount. No balance column at all,
    and only Total debit / Total credit to reconcile against.

    `summary_wording="profile"` prints the exact labels sadapay.pdf.v1's
    [summary] patterns look for. `"unmatched"` prints the same figures under
    different wording, which is what a real statement does whenever one of that
    profile's `# VERIFY` guesses is wrong: every summary pattern then matches
    nothing, the printed totals are never read, and - before the
    `nothing_verified` check - no arithmetic check ran at all while the
    statement still reported usable.
    """
    c, buf = _new_canvas()
    if summary_wording == "profile":
        debit_label, credit_label = "Total debit", "Total credit"
        period_line = (f"Statement Period  {stmt.period_start:%d %b, %Y} to "
                       f"{stmt.period_end:%d %b, %Y}")
    elif summary_wording == "unmatched":
        debit_label, credit_label = "Debits in period", "Credits in period"
        period_line = (f"Period covered  {stmt.period_start:%d %b, %Y} through "
                       f"{stmt.period_end:%d %b, %Y}")
    else:
        raise ValueError(f"unknown summary_wording {summary_wording!r}")

    def header(y: float) -> float:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(_LEFT, y, "Account Statement")
        c.setFont("Helvetica", 8)
        y -= _ROW_H
        c.drawString(_LEFT, y, f"Account Currency  {stmt.account_id}  PKR")
        y -= _ROW_H
        c.drawString(_LEFT, y, f"{debit_label}  {format_paisa(stmt.total_debit)}")
        y -= _ROW_H
        c.drawString(_LEFT, y, f"{credit_label}  {format_paisa(stmt.total_credit)}")
        y -= _ROW_H
        c.drawString(_LEFT, y, period_line)
        y -= _ROW_H * 1.5
        c.setFont("Helvetica-Bold", 8)
        c.drawString(_MZ_DATE_X, y, "Date")
        c.drawString(_MZ_DESC_X, y, "Description")
        c.drawRightString(_MZ_CREDIT_X, y, "Debit/Credit")
        c.setFont("Helvetica", 8)
        return y - _ROW_H

    y = header(_TOP)
    for t in stmt.txns:
        if y < _BOTTOM:
            c.showPage()
            c.setFont("Helvetica", 8)
            y = header(_TOP)
        c.drawString(_MZ_DATE_X, y, f"{t.date:%d %b, %Y}")
        c.drawString(_MZ_DESC_X, y, t.description[:48])
        sign = "+" if t.amount > 0 else "-"
        c.drawRightString(_MZ_CREDIT_X, y, f"{sign}{format_paisa(abs(t.amount))}")
        y -= _ROW_H

    c.drawString(_LEFT, max(y - _ROW_H, 40),
                 "This is a system generated statement  Page 1")
    return _finish(c, buf)


def write_sadapay_paged_pdf(
    stmt: SynthStatement,
    *,
    rows_on_first_page: int = 1,
    summary_wording: str = "profile",
) -> bytes:
    """A SadaPay statement whose page 2 opens with a `Page 2 of 2` line.

    The header is printed once, on page 1; page 2 carries no header, which is
    how a bank that prints its column titles only at the start of the document
    behaves. The engine keeps the page-1 bands and treats every line on page 2
    as a body row - and the FIRST of those lines matches sadapay.pdf.v1's
    `rows.footer` pattern `'(?i)^\\s*page\\s+\\d+'`.

    The PDF engine used to `break` out of the page on a footer match, so every
    transaction printed below that line was discarded with no UnresolvedRow and
    no failing check.
    """
    c, buf = _new_canvas()
    if summary_wording == "profile":
        debit_label, credit_label = "Total debit", "Total credit"
        period_line = (f"Statement Period  {stmt.period_start:%d %b, %Y} to "
                       f"{stmt.period_end:%d %b, %Y}")
    elif summary_wording == "unmatched":
        debit_label, credit_label = "Debits in period", "Credits in period"
        period_line = (f"Period covered  {stmt.period_start:%d %b, %Y} through "
                       f"{stmt.period_end:%d %b, %Y}")
    else:
        raise ValueError(f"unknown summary_wording {summary_wording!r}")

    def row(y: float, t) -> None:
        c.drawString(_MZ_DATE_X, y, f"{t.date:%d %b, %Y}")
        c.drawString(_MZ_DESC_X, y, t.description[:48])
        sign = "+" if t.amount > 0 else "-"
        c.drawRightString(_MZ_CREDIT_X, y, f"{sign}{format_paisa(abs(t.amount))}")

    y = _TOP
    c.setFont("Helvetica-Bold", 11)
    c.drawString(_LEFT, y, "Account Statement")
    c.setFont("Helvetica", 8)
    y -= _ROW_H
    c.drawString(_LEFT, y, f"Account Currency  {stmt.account_id}  PKR")
    y -= _ROW_H
    c.drawString(_LEFT, y, f"{debit_label}  {format_paisa(stmt.total_debit)}")
    y -= _ROW_H
    c.drawString(_LEFT, y, f"{credit_label}  {format_paisa(stmt.total_credit)}")
    y -= _ROW_H
    c.drawString(_LEFT, y, period_line)
    y -= _ROW_H * 1.5
    c.setFont("Helvetica-Bold", 8)
    c.drawString(_MZ_DATE_X, y, "Date")
    c.drawString(_MZ_DESC_X, y, "Description")
    c.drawRightString(_MZ_CREDIT_X, y, "Debit/Credit")
    c.setFont("Helvetica", 8)
    y -= _ROW_H

    for t in stmt.txns[:rows_on_first_page]:
        row(y, t)
        y -= _ROW_H

    c.showPage()
    c.setFont("Helvetica", 8)
    y = _TOP
    c.drawString(_LEFT, y, "Page 2 of 2")
    y -= _ROW_H
    for t in stmt.txns[rows_on_first_page:]:
        row(y, t)
        y -= _ROW_H
    return _finish(c, buf)


def write_meezan_pdf(stmt: SynthStatement) -> bytes:
    """Meezan: Booking Date | Description | Credit | Debit | Available Balance.

    Amounts are UNSIGNED and sit in separate right-aligned columns, so only the
    x-position distinguishes a credit from a debit. This is the layout that
    would silently invert every sign if the engine guessed.
    """
    c, buf = _new_canvas()

    def header(y: float) -> float:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(_LEFT, y, "Meezan Bank  Account Statement")
        c.setFont("Helvetica", 8)
        y -= _ROW_H
        c.drawString(_LEFT, y, f"Account  {stmt.account_id}  {stmt.account_title}")
        y -= _ROW_H
        c.drawString(_LEFT, y, f"OPENING BALANCE  PKR {format_paisa(stmt.opening)}")
        y -= _ROW_H
        c.drawString(_LEFT, y, f"CLOSING BALANCE  PKR {format_paisa(stmt.closing)}")
        y -= _ROW_H
        c.drawString(
            _LEFT, y,
            f"From Date  {stmt.period_start:%d %b %Y}  To Date  {stmt.period_end:%d %b %Y}",
        )
        y -= _ROW_H * 1.5
        c.setFont("Helvetica-Bold", 8)
        c.drawString(_MZ_DATE_X, y, "Booking Date")
        c.drawString(_MZ_DESC_X, y, "Description")
        c.drawRightString(_MZ_CREDIT_X, y, "Credit")
        c.drawRightString(_MZ_DEBIT_X, y, "Debit")
        c.drawRightString(_MZ_BALANCE_X, y, "Available Balance")
        c.setFont("Helvetica", 8)
        return y - _ROW_H

    y = header(_TOP)
    for t in stmt.txns:
        if y < _BOTTOM:
            c.showPage()
            c.setFont("Helvetica", 8)
            y = header(_TOP)
        c.drawString(_MZ_DATE_X, y, f"{t.date:%d %b %Y}")
        c.drawString(_MZ_DESC_X, y, t.description[:42])
        amount = format_paisa(abs(t.amount))
        if t.amount > 0:
            c.drawRightString(_MZ_CREDIT_X, y, amount)
        else:
            c.drawRightString(_MZ_DEBIT_X, y, amount)
        c.drawRightString(_MZ_BALANCE_X, y, format_paisa(t.balance_after))
        y -= _ROW_H
    return _finish(c, buf)


def write_wrapped_description_pdf(stmt: SynthStatement) -> bytes:
    """A Meezan-style PDF whose descriptions wrap onto a continuation line,
    including one that wraps across a page break."""
    c, buf = _new_canvas()

    def header(y: float) -> float:
        c.setFont("Helvetica-Bold", 8)
        c.drawString(_MZ_DATE_X, y, "Booking Date")
        c.drawString(_MZ_DESC_X, y, "Description")
        c.drawRightString(_MZ_CREDIT_X, y, "Credit")
        c.drawRightString(_MZ_DEBIT_X, y, "Debit")
        c.drawRightString(_MZ_BALANCE_X, y, "Available Balance")
        c.setFont("Helvetica", 8)
        return y - _ROW_H

    c.setFont("Helvetica", 8)
    c.drawString(_LEFT, _TOP, f"OPENING BALANCE  PKR {format_paisa(stmt.opening)}")
    y = header(_TOP - _ROW_H * 2)

    for i, t in enumerate(stmt.txns):
        # Force the last row to start just above the page bottom so its
        # continuation line lands on the next page.
        if i == len(stmt.txns) - 1:
            y = _BOTTOM + 2
        c.drawString(_MZ_DATE_X, y, f"{t.date:%d %b %Y}")
        c.drawString(_MZ_DESC_X, y, t.description[:42])
        amount = format_paisa(abs(t.amount))
        if t.amount > 0:
            c.drawRightString(_MZ_CREDIT_X, y, amount)
        else:
            c.drawRightString(_MZ_DEBIT_X, y, amount)
        c.drawRightString(_MZ_BALANCE_X, y, format_paisa(t.balance_after))
        y -= _ROW_H
        # The continuation line: description text only, no date, no amount.
        if y < _BOTTOM:
            c.showPage()
            c.setFont("Helvetica", 8)
            y = header(_TOP)
        c.drawString(_MZ_DESC_X, y, f"CONTINUATION STAN {100000 + i}")
        y -= _ROW_H
    return _finish(c, buf)


def encrypt_pdf(data: bytes, password: str, *, algorithm: str = "AES-256") -> bytes:
    """Encrypt an existing PDF, so the engine's password path has real input."""
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(io.BytesIO(data))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(password, algorithm=algorithm)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
