from collections import Counter
from datetime import date

import pytest

from tests.fixtures.synth import SynthTxn, build_statement, write_meezan_csv
from tools.dump_layout import (
    dump_tabular,
    load_allowlist,
    main,
    mask_text,
    shape,
)

ALLOW = {"BOOKING", "DATE", "DESCRIPTION", "DEBIT", "CREDIT", "BALANCE", "JUL", "PKR"}


@pytest.mark.parametrize(
    "token,expected",
    [
        ("Muhammad", "Xxxxxxxx"),
        ("FAIZAN", "XXXXXX"),
        ("PK" + "96" + "MEZN" + "0003070112153474", "XX99XXXX9999999999999999"),
        ("1,234.56", "9,999.99"),
        ("01", "99"),
        ("STAN123456", "XXXX999999"),
        ("1,234.00Dr", "9,999.99Xx"),
        ("03001234567", "99999999999"),
    ],
)
def test_shape_replaces_letters_and_digits(token, expected):
    assert shape(token, allowlist=set()) == expected


@pytest.mark.parametrize("token", ["Booking", "DATE", "credit", "Jul", "PKR"])
def test_allowlisted_tokens_survive_verbatim(token):
    assert shape(token, allowlist=ALLOW) == token


def test_allowlist_matching_ignores_case_and_punctuation():
    assert shape("Date:", allowlist=ALLOW) == "Date:"
    assert shape("(Credit)", allowlist=ALLOW) == "(Credit)"


def test_hide_magnitude_fixes_the_digit_count():
    a = shape("1,234.56", allowlist=set(), hide_magnitude=True)
    b = shape("12,34,567.89", allowlist=set(), hide_magnitude=True)
    assert a == b, "magnitude must not leak through digit count"
    assert a.endswith(".99")


def test_hide_magnitude_keeps_sign_and_suffix():
    assert shape("-1,234.56", allowlist=set(), hide_magnitude=True).startswith("-")
    assert shape("1,234.00Dr", allowlist=set(), hide_magnitude=True).endswith("Xx")


def test_mask_text_preserves_structure():
    masked = mask_text("Booking Date,Description,Credit\n01 Jul 2025,IBFT from Ali,1,234.56",
                       allowlist=ALLOW | {"IBFT", "FROM"})
    assert "Booking Date,Description,Credit" in masked
    assert "Ali" not in masked
    assert "IBFT" in masked          # allowlisted banking vocabulary survives
    assert "9,999.99" in masked or "9999.99" in masked


def test_no_real_name_survives_masking():
    masked = mask_text("Money Received from MUHAMMAD FAIZAN HASNAAT", allowlist=ALLOW)
    for fragment in ("MUHAMMAD", "FAIZAN", "HASNAAT"):
        assert fragment not in masked


def test_shipped_allowlist_loads_and_holds_banking_vocabulary():
    allow = load_allowlist()
    for word in ("DATE", "DESCRIPTION", "CREDIT", "DEBIT", "BALANCE", "IBFT",
                 "RAAST", "PROFIT", "WITHHOLDING", "ZAKAT", "PAYONEER", "THUNES"):
        assert word in allow, word


def test_extra_allowlist_file_is_merged(tmp_path):
    extra = tmp_path / "dump-allowlist.txt"
    extra.write_text("# a comment\nINTERBANK\n\nkuickpay\n")
    allow = load_allowlist(extra)
    assert "INTERBANK" in allow and "KUICKPAY" in allow


def test_dump_reports_header_and_row_shapes():
    stmt = build_statement(
        opening=100000,
        rows=[SynthTxn(date(2025, 7, 2), "IBFT In from Someone", 50000, None)],
    )
    text, counts = dump_tabular(write_meezan_csv(stmt), "csv",
                                allowlist=load_allowlist(), rows=5, hide_magnitude=False)
    assert "Booking Date" in text          # header labels are allowlisted
    assert "Someone" not in text
    assert isinstance(counts, Counter)


def test_dump_includes_a_column_shape_histogram():
    stmt = build_statement(seed=61)
    text, _ = dump_tabular(write_meezan_csv(stmt), "csv",
                           allowlist=load_allowlist(), rows=5, hide_magnitude=False)
    assert "shape histogram" in text.lower()


def test_dump_counts_masked_tokens_for_the_candidates_file():
    stmt = build_statement(
        opening=0, rows=[SynthTxn(date(2025, 7, 2), "Zzzz Yyyy", 50000, None)]
    )
    _, counts = dump_tabular(write_meezan_csv(stmt), "csv",
                             allowlist=load_allowlist(), rows=5, hide_magnitude=False)
    assert any(tok in counts for tok in ("ZZZZ", "YYYY"))


def test_cli_writes_a_dump_and_prints_only_a_path_and_counts(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("FBR_PRIVATE_DIR", str(tmp_path / "priv"))
    src = tmp_path / "statement.csv"
    stmt = build_statement(
        opening=0, rows=[SynthTxn(date(2025, 7, 2), "IBFT In from Someone", 50000, None)]
    )
    src.write_bytes(write_meezan_csv(stmt))

    assert main([str(src)]) == 0
    out = capsys.readouterr().out
    assert "wrote" in out and "tokens masked" in out
    assert "Someone" not in out, "stdout must never carry statement content"
    assert "500.00" not in out

    dumps = list((tmp_path / "priv" / "dumps").glob("*.dump.md"))
    assert len(dumps) == 1
    assert "Someone" not in dumps[0].read_text()


def test_cli_names_the_dump_by_hash_not_by_filename(tmp_path, monkeypatch):
    monkeypatch.setenv("FBR_PRIVATE_DIR", str(tmp_path / "priv"))
    src = tmp_path / "meezan-PK00TEST0000000000000000.csv"
    src.write_bytes(write_meezan_csv(build_statement(seed=62)))
    main([str(src)])
    name = next((tmp_path / "priv" / "dumps").glob("*.dump.md")).name
    assert "PK00TEST" not in name, "the source filename may itself carry an account number"


def test_cli_writes_candidates_to_the_private_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("FBR_PRIVATE_DIR", str(tmp_path / "priv"))
    src = tmp_path / "s.csv"
    src.write_bytes(write_meezan_csv(build_statement(seed=63)))
    main([str(src)])
    assert list((tmp_path / "priv" / "dump-candidates").glob("*.txt"))


def test_cli_refuses_a_pdf_for_now(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FBR_PRIVATE_DIR", str(tmp_path / "priv"))
    src = tmp_path / "s.pdf"
    src.write_bytes(b"%PDF-1.7\n")
    assert main([str(src)]) == 2
    assert "phase 2" in capsys.readouterr().err.lower()


def test_cli_reports_a_missing_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FBR_PRIVATE_DIR", str(tmp_path / "priv"))
    assert main([str(tmp_path / "nope.csv")]) == 2
    assert "not found" in capsys.readouterr().err.lower()
