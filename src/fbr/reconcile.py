"""Reconciliation: prove a parse before any figure is believed.

Every comparison is exact integer arithmetic. A tolerance would hide the
very bugs these checks exist to catch - a dropped row, a flipped sign, a
misread digit - and a tax return that is nearly right is wrong.

A statement with any failing check contributes nothing to any total
(spec §6.1, "fail closed").
"""

from __future__ import annotations

from fbr.config.schema_profile import Profile
from fbr.engines.tabular import ParseResult
from fbr.model import Check
from fbr.money import format_paisa

_ORDER = {"pass": 0, "warn": 1, "fail": 2}


def worst_status(checks: tuple[Check, ...] | list[Check]) -> str:
    return max((c.status for c in checks), key=lambda s: _ORDER[s], default="pass")


def statement_usable(checks: tuple[Check, ...] | list[Check]) -> bool:
    """False when any check failed: the statement's figures must not be used."""
    return not any(c.status == "fail" for c in checks)


def _check(kind, status, expected, actual, detail, locator=None, scope="document") -> Check:
    return Check(
        check_id=f"{scope}:{kind}",
        scope=scope,
        kind=kind,
        status=status,
        expected=expected,
        actual=actual,
        detail=detail,
        locator=locator,
    )


def _check_running_balance(result: ParseResult, profile: Profile) -> Check | None:
    """prev + amount == balance, walked in PRINTED order.

    Printed order, not date order: a bank may list same-day rows by posting
    sequence, and sorting first would break a chain that is actually correct.
    """
    if profile.balance.semantics != "running":
        return None
    txns = [t for t in result.transactions if t.balance_after is not None]
    if not txns:
        return _check("running_balance", "warn", "a balance column", "none",
                      "no row carried a balance; chain not verified")

    opening = result.document.summary.opening
    if opening is None:
        # Without a printed opening we can still verify every step after the
        # first, which catches dropped and flipped rows from row 2 onwards.
        previous = txns[0].balance_after - txns[0].amount
        note = "opening balance not printed; chain anchored on the first row"
        status_if_ok = "warn"
    else:
        previous = opening
        note = "chain verified from the printed opening balance"
        status_if_ok = "pass"

    for t in txns:
        expected = previous + t.amount
        if t.balance_after != expected:
            return _check(
                "running_balance", "fail",
                format_paisa(expected), format_paisa(t.balance_after),
                f"balance chain breaks at {t.date.isoformat()} "
                f"({t.description[:40]!r}); a row may be missing, merged or misread",
                locator=t.provenance.locator,
            )
        previous = t.balance_after

    return _check("running_balance", status_if_ok,
                  format_paisa(previous), format_paisa(previous), note)


def _check_opening_closing(result: ParseResult) -> Check | None:
    summary = result.document.summary
    if summary.opening is None or summary.closing is None:
        return _check("opening_closing", "warn", "printed opening and closing", "not both printed",
                      "statement does not print both balances; check skipped")
    total = sum(t.amount for t in result.transactions)
    expected = summary.opening + total
    status = "pass" if expected == summary.closing else "fail"
    return _check(
        "opening_closing", status,
        format_paisa(summary.closing), format_paisa(expected),
        "opening + credits - debits must equal the printed closing balance",
    )


def _check_printed_totals(result: ParseResult) -> Check | None:
    summary = result.document.summary
    if summary.total_credit is None and summary.total_debit is None:
        return None
    credits = sum(t.amount for t in result.transactions if t.amount > 0)
    debits = -sum(t.amount for t in result.transactions if t.amount < 0)
    problems = []
    if summary.total_credit is not None and summary.total_credit != credits:
        problems.append(
            f"credits: printed {format_paisa(summary.total_credit)}, "
            f"parsed {format_paisa(credits)}"
        )
    if summary.total_debit is not None and summary.total_debit != debits:
        problems.append(
            f"debits: printed {format_paisa(summary.total_debit)}, "
            f"parsed {format_paisa(debits)}"
        )
    return _check(
        "printed_totals", "fail" if problems else "pass",
        f"credits {format_paisa(summary.total_credit or credits)} / "
        f"debits {format_paisa(summary.total_debit or debits)}",
        f"credits {format_paisa(credits)} / debits {format_paisa(debits)}",
        "; ".join(problems) or "parsed totals match the statement's own totals",
    )


def _check_unresolved(result: ParseResult) -> Check:
    if not result.unresolved:
        return _check("unresolved_rows", "pass", "0", "0", "every row parsed")
    first = result.unresolved[0]
    return _check(
        "unresolved_rows", "fail", "0", str(len(result.unresolved)),
        f"{len(result.unresolved)} row(s) could not be parsed; first: {first.reason}",
        locator=first.locator,
    )


def _check_date_range(result: ParseResult) -> Check:
    doc = result.document
    start, end = doc.summary.period_start, doc.summary.period_end
    if start is None or end is None or not result.transactions:
        return _check("date_range", "warn", "a printed period", "not printed",
                      "statement does not print its period; dates not bounded")
    outside = [t for t in result.transactions if not (start <= t.date <= end)]
    if not outside:
        return _check("date_range", "pass", f"{start}..{end}", f"{start}..{end}",
                      "every transaction falls inside the printed period")
    t = outside[0]
    return _check(
        "date_range", "fail", f"{start}..{end}", t.date.isoformat(),
        f"{len(outside)} transaction(s) fall outside the printed period",
        locator=t.provenance.locator,
    )


def check_statement(result: ParseResult, profile: Profile) -> tuple[Check, ...]:
    """Run every per-statement check (spec §6.1)."""
    checks = [
        _check_running_balance(result, profile),
        _check_opening_closing(result),
        _check_printed_totals(result),
        _check_unresolved(result),
        _check_date_range(result),
    ]
    return tuple(c for c in checks if c is not None)


# --- appended to src/fbr/reconcile.py ---------------------------------------
"""Account-level merge and tax-year boundary balances (spec §6.2-6.4)."""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from fbr.config.schema_taxyear import TaxYear
from fbr.model import Account, Transaction

BalanceSource = Literal["printed", "computed", "anchor", "unknown"]
AccountStatus = Literal["complete", "incomplete", "failed"]


@dataclass(frozen=True, slots=True)
class AccountLedger:
    account_id: str
    transactions: tuple[Transaction, ...]
    checks: tuple[Check, ...]
    opening: int | None
    closing: int | None
    opening_source: BalanceSource
    closing_source: BalanceSource
    status: AccountStatus


def tax_year_slice(txns: tuple[Transaction, ...], tax_year: TaxYear) -> tuple[Transaction, ...]:
    """Transactions whose booking date falls inside the tax year."""
    return tuple(
        t for t in txns if tax_year.period_start <= t.date <= tax_year.period_end
    )


def _row_key(t: Transaction) -> tuple:
    return (t.date, t.amount, t.balance_after, t.description.strip().upper())


def _dedupe_overlaps(
    results: list[ParseResult],
) -> tuple[list[Transaction], list[Check]]:
    """Resolve overlapping statements by PERIOD, never row by row.

    Two identical Rs 1,000 top-ups on one day are both real, so rows are
    never matched across the year. Instead, where two statements cover the
    same days, the overlapping window must tell the same story; if it does,
    one copy is kept, preferring CSV/XLSX over PDF and then the longer period.
    """
    checks: list[Check] = []
    ordered = sorted(
        results,
        key=lambda r: (
            r.document.period_start or date.min,
            0 if r.document.container in ("csv", "xlsx") else 1,
            -((r.document.period_end or date.min) - (r.document.period_start or date.min)).days,
        ),
    )

    kept: list[Transaction] = []
    covered: list[tuple[date, date]] = []

    for result in ordered:
        start = result.document.period_start
        end = result.document.period_end
        window = next(
            ((s, e) for s, e in covered if start and end and s <= start and end <= e), None
        )
        if window is not None:
            # Fully inside an already-accepted period: the stories must agree.
            existing = [t for t in kept if start <= t.date <= end]
            incoming = list(result.transactions)
            if [_row_key(t) for t in existing] != [_row_key(t) for t in incoming]:
                checks.append(
                    _check(
                        "overlap", "fail",
                        f"{len(existing)} row(s) for {start}..{end}",
                        f"{len(incoming)} row(s) from {result.document.filename}",
                        "two statements cover the same period but disagree; "
                        "re-download one of them",
                        scope="account",
                    )
                )
            else:
                checks.append(
                    _check("overlap", "pass", "identical", "identical",
                           f"{result.document.filename} duplicates {start}..{end}; "
                           "one copy kept", scope="account")
                )
            continue

        kept.extend(result.transactions)
        if start and end:
            covered.append((start, end))

    return kept, checks


def _check_continuity(
    results: list[ParseResult], account: Account, tax_year: TaxYear
) -> list[Check]:
    """Warn about days in the tax year that no statement covers."""
    periods = sorted(
        (r.document.period_start, r.document.period_end)
        for r in results
        if r.document.period_start and r.document.period_end
    )
    if not periods:
        return [
            _check("gap", "warn", "a printed period", "none",
                   "no statement printed its period; coverage not verified",
                   scope="account")
        ]

    window_start = max(tax_year.period_start, account.opened_on or tax_year.period_start)
    window_end = min(tax_year.period_end, account.closed_on or tax_year.period_end)

    gaps: list[str] = []
    cursor = window_start
    for start, end in periods:
        if start > cursor:
            missing_end = min(start - timedelta(days=1), window_end)
            if cursor <= missing_end:
                gaps.append(f"{cursor.isoformat()}..{missing_end.isoformat()}")
        cursor = max(cursor, end + timedelta(days=1))
    if cursor <= window_end:
        gaps.append(f"{cursor.isoformat()}..{window_end.isoformat()}")

    if gaps:
        return [
            _check("gap", "warn", f"{window_start}..{window_end}", "; ".join(gaps),
                   f"no statement covers {'; '.join(gaps)}; this account's "
                   "tax-year figures are incomplete", scope="account")
        ]
    return [
        _check("gap", "pass", f"{window_start}..{window_end}", "covered",
               "statements cover the whole tax year", scope="account")
    ]


def boundary_balances(
    all_txns: tuple[Transaction, ...],
    in_year: tuple[Transaction, ...],
    *,
    printed_opening: int | None,
    printed_closing: int | None,
    starts_on_first_day: bool,
    ends_on_last_day: bool,
    anchor: int | None,
    has_balance_column: bool,
) -> tuple[int | None, BalanceSource, int | None, BalanceSource]:
    """Resolve the 1 July and 30 June balances (spec §6.3)."""
    if has_balance_column:
        if in_year:
            first, last = in_year[0], in_year[-1]
            opening = (first.balance_after - first.amount
                       if first.balance_after is not None else None)
            closing = last.balance_after
        else:
            # Dormant in-year: fall back to the printed figures (Review Focus #5).
            opening = printed_opening
            closing = printed_closing if printed_closing is not None else printed_opening

        opening_source: BalanceSource = "unknown" if opening is None else (
            "printed" if starts_on_first_day and printed_opening is not None else "computed"
        )
        closing_source: BalanceSource = "unknown" if closing is None else (
            "printed" if ends_on_last_day and printed_closing is not None else "computed"
        )
        if not in_year and opening is not None:
            opening_source = "printed"
            closing_source = "printed"
        return opening, opening_source, closing, closing_source

    # No balance column (SadaPay): everything hangs off the owner's anchor.
    if anchor is None:
        return None, "unknown", None, "unknown"
    return anchor, "anchor", anchor + sum(t.amount for t in in_year), "computed"


def merge_account(
    results: list[ParseResult],
    account: Account,
    tax_year: TaxYear,
    *,
    profiles: dict[str, Profile],
    anchor: int | None = None,
    prior_year_closing: int | None = None,
) -> AccountLedger:
    """Merge one account's statements into a tax-year ledger."""
    checks: list[Check] = []

    # Per-statement checks first: a failed statement takes the account with it.
    any_failed = False
    used_profiles: list[Profile] = []
    for result in results:
        profile = profiles.get(result.document.layout_id)
        if profile is None:
            # Fail closed. Skipping the checks here would let a broken statement
            # through silently, which is the one outcome this tool must not have.
            raise KeyError(
                f"no profile supplied for layout {result.document.layout_id!r}; "
                "per-statement checks cannot run"
            )
        used_profiles.append(profile)
        statement_checks = check_statement(result, profile)
        checks.extend(statement_checks)
        if not statement_usable(statement_checks):
            any_failed = True

    merged, overlap_checks = _dedupe_overlaps(results)
    checks.extend(overlap_checks)
    checks.extend(_check_continuity(results, account, tax_year))

    if any_failed or any(c.status == "fail" for c in checks):
        return AccountLedger(
            account_id=account.id, transactions=(), checks=tuple(checks),
            opening=None, closing=None, opening_source="unknown",
            closing_source="unknown", status="failed",
        )

    all_txns = tuple(merged)
    in_year = tax_year_slice(all_txns, tax_year)

    # Whether this account's statements carry a real running balance is a
    # property of the LAYOUT, not of which rows happened to survive the
    # merge: a dormant statement (zero transactions in the tax year, or
    # zero transactions at all) must not be mistaken for a wallet with no
    # balance column, which is the bug that a printed-balance dormant
    # account (Review Focus #5) would otherwise trip - `all_txns` empty
    # makes `any(t.balance_after is not None for t in all_txns)` False
    # regardless of the profile, silently routing a genuinely dormant
    # running-balance account into the anchor-required branch below.
    has_balance = any(p.balance.semantics == "running" for p in used_profiles)
    printed_opening = next(
        (r.document.summary.opening for r in results if r.document.summary.opening is not None),
        None,
    )
    printed_closing = next(
        (r.document.summary.closing for r in reversed(results)
         if r.document.summary.closing is not None),
        None,
    )
    starts_first = any(r.document.period_start == tax_year.period_start for r in results)
    ends_last = any(r.document.period_end == tax_year.period_end for r in results)

    opening, opening_source, closing, closing_source = boundary_balances(
        all_txns, in_year,
        printed_opening=printed_opening, printed_closing=printed_closing,
        starts_on_first_day=starts_first, ends_on_last_day=ends_last,
        anchor=anchor, has_balance_column=has_balance,
    )

    if opening_source == "unknown":
        checks.append(
            _check("anchor_missing", "warn", "an opening balance", "none",
                   f"{account.id} has no balance column and no anchor; enter the "
                   "1 July balance in manual inputs", scope="account")
        )

    if prior_year_closing is not None and opening is not None and opening != prior_year_closing:
        checks.append(
            _check("prior_year_mismatch", "warn",
                   format_paisa(prior_year_closing), format_paisa(opening),
                   "the computed 1 July balance differs from last year's declared "
                   "closing balance", scope="account")
        )

    status: AccountStatus = "incomplete" if any(
        c.status == "warn" and c.kind in ("gap", "anchor_missing") for c in checks
    ) else "complete"

    return AccountLedger(
        account_id=account.id, transactions=in_year, checks=tuple(checks),
        opening=opening, closing=closing, opening_source=opening_source,
        closing_source=closing_source, status=status,
    )
