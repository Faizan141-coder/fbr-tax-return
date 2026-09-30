# src/fbr/engines/_shared.py
"""The rules both statement engines must apply identically.

These five helpers were duplicated verbatim in `tabular.py` and `pdf.py`. That
is a drift hazard with a specific shape: `tests/test_loader.py` pins
`loader._capture_as_the_engine_does` against `tabular._read_summary` for every
shipped profile, so the CSV engine's copy could never drift unnoticed - and the
PDF engine's copy could drift freely. A summary pattern that read one figure on
a CSV and a different one on a PDF is exactly the kind of divergence that puts a
wrong number on a return, and nothing would have caught it.

One implementation, imported by both engines, so there is nothing left to drift.
`read_summary` in particular is now pinned by that existing loader test for
every container.
"""

from __future__ import annotations

from datetime import date, datetime

from fbr.config.schema_profile import Profile
from fbr.model import DocumentSummary
from fbr.money import AmountError, parse_paisa

# Values a bank prints to mean "nothing on this side of the ledger".
EMPTY_MARKERS = frozenset({"", "-", "--", "—", "–", "n/a", "na", "nil"})


def is_empty(value: str) -> bool:
    return value.strip().lower() in EMPTY_MARKERS


def labels(spec: str | list[str] | None) -> list[str]:
    """Normalise a profile's role -> label spec into a list of labels."""
    if spec is None:
        return []
    return [spec] if isinstance(spec, str) else list(spec)


def parse_date(text: str, profile: Profile) -> date:
    """First of the profile's own date formats that fits. Raises ValueError."""
    for fmt in profile.formats.dates:
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"date {text!r} matches none of {profile.formats.dates}")


def strip_suffix(text: str, profile: Profile) -> tuple[str, int]:
    """Split an MCB-style '1,234.00Dr' into its number and its direction."""
    cleaned = text.strip()
    for token in profile.formats.credit_tokens:
        if cleaned.lower().endswith(token.lower()):
            return cleaned[: -len(token)].strip(" ."), 1
    for token in profile.formats.debit_tokens:
        if cleaned.lower().endswith(token.lower()):
            return cleaned[: -len(token)].strip(" ."), -1
    raise ValueError(
        f"amount {text!r} has no direction token "
        f"({profile.formats.debit_tokens + profile.formats.credit_tokens})"
    )


def read_summary(text: str, profile: Profile) -> DocumentSummary:
    """Pull opening/closing/totals/period out of the preamble or page text.

    A value the profile's pattern captured but this cannot convert is skipped,
    not guessed at: the summary field stays None and the reconciliation check
    that depends on it reports its own absence.
    """
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
                    parse_date(value, profile)
                )
            except ValueError:
                continue
        else:
            found["account_identifier"] = value.strip()
    return DocumentSummary(**found)          # type: ignore[arg-type]
