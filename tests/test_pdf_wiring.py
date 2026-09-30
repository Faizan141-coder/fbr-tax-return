# tests/test_pdf_wiring.py
"""PDFs through the real seams: detection, the pipeline, dumps, self-tests."""
from datetime import date
from pathlib import Path

import pytest

from fbr.config.loader import ProfileSet, ProfileStatus, load_profiles, run_selftest
from fbr.config.schema_profile import Profile
from fbr.engines.pdf import PdfPasswordError
from fbr.engines.tabular import parse_row
from fbr.ingest import detect_layout, sniff_container, usable_profiles
from fbr.model import Account, Owner, Registry
from fbr.pipeline import InputFile, load_files
from tests.fixtures.synth import build_statement
from tests.fixtures.synth_pdf import encrypt_pdf, write_sadapay_pdf
from tests.test_loader import TAXYEAR_TOML

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def shipped():
    return load_profiles(ROOT / "profiles")


@pytest.fixture
def ty(tmp_path):
    from fbr.config.loader import load_tax_year
    (tmp_path / "TY2026.toml").write_text(TAXYEAR_TOML)
    return load_tax_year("TY2026", tmp_path)


@pytest.fixture
def registry():
    return Registry(
        owner=Owner(name="OWNER NAME"),
        accounts=(Account(
            id="sadapay", institution="SadaPay", kind="wallet", iban="",
            account_number="", wallet_number="03001234567", title="ACCOUNT TITLE",
            type="", ownership="Self", currency="PKR", statement_expected=True,
            match_hints=("SADA",)),),
    )


def test_a_pdf_is_sniffed_as_pdf():
    assert sniff_container(write_sadapay_pdf(build_statement(seed=31))) == "pdf"


def test_the_shipped_sadapay_profile_is_detected(shipped):
    data = write_sadapay_pdf(build_statement(seed=32))
    assert detect_layout(data, shipped, "pdf").id == "sadapay.pdf.v1"


def test_no_two_shipped_profiles_match_the_same_pdf(shipped):
    detect_layout(write_sadapay_pdf(build_statement(seed=33)), shipped, "pdf")


def test_every_shipped_pdf_profile_passes_its_selftest(shipped):
    for profile in shipped.for_container("pdf"):
        status = run_selftest(profile, parse_row,
                              summary_text=profile.selftest.summary_sample or None)
        assert status.ok, f"{profile.id}: {status.message}"


def test_usable_profiles_covers_pdf(shipped):
    usable, report = usable_profiles(shipped, "pdf")
    assert [p.id for p in usable] == ["sadapay.pdf.v1"]
    assert all(s.ok for s in report)


def test_the_pipeline_parses_a_pdf_end_to_end(shipped, registry, ty):
    stmt = build_statement(seed=34, start=date(2025, 7, 1), end=date(2026, 6, 30),
                           account_id="PK00TEST0000000000000000")
    run = load_files([InputFile("sada.pdf", write_sadapay_pdf(stmt),
                                account_id="sadapay")],
                     registry=registry, profiles=shipped, tax_year=ty,
                     anchors={"sadapay": 500000})
    assert run.outcomes[0].status == "ok", run.outcomes[0].message
    assert run.outcomes[0].layout_id == "sadapay.pdf.v1"
    assert len(run.ledgers["sadapay"].transactions) == len(stmt.txns)


def test_a_pdf_is_no_longer_reported_unsupported(shipped, registry, ty):
    run = load_files([InputFile("sada.pdf", write_sadapay_pdf(build_statement(seed=35)),
                                account_id="sadapay")],
                     registry=registry, profiles=shipped, tax_year=ty)
    assert run.outcomes[0].status != "unsupported"


def test_an_encrypted_pdf_parses_when_the_password_is_supplied(shipped, registry, ty):
    stmt = build_statement(seed=36, start=date(2025, 7, 1), end=date(2026, 6, 30))
    data = encrypt_pdf(write_sadapay_pdf(stmt), "s3cret")
    run = load_files([InputFile("sada.pdf", data, account_id="sadapay",
                                password="s3cret")],
                     registry=registry, profiles=shipped, tax_year=ty,
                     anchors={"sadapay": 0})
    assert run.outcomes[0].status == "ok", run.outcomes[0].message


def test_a_wrong_password_is_reported_per_file_without_leaking_it(shipped, registry, ty):
    data = encrypt_pdf(write_sadapay_pdf(build_statement(seed=37)), "s3cret")
    run = load_files([InputFile("sada.pdf", data, account_id="sadapay",
                                password="nope-1234")],
                     registry=registry, profiles=shipped, tax_year=ty)
    outcome = run.outcomes[0]
    assert outcome.status in ("unreadable", "password_required")
    assert "nope-1234" not in outcome.message and "s3cret" not in outcome.message
    assert "password" in outcome.message.lower()


def test_one_bad_pdf_does_not_stop_a_good_one(shipped, registry, ty):
    good = write_sadapay_pdf(build_statement(seed=38, start=date(2025, 7, 1),
                                             end=date(2026, 6, 30)))
    run = load_files(
        [InputFile("bad.pdf", b"%PDF-1.4\nnot really a pdf\n", account_id="sadapay"),
         InputFile("good.pdf", good, account_id="sadapay")],
        registry=registry, profiles=shipped, tax_year=ty, anchors={"sadapay": 0},
    )
    assert {o.status for o in run.outcomes} >= {"ok"}
    assert len(run.outcomes) == 2


# --- the self-test gap that let a real bug ship -----------------------------

_BROKEN_SUMMARY = {
    "id": "broken.pdf.v1", "institution": "Test", "container": "pdf",
    "valid_from": date(2025, 7, 1),
    "detect": {"header_contains": ["Date", "Description", "Debit/Credit"]},
    "columns": {"date": "Date", "description": "Description", "amount": "Debit/Credit"},
    "formats": {"dates": ["%d %b, %Y"], "sign": "signed"},
    # Doubled backslashes in a TOML literal string is exactly the shipped bug:
    # `\\s` matches a literal backslash then s, so this never matches.
    "summary": {"total_credit": r"(?i)Total\\s+credit[^\\d\\n]+?(?P<value>-?[\d,]+\.\d{2})"},
    "balance": {"semantics": "none"},
    "selftest": {
        "cases": [{"row": {"Date": "01 Jul, 2025", "Description": "x",
                           "Debit/Credit": "+1,000.00"},
                   "expect_date": date(2025, 7, 1), "expect_amount": 100000}],
        "summary_sample": "Total credit  1,234.56",
    },
}


def test_selftest_exercises_summary_patterns():
    # Review Focus #5: parse_row alone cannot catch a dead summary pattern.
    profile = Profile.model_validate(_BROKEN_SUMMARY)
    status = run_selftest(profile, parse_row,
                          summary_text=profile.selftest.summary_sample)
    assert not status.ok
    assert "total_credit" in status.message
    assert "summary" in status.message.lower()


def test_a_correct_summary_pattern_passes_the_selftest():
    good = dict(_BROKEN_SUMMARY)
    good["summary"] = {
        "total_credit": r"(?i)Total\s+credit[^\d\n]+?(?P<value>-?[\d,]+\.\d{2})"
    }
    profile = Profile.model_validate(good)
    status = run_selftest(profile, parse_row,
                          summary_text=profile.selftest.summary_sample)
    assert status.ok, status.message


def test_selftest_without_a_summary_sample_still_passes():
    # Profiles that predate summary_sample must keep loading.
    no_sample = dict(_BROKEN_SUMMARY)
    no_sample["selftest"] = {"cases": _BROKEN_SUMMARY["selftest"]["cases"]}
    profile = Profile.model_validate(no_sample)
    assert run_selftest(profile, parse_row).ok


def test_every_shipped_profile_declares_a_summary_sample(shipped):
    # Without one, a dead summary pattern ships unnoticed - which happened.
    missing = [p.id for p in shipped.profiles
               if p.summary.compiled() and not p.selftest.summary_sample]
    assert missing == [], f"profiles with summary patterns but no sample: {missing}"
