"""Wire ingest, parsing and reconciliation into one call.

The Streamlit pages hold no business logic: they call load_files and render
what comes back. That keeps every rule in this codebase testable without a
browser, and keeps the UI from quietly acquiring a rule of its own.

No file failure stops the run. Each file reports its own outcome, because a
statement that cannot be read is information the owner needs, not a crash.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fbr import paths
from fbr.config.loader import ProfileSet
from fbr.config.schema_taxyear import TaxYear
from fbr.engines.tabular import ParseError, ParseResult, parse_tabular, read_rows
from fbr.ingest import (
    LayoutAmbiguous,
    LayoutUnknown,
    detect_layout,
    resolve_account,
    sha256_of,
    sniff_container,
)
from fbr.model import Check, Registry
from fbr.reconcile import AccountLedger, merge_account

_STATEMENT_SUFFIXES = {".csv", ".xlsx", ".xls", ".pdf"}


@dataclass(frozen=True, slots=True)
class InputFile:
    name: str
    data: bytes
    account_id: str | None = None      # set by the owner when detection fails
    password: str | None = None        # held in memory only, never stored


@dataclass(frozen=True, slots=True)
class FileOutcome:
    name: str
    sha256: str
    status: str            # ok | unknown_layout | ambiguous_layout | unassigned
                           # | unreadable | duplicate | unsupported
    layout_id: str | None
    account_id: str | None
    message: str
    transactions_parsed: int


@dataclass(frozen=True, slots=True)
class RunResult:
    outcomes: tuple[FileOutcome, ...]
    ledgers: dict[str, AccountLedger] = field(default_factory=dict)
    account_status: dict[str, str] = field(default_factory=dict)
    all_checks: tuple[Check, ...] = ()
    unassigned: tuple[InputFile, ...] = ()
    # Registry accounts with statement_expected = true that produced no
    # ledger at all: the statement was forgotten, unreadable, or could not be
    # assigned. They carry `account_status = "missing"` and a
    # `statement_missing` check, because an account that simply vanishes from
    # the Checks page understates declared wealth with nothing to notice.
    missing_accounts: tuple[str, ...] = ()


def read_statement_dir(tax_year_name: str) -> list[InputFile]:
    """Read statements from the private folder. The Load page's default.

    Preferred over Streamlit's uploader, because Streamlit spools an upload
    over 1 MB to a temporary file of its own - outside ~/fbr-private, in the
    OS temp directory - and these files are already on disk where the owner
    deliberately put them.

    Spec §8.1 keeps upload as the alternative, so the Load page still offers
    it; the page states that cost where the owner chooses. Either way the
    bytes arrive here as an InputFile and nothing downstream can tell the
    two apart.
    """
    folder = paths.statements_dir(tax_year_name)
    if not folder.is_dir():
        return []
    return [
        InputFile(p.name, p.read_bytes())
        for p in sorted(folder.iterdir())
        if p.is_file() and p.suffix.lower() in _STATEMENT_SUFFIXES
    ]


def _parse_for(container: str):
    """Pick the engine for a container. Both return the same ParseResult."""
    if container == "pdf":
        from fbr.engines.pdf import parse_pdf

        def run(data, profile, *, sha256, filename, account_id, password=None):
            return parse_pdf(data, profile, sha256=sha256, filename=filename,
                             account_id=account_id, password=password)
        return run

    def run(data, profile, *, sha256, filename, account_id, password=None):
        return parse_tabular(data, profile, sha256=sha256, filename=filename,
                             account_id=account_id)
    return run


def _free_text(data: bytes, container: str, *, password: str | None = None) -> str:
    """Body text for `resolve_account` to search for a printed identifier.

    A PDF must go through the PDF text extractor. Running PDF bytes through
    `read_rows` - the CSV decoder - yielded the file's own binary preamble
    ("%PDF-1.3 ... ReportLab Generated PDF document"), so `resolve_account`
    searched that and matched nothing: a SadaPay PDF printing a registry
    account's IBAN resolved to `unassigned` while the identical CSV resolved
    `ok`. Every PDF wiring test passed `account_id` explicitly, which is why
    nothing caught it. The CSV/XLSX path is unchanged.
    """
    if container == "pdf":
        from fbr.engines.pdf import extract_text

        try:
            return extract_text(data, password=password)
        except ParseError:
            # A wrong password or an unreadable PDF. Detection and the parse
            # both report it per file with their own message; there is nothing
            # to add here, and the password must not reach one.
            return ""
    try:
        return "\n".join(",".join(r) for r in read_rows(data, container)[:30])
    except ParseError:
        return ""


def load_files(
    files: list[InputFile],
    *,
    registry: Registry,
    profiles: ProfileSet,
    tax_year: TaxYear,
    anchors: dict[str, int] | None = None,
    prior_year: dict[str, int] | None = None,
) -> RunResult:
    """Parse and reconcile a set of statement files."""
    outcomes: list[FileOutcome] = []
    unassigned: list[InputFile] = []
    by_account: dict[str, list[ParseResult]] = {}
    used_profiles: dict[str, object] = {}
    seen_hashes: set[str] = set()

    for item in files:
        digest = sha256_of(item.data)

        if digest in seen_hashes:
            outcomes.append(FileOutcome(
                item.name, digest, "duplicate", None, None,
                "identical to a file already loaded; ignored", 0,
            ))
            continue
        seen_hashes.add(digest)

        container = sniff_container(item.data)

        try:
            profile = detect_layout(item.data, profiles, container,
                                     password=item.password)
        except LayoutUnknown as exc:
            outcomes.append(FileOutcome(
                item.name, digest, "unknown_layout", None, None, str(exc), 0))
            continue
        except LayoutAmbiguous as exc:
            outcomes.append(FileOutcome(
                item.name, digest, "ambiguous_layout", None, None, str(exc), 0))
            continue
        except ParseError as exc:
            # A missing or wrong PDF password: reported per file, never with
            # the password itself.
            outcomes.append(FileOutcome(
                item.name, digest, "unreadable", None, None, str(exc), 0))
            continue

        account_id = item.account_id
        if account_id is not None and registry.by_id(account_id) is None:
            # An explicit override the owner picked (or a caller supplied)
            # that names no account in the registry must not be silently
            # treated as valid: parse_tabular would happily attach the
            # transactions to that id, report "ok", and merge_account's
            # `registry.by_id(account_id) is None` guard would then drop the
            # whole account with no outcome ever telling the owner why their
            # figures went missing. Route it through the same manual-
            # assignment path as an unresolved account instead.
            unassigned.append(item)
            outcomes.append(FileOutcome(
                item.name, digest, "unassigned", profile.id, None,
                f"{account_id!r} is not a known registry account id; it must "
                "match an account's `id` in accounts.toml", 0,
            ))
            continue

        if account_id is None:
            try:
                probe = _parse_for(container)(
                    item.data, profile, sha256=digest, filename=item.name,
                    account_id=None, password=item.password)
            except ParseError as exc:
                outcomes.append(FileOutcome(
                    item.name, digest, "unreadable", profile.id, None, str(exc), 0))
                continue
            account_id = resolve_account(
                probe.document.summary,
                _free_text(item.data, container, password=item.password),
                registry,
            )

        if account_id is None:
            unassigned.append(item)
            # The message names the ONE thing the owner can actually do. It used
            # to say "choose one on the Load page", and that page has no account
            # picker - only a warning pointing at accounts.toml. A message
            # naming a control that does not exist is worse than a blunt one.
            outcomes.append(FileOutcome(
                item.name, digest, "unassigned", profile.id, None,
                "no registry account matches this statement; add the IBAN, "
                "account number or wallet number it prints to that account in "
                "accounts.toml, then parse again", 0,
            ))
            continue

        try:
            result = _parse_for(container)(
                item.data, profile, sha256=digest, filename=item.name,
                account_id=account_id, password=item.password,
            )
        except ParseError as exc:
            # PdfPasswordError subclasses ParseError. Its message never contains
            # the password - asserted by a test in tests/test_pdf_engine.py.
            outcomes.append(FileOutcome(
                item.name, digest, "unreadable", profile.id, account_id, str(exc), 0))
            continue

        by_account.setdefault(account_id, []).append(result)
        used_profiles[profile.id] = profile
        outcomes.append(FileOutcome(
            item.name, digest, "ok", profile.id, account_id,
            f"parsed {len(result.transactions)} transaction(s)", len(result.transactions),
        ))

    ledgers: dict[str, AccountLedger] = {}
    status: dict[str, str] = {}
    checks: list[Check] = []

    for account_id, results in by_account.items():
        account = registry.by_id(account_id)
        if account is None:      # pragma: no cover - guarded above; every id here is valid
            continue
        ledger = merge_account(
            results, account, tax_year,
            profiles=used_profiles,  # type: ignore[arg-type]
            anchor=(anchors or {}).get(account_id),
            prior_year_closing=(prior_year or {}).get(account_id),
        )
        ledgers[account_id] = ledger
        status[account_id] = ledger.status
        checks.extend(ledger.checks)

    # An expected account that produced no ledger at all must be reported.
    # `ledgers` is built only from accounts that produced a parse, so an
    # account whose statement was forgotten, unreadable or unassigned showed
    # no row and no warning anywhere - it simply was not there, which
    # understates declared wealth in exactly the way nobody notices.
    missing: list[str] = []
    for account in registry.accounts:
        if not account.statement_expected or account.id in ledgers:
            continue
        if account.closed_on and account.closed_on < tax_year.period_start:
            continue      # closed before the year began; no statement is due
        if account.opened_on and account.opened_on > tax_year.period_end:
            continue      # not opened until after the year ended
        missing.append(account.id)
        status[account.id] = "missing"
        checks.append(Check(
            check_id="account:statement_missing",
            scope="account",
            kind="statement_missing",
            status="warn",
            expected=f"a {tax_year.name} statement for {account.id}",
            actual="none loaded",
            detail=(
                f"{account.id} ({account.institution}) is marked "
                "statement_expected in accounts.toml but no statement was "
                "loaded for it. Its balances and transactions are missing "
                "from this run entirely - add the file, or set "
                "statement_expected = false if none is due."
            ),
        ))

    return RunResult(
        outcomes=tuple(outcomes),
        ledgers=ledgers,
        account_status=status,
        all_checks=tuple(checks),
        unassigned=tuple(unassigned),
        missing_accounts=tuple(missing),
    )
