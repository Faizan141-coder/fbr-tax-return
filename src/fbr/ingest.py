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


def sniff_container(data: bytes) -> str:
    """Identify the container from the file's own bytes.

    Takes no filename on purpose. It used to accept one, ignore it, and
    invite the belief that the extension had a say - a bank that emails
    XLSX bytes named .csv would then crash the CSV reader.
    """
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
    except Exception as exc:  # noqa: BLE001 - see comment below
        # A corrupt or partially-downloaded file must not crash detection: a
        # later task feeds this function every one of the owner's real files
        # in turn and reports a per-file outcome, so one bad file has to
        # become a clear result here rather than an unhandled traceback that
        # takes the whole run down. `ParseError` is this module's own signal
        # for an undecodable CSV, but the xlsx path runs the bytes through
        # openpyxl and zipfile, which raise their own exception types
        # depending on exactly how the archive is damaged (confirmed by
        # hand: `zipfile.BadZipFile` for garbage or a truncated archive,
        # `KeyError` for a well-formed zip missing its xlsx parts) - and
        # further corruption patterns could raise others we have not seen
        # yet. This is a bytes-are-unreadable failure, not an
        # unrecognised-layout one, so it must not be reported as the latter:
        # telling the owner to run fbr-dump and send a masked sample would
        # be the wrong advice for a file that is simply damaged.
        raise LayoutUnknown(
            f"this file could not be read as a {container} file ({exc}); it "
            "may be corrupt or only partially downloaded - try "
            "re-downloading it."
        ) from exc
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


def _accounts_named_in(haystack: str, registry: Registry) -> list[str]:
    """Every registry account whose IBAN, number or wallet appears in `haystack`."""
    hits: list[str] = []
    for account in registry.accounts:
        for identifier in (account.iban, account.account_number, account.wallet_number):
            if identifier and _squash(identifier) in haystack:
                hits.append(account.id)
                break
    return hits


def resolve_account(
    summary: DocumentSummary, text: str, registry: Registry
) -> str | None:
    """Link a statement to a registry account by IBAN, number or wallet.

    Spec §4.2: a statement is linked "by matching its **printed account
    identifier**". The printed identifier is therefore tried on its own
    first, and body text only when it names no account at all.

    Squashing the whole file - the printed identifier plus 30 rows of
    transaction descriptions - into one haystack and returning the first
    registry account found anywhere in it is how this used to work, and it
    misattributes a whole statement: a Meezan CSV printing the Meezan IBAN,
    with a description reading "Raast P2P Fund transfer to 0300 1234567",
    resolved to the WALLET that owns 03001234567 whenever that wallet was
    declared first in accounts.toml. Every Meezan transaction was then
    booked to the wallet, the wallet's 30 June balance became Meezan's, and
    meezan-main vanished from the Checks page with nothing warning about it.

    More than one match returns None rather than picking one. An unassigned
    file is reported to the owner and is recoverable on the Load page; a
    wrongly attributed one produces confident, wrong figures instead.

    Comparison ignores spacing and case, because statements print IBANs
    grouped in fours as often as not.
    """
    printed = _squash(summary.account_identifier or "")
    if printed:
        hits = _accounts_named_in(printed, registry)
        if len(hits) == 1:
            return hits[0]
        if hits:
            # The printed identifier is the authority, and it is ambiguous.
            # Reading on into the body text could only contradict it.
            return None

    body = _squash(text or "")
    if not body:
        return None
    hits = _accounts_named_in(body, registry)
    return hits[0] if len(hits) == 1 else None
