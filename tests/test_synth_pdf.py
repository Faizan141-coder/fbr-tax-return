# tests/test_synth_pdf.py
"""Synthetic PDFs, so a real statement never enters the repo.

reportlab draws text at exact coordinates, which is what makes these fixtures
useful: the column-band logic in the engine is geometry, and geometry needs a
page whose geometry we chose.
"""
from datetime import date

import pdfplumber
import pytest

from tests.fixtures.synth import SynthTxn, build_statement
from tests.fixtures.synth_pdf import (
    encrypt_pdf,
    write_meezan_pdf,
    write_sadapay_pdf,
    write_wrapped_description_pdf,
)


def _words(data: bytes, password: str | None = None):
    import io
    with pdfplumber.open(io.BytesIO(data), password=password) as pdf:
        return [w for page in pdf.pages for w in page.extract_words()]


def test_sadapay_pdf_is_a_pdf_with_extractable_text():
    data = write_sadapay_pdf(build_statement(seed=1))
    assert data.startswith(b"%PDF")
    text = " ".join(w["text"] for w in _words(data))
    assert "Account Statement" in text
    assert "Total debit" in text and "Total credit" in text


def test_sadapay_amounts_carry_their_sign():
    stmt = build_statement(
        opening=0,
        rows=[SynthTxn(date(2025, 7, 2), "TRANSF CR/ICT/ Top-up", 50000, None),
              SynthTxn(date(2025, 7, 3), "PUR/ Shop", -20000, None)],
    )
    text = " ".join(w["text"] for w in _words(write_sadapay_pdf(stmt)))
    assert "+500.00" in text.replace(" +", " +")
    assert "-200.00" in text


def test_sadapay_pdf_has_no_balance_column():
    stmt = build_statement(seed=2)
    header = " ".join(w["text"] for w in _words(write_sadapay_pdf(stmt))[:40])
    assert "Balance" not in header


def test_meezan_pdf_puts_credit_and_debit_in_separate_columns():
    # The whole point: amounts are UNSIGNED and only x-position tells them apart.
    stmt = build_statement(
        opening=100000,
        rows=[SynthTxn(date(2025, 7, 2), "Money Received", 50000, None),
              SynthTxn(date(2025, 7, 3), "ATM Cash Withdrawal", -20000, None)],
    )
    words = _words(write_meezan_pdf(stmt))
    credit_hdr = next(w for w in words if w["text"] == "Credit")
    debit_hdr = next(w for w in words if w["text"] == "Debit")
    assert credit_hdr["x1"] < debit_hdr["x1"], "Meezan PDF prints Credit before Debit"
    amounts = [w for w in words if w["text"] in ("500.00", "200.00")]
    assert len(amounts) == 2
    assert all("-" not in w["text"] and "+" not in w["text"] for w in amounts)


def test_meezan_pdf_amounts_land_under_their_own_header():
    stmt = build_statement(
        opening=100000,
        rows=[SynthTxn(date(2025, 7, 2), "Money Received", 50000, None),
              SynthTxn(date(2025, 7, 3), "ATM Cash Withdrawal", -20000, None)],
    )
    words = _words(write_meezan_pdf(stmt))
    credit_x1 = next(w for w in words if w["text"] == "Credit")["x1"]
    debit_x1 = next(w for w in words if w["text"] == "Debit")["x1"]
    credit_amt = next(w for w in words if w["text"] == "500.00")
    debit_amt = next(w for w in words if w["text"] == "200.00")
    # Right-aligned within a tolerance of its own header.
    assert abs(credit_amt["x1"] - credit_x1) < 6
    assert abs(debit_amt["x1"] - debit_x1) < 6


def test_repeated_header_on_every_page():
    stmt = build_statement(seed=3, count=60)
    data = write_sadapay_pdf(stmt)
    import io
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        assert len(pdf.pages) >= 2
        for page in pdf.pages:
            assert "Description" in page.extract_text()


@pytest.mark.parametrize("algorithm", ["RC4-128", "AES-128", "AES-256"])
def test_encrypted_pdf_opens_only_with_the_password(algorithm):
    data = encrypt_pdf(write_sadapay_pdf(build_statement(seed=4)), "s3cret",
                       algorithm=algorithm)
    assert len(_words(data, password="s3cret")) > 0
    import io
    with pytest.raises(Exception):
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pdf.pages[0].extract_words()


def test_wrapped_description_spans_two_lines_and_a_page_break():
    data = write_wrapped_description_pdf(build_statement(seed=5))
    import io
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        assert len(pdf.pages) >= 2
        joined = " ".join(p.extract_text() for p in pdf.pages)
    assert "CONTINUATION" in joined


def test_fake_ibans_use_the_reserved_prefix():
    text = " ".join(w["text"] for w in _words(write_sadapay_pdf(build_statement(seed=6))))
    import re
    for m in re.findall(r"PK\d{2}\w*", text):
        assert m.startswith("PK00TEST"), m
