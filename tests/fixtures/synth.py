"""Generate look-alike statements for tests.

Real statements never enter this repository (Global Constraints). These
fixtures reproduce the *shape* of each layout - column order, separators,
Dr/Cr tokens, blank unused sides - with invented values. Balances are
computed from the transactions, so a fixture can never contain an
arithmetic error that hides a parser bug.
"""

from __future__ import annotations

import csv
import io
import random
import zipfile
from dataclasses import dataclass, replace
from datetime import date, timedelta

from fbr.money import format_paisa

TEST_IBAN = "PK00TEST0000000000000000"

_DESCRIPTIONS = [
    "IBFT In from THUNES STAN 123456",
    "Payment of Profit",
    "Withholding Tax Debit",
    "ATM Cash Withdrawal STAN 654321",
    "Raast P2P Fund transfer",
    "POS Transaction STAN 222333",
    "Money Transferred To",
]


@dataclass(frozen=True, slots=True)
class SynthTxn:
    date: date
    description: str
    amount: int                 # signed paisa
    balance_after: int | None   # filled in by build_statement


@dataclass(frozen=True, slots=True)
class SynthStatement:
    account_title: str
    account_id: str
    period_start: date
    period_end: date
    opening: int
    txns: tuple[SynthTxn, ...]

    @property
    def closing(self) -> int:
        return self.txns[-1].balance_after if self.txns else self.opening

    @property
    def total_credit(self) -> int:
        return sum(t.amount for t in self.txns if t.amount > 0)

    @property
    def total_debit(self) -> int:
        return -sum(t.amount for t in self.txns if t.amount < 0)


def build_statement(
    *,
    opening: int = 500000,
    rows: list[SynthTxn] | None = None,
    start: date = date(2025, 7, 1),
    end: date | None = None,
    count: int = 8,
    seed: int = 0,
    account_title: str = "ACCOUNT TITLE",
    account_id: str = TEST_IBAN,
) -> SynthStatement:
    """Build a statement whose running balances are computed, not asserted."""
    if rows is None:
        rng = random.Random(seed)
        rows = []
        day = start
        for _ in range(count):
            day = day + timedelta(days=rng.randint(1, 20))
            amount = rng.randrange(5000, 2_000_000)
            if rng.random() < 0.5:
                amount = -amount
            rows.append(SynthTxn(day, rng.choice(_DESCRIPTIONS), amount, None))

    running = opening
    filled: list[SynthTxn] = []
    for t in rows:
        running += t.amount
        filled.append(replace(t, balance_after=running))

    return SynthStatement(
        account_title=account_title,
        account_id=account_id,
        period_start=start,
        period_end=end or (filled[-1].date if filled else start),
        opening=opening,
        txns=tuple(filled),
    )


def _csv_bytes(rows: list[list[str]]) -> bytes:
    buf = io.StringIO(newline="")
    csv.writer(buf, lineterminator="\r\n").writerows(rows)
    return buf.getvalue().encode("utf-8")


def write_meezan_csv(stmt: SynthStatement) -> bytes:
    """Meezan CSV: preamble rows, then a header with Debit BEFORE Credit."""
    rows: list[list[str]] = [
        [stmt.account_id, stmt.account_title],
        ["OPENING BALANCE", f"PKR {format_paisa(stmt.opening)}"],
        ["CLOSING BALANCE", f"PKR {format_paisa(stmt.closing)}"],
        ["Currency", "PKR"],
        ["Booking Date", "Value Date", "Doc No", "Description",
         "Debit", "Credit", "Available Balance"],
    ]
    for i, t in enumerate(stmt.txns, start=1):
        stamp = t.date.strftime("%d %b %Y")
        rows.append([
            stamp, stamp, f"D{i:05d}", t.description,
            format_paisa(-t.amount) if t.amount < 0 else "",
            format_paisa(t.amount) if t.amount > 0 else "",
            format_paisa(t.balance_after),
        ])
    return _csv_bytes(rows)


def write_mcb_csv(stmt: SynthStatement) -> bytes:
    """MCB CSV: one Amount column carrying a glued Dr/Cr suffix."""
    rows: list[list[str]] = [
        ["Account Number", stmt.account_id],
        ["Opening Balance", format_paisa(stmt.opening)],
        ["Closing Balance", format_paisa(stmt.closing)],
        ["Date", "Description", "Reference Number", "Amount", "Balance"],
    ]
    for i, t in enumerate(stmt.txns, start=1):
        suffix = "Cr" if t.amount > 0 else "Dr"
        rows.append([
            t.date.strftime("%d %b %Y"), t.description, f"{1000000000 + i}",
            f"{format_paisa(abs(t.amount))}{suffix}",
            format_paisa(t.balance_after),
        ])
    return _csv_bytes(rows)


def write_nayapay_csv(stmt: SynthStatement) -> bytes:
    """NayaPay CSV: signed amounts and a running balance."""
    rows: list[list[str]] = [
        ["Account", stmt.account_id],
        ["Opening Balance", format_paisa(stmt.opening)],
        ["Closing Balance", format_paisa(stmt.closing)],
        ["Total Income", format_paisa(stmt.total_credit)],
        ["Total Spent", format_paisa(stmt.total_debit)],
        ["Date", "Time", "Type", "Description", "Amount", "Balance"],
    ]
    for t in stmt.txns:
        sign = "+" if t.amount > 0 else "-"
        rows.append([
            t.date.strftime("%d %b %Y"), "10:15 AM",
            "IBFT In" if t.amount > 0 else "IBFT Out", t.description,
            f"{sign}Rs. {format_paisa(abs(t.amount))}",
            f"Rs. {format_paisa(t.balance_after)}",
        ])
    return _csv_bytes(rows)


def write_xlsx(stmt: SynthStatement, layout: str = "meezan") -> bytes:
    """Minimal .xlsx with one sheet of inline strings, readable by openpyxl."""
    writer = {"meezan": write_meezan_csv, "mcb": write_mcb_csv,
              "nayapay": write_nayapay_csv}[layout]
    rows = list(csv.reader(io.StringIO(writer(stmt).decode("utf-8"))))

    def esc(s: str) -> str:
        return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    def col(i: int) -> str:
        name, i = "", i + 1
        while i:
            i, r = divmod(i - 1, 26)
            name = chr(65 + r) + name
        return name

    body = []
    for r, row in enumerate(rows, start=1):
        cells = "".join(
            f'<c r="{col(c)}{r}" t="inlineStr"><is><t xml:space="preserve">'
            f"{esc(v)}</t></is></c>"
            for c, v in enumerate(row)
        )
        body.append(f'<row r="{r}">{cells}</row>')

    sheet = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(body)}</sheetData></worksheet>"
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Statement" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Target="worksheets/sheet1.xml" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/>'
        "</Relationships>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-'
        'officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.'
        'openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>'
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Target="xl/workbook.xml" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
        'officeDocument"/></Relationships>'
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", rels)
        z.writestr("xl/worksheets/sheet1.xml", sheet)
    return buf.getvalue()


def corrupt(data: bytes, how: str) -> bytes:
    """Damage a CSV in one specific way, for fault-injection tests."""
    rows = list(csv.reader(io.StringIO(data.decode("utf-8"))))
    header_i = next(i for i, r in enumerate(rows) if r and r[0] in ("Booking Date", "Date"))
    body = rows[header_i + 1:]
    if not body:
        raise ValueError("nothing to corrupt")

    if how == "drop_row":
        del rows[header_i + 1 + len(body) // 2]
    elif how == "flip_sign":
        r = rows[header_i + 1]
        hdr = rows[header_i]
        if "Debit" in hdr and "Credit" in hdr:
            d, c = hdr.index("Debit"), hdr.index("Credit")
            r[d], r[c] = r[c], r[d]
        else:
            a = hdr.index("Amount")
            r[a] = r[a].replace("Dr", "Cr") if "Dr" in r[a] else r[a].replace("Cr", "Dr")
    elif how == "wrong_total":
        for r in rows[:header_i]:
            if r and r[0] in ("CLOSING BALANCE", "Closing Balance", "Total Income"):
                r[1] = "PKR 1.00" if r[1].startswith("PKR") else "1.00"
    elif how == "bad_amount":
        hdr = rows[header_i]
        idx = hdr.index("Credit") if "Credit" in hdr else hdr.index("Amount")
        rows[header_i + 1][idx] = "1,23.456"
    elif how == "blank_debit_and_credit":
        hdr = rows[header_i]
        if "Debit" in hdr and "Credit" in hdr:
            rows[header_i + 1][hdr.index("Debit")] = ""
            rows[header_i + 1][hdr.index("Credit")] = ""
        else:
            rows[header_i + 1][hdr.index("Amount")] = ""
    elif how == "unsorted_dates":
        if len(body) >= 2:
            rows[header_i + 1], rows[header_i + 2] = rows[header_i + 2], rows[header_i + 1]
    else:
        raise ValueError(f"unknown corruption {how!r}")
    return _csv_bytes(rows)
