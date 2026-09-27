from datetime import date

import pytest

from fbr.config.loader import ProfileSet, ProfileStatus
from fbr.config.schema_profile import Profile
from fbr.ingest import (
    LayoutAmbiguous,
    LayoutUnknown,
    detect_layout,
    resolve_account,
    sha256_of,
    sniff_container,
    usable_profiles,
)
from fbr.model import Account, DocumentSummary, Owner, Registry
from tests.fixtures.synth import build_statement, write_meezan_csv, write_mcb_csv, write_xlsx
from tests.test_tabular import MCB, MEEZAN


def _set(*profiles: Profile) -> ProfileSet:
    return ProfileSet(
        profiles,
        tuple(ProfileStatus(p.id, f"{p.id}.toml", True, "loaded") for p in profiles),
    )


def test_sniffs_csv_xlsx_and_pdf_from_bytes():
    stmt = build_statement(seed=21)
    assert sniff_container(write_meezan_csv(stmt), "x.csv") == "csv"
    assert sniff_container(write_xlsx(stmt), "x.xlsx") == "xlsx"
    assert sniff_container(b"%PDF-1.7\n...", "x.pdf") == "pdf"


def test_sniffing_ignores_a_misleading_extension():
    stmt = build_statement(seed=22)
    # A bank emailing XLSX bytes named .csv must not crash the CSV reader.
    assert sniff_container(write_xlsx(stmt), "statement.csv") == "xlsx"


def test_detects_the_matching_layout():
    stmt = build_statement(seed=23)
    got = detect_layout(write_meezan_csv(stmt), _set(MEEZAN, MCB), "csv")
    assert got.id == "meezan.csv.v1"


def test_unknown_layout_raises_with_guidance():
    with pytest.raises(LayoutUnknown, match="fbr-dump"):
        detect_layout(b"a,b\n1,2\n", _set(MEEZAN, MCB), "csv")


def test_unreadable_file_is_reported_distinctly_from_unknown_layout():
    # Fix round 1: xlsx-magic bytes that are not a valid zip at all (a
    # corrupt or partially-downloaded file) must not be reported the same
    # way as a file that reads fine but matches no profile - "run fbr-dump
    # and send a masked sample" is the wrong advice when the bytes are
    # simply unreadable.
    garbage = b"PK\x03\x04" + b"not actually a zip file" * 5
    with pytest.raises(LayoutUnknown, match="could not be read") as exc_info:
        detect_layout(garbage, _set(MEEZAN, MCB), "xlsx")
    assert "fbr-dump" not in str(exc_info.value)


def test_unknown_layout_message_is_not_the_unreadable_file_message():
    # The reverse of the case above: a well-formed file that simply matches
    # no profile must keep the original guidance, so the two messages can
    # never silently collapse into one.
    with pytest.raises(LayoutUnknown, match="fbr-dump") as exc_info:
        detect_layout(b"a,b\n1,2\n", _set(MEEZAN, MCB), "csv")
    assert "could not be read" not in str(exc_info.value)


def test_two_matching_profiles_raise_rather_than_guess():
    # Review Focus #3: picking one silently would attach a wrong layout.
    twin = MEEZAN.model_copy(update={"id": "meezan.csv.v2"})
    stmt = build_statement(seed=24)
    with pytest.raises(LayoutAmbiguous, match="meezan.csv.v1.*meezan.csv.v2"):
        detect_layout(write_meezan_csv(stmt), _set(MEEZAN, twin), "csv")


def test_valid_from_narrows_candidates():
    future = MEEZAN.model_copy(update={"id": "meezan.csv.v2", "valid_from": date(2030, 7, 1)})
    stmt = build_statement(seed=25)
    got = detect_layout(write_meezan_csv(stmt), _set(MEEZAN, future), "csv", on=date(2026, 1, 1))
    assert got.id == "meezan.csv.v1"


def test_only_profiles_for_the_container_are_considered():
    pdf_profile = MEEZAN.model_copy(update={"id": "meezan.pdf.v1", "container": "pdf"})
    stmt = build_statement(seed=26)
    got = detect_layout(write_meezan_csv(stmt), _set(pdf_profile, MEEZAN), "csv")
    assert got.id == "meezan.csv.v1"


REGISTRY = Registry(
    owner=Owner(name="OWNER NAME"),
    accounts=(
        Account(
            id="meezan-main", institution="Meezan Bank Limited", kind="bank",
            # The account number is deliberately NOT a substring of the IBAN.
            # It used to be "0000000000", which the IBAN below contains
            # verbatim, so test_resolves_an_account_by_iban could not tell an
            # IBAN match from an account-number match - it would have passed
            # either way and proved neither.
            iban="PK00TEST0000000000000000", account_number="1122334455",
            wallet_number="", title="ACCOUNT TITLE", type="Saving", ownership="Self",
            currency="PKR", statement_expected=True, match_hints=("MEEZAN",),
        ),
        Account(
            id="sadapay", institution="SadaPay", kind="wallet", iban="",
            account_number="", wallet_number="03001234567", title="ACCOUNT TITLE",
            type="", ownership="Self", currency="PKR", statement_expected=True,
            match_hints=("SADA",),
        ),
    ),
)


def test_resolves_an_account_by_iban():
    account = REGISTRY.by_id("meezan-main")
    # Pin what makes this test meaningful: if the account number were a
    # substring of the IBAN, the account-number branch alone could satisfy
    # the assertion below and the IBAN branch could be broken unnoticed.
    assert account.account_number not in account.iban
    s = DocumentSummary(account_identifier=account.iban)
    assert resolve_account(s, "", REGISTRY) == "meezan-main"


def test_resolves_by_account_number_inside_free_text():
    account = REGISTRY.by_id("meezan-main")
    text = f"Account No {account.account_number}"
    assert account.iban not in text        # the IBAN branch cannot be what matched
    assert resolve_account(DocumentSummary(), text, REGISTRY) == "meezan-main"


def test_resolves_by_wallet_number():
    assert resolve_account(DocumentSummary(), "Wallet 03001234567", REGISTRY) == "sadapay"


def test_iban_match_ignores_spacing_and_case():
    s = DocumentSummary(account_identifier="pk00 test 0000 0000 0000 0000")
    assert resolve_account(s, "", REGISTRY) == "meezan-main"


def test_returns_none_when_nothing_matches():
    assert resolve_account(DocumentSummary(), "no identifiers here", REGISTRY) is None


# --- spec §4.2: the PRINTED account identifier is what links a statement ----
#
# The registry below declares the wallet FIRST, which is what made the old
# "squash everything into one haystack, return the first account found"
# implementation misattribute a whole bank statement to a wallet.

WALLET_FIRST = Registry(
    owner=Owner(name="OWNER NAME"),
    accounts=(
        Account(
            id="nayapay", institution="NayaPay", kind="wallet", iban="",
            account_number="", wallet_number="03001234567", title="ACCOUNT TITLE",
            type="", ownership="Self", currency="PKR", statement_expected=True,
        ),
        Account(
            id="meezan-main", institution="Meezan Bank Limited", kind="bank",
            iban="PK00TEST0000000000000000", account_number="1122334455",
            wallet_number="", title="ACCOUNT TITLE", type="Saving", ownership="Self",
            currency="PKR", statement_expected=True,
        ),
    ),
)


def test_a_unique_printed_identifier_resolves_the_account():
    s = DocumentSummary(account_identifier="PK00TEST0000000000000000")
    assert resolve_account(s, "", WALLET_FIRST) == "meezan-main"


def test_body_text_naming_another_account_never_overrides_the_printed_one():
    # The exact reproduction: a Meezan statement whose printed identifier is
    # the Meezan IBAN, and whose description happens to name a wallet number
    # that belongs to a DIFFERENT registry account, declared first. Before
    # the fix this returned "nayapay" and every Meezan row was booked to the
    # wallet.
    s = DocumentSummary(account_identifier="PK00TEST0000000000000000")
    body = "01 Jul 2025,Raast P2P Fund transfer to 0300 1234567,5,000.00"
    assert resolve_account(s, body, WALLET_FIRST) == "meezan-main"


def test_two_accounts_matching_resolve_to_none_rather_than_guessing():
    # An unassigned file is reported to the owner and recoverable on the Load
    # page; a wrongly attributed one silently produces wrong figures.
    twins = Registry(
        owner=Owner(name="OWNER NAME"),
        accounts=(
            Account(id="joint-a", institution="Bank", kind="bank",
                    iban="PK00TEST0000000000000000", account_number="", wallet_number="",
                    title="T", type="Saving", ownership="Self", currency="PKR",
                    statement_expected=True),
            Account(id="joint-b", institution="Bank", kind="bank",
                    iban="PK00TEST0000000000000000", account_number="", wallet_number="",
                    title="T", type="Current", ownership="50%", currency="PKR",
                    statement_expected=True),
        ),
    )
    s = DocumentSummary(account_identifier="PK00TEST0000000000000000")
    assert resolve_account(s, "", twins) is None


def test_two_accounts_named_only_in_body_text_also_resolve_to_none():
    # Same rule on the fallback path: with no printed identifier, body text
    # naming two different registry accounts is not evidence for either.
    body = ("PK00TEST0000000000000000,ACCOUNT TITLE\n"
            "01 Jul 2025,Raast P2P Fund transfer to 0300 1234567,5,000.00")
    assert resolve_account(DocumentSummary(), body, WALLET_FIRST) is None


def test_body_text_is_used_only_when_the_printed_identifier_matches_nothing():
    # A printed identifier that names no registry account at all must not
    # block the fallback - that is the ordinary case for a layout whose
    # profile has no [summary] account_id pattern yet.
    s = DocumentSummary(account_identifier="PK00TEST9999999999999999")
    assert resolve_account(s, "Account No 1122334455", WALLET_FIRST) == "meezan-main"


def test_sha256_is_stable():
    assert sha256_of(b"abc") == sha256_of(b"abc")
    assert len(sha256_of(b"abc")) == 64


def test_usable_profiles_drops_one_whose_selftest_fails():
    broken = MEEZAN.model_copy(update={
        "id": "broken.csv.v1",
        "selftest": MEEZAN.selftest.model_copy(update={
            "cases": [MEEZAN.selftest.cases[0].model_copy(update={"expect_amount": 999})]
        }),
    })
    usable, report = usable_profiles(_set(MEEZAN, broken), "csv")
    assert [p.id for p in usable] == ["meezan.csv.v1"]
    assert any(not s.ok and s.profile_id == "broken.csv.v1" for s in report)


def test_a_failing_profile_cannot_be_detected():
    broken = MEEZAN.model_copy(update={
        "id": "broken.csv.v1",
        "selftest": MEEZAN.selftest.model_copy(update={
            "cases": [MEEZAN.selftest.cases[0].model_copy(update={"expect_amount": 999})]
        }),
    })
    stmt = build_statement(seed=27)
    # Both would match by header; only the healthy one is a candidate.
    got = detect_layout(write_meezan_csv(stmt), _set(MEEZAN, broken), "csv")
    assert got.id == "meezan.csv.v1"
