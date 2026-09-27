import re
from datetime import date

import pytest
from pydantic import ValidationError

from fbr.config.schema_profile import Profile
from fbr.config.schema_registry import RegistryFile
from fbr.config.schema_taxyear import TaxYear

MINIMAL_PROFILE = {
    "id": "meezan.csv.v1",
    "institution": "Meezan Bank Limited",
    "container": "csv",
    "valid_from": date(2025, 7, 1),
    "detect": {"header_contains": ["Booking Date", "Value Date"]},
    "columns": {
        "date": "Booking Date",
        "description": "Description",
        "debit": "Debit",
        "credit": "Credit",
        "balance": "Available Balance",
    },
    "formats": {"dates": ["%d %b %Y"], "sign": "columns"},
    "rows": {},
    "summary": {"opening": r"(?i)opening\s+balance\D+(?P<value>[\d,]+\.\d{2})"},
    "balance": {"semantics": "running", "kind": "available"},
    "selftest": {
        "cases": [
            {
                "row": {
                    "Booking Date": "01 Jul 2025",
                    "Description": "Opening top-up",
                    "Debit": "",
                    "Credit": "1,000.00",
                    "Available Balance": "1,000.00",
                },
                "expect_date": date(2025, 7, 1),
                "expect_amount": 100000,
            }
        ]
    },
}


def test_minimal_profile_validates():
    p = Profile.model_validate(MINIMAL_PROFILE)
    assert p.id == "meezan.csv.v1"
    assert p.formats.sign == "columns"
    assert p.columns.credit == "Credit"


def test_profile_rejects_unknown_keys():
    bad = {**MINIMAL_PROFILE, "header_contian": ["typo"]}
    with pytest.raises(ValidationError, match="header_contian"):
        Profile.model_validate(bad)


def test_profile_rejects_unknown_nested_keys():
    bad = {**MINIMAL_PROFILE, "formats": {**MINIMAL_PROFILE["formats"], "datez": ["%d"]}}
    with pytest.raises(ValidationError):
        Profile.model_validate(bad)


def test_sign_columns_requires_both_debit_and_credit_columns():
    bad = {**MINIMAL_PROFILE, "columns": {"date": "D", "description": "X", "debit": "Debit"}}
    with pytest.raises(ValidationError, match="debit.*credit|credit.*debit"):
        Profile.model_validate(bad)


def test_sign_signed_requires_a_single_amount_column():
    bad = {
        **MINIMAL_PROFILE,
        "formats": {"dates": ["%d %b %Y"], "sign": "signed"},
        "columns": {"date": "D", "description": "X", "debit": "Debit", "credit": "Credit"},
    }
    with pytest.raises(ValidationError, match="amount"):
        Profile.model_validate(bad)


def test_sign_suffix_requires_tokens():
    bad = {
        **MINIMAL_PROFILE,
        "formats": {"dates": ["%d %b %Y"], "sign": "suffix"},
        "columns": {"date": "D", "description": "X", "amount": "Amount"},
    }
    with pytest.raises(ValidationError, match="debit_tokens|credit_tokens"):
        Profile.model_validate(bad)


def test_summary_patterns_compile_and_expose_a_value_group():
    bad = {**MINIMAL_PROFILE, "summary": {"opening": r"(?i)opening\s+balance"}}
    with pytest.raises(ValidationError, match="value"):
        Profile.model_validate(bad)


def test_invalid_regex_is_rejected_at_load_time():
    bad = {**MINIMAL_PROFILE, "summary": {"opening": r"(?P<value>[unclosed"}}
    with pytest.raises(ValidationError):
        Profile.model_validate(bad)


def test_date_formats_must_include_a_year():
    # %d %b without %Y is deprecated in Python and would silently pick 1900.
    bad = {**MINIMAL_PROFILE, "formats": {"dates": ["%d %b"], "sign": "columns"}}
    with pytest.raises(ValidationError, match="year"):
        Profile.model_validate(bad)


def test_profile_must_have_at_least_one_selftest_case():
    bad = {**MINIMAL_PROFILE, "selftest": {"cases": []}}
    with pytest.raises(ValidationError, match="at least one"):
        Profile.model_validate(bad)


def test_compiled_patterns_are_python_re():
    p = Profile.model_validate(MINIMAL_PROFILE)
    assert isinstance(p.summary.compiled()["opening"], re.Pattern)


REGISTRY = {
    "owner": {"name": "OWNER NAME"},
    "account": [
        {
            "id": "meezan-main",
            "institution": "Meezan Bank Limited",
            "kind": "bank",
            "iban": "PK00TEST0000000000000000",
            "title": "ACCOUNT TITLE",
            "type": "Saving",
            "ownership": "Self",
            "currency": "PKR",
            "statement_expected": True,
            "match_hints": ["MEEZAN"],
        }
    ],
}


def test_registry_validates_and_converts_to_model():
    reg = RegistryFile.model_validate(REGISTRY).to_model()
    assert reg.owner.name == "OWNER NAME"
    assert reg.accounts[0].id == "meezan-main"
    assert reg.accounts[0].account_number == ""     # optional fields default to empty


def test_registry_rejects_duplicate_account_ids():
    bad = {**REGISTRY, "account": [REGISTRY["account"][0], REGISTRY["account"][0]]}
    with pytest.raises(ValidationError, match="duplicate"):
        RegistryFile.model_validate(bad)


def test_registry_rejects_an_account_with_no_identifier():
    acct = {k: v for k, v in REGISTRY["account"][0].items() if k != "iban"}
    with pytest.raises(ValidationError, match="identifier"):
        RegistryFile.model_validate({**REGISTRY, "account": [acct]})


TAXYEAR = {
    "name": "TY2026",
    "period_start": date(2025, 7, 1),
    "period_end": date(2026, 6, 30),
    "atl": True,
    "codes": {
        "export_receipts": {
            "code": "64060285",
            "label": "Export of services u/s 154A @1%",
            "tab": "Business / Final Tax",
            "columns": {"1": "Receipts", "2": "Tax deducted"},
            "source": "SRO 1495(I)/2026 p.15",
            "verification": "form_scan",
        },
        "wealth_bank_accounts": {
            "code": "",
            "label": "Bank Account(s)",
            "tab": "Wealth Statement",
            "columns": {},
            "source": "SRO 1495(I)/2026 p.38 (illegible)",
            "verification": "unknown",
        },
    },
    "thresholds": {
        "profit_final_regime_max": 500000000,
        "s111_4_cap": 500000000,
        "review_threshold": 1000000,
        "wht_ratio_tolerance_pp": 1.0,
        "profit_wht_window_days": 1,
        "tax154a_window_days": 1,
        "tax154a_amount_tolerance": 100,
        "transfer_window_days": 3,
        "transfer_fee_tolerance": 10000,
        "reversal_window_days": 30,
    },
    "rates": {"s151_atl": 0.20, "s151_non_atl": 0.40, "s7b": 0.20,
              "s236y_atl": 0.05, "s236y_non_atl": 0.10,
              "s231ab_non_atl": 0.008, "s154a": 0.01, "s154a_pseb": 0.0025},
    "templates": {
        "wealth_line": "{iban} - {title} - {institution_upper} - {ownership}",
        "profit_line": "Profit on Debt u/s 151(1)(b) from Bank Accounts/Deposits - "
                       "Profit on Savings Account - Investment in {institution}",
    },
}


def test_taxyear_validates():
    ty = TaxYear.model_validate(TAXYEAR)
    assert ty.codes["export_receipts"].code == "64060285"
    assert ty.thresholds.review_threshold == 1000000       # Rs 10,000 in paisa


def test_taxyear_allows_a_blank_code_only_when_unknown():
    bad = {**TAXYEAR}
    bad["codes"] = {
        **TAXYEAR["codes"],
        "wealth_bank_accounts": {
            **TAXYEAR["codes"]["wealth_bank_accounts"], "verification": "iris_verified"
        },
    }
    with pytest.raises(ValidationError, match="blank code"):
        TaxYear.model_validate(bad)


def test_taxyear_rejects_an_unknown_verification_state():
    bad = {**TAXYEAR}
    bad["codes"] = {
        **TAXYEAR["codes"],
        "export_receipts": {**TAXYEAR["codes"]["export_receipts"], "verification": "probably"},
    }
    with pytest.raises(ValidationError):
        TaxYear.model_validate(bad)


def test_taxyear_period_must_be_july_to_june():
    bad = {**TAXYEAR, "period_start": date(2025, 8, 1)}
    with pytest.raises(ValidationError, match="1 July"):
        TaxYear.model_validate(bad)
