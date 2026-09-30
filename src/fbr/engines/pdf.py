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
from datetime import date

import pdfplumber

from fbr.config.schema_profile import Profile
from fbr.engines._bands import BandError, Word, assign, build_bands, group_lines
from fbr.engines._shared import is_empty, labels, parse_date, read_summary, strip_suffix
from fbr.engines.tabular import ParseError, ParseResult, UnresolvedRow
from fbr.model import (
    Document,
    Provenance,
    Transaction,
    assign_occurrences,
    make_txn_id,
    tax_year_for,
)
from fbr.money import AmountError, parse_paisa


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


def extract_text(data: bytes, *, password: str | None = None,
                 pages: int = 2) -> str:
    """Plain text from the first `pages` pages, for account resolution.

    `pipeline._free_text` used to push PDF bytes through the CSV decoder, so
    `resolve_account` searched `'%PDF-1.3\\n%...ReportLab...'` and found no
    identifier: a SadaPay PDF printing an IBAN that a registry account holds
    resolved to `unassigned`, while the identical CSV resolved `ok`. No profile
    declares an `account_id` summary pattern, so this body text is the only
    thing account resolution has to work with on a PDF.

    Two pages, matching `ingest._head_text`: the printed identifier sits in the
    statement header, and reading the whole document would only widen the window
    for a transaction description to name some other registry account - which
    `resolve_account` answers with `None` rather than a guess, but an
    unnecessary `None` is still a statement the owner has to assign by hand.

    The password reaches `_open` and nothing else: it is never logged, never put
    in an error message, and never written anywhere.
    """
    with _open(data, password) as pdf:
        return "\n".join((page.extract_text() or "") for page in pdf.pages[:pages])


def _page_words(page) -> list[Word]:
    raw = page.extract_words(use_text_flow=False, keep_blank_chars=False,
                             extra_attrs=[])
    return [Word.from_dict(w) for w in raw]


def _roles_and_aligns(profile: Profile) -> tuple[dict[str, str], dict[str, str]]:
    roles: dict[str, str] = {}
    for role in ("date", "value_date", "description", "reference", "debit",
                 "credit", "amount", "balance", "type"):
        found = labels(getattr(profile.columns, role, None))
        if found:
            roles[role] = found[0]
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


def _amount_from_cells(cells: dict[str, str], profile: Profile) -> tuple[int, str]:
    mode = profile.formats.sign
    dec = profile.formats.decimals
    if mode == "columns":
        debit, credit = cells.get("debit", ""), cells.get("credit", "")
        d_empty = is_empty(debit)
        c_empty = is_empty(credit)
        if d_empty and c_empty:
            raise ValueError("row has no amount in either the debit or credit column")
        if not d_empty and not c_empty:
            raise ValueError(f"row has amounts in both columns: {debit!r} and {credit!r}")
        if c_empty:
            return -parse_paisa(debit, decimals=dec), "column"
        return parse_paisa(credit, decimals=dec), "column"
    raw = cells.get("amount", "")
    if is_empty(raw):
        raise ValueError("row has no amount")
    if mode == "suffix":
        number, direction = strip_suffix(raw, profile)
        return direction * abs(parse_paisa(number, decimals=dec)), "suffix"
    return parse_paisa(raw, decimals=dec), "signed"


def _rows_from_pdf(
    pdf, profile: Profile
) -> tuple[list[dict], list[UnresolvedRow], str, int]:
    """Walk every page, returning staged row dicts and unresolved rows."""
    roles, aligns = _roles_and_aligns(profile)
    skip_res = [re.compile(p) for p in profile.rows.skip]
    summary_res = [re.compile(p) for p in profile.rows.summary]
    footer_res = [re.compile(p) for p in profile.rows.footer]

    def is_furniture(text: str) -> bool:
        """A line a profile has already told us carries no transaction."""
        return (any(r.search(text) for r in skip_res)
                or any(r.search(text) for r in summary_res)
                or any(r.search(text) for r in footer_res))

    staged: list[dict] = []
    unresolved: list[UnresolvedRow] = []
    preamble_parts: list[str] = []
    bands = None
    empty_pages = 0
    pages_seen = 0
    open_row: dict | None = None      # persists across pages: a wrapped
                                      # description can start a new page

    for page_no, page in enumerate(pdf.pages, start=1):
        pages_seen += 1
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

        for index, line in enumerate(body):
            raw = " ".join(w.text for w in line)
            if any(r.search(raw) for r in footer_res):
                # A footer ends the page - but ONLY if nothing that could be a
                # transaction follows it. `break` alone silently discarded every
                # row below the match, and sadapay.pdf.v1's own footer pattern
                # '(?i)^\s*page\s+\d+' matches a "Page 2 of 2" line printed at
                # the TOP of a continuation page. Measured: a two-page statement
                # parsed 1 of 2 rows, reported a net of Rs 300.00 where the truth
                # was Rs 100.00, and raised no UnresolvedRow and no failing
                # check. Money must never leave this engine unannounced, so a
                # footer with body lines still after it fails the statement
                # instead. Lines the profile itself classes as furniture (skip,
                # summary or another footer match) do not count: a real footer
                # followed by a page number or a disclaimer the profile lists is
                # the ordinary end of a page.
                following = [
                    " ".join(w.text for w in l) for l in body[index + 1:]
                ]
                orphaned = [t for t in following if not is_furniture(t)]
                if orphaned:
                    unresolved.append(UnresolvedRow(
                        f"page:{page_no},y:{round(line[0].top)}", raw,
                        f"a rows.footer pattern matched this line, but "
                        f"{len(orphaned)} line(s) follow it on page {page_no}; "
                        "ending the page here would discard them without a "
                        "trace, so the statement is refused instead - tighten "
                        "the footer pattern so it matches only the real end of "
                        "a page",
                    ))
                    open_row = None
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
            has_date = not is_empty(date_text)

            if profile.rows.row_anchor == "date" and not has_date:
                # A dateless line. ONLY description text may be absorbed into
                # the open row. A dateless line that carries money is not a
                # continuation - it is a row whose date the bank did not
                # reprint (common on a same-day second row), and absorbing it
                # DISCARDED the amount, the balance and the ambiguity list.
                # That lost real money while every check stayed green: the
                # balance vanished with the row, so the running-balance chain
                # still verified over the rows that survived, `unresolved` was
                # empty, and statement_usable() returned True. Money must
                # never leave this engine without an UnresolvedRow naming it.
                carried = [
                    f"{role} {cells[role]!r}"
                    for role in ("debit", "credit", "amount", "balance")
                    if not is_empty(cells.get(role, ""))
                ]
                problems: list[str] = []
                if carried:
                    problems.append("carries " + ", ".join(carried))
                if ambiguous:
                    problems.append(
                        f"has token(s) outside every column band: {ambiguous!r}"
                    )
                if problems:
                    unresolved.append(UnresolvedRow(
                        locator, raw,
                        f"row has no date in the {roles.get('date', 'date')!r} "
                        f"column but {' and '.join(problems)}; it cannot be a "
                        "description continuation, and its figures must not be "
                        "silently dropped",
                    ))
                    open_row = None
                    continue
                # A genuine continuation: description text only.
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
                d = parse_date(date_text, profile)
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
            if profile.balance.semantics == "running" and not is_empty(balance_text):
                try:
                    balance = parse_paisa(balance_text,
                                          decimals=profile.formats.decimals)
                except AmountError as exc:
                    unresolved.append(UnresolvedRow(
                        locator, raw, f"unreadable balance: {exc}"))
                    open_row = None
                    continue

            # A value_date band is built whenever the profile names the column
            # (_roles_and_aligns), so its words were assigned, consumed, and then
            # thrown away against a hardcoded None - no field, no unresolved row,
            # nothing. The tabular engine parses value_date, so this one does
            # too. An unreadable one stays None exactly as it does there: the
            # value date moves no money and the booking date is what every check
            # and every tax-year slice uses.
            value_date: date | None = None
            value_date_text = cells.get("value_date", "")
            if not is_empty(value_date_text):
                try:
                    value_date = parse_date(value_date_text, profile)
                except ValueError:
                    value_date = None

            open_row = {
                "date": d,
                "value_date": value_date,
                "amount": amount,
                "balance_after": balance,
                "description": cells.get("description", ""),
                "reference": cells.get("reference") or None,
                "sign_source": sign_source,
                "locator": locator,
                "raw": raw,
            }
            staged.append(open_row)

    if bands is None and pages_seen > empty_pages:
        # No page ever produced a header, yet at least one page had text. The
        # tabular engine raises here (tabular._find_header); this one used to
        # return nothing at all, so a SadaPay PDF read with the Meezan profile
        # gave 0 transactions, 0 unresolved rows, no exception and
        # statement_usable() == True. An engine that reports a wrong layout as
        # a clean empty statement fails open, which is the one thing it may
        # not do. A cover page before the first header, and continuation pages
        # that repeat no header, are still fine: this fires only when NOT ONE
        # page matched.
        raise ParseError(
            f"header row not found for profile {profile.id!r} on any of the "
            f"{pages_seen} page(s); expected all of "
            f"{profile.detect.header_contains}"
        )

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

    summary = read_summary(preamble, profile)
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
