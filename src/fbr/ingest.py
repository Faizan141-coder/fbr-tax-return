"""Decide what a file is, which layout reads it, and whose account it is.

The container is sniffed from the bytes rather than the file name, and an
ambiguous layout match raises instead of picking: attaching the wrong layout
to a real statement is exactly the failure that would produce confident,
wrong numbers.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date

from fbr.config.loader import ProfileSet, ProfileStatus, run_selftest
from fbr.config.schema_profile import Profile
from fbr.engines.tabular import ParseError, parse_row, read_rows
from fbr.model import DocumentSummary, Registry

_XLSX_MAGIC = b"PK\x03\x04"
_PDF_MAGIC = b"%PDF"
_NON_ALNUM = re.compile(r"[^A-Za-z0-9]")


class LayoutUnknown(RuntimeError):
    """No profile matches this file."""


class LayoutAmbiguous(RuntimeError):
    """More than one profile matches; the signatures need tightening."""


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sniff_container(data: bytes, filename: str = "") -> str:
    """Identify the container from the file's own bytes."""
    if data.startswith(_PDF_MAGIC):
        return "pdf"
    if data.startswith(_XLSX_MAGIC):
        # .docx/.pptx share this magic, but only spreadsheets reach this tool.
        return "xlsx"
    return "csv"


def usable_profiles(
    profiles: ProfileSet, container: str
) -> tuple[tuple[Profile, ...], tuple[ProfileStatus, ...]]:
    """Profiles for this container that pass their own self-tests.

    A profile that cannot parse its own sample rows is excluded: it would
    otherwise fail silently on the statement it was written for (spec §5.4).
    """
    candidates = profiles.for_container(container)
    ok: list[Profile] = []
    report: list[ProfileStatus] = []
    for profile in candidates:
        status = run_selftest(profile, parse_row)
        report.append(status)
        if status.ok:
            ok.append(profile)
    return tuple(ok), tuple(report)


def _head_text(data: bytes, container: str, rows: int = 30) -> str:
    try:
        parsed = read_rows(data, container)
    except ParseError:
        return ""
    return "\n".join(",".join(r) for r in parsed[:rows])


def _matches(profile: Profile, head: str) -> bool:
    lowered = head.lower()
    if not all(token.strip().lower() in lowered for token in profile.detect.header_contains):
        return False
    if profile.detect.title_regex and not re.search(profile.detect.title_regex, head):
        return False
    return True


def detect_layout(
    data: bytes,
    profiles: ProfileSet,
    container: str,
    *,
    on: date | None = None,
) -> Profile:
    """Return the single profile that matches this file."""
    candidates, _ = usable_profiles(profiles, container)
    if on is not None:
        candidates = tuple(
            p for p in candidates
            if p.valid_from <= on and (p.valid_to is None or on <= p.valid_to)
        )

    head = _head_text(data, container)
    matched = [p for p in candidates if _matches(p, head)]

    if not matched:
        raise LayoutUnknown(
            f"no {container} profile matches this file. Run `fbr-dump <file>` and "
            "send the masked dump so a profile can be written for this layout."
        )
    if len(matched) > 1:
        ids = ", ".join(sorted(p.id for p in matched))
        raise LayoutAmbiguous(
            f"{len(matched)} profiles match this file ({ids}); tighten their "
            "[detect] signatures so exactly one matches"
        )
    return matched[0]


def _squash(value: str) -> str:
    return _NON_ALNUM.sub("", value).upper()


def resolve_account(
    summary: DocumentSummary, text: str, registry: Registry
) -> str | None:
    """Link a statement to a registry account by IBAN, number or wallet.

    Comparison ignores spacing and case, because statements print IBANs
    grouped in fours as often as not.
    """
    haystack = _squash(f"{summary.account_identifier or ''} {text}")
    if not haystack:
        return None
    for account in registry.accounts:
        for identifier in (account.iban, account.account_number, account.wallet_number):
            if identifier and _squash(identifier) in haystack:
                return account.id
    return None
