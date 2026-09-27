# src/fbr/model.py
"""Frozen types for every stage of the pipeline.

Frozen because a transaction that changes after a check has passed would
make the audit trail a lie: the Excel export must be able to say that this
figure came from that row, and that row must still be what was checked.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

SignSource = Literal["column", "suffix", "signed", "balance"]
CheckStatus = Literal["pass", "warn", "fail"]
CheckScope = Literal["document", "account", "tax_year"]
Container = Literal["csv", "xlsx", "pdf"]
DocKind = Literal["statement", "wht_certificate", "prc_statement"]


def tax_year_for(d: date) -> str:
    """Return the FBR tax year label for a date.

    A tax year runs 1 July to 30 June and is named for the June it ends in
    (spec §4.3), so 2025-07-01 through 2026-06-30 are all TY2026.
    """
    year = d.year + 1 if d.month >= 7 else d.year
    return f"TY{year}"


_WS = re.compile(r"\s+")


def normalize_description(s: str) -> str:
    """Fold a description to a stable key: NFKC, upper case, collapsed spaces.

    Used only for id derivation, never for display or classification, which
    both need the original text.
    """
    return _WS.sub(" ", unicodedata.normalize("NFKC", s)).strip().upper()


def make_txn_id(
    account_id: str,
    d: date,
    amount: int,
    balance_after: int | None,
    description: str,
    occurrence: int,
) -> str:
    """Derive a stable 16-hex-character transaction id (spec §4.1).

    Stability is the point: a review decision saved last week must still
    attach to the same row when the same file is loaded again. `None` and `0`
    balances hash differently, because a wallet with no balance column is not
    an account that happened to hit zero.
    """
    balance = "none" if balance_after is None else str(balance_after)
    payload = "\x1f".join(
        [
            account_id,
            d.isoformat(),
            str(amount),
            balance,
            normalize_description(description),
            str(occurrence),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def assign_occurrences(rows: list[dict]) -> list[int]:
    """Number rows that share (date, amount, balance, description) 1, 2, ...

    Numbering follows printed order, not sorted order, so that a statement
    listing same-day rows by posting sequence still yields the same ids on
    every run (Review Focus #2).
    """
    seen: Counter[tuple] = Counter()
    out: list[int] = []
    for r in rows:
        key = (
            r["date"],
            r["amount"],
            r.get("balance_after"),
            normalize_description(r["description"]),
        )
        seen[key] += 1
        out.append(seen[key])
    return out


@dataclass(frozen=True, slots=True)
class Provenance:
    """Where a value came from, precisely enough to find it again by hand."""

    sha256: str
    locator: str          # "row:12" (tabular) or "page:2,y:341" (pdf)
    raw_text: str
    sign_source: SignSource


@dataclass(frozen=True, slots=True)
class Transaction:
    txn_id: str
    account_id: str
    date: date            # booking date; drives tax_year
    value_date: date | None
    amount: int           # signed paisa: + credit, - debit
    balance_after: int | None
    description: str      # complete; wrapped lines already joined
    reference: str | None
    tax_year: str
    provenance: Provenance


@dataclass(frozen=True, slots=True)
class DocumentSummary:
    """Figures the statement prints about itself. Every field is optional,
    because SadaPay prints totals with no balances and others do the reverse."""

    opening: int | None = None
    closing: int | None = None
    total_credit: int | None = None
    total_debit: int | None = None
    period_start: date | None = None
    period_end: date | None = None
    account_identifier: str | None = None


@dataclass(frozen=True, slots=True)
class Document:
    sha256: str
    filename: str
    kind: DocKind
    container: Container
    layout_id: str
    account_id: str | None
    period_start: date | None
    period_end: date | None
    pages: int
    encrypted: bool
    summary: DocumentSummary


@dataclass(frozen=True, slots=True)
class Check:
    check_id: str
    scope: CheckScope
    kind: str
    status: CheckStatus
    expected: str
    actual: str
    detail: str
    locator: str | None = None


@dataclass(frozen=True, slots=True)
class Account:
    id: str
    institution: str
    kind: Literal["bank", "wallet", "foreign"]
    iban: str
    account_number: str
    wallet_number: str
    title: str
    type: str
    ownership: str
    currency: str
    statement_expected: bool
    match_hints: tuple[str, ...] | list[str] = field(default_factory=tuple)
    opened_on: date | None = None
    closed_on: date | None = None


@dataclass(frozen=True, slots=True)
class Owner:
    name: str


@dataclass(frozen=True, slots=True)
class Registry:
    owner: Owner
    accounts: tuple[Account, ...]

    def by_id(self, account_id: str) -> Account | None:
        return next((a for a in self.accounts if a.id == account_id), None)
