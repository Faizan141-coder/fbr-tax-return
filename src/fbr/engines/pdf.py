# src/fbr/engines/pdf.py
"""PDF statement engine: positioned words in, typed transactions out.

Emits the same ParseResult the tabular engine does, so reconcile.py's five
checks apply unchanged. Two rules carry the weight:

  * An unsigned amount's column is decided by geometry (_bands), never by
    guess. Ambiguity becomes an UnresolvedRow, which fails the statement.
  * Rows keep printed order, because the running-balance check walks the
    printed sequence.

Encrypted files are decrypted in memory with a password held only in a local
variable - never written to disk, a log, or a command line. The password is
also kept out of every exception message, since those get displayed.
"""

from __future__ import annotations

import io
import re
from datetime import date, datetime

import pdfplumber

from fbr.config.schema_profile import Profile
from fbr.engines._bands import BandError, Word, assign, build_bands, group_lines
from fbr.engines.tabular import ParseError, ParseResult, UnresolvedRow
from fbr.model import (
    Document,
    DocumentSummary,
    Provenance,
    Transaction,
    assign_occurrences,
    make_txn_id,
    tax_year_for,
)
from fbr.money import AmountError, parse_paisa

_EMPTY = {"", "-", "--", "—", "–", "n/a", "na", "nil"}


class PdfPasswordError(ParseError):
    """The file is encrypted and the supplied password did not open it."""


class PdfNotTextual(ParseError):
    """The file has no extractable text layer, or unmapped fonts."""


def _open(data: bytes, password: str | None):
    """Open a PDF, decrypting in memory. Never puts the password in an error."""
    try:
        return pdfplumber.open(io.BytesIO(data), password=password or "")
    except Exception as exc:                        # noqa: BLE001
        # pdfplumber wraps pdfminer's error, whose str() is empty; the wrapped
        # type is the reliable signal. Message text is a fallback only.
        names = " ".join(type(a).__name__ for a in exc.args) + " " + type(exc).__name__
        text = (str(exc) + " " + names).lower()
        if "password" in text or "decrypt" in text or "incorrect" in text:
            raise PdfPasswordError(
                "this PDF is encrypted and the password did not open it; "
                "check the password and try again"
            ) from None                             # `from None`: the original
                                                    # may echo the password
        raise ParseError(f"cannot open this PDF: {type(exc).__name__}") from None


def _page_words(page) -> list[Word]:
    raw = page.extract_words(use_text_flow=False, keep_blank_chars=False,
                             extra_attrs=[])
    return [Word.from_dict(w) for w in raw]


def _labels(spec) -> list[str]:
    if spec is None:
        return []
    return [spec] if isinstance(spec, str) else list(spec)


def _roles_and_aligns(profile: Profile) -> tuple[dict[str, str], dict[str, str]]:
    roles: dict[str, str] = {}
    for role in ("date", "value_date", "description", "reference", "debit",
                 "credit", "amount", "balance", "type"):
        labels = _labels(getattr(profile.columns, role, None))
        if labels:
            roles[role] = labels[0]
    align = profile.columns.align
    aligns = {
        "date": "left", "value_date": "left", "description": "left",
        "reference": "left", "type": "left",
        "debit": align.debit, "credit": align.credit,
        "amount": align.amount, "balance": align.balance,
    }
    return roles, aligns


def _find_header(lines: list[list[Word]], profile: Profile) -> int | None:
    wanted = [t.strip().lower() for t in profile.detect.header_contains]
    for i, line in enumerate(lines):
        joined = " ".join(w.text for w in line).lower()
        if all(t in joined for t in wanted):
            return i
    return None


def _parse_date(text: str, profile: Profile) -> date:
    for fmt in profile.formats.dates:
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"date {text!r} matches none of {profile.formats.dates}")


def _strip_suffix(text: str, profile: Profile) -> tuple[str, int]:
    cleaned = text.strip()
    for token in profile.formats.credit_tokens:
        if cleaned.lower().endswith(token.lower()):
            return cleaned[: -len(token)].strip(" ."), 1
    for token in profile.formats.debit_tokens:
        if cleaned.lower().endswith(token.lower()):
            return cleaned[: -len(token)].strip(" ."), -1
    raise ValueError(f"amount {text!r} carries no Dr/Cr token")


def _amount_from_cells(cells: dict[str, str], profile: Profile) -> tuple[int, str]:
    mode = profile.formats.sign
    dec = profile.formats.decimals
    if mode == "columns":
        debit, credit = cells.get("debit", ""), cells.get("credit", "")
        d_empty = debit.strip().lower() in _EMPTY
        c_empty = credit.strip().lower() in _EMPTY
        if d_empty and c_empty:
            raise ValueError("row has no amount in either the debit or credit column")
        if not d_empty and not c_empty:
            raise ValueError(f"row has amounts in both columns: {debit!r} and {credit!r}")
        if c_empty:
            return -parse_paisa(debit, decimals=dec), "column"
        return parse_paisa(credit, decimals=dec), "column"
    raw = cells.get("amount", "")
    if raw.strip().lower() in _EMPTY:
        raise ValueError("row has no amount")
    if mode == "suffix":
        number, direction = _strip_suffix(raw, profile)
        return direction * abs(parse_paisa(number, decimals=dec)), "suffix"
    return parse_paisa(raw, decimals=dec), "signed"


def _read_summary(text: str, profile: Profile) -> DocumentSummary:
    found: dict[str, object] = {}
    for name, pattern in profile.summary.compiled().items():
        m = pattern.search(text)
        if not m:
            continue
        value = m.group("value")
        if name in ("opening", "closing", "total_credit", "total_debit"):
            try:
                found[name] = parse_paisa(value, decimals=profile.formats.decimals)
            except AmountError:
                continue
        elif name in ("period_from", "period_to"):
            try:
                found["period_start" if name == "period_from" else "period_end"] = (
                    _parse_date(value, profile)
                )
            except ValueError:
                continue
        else:
            found["account_identifier"] = value.strip()
    return DocumentSummary(**found)          # type: ignore[arg-type]


def _rows_from_pdf(
    pdf, profile: Profile
) -> tuple[list[dict], list[UnresolvedRow], str, int]:
    """Walk every page, returning staged row dicts and unresolved rows."""
    roles, aligns = _roles_and_aligns(profile)
    skip_res = [re.compile(p) for p in profile.rows.skip]
    summary_res = [re.compile(p) for p in profile.rows.summary]
    footer_res = [re.compile(p) for p in profile.rows.footer]

    staged: list[dict] = []
    unresolved: list[UnresolvedRow] = []
    preamble_parts: list[str] = []
    bands = None
    empty_pages = 0

    for page_no, page in enumerate(pdf.pages, start=1):
        words = _page_words(page)
        if not words:
            empty_pages += 1
            continue
        if any("(cid:" in w.text for w in words):
            raise PdfNotTextual(
                f"page {page_no} has unmapped fonts ((cid:) glyphs); this PDF "
                "cannot be read as text"
            )
        lines = group_lines(words)
        header_i = _find_header(lines, profile)
        if header_i is not None:
            preamble_parts.append(
                "\n".join(" ".join(w.text for w in l) for l in lines[:header_i])
            )
            try:
                bands = build_bands(lines[header_i], roles, aligns)
            except BandError as exc:
                raise ParseError(str(exc)) from None
            body = lines[header_i + 1:]
        else:
            if bands is None:
                continue          # a cover page before any header
            body = lines

        open_row: dict | None = None
        for line in body:
            raw = " ".join(w.text for w in line)
            if any(r.search(raw) for r in footer_res):
                break
            if any(r.search(raw) for r in skip_res) or any(
                r.search(raw) for r in summary_res
            ):
                continue

            cells: dict[str, str] = {}
            ambiguous: list[str] = []
            for word in line:
                role = assign(word, bands)
                if role is None:
                    ambiguous.append(word.text)
                    continue
                cells[role] = (cells.get(role, "") + " " + word.text).strip()

            locator = f"page:{page_no},y:{round(line[0].top)}"
            date_text = cells.get("date", "")
            has_date = bool(date_text) and date_text.strip().lower() not in _EMPTY

            if profile.rows.row_anchor == "date" and not has_date:
                # A continuation line: append its description to the open row.
                if open_row is not None and cells.get("description"):
                    open_row["description"] = (
                        open_row["description"] + " " + cells["description"]
                    ).strip()
                    open_row["raw"] = open_row["raw"] + " / " + raw
                continue

            if ambiguous:
                unresolved.append(UnresolvedRow(
                    locator, raw,
                    f"ambiguous column for {ambiguous!r}: a token sat outside "
                    "every column band or equally close to two",
                ))
                open_row = None
                continue

            try:
                d = _parse_date(date_text, profile)
            except ValueError as exc:
                unresolved.append(UnresolvedRow(locator, raw, f"unreadable date: {exc}"))
                open_row = None
                continue

            try:
                amount, sign_source = _amount_from_cells(cells, profile)
            except (ValueError, AmountError) as exc:
                unresolved.append(UnresolvedRow(locator, raw, str(exc)))
                open_row = None
                continue

            balance: int | None = None
            balance_text = cells.get("balance", "")
            if profile.balance.semantics == "running" and balance_text.strip().lower() not in _EMPTY:
                try:
                    balance = parse_paisa(balance_text,
                                          decimals=profile.formats.decimals)
                except AmountError as exc:
                    unresolved.append(UnresolvedRow(
                        locator, raw, f"unreadable balance: {exc}"))
                    open_row = None
                    continue

            open_row = {
                "date": d,
                "value_date": None,
                "amount": amount,
                "balance_after": balance,
                "description": cells.get("description", ""),
                "reference": cells.get("reference") or None,
                "sign_source": sign_source,
                "locator": locator,
                "raw": raw,
            }
            staged.append(open_row)

    return staged, unresolved, "\n".join(preamble_parts), empty_pages


def parse_pdf(
    data: bytes,
    profile: Profile,
    *,
    sha256: str,
    filename: str,
    account_id: str | None,
    password: str | None = None,
) -> ParseResult:
    """Parse a PDF statement into a Document and its Transactions."""
    with _open(data, password) as pdf:
        pages = len(pdf.pages)
        staged, unresolved, preamble, empty_pages = _rows_from_pdf(pdf, profile)

    if not staged and not unresolved and empty_pages == pages:
        raise PdfNotTextual(
            "this PDF has no extractable text on any page; it is probably a "
            "scan, which is not supported"
        )

    summary = _read_summary(preamble, profile)
    occurrences = assign_occurrences(staged)
    transactions = tuple(
        Transaction(
            txn_id=make_txn_id(account_id or "unassigned", s["date"], s["amount"],
                               s["balance_after"], s["description"], occ),
            account_id=account_id or "unassigned",
            date=s["date"],
            value_date=s["value_date"],
            amount=s["amount"],
            balance_after=s["balance_after"],
            description=s["description"],
            reference=s["reference"],
            tax_year=tax_year_for(s["date"]),
            provenance=Provenance(sha256=sha256, locator=s["locator"],
                                  raw_text=s["raw"], sign_source=s["sign_source"]),
        )
        for s, occ in zip(staged, occurrences, strict=True)
    )

    document = Document(
        sha256=sha256, filename=filename, kind="statement", container="pdf",
        layout_id=profile.id, account_id=account_id,
        period_start=summary.period_start or (transactions[0].date if transactions else None),
        period_end=summary.period_end or (transactions[-1].date if transactions else None),
        pages=pages, encrypted=bool(password), summary=summary,
    )
    return ParseResult(document, transactions, tuple(unresolved))


def pdf_row_samples(
    data: bytes,
    profile: Profile,
    *,
    password: str | None = None,
    limit: int = 5,
) -> list[dict[str, str]]:
    """Return labelled cell dicts for the first rows, keyed by header label.

    This is what lets a PDF profile's `selftest` cases run through the same
    `parse_row` the tabular engine uses - so a PDF profile proves it can read
    its own sample rows before it is trusted on a real statement.
    """
    roles, _ = _roles_and_aligns(profile)
    role_to_label = dict(roles)
    with _open(data, password) as pdf:
        staged, _, _, _ = _rows_from_pdf(pdf, profile)

    out: list[dict[str, str]] = []
    for s in staged[:limit]:
        row: dict[str, str] = {}
        for role, label in role_to_label.items():
            if role == "date":
                row[label] = s["date"].strftime(profile.formats.dates[0])
            elif role == "description":
                row[label] = s["description"]
            elif role in ("amount", "credit", "debit", "balance"):
                row[label] = ""
        # Re-render the amount in the profile's own shape.
        from fbr.money import format_paisa
        if profile.formats.sign == "columns":
            if s["amount"] > 0:
                row[role_to_label["credit"]] = format_paisa(s["amount"])
            else:
                row[role_to_label["debit"]] = format_paisa(-s["amount"])
            if "balance" in role_to_label and s["balance_after"] is not None:
                row[role_to_label["balance"]] = format_paisa(s["balance_after"])
        else:
            sign = "+" if s["amount"] > 0 else "-"
            row[role_to_label["amount"]] = f"{sign}{format_paisa(abs(s['amount']))}"
        out.append(row)
    return out
