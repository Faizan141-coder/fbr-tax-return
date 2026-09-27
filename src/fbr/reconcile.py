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
