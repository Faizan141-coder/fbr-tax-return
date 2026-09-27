from datetime import date

import pytest

from fbr.config.loader import ProfileSet, ProfileStatus, load_tax_year
from fbr.model import Account, Owner, Registry
from fbr.pipeline import InputFile, load_files, read_statement_dir
from tests.fixtures.synth import SynthTxn, build_statement, corrupt, write_meezan_csv, write_mcb_csv
from tests.test_loader import TAXYEAR_TOML
from tests.test_tabular import MCB, MEEZAN


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


@pytest.fixture
def profiles():
    return ProfileSet(
        (MEEZAN, MCB),
        tuple(ProfileStatus(p.id, f"{p.id}.toml", True, "loaded") for p in (MEEZAN, MCB)),
    )


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


def test_the_same_file_twice_is_deduplicated_by_hash(ty, registry, profiles):
    data = write_meezan_csv(_full_year())
    run = load_files([InputFile("a.csv", data), InputFile("copy.csv", data)],
                     registry=registry, profiles=profiles, tax_year=ty)
    assert len(run.ledgers["meezan-main"].transactions) == 2   # not 4
    assert any(o.status == "duplicate" for o in run.outcomes)


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
