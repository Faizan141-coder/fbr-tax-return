"""CSV/XLSX statement engine.

Columns are found by header NAME, never by index: Meezan's CSV export puts
Debit before Credit while its PDF puts Credit first, so a positional parser
would invert the sign of every row in one of them and reconcile perfectly
against nothing.

Rows stay in printed order. Anything this engine cannot read becomes an
UnresolvedRow, which fails the statement in reconcile.py, rather than a
silent zero.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import date

from fbr.config.schema_profile import Profile
from fbr.engines._shared import is_empty, labels, parse_date, read_summary, strip_suffix
from fbr.model import (
    Document,
    Provenance,
    Transaction,
    assign_occurrences,
    make_txn_id,
    tax_year_for,
)
from fbr.money import AmountError, parse_paisa

# `_read_summary` stays importable under its old name: tests/test_loader.py pins
# the loader's capture parsing against it, and that pin now covers the ONE
# implementation both engines use (fbr.engines._shared).
_read_summary = read_summary


class ParseError(RuntimeError):
    """The file cannot be parsed with this profile at all."""


@dataclass(frozen=True, slots=True)
class UnresolvedRow:
    locator: str
    raw: str
    reason: str


@dataclass(frozen=True, slots=True)
class ParseResult:
    document: Document
    transactions: tuple[Transaction, ...]
    unresolved: tuple[UnresolvedRow, ...]


def read_rows(data: bytes, container: str) -> list[list[str]]:
    """Decode a CSV or XLSX file into a list of string rows."""
    if container == "xlsx":
        return _read_xlsx(data)
    text = _decode_csv(data)
    return [row for row in csv.reader(io.StringIO(text))]


def _decode_csv(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ParseError("cannot decode file as UTF-8 or CP1252")


def _read_xlsx(data: bytes) -> list[list[str]]:
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    try:
        ws = wb[wb.sheetnames[0]]
        return [
            ["" if c is None else str(c) for c in row]
            for row in ws.iter_rows(values_only=True)
        ]
    finally:
        wb.close()


def _find_header(rows: list[list[str]], profile: Profile) -> int:
    """Return the index of the header row, searching the first 30 rows."""
    wanted = [w.strip().lower() for w in profile.detect.header_contains]
    for i, row in enumerate(rows[:30]):
        cells = [c.strip().lower() for c in row]
        if all(any(w == c for c in cells) for w in wanted):
            return i
    raise ParseError(
        f"header row not found for profile {profile.id!r}; expected all of "
        f"{profile.detect.header_contains}"
    )


def _map_columns(
    header: list[str], profile: Profile, *, require_balance: bool = True
) -> dict[str, int]:
    """Map each profile role to a column index by header name.

    `require_balance` is `False` only for `parse_row`'s selftest use: a
    selftest case is a hand-picked dict pinning (date, amount) and has no
    reason to also carry a balance column, so it must not be held to the
    same requirement a real statement is.
    """
    normalized = {c.strip().lower(): i for i, c in enumerate(header)}
    mapping: dict[str, int] = {}
    roles = ("date", "value_date", "description", "reference", "debit",
             "credit", "amount", "balance", "type")
    required = {"date", "description"}
    required |= ({"debit", "credit"} if profile.formats.sign == "columns" else {"amount"})
    # A profile that declares a running balance is asserting that every row
    # of a real statement carries one; if the column is missing/renamed,
    # silently mapping no "balance" role would drop every balance_after to
    # None with no error raised anywhere, which is the same silent-data-loss
    # failure mode the unresolved-row mechanism exists to prevent for
    # amounts. This must not bind parse_row's selftest rows (require_balance
    # is False there) or a profile whose selftest omits balance would raise
    # inside run_selftest, be marked ok=False, and quietly stop matching any
    # real statement.
    if profile.balance.semantics == "running" and require_balance:
        required.add("balance")

    for role in roles:
        for label in labels(getattr(profile.columns, role, None)):
            idx = normalized.get(label.strip().lower())
            if idx is not None:
                mapping[role] = idx
                break
        else:
            if role in required:
                wanted = labels(getattr(profile.columns, role, None))
                raise ParseError(
                    f"profile {profile.id!r} expects column {wanted!r} for role "
                    f"{role!r}; header has {header!r}"
                )
    return mapping


def _cell(row: list[str], mapping: dict[str, int], role: str) -> str:
    idx = mapping.get(role)
    if idx is None or idx >= len(row):
        return ""
    return row[idx].strip()


def _amount_for(row: list[str], mapping: dict[str, int], profile: Profile) -> tuple[int, str]:
    """Return (signed paisa, sign_source). Raises ValueError if unreadable."""
    mode = profile.formats.sign

    if mode == "columns":
        debit, credit = _cell(row, mapping, "debit"), _cell(row, mapping, "credit")
        d_empty, c_empty = is_empty(debit), is_empty(credit)
        if d_empty and c_empty:
            raise ValueError("row has no amount in either the debit or credit column")
        if not d_empty and not c_empty:
            raise ValueError(f"row has amounts in both columns: {debit!r} and {credit!r}")
        if c_empty:
            return -parse_paisa(debit, decimals=profile.formats.decimals), "column"
        return parse_paisa(credit, decimals=profile.formats.decimals), "column"

    raw = _cell(row, mapping, "amount")
    if is_empty(raw):
        raise ValueError("row has no amount")

    if mode == "suffix":
        number, direction = strip_suffix(raw, profile)
        return direction * abs(parse_paisa(number, decimals=profile.formats.decimals)), "suffix"

    return parse_paisa(raw, decimals=profile.formats.decimals), "signed"


def parse_row(profile: Profile, row: dict[str, str]) -> tuple[date, int]:
    """Parse one labelled row. Used by profile self-tests (loader.run_selftest).

    Returns only (date, amount) — a selftest case has no use for a balance,
    so this must not require the balance column a real statement would.
    """
    header = list(row.keys())
    values = [row[k] for k in header]
    mapping = _map_columns(header, profile, require_balance=False)
    d = parse_date(_cell(values, mapping, "date"), profile)
    amount, _ = _amount_for(values, mapping, profile)
    return d, amount


def parse_tabular(
    data: bytes,
    profile: Profile,
    *,
    sha256: str,
    filename: str,
    account_id: str | None,
) -> ParseResult:
    """Parse a CSV/XLSX statement into a Document and its Transactions."""
    rows = read_rows(data, profile.container)
    if not rows:
        raise ParseError("file is empty")

    header_i = _find_header(rows, profile)
    mapping = _map_columns(rows[header_i], profile)
    preamble = "\n".join(",".join(r) for r in rows[:header_i])
    summary = read_summary(preamble, profile)

    skip_res = [re.compile(p) for p in profile.rows.skip]
    summary_res = [re.compile(p) for p in profile.rows.summary]

    staged: list[dict] = []
    unresolved: list[UnresolvedRow] = []

    for offset, row in enumerate(rows[header_i + 1:], start=header_i + 2):
        raw = ",".join(row)
        locator = f"row:{offset}"
        if not any(cell.strip() for cell in row):
            continue
        if any(r.search(raw) for r in skip_res) or any(r.search(raw) for r in summary_res):
            continue

        date_text = _cell(row, mapping, "date")
        if is_empty(date_text):
            unresolved.append(UnresolvedRow(locator, raw, "row has no date"))
            continue
        try:
            d = parse_date(date_text, profile)
        except ValueError as exc:
            unresolved.append(UnresolvedRow(locator, raw, f"unreadable date: {exc}"))
            continue

        try:
            amount, sign_source = _amount_for(row, mapping, profile)
        except (ValueError, AmountError) as exc:
            unresolved.append(UnresolvedRow(locator, raw, str(exc)))
            continue

        balance_text = _cell(row, mapping, "balance")
        balance: int | None = None
        if profile.balance.semantics == "running" and not is_empty(balance_text):
            try:
                balance = parse_paisa(balance_text, decimals=profile.formats.decimals)
            except AmountError as exc:
                unresolved.append(UnresolvedRow(locator, raw, f"unreadable balance: {exc}"))
                continue

        value_date_text = _cell(row, mapping, "value_date")
        value_date: date | None = None
        if not is_empty(value_date_text):
            try:
                value_date = parse_date(value_date_text, profile)
            except ValueError:
                value_date = None

        staged.append({
            "date": d,
            "value_date": value_date,
            "amount": amount,
            "balance_after": balance,
            "description": _cell(row, mapping, "description"),
            "reference": _cell(row, mapping, "reference") or None,
            "sign_source": sign_source,
            "locator": locator,
            "raw": raw,
        })

    occurrences = assign_occurrences(staged)
    transactions = tuple(
        Transaction(
            txn_id=make_txn_id(
                account_id or "unassigned", s["date"], s["amount"],
                s["balance_after"], s["description"], occ,
            ),
            account_id=account_id or "unassigned",
            date=s["date"],
            value_date=s["value_date"],
            amount=s["amount"],
            balance_after=s["balance_after"],
            description=s["description"],
            reference=s["reference"],
            tax_year=tax_year_for(s["date"]),
            provenance=Provenance(
                sha256=sha256, locator=s["locator"], raw_text=s["raw"],
                sign_source=s["sign_source"],
            ),
        )
        for s, occ in zip(staged, occurrences, strict=True)
    )

    document = Document(
        sha256=sha256,
        filename=filename,
        kind="statement",
        container=profile.container,
        layout_id=profile.id,
        account_id=account_id,
        period_start=summary.period_start or (transactions[0].date if transactions else None),
        period_end=summary.period_end or (transactions[-1].date if transactions else None),
        pages=1,
        encrypted=False,
        summary=summary,
    )
    return ParseResult(document, transactions, tuple(unresolved))
