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
    # No account acquired figures from this file. Both registry accounts are
    # now reported as still awaiting a statement (final fix round, Finding 5)
    # rather than being absent from the run with nothing said about them.
    assert run.account_status == {"meezan-main": "missing", "mcb-main": "missing"}


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
    # Nothing about this account warns. (mcb-main is separately and correctly
    # reported as still awaiting its own statement.)
    assert not [c for c in ledger.checks if c.status == "warn"]


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


# --- an expected account must never vanish (final fix round, Finding 5) -----


def test_an_expected_account_with_no_statement_is_reported(ty, registry, profiles):
    # `ledgers` is built only from accounts that produced a parse, so
    # mcb-main - statement_expected = true, statement simply not loaded -
    # produced no row, no status and no check. Declared wealth silently
    # understated by a whole account.
    run = load_files([InputFile("meezan.csv", write_meezan_csv(_full_year()))],
                     registry=registry, profiles=profiles, tax_year=ty)

    assert set(run.ledgers) == {"meezan-main"}
    assert run.missing_accounts == ("mcb-main",)
    assert run.account_status["mcb-main"] == "missing"

    warning = next(c for c in run.all_checks if c.kind == "statement_missing")
    assert warning.status == "warn"
    assert warning.scope == "account"
    assert "mcb-main" in warning.detail
    assert "MCB Bank Limited" in warning.detail


def test_an_unassigned_statement_still_leaves_its_account_reported(ty, registry, profiles):
    # The file was loaded but could not be attached to an account. Both
    # halves must be visible: the file is unassigned AND the accounts that
    # are still without one are named.
    stmt = _full_year(account_id="PK00TEST9999999999999999")
    run = load_files([InputFile("x.csv", write_meezan_csv(stmt))],
                     registry=registry, profiles=profiles, tax_year=ty)
    assert run.outcomes[0].status == "unassigned"
    assert set(run.missing_accounts) == {"meezan-main", "mcb-main"}
    assert {c.kind for c in run.all_checks if c.status == "warn"} == {"statement_missing"}


def test_an_account_that_expects_no_statement_is_not_reported_missing(ty, profiles):
    reg = Registry(
        owner=Owner(name="OWNER NAME"),
        accounts=(
            Account(id="meezan-main", institution="Meezan Bank Limited", kind="bank",
                    iban="PK00TEST0000000000000000", account_number="", wallet_number="",
                    title="T", type="Saving", ownership="Self", currency="PKR",
                    statement_expected=True),
            # Spec §4.2: these exist only so transfers to them are recognised.
            Account(id="payoneer", institution="Payoneer", kind="foreign", iban="",
                    account_number="", wallet_number="", title="T", type="",
                    ownership="Self", currency="USD", statement_expected=False),
        ),
    )
    run = load_files([InputFile("meezan.csv", write_meezan_csv(_full_year()))],
                     registry=reg, profiles=profiles, tax_year=ty)
    assert run.missing_accounts == ()


@pytest.mark.parametrize(
    "over",
    [
        {"closed_on": date(2025, 3, 31)},     # closed before the tax year began
        {"opened_on": date(2026, 9, 1)},      # not opened until after it ended
    ],
)
def test_an_account_outside_the_tax_year_is_not_reported_missing(ty, profiles, over):
    reg = Registry(
        owner=Owner(name="OWNER NAME"),
        accounts=(
            Account(id="meezan-main", institution="Meezan Bank Limited", kind="bank",
                    iban="PK00TEST0000000000000000", account_number="", wallet_number="",
                    title="T", type="Saving", ownership="Self", currency="PKR",
                    statement_expected=True),
            Account(id="old-account", institution="Old Bank", kind="bank",
                    iban="PK00TEST2222222222222222", account_number="", wallet_number="",
                    title="T", type="Saving", ownership="Self", currency="PKR",
                    statement_expected=True, **over),
        ),
    )
    run = load_files([InputFile("meezan.csv", write_meezan_csv(_full_year()))],
                     registry=reg, profiles=profiles, tax_year=ty)
    assert run.missing_accounts == ()


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


# --- spec 4.2: the owner assigns a file the registry could not match --------


def _wallet_registry():
    """meezan-main matches the CSV's printed IBAN; sadapay matches nothing.

    The SadaPay statement below prints an IBAN that is in no registry account,
    so it lands in `unassigned` exactly as a real first statement printing an
    unanticipated identifier would - which is the case the picker exists for.
    """
    return Registry(
        owner=Owner(name="OWNER NAME"),
        accounts=(
            Account(id="meezan-main", institution="Meezan Bank Limited", kind="bank",
                    iban="PK00TEST0000000000000000", account_number="", wallet_number="",
                    title="ACCOUNT TITLE", type="Saving", ownership="Self",
                    currency="PKR", statement_expected=True, match_hints=("MEEZAN",)),
            Account(id="sadapay", institution="SadaPay", kind="wallet", iban="",
                    account_number="", wallet_number="03009999999",
                    title="ACCOUNT TITLE", type="", ownership="Self", currency="PKR",
                    statement_expected=True, match_hints=("SADA",)),
        ),
    )


def _two_files():
    """A CSV that resolves on its own, and a PDF that cannot."""
    from tests.fixtures.synth_pdf import write_sadapay_pdf

    sada = build_statement(
        opening=0, start=date(2025, 7, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2025, 9, 1), "Top-up", 30000, None),
              SynthTxn(date(2026, 3, 1), "POS Transaction", -20000, None)],
        account_id="PK00TEST9999999999999999",     # in no registry account
    )
    return (
        [InputFile("meezan.csv", write_meezan_csv(_full_year())),
         InputFile("sada.pdf", write_sadapay_pdf(sada))],
        sada,
    )


def test_an_owner_assignment_produces_a_ledger_and_keeps_the_existing_ones(ty, profiles):
    """Spec 4.2, the whole rule, without a browser.

    The picker's job: assign the file the registry could not match, and do not
    cost the owner the parse that already worked. Re-running the WHOLE set is
    what guarantees the second half - see load_files_with_assignments.
    """
    from fbr.pipeline import load_files_with_assignments

    reg = _wallet_registry()
    files, sada = _two_files()

    # Before: the CSV resolved itself, the PDF did not.
    first = load_files(files, registry=reg, profiles=profiles, tax_year=ty)
    assert {o.name: o.status for o in first.outcomes} == {
        "meezan.csv": "ok", "sada.pdf": "unassigned",
    }
    assert [f.name for f in first.unassigned] == ["sada.pdf"]
    assert set(first.ledgers) == {"meezan-main"}
    meezan_before = first.ledgers["meezan-main"]

    # The owner picks "sadapay" for sada.pdf and parses again.
    second = load_files_with_assignments(
        files, {"sada.pdf": "sadapay"},
        registry=reg, profiles=profiles, tax_year=ty,
        anchors={"sadapay": 500000},
    )

    # The assigned file now has a ledger of its own...
    assert second.unassigned == ()
    assert {o.name: o.status for o in second.outcomes} == {
        "meezan.csv": "ok", "sada.pdf": "ok",
    }
    assert set(second.ledgers) == {"meezan-main", "sadapay"}
    sadapay = second.ledgers["sadapay"]
    assert len(sadapay.transactions) == len(sada.txns)
    # Integer paisa, exact: anchor 5,000.00 + 300.00 - 200.00 = 5,100.00.
    assert sadapay.closing == 510000
    assert sadapay.opening == 500000 and sadapay.opening_source == "anchor"

    # ...and the ledger that already worked came back untouched.
    assert second.ledgers["meezan-main"].closing == meezan_before.closing
    assert second.ledgers["meezan-main"].transactions == meezan_before.transactions
    assert second.ledgers["meezan-main"].status == meezan_before.status


def test_an_assignment_for_a_file_no_longer_loaded_does_not_break_the_parse(
    ty, profiles
):
    """A stale choice - the owner removed the file after picking - is inert."""
    from fbr.pipeline import load_files_with_assignments

    reg = _wallet_registry()
    run = load_files_with_assignments(
        [InputFile("meezan.csv", write_meezan_csv(_full_year()))],
        {"a-file-that-is-gone.pdf": "sadapay"},
        registry=reg, profiles=profiles, tax_year=ty,
    )
    assert run.outcomes[0].status == "ok"
    assert set(run.ledgers) == {"meezan-main"}


def test_an_assignment_naming_no_registry_account_fails_closed(ty, profiles):
    """The picker only offers real ids, but the seam must not trust that."""
    from fbr.pipeline import load_files_with_assignments

    files, _ = _two_files()
    run = load_files_with_assignments(
        files, {"sada.pdf": "not-an-account"},
        registry=_wallet_registry(), profiles=profiles, tax_year=ty,
    )
    sada = next(o for o in run.outcomes if o.name == "sada.pdf")
    assert sada.status == "unassigned"
    assert "not-an-account" in sada.message
    # And the good file still parsed.
    assert set(run.ledgers) == {"meezan-main"}


def test_no_assignments_is_exactly_load_files(ty, profiles):
    """The helper must not change behaviour when the owner has chosen nothing."""
    from fbr.pipeline import load_files_with_assignments

    reg = _wallet_registry()
    files, _ = _two_files()
    plain = load_files(files, registry=reg, profiles=profiles, tax_year=ty)
    same = load_files_with_assignments(files, {}, registry=reg, profiles=profiles,
                                       tax_year=ty)
    assert [(o.name, o.status, o.account_id) for o in same.outcomes] == \
           [(o.name, o.status, o.account_id) for o in plain.outcomes]
    assert set(same.ledgers) == set(plain.ledgers)
