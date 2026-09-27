# src/fbr/money.py
"""Money is integer paisa everywhere in this codebase (spec Global Constraints).

Decimal appears only inside parse_paisa, where text becomes an integer. No
other module parses an amount, and no money value is ever a float: a float
rupee figure cannot represent 0.10 exactly, and a tax return must reconcile
to the paisa.
"""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation

PAISA_PER_RUPEE = 100


class AmountError(ValueError):
    """The text is not an amount this grammar accepts.

    Raised rather than guessed: a silently coerced amount is a wrong number on
    a tax return, which is worse than a row the operator must look at.
    """


# Groups are 2 or 3 digits to accept both 1,234,567 and lakh-style 12,34,567.
_AMOUNT = re.compile(
    r"""(?x) ^
    (?P<lparen>\()?
    (?P<sign>[-+])?
    \s*
    (?:(?:PKR|Rs)\.?)?
    \s*
    (?P<int>[0-9]{1,3}(?:,[0-9]{2,3})*|[0-9]+)
    (?:\.(?P<frac>[0-9]{1,2}))?
    \s*
    (?P<rparen>\))?
    (?P<trailing>-)?
    $""",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    """Drop the NBSP thousands separator, NFKC-fold, map the Unicode minus to ASCII.

    Statement PDFs and CSVs sometimes use a non-breaking space (U+00A0) as a
    thousands separator inside the digit run, where the grammar below has no
    whitespace tolerance; it is removed before NFKC would fold it into a
    plain space and make it indistinguishable from one. NFKC also folds it
    into a plain space, so it must be dropped first, not after. Ordinary
    spaces are deliberately left alone: the grammar's own `\\s*` tokens
    already cover leading/trailing whitespace and space around a PKR/Rs
    prefix, and a bare interior space (as in "1 234 56") is not a grouping
    separator this grammar accepts — it must still fail to parse.
    """
    s = text.replace("\xa0", "")
    s = unicodedata.normalize("NFKC", s)
    return s.replace("−", "-")


def parse_paisa(text: str, *, decimals: int = 2) -> int:
    """Parse an amount into signed integer paisa.

    Accepts optional PKR/Rs prefix, comma grouping (3- or 2-digit groups),
    up to `decimals` decimal places, and a sign expressed as a leading -/+,
    surrounding parentheses, or a trailing minus.

    Rejects Dr/Cr suffixes: direction is the layout profile's job, because
    only the profile knows which token that bank uses for which direction.
    """
    if text is None:
        raise AmountError("amount is None")
    s = _normalize(str(text))
    if not s:
        raise AmountError("empty amount")

    m = _AMOUNT.match(s)
    if m is None:
        raise AmountError(f"unparseable amount: {text!r}")

    if bool(m.group("lparen")) != bool(m.group("rparen")):
        raise AmountError(f"unbalanced parentheses: {text!r}")

    signs = [
        m.group("sign") == "-",
        bool(m.group("lparen")),
        bool(m.group("trailing")),
    ]
    if sum(signs) > 1:
        raise AmountError(f"more than one negative marker: {text!r}")
    negative = any(signs)

    frac = m.group("frac") or ""
    if len(frac) > decimals:
        raise AmountError(f"more than {decimals} decimal places: {text!r}")

    digits = m.group("int").replace(",", "")
    try:
        value = Decimal(digits) * PAISA_PER_RUPEE + Decimal(frac.ljust(decimals, "0") or 0)
    except InvalidOperation as exc:  # pragma: no cover - guarded by the regex
        raise AmountError(f"unparseable amount: {text!r}") from exc

    paisa = int(value)
    return -paisa if negative else paisa


def format_paisa(paisa: int) -> str:
    """Render integer paisa as a grouped decimal string for display and export."""
    sign = "-" if paisa < 0 else ""
    whole, frac = divmod(abs(paisa), PAISA_PER_RUPEE)
    return f"{sign}{whole:,}.{frac:02d}"
