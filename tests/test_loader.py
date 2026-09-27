from pathlib import Path

import pytest

from fbr.config.loader import ConfigError, load_profiles, load_registry, load_tax_year

PROFILE_TOML = """
id          = "meezan.csv.v1"
institution = "Meezan Bank Limited"
container   = "csv"
valid_from  = 2025-07-01

[detect]
header_contains = ["Booking Date", "Value Date"]

[columns]
date        = "Booking Date"
description = "Description"
debit       = "Debit"
credit      = "Credit"
balance     = "Available Balance"

[formats]
dates = ["%d %b %Y"]
sign  = "columns"

[balance]
semantics = "running"
kind      = "available"

[[selftest.cases]]
row = { "Booking Date" = "01 Jul 2025", "Description" = "Top-up", "Debit" = "", "Credit" = "1,000.00", "Available Balance" = "1,000.00" }
expect_date   = 2025-07-01
expect_amount = 100000
"""


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text)
    return p


def test_loads_a_directory_of_profiles(tmp_path):
    _write(tmp_path, "meezan.toml", PROFILE_TOML)
    ps = load_profiles(tmp_path)
    assert [p.id for p in ps.profiles] == ["meezan.csv.v1"]
    assert ps.by_id("meezan.csv.v1").institution == "Meezan Bank Limited"


def test_for_container_filters(tmp_path):
    _write(tmp_path, "meezan.toml", PROFILE_TOML)
    ps = load_profiles(tmp_path)
    assert len(ps.for_container("csv")) == 1
    assert ps.for_container("pdf") == ()


def test_duplicate_ids_across_files_are_rejected(tmp_path):
    # Review Focus #3: silent first-wins would attach a wrong layout to a
    # real statement.
    _write(tmp_path, "a.toml", PROFILE_TOML)
    _write(tmp_path, "b.toml", PROFILE_TOML)
    with pytest.raises(ConfigError, match="duplicate profile id"):
        load_profiles(tmp_path)


def test_an_invalid_profile_names_its_file(tmp_path):
    _write(tmp_path, "broken.toml", PROFILE_TOML.replace("sign  = \"columns\"", "sign  = \"nope\""))
    with pytest.raises(ConfigError, match="broken.toml"):
        load_profiles(tmp_path)


def test_malformed_toml_names_its_file(tmp_path):
    _write(tmp_path, "bad.toml", "id = [unclosed")
    with pytest.raises(ConfigError, match="bad.toml"):
        load_profiles(tmp_path)


def test_missing_directory_is_an_error(tmp_path):
    with pytest.raises(ConfigError, match="no profile directory"):
        load_profiles(tmp_path / "nope")


def test_empty_directory_is_an_error(tmp_path):
    with pytest.raises(ConfigError, match="no profiles"):
        load_profiles(tmp_path)


REGISTRY_TOML = """
[owner]
name = "OWNER NAME"

[[account]]
id                 = "meezan-main"
institution        = "Meezan Bank Limited"
kind               = "bank"
iban               = "PK00TEST0000000000000000"
title              = "ACCOUNT TITLE"
type               = "Saving"
statement_expected = true
match_hints        = ["MEEZAN"]
"""


def test_loads_the_registry(tmp_path):
    p = _write(tmp_path, "accounts.toml", REGISTRY_TOML)
    reg = load_registry(p)
    assert reg.owner.name == "OWNER NAME"
    assert reg.by_id("meezan-main").kind == "bank"


def test_missing_registry_explains_how_to_create_it(tmp_path):
    with pytest.raises(ConfigError, match="accounts.toml"):
        load_registry(tmp_path / "accounts.toml")


TAXYEAR_TOML = """
name         = "TY2026"
period_start = 2025-07-01
period_end   = 2026-06-30
atl          = true

[codes.export_receipts]
code         = "64060285"
label        = "Export of services u/s 154A @1%"
tab          = "Business / Final Tax"
source       = "SRO 1495(I)/2026 p.15"
verification = "form_scan"
columns      = { "1" = "Receipts", "2" = "Tax deducted" }

[thresholds]
profit_final_regime_max  = 500000000
s111_4_cap               = 500000000
review_threshold         = 1000000
wht_ratio_tolerance_pp   = 1.0
profit_wht_window_days   = 1
tax154a_window_days      = 1
tax154a_amount_tolerance = 100
transfer_window_days     = 3
transfer_fee_tolerance   = 10000
reversal_window_days     = 30

[rates]
s151_atl = 0.20
s151_non_atl = 0.40
s7b = 0.20
s236y_atl = 0.05
s236y_non_atl = 0.10
s231ab_non_atl = 0.008
s154a = 0.01
s154a_pseb = 0.0025

[templates]
wealth_line = "{iban} - {title} - {institution_upper} - {ownership}"
profit_line = "Profit on Debt u/s 151(1)(b) from Bank Accounts/Deposits - Profit on Savings Account - Investment in {institution}"
"""


def test_loads_a_tax_year(tmp_path):
    _write(tmp_path, "TY2026.toml", TAXYEAR_TOML)
    ty = load_tax_year("TY2026", tmp_path)
    assert ty.codes["export_receipts"].code == "64060285"
    assert ty.thresholds.review_threshold == 1000000


def test_unknown_tax_year_lists_what_is_available(tmp_path):
    _write(tmp_path, "TY2026.toml", TAXYEAR_TOML)
    with pytest.raises(ConfigError, match="TY2026"):
        load_tax_year("TY2030", tmp_path)
