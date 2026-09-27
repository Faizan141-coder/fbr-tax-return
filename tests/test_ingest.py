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
            iban="PK00TEST0000000000000000", account_number="0000000000",
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
    s = DocumentSummary(account_identifier="PK00TEST0000000000000000")
    assert resolve_account(s, "", REGISTRY) == "meezan-main"


def test_resolves_by_account_number_inside_free_text():
    assert resolve_account(DocumentSummary(), "Account No 0000000000", REGISTRY) == "meezan-main"


def test_resolves_by_wallet_number():
    assert resolve_account(DocumentSummary(), "Wallet 03001234567", REGISTRY) == "sadapay"


def test_iban_match_ignores_spacing_and_case():
    s = DocumentSummary(account_identifier="pk00 test 0000 0000 0000 0000")
    assert resolve_account(s, "", REGISTRY) == "meezan-main"


def test_returns_none_when_nothing_matches():
    assert resolve_account(DocumentSummary(), "no identifiers here", REGISTRY) is None


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
