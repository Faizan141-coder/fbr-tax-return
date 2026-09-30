# tests/test_load_page.py
"""The Load page's account picker, driven through Streamlit's own test harness.

Spec §4.2's rule lives in `pipeline.load_files_with_assignments` and is tested
there, without Streamlit, because the pages hold no business logic. What is left
here is wiring the page cannot delegate: that the selectbox offers every registry
account and defaults to leaving the file alone, that the choice reaches the
pipeline, and that the run which already worked survives the re-parse.

`AppTest` runs the page's script in-process, so this needs no browser.
"""
from datetime import date
from pathlib import Path

import pytest

from fbr.config.loader import load_profiles, load_tax_year
from fbr.model import Account, Owner, Registry
from tests.fixtures.synth import SynthTxn, build_statement, write_meezan_csv
from tests.fixtures.synth_pdf import write_sadapay_pdf
from tests.test_loader import TAXYEAR_TOML

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "app" / "pages" / "2_Load.py"


@pytest.fixture
def app(tmp_path, monkeypatch):
    """The Load page, with two statements filed in a private folder.

    meezan.csv prints an IBAN a registry account holds, so it resolves itself.
    sada.pdf prints one no account holds - the case the picker exists for, and
    the one a real first statement hits when it prints an identifier in a form
    no profile anticipated.
    """
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

    monkeypatch.setenv("FBR_PRIVATE_DIR", str(tmp_path / "priv"))
    from fbr import paths

    paths.ensure_private_layout()
    folder = paths.statements_dir("TY2026")
    folder.mkdir(parents=True, exist_ok=True)

    meezan = build_statement(
        opening=100000, start=date(2025, 7, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2025, 8, 1), "Top-up", 50000, None),
              SynthTxn(date(2026, 5, 1), "Withdrawal", -20000, None)],
        account_id="PK00TEST0000000000000000",
    )
    sada = build_statement(
        opening=0, start=date(2025, 7, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2025, 9, 1), "Top-up", 30000, None),
              SynthTxn(date(2026, 3, 1), "POS Transaction", -20000, None)],
        account_id="PK00TEST9999999999999999",
    )
    (folder / "meezan.csv").write_bytes(write_meezan_csv(meezan))
    (folder / "sada.pdf").write_bytes(write_sadapay_pdf(sada))

    (tmp_path / "TY2026.toml").write_text(TAXYEAR_TOML)

    at = AppTest.from_file(str(PAGE), default_timeout=60)
    at.session_state["tax_year"] = "TY2026"
    at.session_state["registry"] = Registry(
        owner=Owner(name="OWNER NAME"),
        accounts=(
            Account(id="meezan-main", institution="Meezan Bank Limited", kind="bank",
                    iban="PK00TEST0000000000000000", account_number="",
                    wallet_number="", title="ACCOUNT TITLE", type="Saving",
                    ownership="Self", currency="PKR", statement_expected=True,
                    match_hints=("MEEZAN",)),
            Account(id="sadapay", institution="SadaPay", kind="wallet", iban="",
                    account_number="", wallet_number="03009999999",
                    title="ACCOUNT TITLE", type="", ownership="Self",
                    currency="PKR", statement_expected=True,
                    match_hints=("SADA",)),
        ),
    )
    at.session_state["profiles"] = load_profiles(ROOT / "profiles")
    at.session_state["tax_year_config"] = load_tax_year("TY2026", tmp_path)
    at.run()
    assert not at.exception, at.exception
    return at


def _click(at, label_part):
    button = next(b for b in at.button if label_part in b.label)
    button.click().run()
    assert not at.exception, at.exception
    return at


def test_the_picker_offers_every_account_and_defaults_to_leaving_it_alone(app):
    at = _click(app, "Parse")

    assert [f.name for f in at.session_state["run"].unassigned] == ["sada.pdf"]
    box = next(s for s in at.selectbox if "sada.pdf" in s.label)
    # Every registry account, labelled with its institution so two ids of the
    # same bank are still tellable apart.
    assert box.options == [
        "— leave unassigned —",
        "meezan-main — Meezan Bank Limited",
        "sadapay — SadaPay",
    ]
    # Nothing is assigned by accident: a statement booked to the wrong account
    # produces confident, wrong figures that no downstream check can catch.
    assert box.value == "— leave unassigned —"
    assert next(b for b in at.button if "again" in b.label).disabled is True


def test_choosing_an_account_assigns_the_file_and_keeps_the_good_ledger(app):
    at = _click(app, "Parse")
    before = at.session_state["run"]
    assert set(before.ledgers) == {"meezan-main"}
    meezan_before = before.ledgers["meezan-main"]

    next(s for s in at.selectbox if "sada.pdf" in s.label).select("sadapay").run()
    assert next(b for b in at.button if "again" in b.label).disabled is False
    at = _click(at, "again")

    run = at.session_state["run"]
    # The choice reached the pipeline and is remembered in session state only.
    assert at.session_state["account_assignments"] == {"sada.pdf": "sadapay"}
    assert run.unassigned == ()
    assert set(run.ledgers) == {"meezan-main", "sadapay"}
    assert len(run.ledgers["sadapay"].transactions) == 2

    # And the parse that already worked is untouched - integer paisa, exact.
    assert run.ledgers["meezan-main"].closing == meezan_before.closing == 130000
    assert run.ledgers["meezan-main"].transactions == meezan_before.transactions


def test_a_remembered_choice_still_applies_on_a_plain_re_parse(app):
    """The owner must not have to pick the same account twice."""
    at = _click(app, "Parse")
    next(s for s in at.selectbox if "sada.pdf" in s.label).select("sadapay").run()
    at = _click(at, "again")
    assert at.session_state["run"].unassigned == ()

    # Press the ordinary Parse button again: the assignment must survive.
    at = _click(at, "Parse")
    run = at.session_state["run"]
    assert run.unassigned == ()
    assert set(run.ledgers) == {"meezan-main", "sadapay"}


def test_the_page_stores_only_the_run_and_the_assignments(app):
    """The picker must not grow a store of its own, least of all for a password.

    The page attaches a password per run, inside the InputFile it parses with,
    and writes nothing else. `st.text_input` necessarily holds its own widget
    value in Streamlit's in-memory widget state - that is the framework's, not
    something this page puts there - so what is asserted is the page's own keys.
    """
    at = _click(app, "Parse")
    next(s for s in at.selectbox if "sada.pdf" in s.label).select("sadapay").run()
    at = _click(at, "again")

    seeded = {"tax_year", "registry", "profiles", "tax_year_config"}
    assert set(at.session_state) - seeded == {"run", "account_assignments"}
    # Account ids only. Nothing else rides along in here.
    known = {a.id for a in at.session_state["registry"].accounts}
    assert set(at.session_state["account_assignments"].values()) <= known
