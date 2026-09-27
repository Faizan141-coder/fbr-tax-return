from datetime import date
from pathlib import Path

import pytest

from fbr.config.loader import ProfileSet, ProfileStatus, load_profiles, load_tax_year
from fbr.model import Account, Owner, Registry
from fbr.pipeline import InputFile, load_files, read_statement_dir
from tests.fixtures.synth import SynthTxn, build_statement, corrupt, write_meezan_csv, write_mcb_csv
from tests.test_loader import TAXYEAR_TOML

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def ty(tmp_path):
    (tmp_path / "TY2026.toml").write_text(TAXYEAR_TOML)
    return load_tax_year("TY2026", tmp_path)


@pytest.fixture
def registry():
    return Registry(
        owner=Owner(name="OWNER NAME"),
        accounts=(
            Account(id="meezan-main", institution="Meezan Bank Limited", kind="bank",
                    iban="PK00TEST0000000000000000", account_number="", wallet_number="",
                    title="ACCOUNT TITLE", type="Saving", ownership="Self", currency="PKR",
                    statement_expected=True, match_hints=("MEEZAN",)),
            Account(id="mcb-main", institution="MCB Bank Limited", kind="bank",
                    iban="PK00TEST1111111111111111", account_number="", wallet_number="",
                    title="ACCOUNT TITLE", type="Current", ownership="Self", currency="PKR",
                    statement_expected=True, match_hints=("MCB",)),
        ),
    )


@pytest.fixture(scope="module")
def profiles():
    """The profiles that actually SHIP, not a hand-built stand-in.

    Final fix round, Finding 3: this fixture used to build a ProfileSet from
    tests/test_tabular.py's MEEZAN/MCB, which carry period_from/period_to
    patterns the shipped profiles did not. Every end-to-end test therefore
    exercised configuration no owner ever runs, and CI stayed green while a
    clean full-year statement reported `account_status = incomplete` with a
    false gap warning against the real profiles/ directory. The hand-built
    profiles remain in test_tabular.py for the unit tests that need to vary
    one setting at a time.
    """
    return load_profiles(ROOT / "profiles")


# Fix round 1: isolating one account's `anchor` from another's `prior_year`
# needs an account whose ledger the anchor can actually move. A running-
# balance account (the shipped meezan/mcb profiles) ignores `anchor` entirely
# (reconcile.boundary_balances only consults it when there is no balance
# column), so proving the anchor landed - and only landed - on its own
# account needs a no-balance-column variant, same as
# tests/test_reconcile_account.py's NO_BALANCE_PROFILE. This is scoped to
# its own local ProfileSet in that one test, not the shared `profiles`
# fixture, because it shares the shipped meezan [detect] signature and would
# make any meezan-shaped file match two profiles at once (LayoutAmbiguous)
# if both were loaded together.
def _no_balance(profile):
    return profile.model_copy(update={
        "balance": profile.balance.model_copy(update={"semantics": "none"})
    })


def _full_year(account_id="PK00TEST0000000000000000", seed=71):
    return build_statement(
        opening=100000, start=date(2025, 7, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2025, 8, 1), "Top-up", 50000, None),
              SynthTxn(date(2026, 5, 1), "Withdrawal", -20000, None)],
        account_id=account_id,
    )


def test_one_file_parses_reconciles_and_lands_in_a_ledger(ty, registry, profiles):
    files = [InputFile("meezan.csv", write_meezan_csv(_full_year()))]
    run = load_files(files, registry=registry, profiles=profiles, tax_year=ty)
    assert run.outcomes[0].status == "ok"
    assert run.outcomes[0].layout_id == "meezan.csv.v1"
    assert run.outcomes[0].account_id == "meezan-main"
    assert run.account_status["meezan-main"] == "complete"
    assert len(run.ledgers["meezan-main"].transactions) == 2


def test_two_accounts_stay_separate(ty, registry, profiles):
    files = [
        InputFile("meezan.csv", write_meezan_csv(_full_year())),
        InputFile("mcb.csv", write_mcb_csv(
            build_statement(opening=200000, start=date(2025, 7, 1), end=date(2026, 6, 30),
                            rows=[SynthTxn(date(2025, 9, 1), "Salary", 300000, None)],
                            account_id="PK00TEST1111111111111111"))),
    ]
    run = load_files(files, registry=registry, profiles=profiles, tax_year=ty)
    assert set(run.ledgers) == {"meezan-main", "mcb-main"}
    assert len(run.ledgers["mcb-main"].transactions) == 1


def test_an_unknown_layout_is_reported_not_raised(ty, registry, profiles):
    run = load_files([InputFile("weird.csv", b"a,b\n1,2\n")],
                     registry=registry, profiles=profiles, tax_year=ty)
    assert run.outcomes[0].status == "unknown_layout"
    assert "fbr-dump" in run.outcomes[0].message
    assert run.ledgers == {}


def test_an_unresolvable_account_is_listed_for_manual_assignment(ty, registry, profiles):
    stmt = _full_year(account_id="PK00TEST9999999999999999")
    run = load_files([InputFile("x.csv", write_meezan_csv(stmt))],
                     registry=registry, profiles=profiles, tax_year=ty)
    assert run.outcomes[0].status == "unassigned"
    assert run.unassigned and run.unassigned[0].name == "x.csv"


def test_an_explicit_account_override_is_honoured(ty, registry, profiles):
    stmt = _full_year(account_id="PK00TEST9999999999999999")
    run = load_files([InputFile("x.csv", write_meezan_csv(stmt), account_id="meezan-main")],
                     registry=registry, profiles=profiles, tax_year=ty)
    assert run.outcomes[0].status == "ok"
    assert "meezan-main" in run.ledgers


def test_an_invalid_account_override_is_reported_not_silently_dropped(ty, registry, profiles):
    # Fix round 1 (coordinator review): a caller-supplied account_id that
    # names no registry account must not be treated as valid. Before the
    # fix, load_files parsed the file, attached it to the bogus id, and
    # reported "ok" - then the merge loop's `registry.by_id(...) is None`
    # guard silently dropped that account, so its figures never reached any
    # ledger with no outcome ever saying why. Confirmed this test goes red
    # without the guard: see task-13-report.md, "Fix round 1".
    run = load_files(
        [InputFile("x.csv", write_meezan_csv(_full_year()), account_id="does-not-exist")],
        registry=registry, profiles=profiles, tax_year=ty,
    )
    assert run.outcomes[0].status == "unassigned"
    assert "does-not-exist" in run.outcomes[0].message
    assert run.unassigned and run.unassigned[0].name == "x.csv"
    assert run.ledgers == {}
    assert run.account_status == {}


def test_a_failed_statement_marks_the_account_failed_and_contributes_nothing(ty, registry, profiles):
    data = corrupt(write_meezan_csv(_full_year()), "drop_row")
    run = load_files([InputFile("x.csv", data)],
                     registry=registry, profiles=profiles, tax_year=ty)
    assert run.account_status["meezan-main"] == "failed"
    assert run.ledgers["meezan-main"].transactions == ()


def test_one_bad_file_does_not_stop_the_others(ty, registry, profiles):
    files = [
        InputFile("bad.csv", b"nothing,here\n"),
        InputFile("good.csv", write_meezan_csv(_full_year())),
    ]
    run = load_files(files, registry=registry, profiles=profiles, tax_year=ty)
    assert {o.status for o in run.outcomes} == {"unknown_layout", "ok"}
    assert run.account_status["meezan-main"] == "complete"


def test_anchors_and_prior_year_reach_the_ledger(ty, registry, profiles):
    run = load_files(
        [InputFile("x.csv", write_meezan_csv(_full_year()))],
        registry=registry, profiles=profiles, tax_year=ty,
        prior_year={"meezan-main": 999999},
    )
    assert any(c.kind == "prior_year_mismatch" for c in run.all_checks)


def test_anchor_and_prior_year_do_not_cross_accounts(ty, registry, profiles):
    # Fix round 1 (coordinator review): the single-account version above
    # cannot structurally rule out a value keyed to one account leaking onto
    # another's ledger. meezan-main here carries no balance column, so its
    # opening is driven entirely by `anchor` (never a printed/computed
    # balance); mcb-main keeps its normal running balance, so
    # `prior_year_closing`'s mismatch check is the only thing that can fire
    # for it. Each input is supplied for one account only.
    variants = (_no_balance(profiles.by_id("meezan.csv.v1")), profiles.by_id("mcb.csv.v1"))
    local_profiles = ProfileSet(
        variants,
        tuple(ProfileStatus(p.id, f"{p.id}.toml", True, "loaded") for p in variants),
    )
    files = [
        InputFile("meezan.csv", write_meezan_csv(_full_year())),
        InputFile("mcb.csv", write_mcb_csv(
            build_statement(opening=200000, start=date(2025, 7, 1), end=date(2026, 6, 30),
                            rows=[SynthTxn(date(2025, 9, 1), "Salary", 300000, None)],
                            account_id="PK00TEST1111111111111111"))),
    ]
    run = load_files(
        files, registry=registry, profiles=local_profiles, tax_year=ty,
        anchors={"meezan-main": 700000},
        prior_year={"mcb-main": 1},
    )

    meezan, mcb = run.ledgers["meezan-main"], run.ledgers["mcb-main"]

    # The anchor landed on the account it was keyed to...
    assert meezan.opening == 700000
    assert meezan.opening_source == "anchor"
    # ...and not on the other.
    assert mcb.opening_source != "anchor"

    # The prior-year mismatch landed on the account it was keyed to...
    assert any(c.kind == "prior_year_mismatch" for c in mcb.checks)
    # ...and not on the other.
    assert not any(c.kind == "prior_year_mismatch" for c in meezan.checks)


def test_the_same_file_twice_is_deduplicated_by_hash(ty, registry, profiles):
    data = write_meezan_csv(_full_year())
    run = load_files([InputFile("a.csv", data), InputFile("copy.csv", data)],
                     registry=registry, profiles=profiles, tax_year=ty)
    assert len(run.ledgers["meezan-main"].transactions) == 2   # not 4
    assert any(o.status == "duplicate" for o in run.outcomes)


# --- the gap warning must mean something (final fix round, Finding 3) -------


def test_a_clean_full_year_statement_is_complete_with_no_false_gap(ty, registry, profiles):
    # Against the SHIPPED profiles this reported `incomplete` with
    # "no statement covers 2025-07-01..2025-07-31; 2026-05-02..2026-06-30" -
    # periods the statement does in fact cover - because neither profile
    # defined period_from/period_to, so Document.period_start/end fell back
    # to the first and last printed transaction (1 Aug and 1 May).
    run = load_files([InputFile("meezan.csv", write_meezan_csv(_full_year()))],
                     registry=registry, profiles=profiles, tax_year=ty)
    ledger = run.ledgers["meezan-main"]
    assert run.account_status["meezan-main"] == "complete"

    date_range = next(c for c in ledger.checks if c.kind == "date_range")
    assert date_range.status == "pass", date_range.detail
    assert date_range.expected == "2025-07-01..2026-06-30"

    gap = next(c for c in ledger.checks if c.kind == "gap")
    assert gap.status == "pass", gap.detail
    assert not [c for c in run.all_checks if c.status == "warn"]


def test_a_genuinely_missing_period_still_warns(ty, registry, profiles):
    # The other half: the check has to keep firing when data really is
    # missing, or silencing the false positive would have silenced the
    # signal too. Jul-Dec only, so Jan-Jun is a real hole.
    half = build_statement(
        opening=100000, start=date(2025, 7, 1), end=date(2025, 12, 31),
        rows=[SynthTxn(date(2025, 8, 1), "Top-up", 50000, None)],
        account_id="PK00TEST0000000000000000",
    )
    run = load_files([InputFile("meezan.csv", write_meezan_csv(half))],
                     registry=registry, profiles=profiles, tax_year=ty)
    assert run.account_status["meezan-main"] == "incomplete"
    gap = next(c for c in run.ledgers["meezan-main"].checks if c.kind == "gap")
    assert gap.status == "warn"
    assert gap.actual == "2026-01-01..2026-06-30"


def test_every_shipped_profile_bounds_its_own_dates(ty, registry, profiles):
    # date_range must be live for every shipped layout, not just Meezan: a
    # profile with no period patterns silently degrades to a permanent warn.
    for profile in profiles.profiles:
        assert profile.summary.period_from, f"{profile.id} defines no period_from"
        assert profile.summary.period_to, f"{profile.id} defines no period_to"


def test_read_statement_dir_returns_files(tmp_path, monkeypatch):
    monkeypatch.setenv("FBR_PRIVATE_DIR", str(tmp_path / "priv"))
    from fbr import paths
    paths.ensure_private_layout()
    folder = paths.statements_dir("TY2026")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "a.csv").write_bytes(write_meezan_csv(_full_year()))
    (folder / "notes.txt").write_text("ignored")
    files = read_statement_dir("TY2026")
    assert [f.name for f in files] == ["a.csv"]
