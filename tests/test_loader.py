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


# --------------------------------------------------------------------------
# selftest.summary_expect: a summary pattern must capture the RIGHT figure.
#
# run_selftest used to test `pattern.search()` truthiness only, so a pattern
# aimed one line off matched happily and passed. All six shipped profiles
# accepted `opening` reading the closing balance - Rs 25,935.59 in place of
# Rs 5,000.00, a Rs 20,935.59 error - with ok=True. "Never matches" was caught;
# "captures the wrong figure" is the one that puts a wrong number on a return.
# --------------------------------------------------------------------------

EXPECT_TOML = """
id          = "expect.csv.v1"
institution = "Test Bank"
container   = "csv"
valid_from  = 2025-07-01

[detect]
header_contains = ["Date"]

[columns]
date        = "Date"
description = "Description"
amount      = "Amount"

[formats]
dates = ["%d %b %Y"]
sign  = "signed"

[summary]
opening     = '(?i)Opening\\s+Balance[^\\d\\n]+?(?P<value>-?[\\d,]+\\.\\d{2})'
closing     = '(?i)Closing\\s+Balance[^\\d\\n]+?(?P<value>-?[\\d,]+\\.\\d{2})'
period_from = '(?i)Statement\\s+Period[^\\d\\n]+?(?P<value>\\d{2} \\w{3} \\d{4})'

[[selftest.cases]]
row = { "Date" = "01 Jul 2025", "Description" = "Top-up", "Amount" = "+1,000.00" }
expect_date   = 2025-07-01
expect_amount = 100000

[selftest]
summary_sample = '''
Opening Balance,5,000.00
Closing Balance,25,935.59
Statement Period,01 Jul 2025 to 23 Aug 2025
'''

[selftest.summary_expect]
opening     = 500000
closing     = 2593559
period_from = "2025-07-01"
"""


def _expect_profile(**overrides):
    """Load EXPECT_TOML, optionally replacing whole lines by key = value text."""
    import tomllib

    from fbr.config.schema_profile import Profile

    data = tomllib.loads(EXPECT_TOML)
    for dotted, value in overrides.items():
        target = data
        *path, leaf = dotted.split("__")
        for step in path:
            target = target[step]
        if value is _DELETE:
            target.pop(leaf, None)
        else:
            target[leaf] = value
    return Profile.model_validate(data)


_DELETE = object()


def _selftest(profile):
    from fbr.config.loader import run_selftest
    from fbr.engines.tabular import parse_row

    return run_selftest(profile, parse_row,
                        summary_text=profile.selftest.summary_sample)


def test_the_shipped_expectations_pass():
    status = _selftest(_expect_profile())
    assert status.ok, status.message
    assert "expected capture(s)" in status.message


def test_a_pattern_that_captures_the_wrong_money_fails_the_selftest():
    # `opening` aimed at the Closing Balance line. It still MATCHES, so the
    # dead-pattern check is happy; only the expected value catches it.
    profile = _expect_profile(
        summary__opening=r'(?i)Closing\s+Balance[^\d\n]+?(?P<value>-?[\d,]+\.\d{2})'
    )
    status = _selftest(profile)
    assert not status.ok
    assert "opening" in status.message
    assert "25,935.59" in status.message      # what it wrongly read
    assert "500000" in status.message         # what it must read, in paisa


def test_a_pattern_that_captures_the_wrong_date_fails_the_selftest():
    profile = _expect_profile(
        selftest__summary_expect__period_from="2025-08-23"   # the period END
    )
    status = _selftest(profile)
    assert not status.ok
    assert "period_from" in status.message
    assert "2025-07-01" in status.message


def test_expectations_are_compared_as_integer_paisa_not_text():
    # Exact integer comparison, no tolerance: one paisa out must fail.
    status = _selftest(_expect_profile(selftest__summary_expect__opening=500001))
    assert not status.ok
    assert "500001" in status.message


def test_money_expectations_must_be_integer_paisa():
    from pydantic import ValidationError

    for bad in ("5,000.00", 5000.0, "500000"):
        with pytest.raises(ValidationError) as exc:
            _expect_profile(selftest__summary_expect__opening=bad)
        assert "integer" in str(exc.value)


def test_a_period_expectation_must_be_an_iso_date():
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as exc:
        _expect_profile(selftest__summary_expect__period_from="01 Jul 2025")
    assert "ISO date" in str(exc.value)


def test_an_expectation_for_an_undeclared_pattern_is_rejected_at_load():
    # An expectation on a pattern the profile does not declare would never run.
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as exc:
        _expect_profile(selftest__summary_expect__total_credit=1)
    assert "declares no [summary] pattern" in str(exc.value)


def test_an_unknown_expectation_role_is_rejected_at_load():
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as exc:
        _expect_profile(selftest__summary_expect__opening_balance=1)
    assert "not a summary pattern" in str(exc.value)


def test_summary_expect_is_optional():
    # A profile without it must still load and still pass, so the mechanism
    # cannot break a profile that predates it.
    status = _selftest(_expect_profile(selftest__summary_expect=_DELETE))
    assert status.ok, status.message
    assert "expected capture" not in status.message


def test_every_shipped_profile_pins_every_summary_pattern_it_declares():
    """A declared pattern with no expectation is a figure nothing checks."""
    root = Path(__file__).resolve().parents[1]
    for profile in load_profiles(root / "profiles").profiles:
        declared = set(profile.summary.compiled())
        pinned = set(profile.selftest.summary_expect)
        assert declared == pinned, (
            f"{profile.id}: [summary] declares {sorted(declared)} but "
            f"summary_expect pins {sorted(pinned)}; an unpinned pattern can "
            "capture the wrong figure and still pass"
        )


def test_the_loader_parses_a_capture_exactly_as_the_engine_does():
    """Pin the loader's capture parsing to the engine's own `_read_summary`.

    run_selftest cannot import the engine (the engine is injected as
    `parse_row`), so it re-implements the two conversions. If they ever drift,
    the selftest would bless a value the engine reads differently - the exact
    class of bug summary_expect exists to stop.
    """
    from fbr.config.loader import _capture_as_the_engine_does
    from fbr.engines.tabular import _read_summary

    root = Path(__file__).resolve().parents[1]
    checked = 0
    for profile in load_profiles(root / "profiles").profiles:
        sample = profile.selftest.summary_sample
        engine = _read_summary(sample, profile)
        engine_field = {"opening": "opening", "closing": "closing",
                        "total_credit": "total_credit", "total_debit": "total_debit",
                        "period_from": "period_start", "period_to": "period_end",
                        "account_id": "account_identifier"}
        for role, pattern in profile.summary.compiled().items():
            captured = pattern.search(sample).group("value")
            mine = _capture_as_the_engine_does(role, captured, profile)
            theirs = getattr(engine, engine_field[role])
            if role in ("period_from", "period_to"):
                theirs = theirs.isoformat()
            assert mine == theirs, (
                f"{profile.id}.{role}: loader read {mine!r}, engine read {theirs!r}"
            )
            checked += 1
    assert checked == 30, checked      # 6 profiles, 30 declared patterns
