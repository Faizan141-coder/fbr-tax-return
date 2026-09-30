# FBR Aggregator — Phase 2 (PDF Engine + SadaPay) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Read PDF statements — unblocking SadaPay, which is PDF-only — through the same profile abstraction, checks and pipeline the CSV/XLSX engine already uses.

**Architecture:** A positioned-words PDF engine joins the tabular one behind the same `Profile` abstraction, emitting the same `ParseResult` so `reconcile.check_statement`'s five checks apply unchanged. Column geometry is isolated in its own module and tested as arithmetic, because an amount placed in the wrong column is a silent sign inversion. Encrypted files decrypt in memory.

**This is the first of four remaining plans.** Phase 3 (classification and review), phase 4 (internal-transfer matching) and phase 5 (IRIS summary, manual inputs, Excel export) each get their own plan and their own spec sections; splitting them keeps every plan reviewable and each one ships working software. Phase 6 (acceptance against the owner's filed TY2026 return) needs their real figures.

**Tech Stack:** Python 3.14, pdfplumber (PDF text + coordinates + in-memory decryption), pandas, Streamlit, XlsxWriter, pydantic 2, pytest, reportlab (synthetic PDF fixtures), pypdf (encrypted fixtures).

**Spec:** [docs/superpowers/specs/2026-09-27-fbr-aggregator-design.md](../specs/2026-09-27-fbr-aggregator-design.md) — read §5.1, §5.3, §5.4 and §6 before starting. This plan covers spec §11 phase 2.

**Starting point:** commit `4eb9fb5`, 313 tests passing. Phases 0–1 are complete and reviewed: money, model, paths, config schemas, loader, synthetic fixtures, the CSV/XLSX engine, ingest, reconciliation, the pipeline, five shipped profiles, and the Setup/Load/Checks pages.

## Global Constraints

Copied verbatim from the phase 0–1 plan and the spec. Every task's requirements implicitly include this section.

- **Python:** CPython 3.14 via `uv run`. Never the system Python 3.9.6.
- **Money:** integer paisa everywhere. `Decimal` only while parsing text. Never `float` for money. Never `astype(float)` on a money column.
- **Regex:** always Python `re`, applied directly. Never through pandas `.str` methods. In a TOML **single-quoted** (literal) string, write `\s` and `\d` with ONE backslash — doubling them was a real shipped bug. Never `\D` as a separator in a summary pattern; use `[^\d\n]` so it cannot cross a row.
- **Types:** model types are frozen dataclasses. Dates are `datetime.date`.
- **Config validation:** pydantic `ConfigDict(extra="forbid")`. A mistyped key is a loud error.
- **Fail closed:** anything unverifiable is reported, never guessed. A statement failing any check contributes nothing. An unknown value is `None` and renders as "unknown", never `0`.
- **Never compute an IRIS figure from a rate.** Report the tax actually deducted; use rates only to flag a deviation.
- **Privacy — repo:** no real statement data, ever. Fake IBANs use the `PK00TEST` prefix exclusively. The pre-commit hook blocks IBAN- and CNIC-shaped strings including spaced and hyphenated forms.
- **Privacy — runtime:** state in `st.session_state` only, never `st.cache_data`/`st.cache_resource`. No `page_icon=":material/…"`, no map elements. Passwords live only in memory and never on a command line.
- **Privacy — Claude's rule:** Claude reads only `~/fbr-private/dumps/`. Never a real statement, never `dump-candidates/`, never the registry, decisions or manual inputs.
- **Commits:** logical commits, explicit paths, never `git add -A`. Do not push. Do not create PRs. For the `Co-Authored-By:` trailer follow your own session's attribution guidance.

## Review Focus

Input classes the spec implies that no task's happy-path tests would exercise. Each has its test pinned to the task that owns the code.

1. **A password-protected PDF whose password is wrong, missing, or supplied for a file that needs none** — must raise a clear error or proceed cleanly, never crash, and the password must never reach an exception message, a log or a command line. *(Task 3: `test_wrong_password_reprompts_without_leaking_it`, `test_missing_password_on_an_encrypted_pdf_raises_password_error`, `test_password_on_unencrypted_pdf_is_harmless`)*
2. **An unsigned amount drawn between two money columns** — Meezan prints Credit and Debit as separate unsigned columns, so a positional guess inverts the sign while the statement still reconciles against itself. It must become an unresolved row. *(Task 2: `test_an_amount_between_two_columns_is_ambiguous_not_guessed`; Task 3: `test_an_amount_between_two_columns_is_unresolved_not_guessed`)*
3. **A scanned PDF, or one whose fonts have no Unicode mapping** — must be refused with a message naming the reason, never parsed into partial rows. *(Task 3: `test_a_pdf_with_no_text_layer_is_refused`)*
4. **A description wrapping onto a continuation line, including across a page break** — the continuation must join its row and must not become a transaction of its own, which would invent a zero-amount entry. *(Task 1: `test_wrapped_description_spans_two_lines_and_a_page_break`; Task 3: `test_a_wrapped_description_is_joined_onto_its_row`)*
5. **A profile whose summary patterns never match** — a shipped Meezan XLSX profile had doubled backslashes in TOML literal strings and its four summary patterns silently never matched, disabling a reconciliation check while 313 tests passed. A profile's self-test must exercise its summary patterns, not only `parse_row`. *(Task 4: `test_selftest_exercises_summary_patterns`)*

---

## File Structure

| File | Responsibility |
|---|---|
| `tests/fixtures/synth_pdf.py` | reportlab PDF generators (SadaPay signed, Meezan unsigned columns, wrapped descriptions) and encrypted variants |
| `src/fbr/engines/_bands.py` | Pure column-band geometry: header boxes → bands, token → column, ambiguity detection. Free of pdfplumber so it is tested as arithmetic. |
| `src/fbr/engines/pdf.py` | The PDF engine: open (incl. encrypted), find the header on every page, rebuild rows, emit the same `ParseResult` as the tabular engine |
| `profiles/sadapay.pdf.v1.toml` | SadaPay's layout — signed amounts, no balance column, totals only |
| `src/fbr/ingest.py` (modify) | Route PDFs to the PDF engine; carry a password through detection |
| `src/fbr/pipeline.py` (modify) | Accept a per-file password; stop reporting PDFs as `unsupported` |
| `src/fbr/config/loader.py` (modify) | Let a profile's self-test exercise its summary patterns, not only `parse_row` |
| `tools/dump_layout.py` (modify) | Masked dumps for PDFs: word shapes with coordinates |
| `app/pages/2_Load.py` (modify) | Prompt for a PDF password, held in memory only |

---


## Task 1: Synthetic PDF fixtures and in-memory decryption

**Files:**
- Create: `tests/fixtures/synth_pdf.py`
- Test: `tests/test_synth_pdf.py`

**Interfaces:**
- Consumes: `tests/fixtures/synth.py` — `SynthStatement`, `SynthTxn`, `build_statement`; `src/fbr/money.py` — `format_paisa`
- Produces:
  - `write_sadapay_pdf(stmt: SynthStatement, *, pages_hint: int = 0) -> bytes` — signed amounts, Total debit/credit summary, **no balance column**
  - `write_meezan_pdf(stmt: SynthStatement) -> bytes` — unsigned amounts in separate Credit and Debit columns, running balance
  - `encrypt_pdf(data: bytes, password: str, *, algorithm: str = "AES-256") -> bytes`
  - `write_wrapped_description_pdf(stmt: SynthStatement) -> bytes` — a description wrapping onto a second line, and one wrapping across a page break

**Why these two layouts:** SadaPay is the phase-2 target and is the *easy* PDF case (the sign is printed). Meezan PDF is the *hard* case — unsigned amounts in two columns, where only the x-position distinguishes a credit from a debit. Building both now means the engine is exercised against the failure mode that matters before a real statement arrives.

- [ ] **Step 1: Write the failing test**

```python
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
    for m in re.findall(r"PK\w+", text):
        assert m.startswith("PK00TEST"), m
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_synth_pdf.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tests.fixtures.synth_pdf'`

- [ ] **Step 3: Add the dev dependencies**

```bash
cd /Users/faizanhasnaat/Documents/Github/fbr-tax-return
uv add --group dev 'reportlab>=5.0' 'pypdf[crypto]>=6.19'
uv run python -c "import reportlab, pypdf; print(reportlab.Version, pypdf.__version__)"
```

- [ ] **Step 4: Write the implementation**

```python
# tests/fixtures/synth_pdf.py
"""Draw look-alike statement PDFs at exact coordinates.

The engine under test decides whether an amount is a credit or a debit from
its x-position, so the fixtures must control x-positions precisely. reportlab's
canvas does: drawRightString places a string's right edge at a given x, which
is how a bank's right-aligned money column behaves.

No real statement ever enters this repo; every value here is invented.
"""

from __future__ import annotations

import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from fbr.money import format_paisa
from tests.fixtures.synth import SynthStatement

_W, _H = A4
_LEFT = 40
_TOP = _H - 60
_ROW_H = 16
_BOTTOM = 70

# Column right edges for the Meezan-style layout. Credit before Debit, which
# is the reverse of Meezan's CSV export - the difference the engine must not
# paper over.
_MZ_DATE_X = 40          # left-aligned
_MZ_DESC_X = 130         # left-aligned
_MZ_CREDIT_X = 400       # right-aligned
_MZ_DEBIT_X = 470        # right-aligned
_MZ_BALANCE_X = 555      # right-aligned


def _new_canvas() -> tuple[canvas.Canvas, io.BytesIO]:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 8)
    return c, buf


def _finish(c: canvas.Canvas, buf: io.BytesIO) -> bytes:
    c.save()
    return buf.getvalue()


def write_sadapay_pdf(stmt: SynthStatement, *, pages_hint: int = 0) -> bytes:
    """SadaPay: Date | Description | signed amount. No balance column at all,
    and only Total debit / Total credit to reconcile against."""
    c, buf = _new_canvas()

    def header(y: float) -> float:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(_LEFT, y, "Account Statement")
        c.setFont("Helvetica", 8)
        y -= _ROW_H
        c.drawString(_LEFT, y, f"Account Currency  {stmt.account_id}  PKR")
        y -= _ROW_H
        c.drawString(_LEFT, y, f"Total debit  {format_paisa(stmt.total_debit)}")
        y -= _ROW_H
        c.drawString(_LEFT, y, f"Total credit  {format_paisa(stmt.total_credit)}")
        y -= _ROW_H
        c.drawString(
            _LEFT, y,
            f"Statement Period  {stmt.period_start:%d %b, %Y} to {stmt.period_end:%d %b, %Y}",
        )
        y -= _ROW_H * 1.5
        c.setFont("Helvetica-Bold", 8)
        c.drawString(_MZ_DATE_X, y, "Date")
        c.drawString(_MZ_DESC_X, y, "Description")
        c.drawRightString(_MZ_CREDIT_X, y, "Debit/Credit")
        c.setFont("Helvetica", 8)
        return y - _ROW_H

    y = header(_TOP)
    for t in stmt.txns:
        if y < _BOTTOM:
            c.showPage()
            c.setFont("Helvetica", 8)
            y = header(_TOP)
        c.drawString(_MZ_DATE_X, y, f"{t.date:%d %b, %Y}")
        c.drawString(_MZ_DESC_X, y, t.description[:48])
        sign = "+" if t.amount > 0 else "-"
        c.drawRightString(_MZ_CREDIT_X, y, f"{sign}{format_paisa(abs(t.amount))}")
        y -= _ROW_H

    c.drawString(_LEFT, max(y - _ROW_H, 40),
                 "This is a system generated statement  Page 1")
    return _finish(c, buf)


def write_meezan_pdf(stmt: SynthStatement) -> bytes:
    """Meezan: Booking Date | Description | Credit | Debit | Available Balance.

    Amounts are UNSIGNED and sit in separate right-aligned columns, so only the
    x-position distinguishes a credit from a debit. This is the layout that
    would silently invert every sign if the engine guessed.
    """
    c, buf = _new_canvas()

    def header(y: float) -> float:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(_LEFT, y, "Meezan Bank  Account Statement")
        c.setFont("Helvetica", 8)
        y -= _ROW_H
        c.drawString(_LEFT, y, f"Account  {stmt.account_id}  {stmt.account_title}")
        y -= _ROW_H
        c.drawString(_LEFT, y, f"OPENING BALANCE  PKR {format_paisa(stmt.opening)}")
        y -= _ROW_H
        c.drawString(_LEFT, y, f"CLOSING BALANCE  PKR {format_paisa(stmt.closing)}")
        y -= _ROW_H
        c.drawString(
            _LEFT, y,
            f"From Date  {stmt.period_start:%d %b %Y}  To Date  {stmt.period_end:%d %b %Y}",
        )
        y -= _ROW_H * 1.5
        c.setFont("Helvetica-Bold", 8)
        c.drawString(_MZ_DATE_X, y, "Booking Date")
        c.drawString(_MZ_DESC_X, y, "Description")
        c.drawRightString(_MZ_CREDIT_X, y, "Credit")
        c.drawRightString(_MZ_DEBIT_X, y, "Debit")
        c.drawRightString(_MZ_BALANCE_X, y, "Available Balance")
        c.setFont("Helvetica", 8)
        return y - _ROW_H

    y = header(_TOP)
    for t in stmt.txns:
        if y < _BOTTOM:
            c.showPage()
            c.setFont("Helvetica", 8)
            y = header(_TOP)
        c.drawString(_MZ_DATE_X, y, f"{t.date:%d %b %Y}")
        c.drawString(_MZ_DESC_X, y, t.description[:42])
        amount = format_paisa(abs(t.amount))
        if t.amount > 0:
            c.drawRightString(_MZ_CREDIT_X, y, amount)
        else:
            c.drawRightString(_MZ_DEBIT_X, y, amount)
        c.drawRightString(_MZ_BALANCE_X, y, format_paisa(t.balance_after))
        y -= _ROW_H
    return _finish(c, buf)


def write_wrapped_description_pdf(stmt: SynthStatement) -> bytes:
    """A Meezan-style PDF whose descriptions wrap onto a continuation line,
    including one that wraps across a page break."""
    c, buf = _new_canvas()

    def header(y: float) -> float:
        c.setFont("Helvetica-Bold", 8)
        c.drawString(_MZ_DATE_X, y, "Booking Date")
        c.drawString(_MZ_DESC_X, y, "Description")
        c.drawRightString(_MZ_CREDIT_X, y, "Credit")
        c.drawRightString(_MZ_DEBIT_X, y, "Debit")
        c.drawRightString(_MZ_BALANCE_X, y, "Available Balance")
        c.setFont("Helvetica", 8)
        return y - _ROW_H

    c.setFont("Helvetica", 8)
    c.drawString(_LEFT, _TOP, f"OPENING BALANCE  PKR {format_paisa(stmt.opening)}")
    y = header(_TOP - _ROW_H * 2)

    for i, t in enumerate(stmt.txns):
        # Force the last row to start just above the page bottom so its
        # continuation line lands on the next page.
        if i == len(stmt.txns) - 1:
            y = _BOTTOM + 2
        c.drawString(_MZ_DATE_X, y, f"{t.date:%d %b %Y}")
        c.drawString(_MZ_DESC_X, y, t.description[:42])
        amount = format_paisa(abs(t.amount))
        if t.amount > 0:
            c.drawRightString(_MZ_CREDIT_X, y, amount)
        else:
            c.drawRightString(_MZ_DEBIT_X, y, amount)
        c.drawRightString(_MZ_BALANCE_X, y, format_paisa(t.balance_after))
        y -= _ROW_H
        # The continuation line: description text only, no date, no amount.
        if y < _BOTTOM:
            c.showPage()
            c.setFont("Helvetica", 8)
            y = header(_TOP)
        c.drawString(_MZ_DESC_X, y, f"CONTINUATION STAN {100000 + i}")
        y -= _ROW_H
    return _finish(c, buf)


def encrypt_pdf(data: bytes, password: str, *, algorithm: str = "AES-256") -> bytes:
    """Encrypt an existing PDF, so the engine's password path has real input."""
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(io.BytesIO(data))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(password, algorithm=algorithm)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_synth_pdf.py -v`
Expected: PASS. If `test_repeated_header_on_every_page` gets only one page, raise `count` until the rows overflow; do not weaken the assertion. If an `encrypt_pdf` algorithm name is rejected, print `pypdf`'s accepted values and use the equivalent — record which in your report.

- [ ] **Step 6: Commit**

```bash
git add tests/fixtures/synth_pdf.py tests/test_synth_pdf.py pyproject.toml uv.lock
git commit -m "$(cat <<'EOF'
test: add synthetic statement PDFs and encrypted variants

reportlab draws at exact coordinates, so the column-band geometry the PDF
engine depends on can be tested against a page whose geometry we chose.
Covers SadaPay (signed, no balance column), Meezan (unsigned amounts in
separate Credit/Debit columns), wrapped descriptions across a page break,
and RC4/AES-128/AES-256 encryption.
EOF
)"
```

---

## Task 2: Column bands — the geometry, without a PDF

**Files:**
- Create: `src/fbr/engines/_bands.py`
- Test: `tests/test_bands.py`

**Interfaces:**
- Consumes: nothing (pure geometry)
- Produces:
  - `Word(text: str, x0: float, x1: float, top: float, bottom: float)` — a frozen dataclass; pdfplumber dicts convert with `Word.from_dict`
  - `Band(role: str, x0: float, x1: float, align: str)` — for a right- or centre-aligned column `x0..x1` is the header label's own box; for a left-aligned text column `x1` extends to where the next column starts
  - `build_bands(header: list[Word], roles: dict[str, str], aligns: dict[str, str]) -> tuple[Band, ...]` — `roles` maps a role name to the header label that marks it
  - `assign(word: Word, bands: tuple[Band, ...], *, tolerance: float = 6.0) -> str | None` — **two stages.** A numeric (right- or centre-aligned) column claims the word by edge proximity, which is what separates Meezan's unsigned Credit from its Debit. Only if no numeric column claims it does a left-aligned text column claim it by *containment*, because a description spans far more than a tolerance's width. Returns `None` when nothing claims it, or when two numeric columns are equally close.
  - `group_lines(words: list[Word], *, y_tolerance: float = 3.0) -> list[list[Word]]` — visual lines in printed order
  - `class BandError(RuntimeError)`

**Why a separate module:** column assignment is the single most dangerous computation in the whole tool — get it wrong on Meezan and every sign inverts while the statement still reconciles against itself. Isolating it from pdfplumber means it can be tested exhaustively with plain numbers.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_bands.py
"""Column geometry, tested with numbers rather than PDFs.

An amount in the wrong column is a sign inversion, and a sign inversion on a
bank statement still reconciles against itself - which is why this is tested
harder than its size suggests.
"""
import pytest

from fbr.engines._bands import Band, BandError, Word, assign, build_bands, group_lines

# A Meezan-style header: Credit at x1=400, Debit at x1=470, Balance at x1=555.
HEADER = [
    Word("Booking", 40, 72, 100, 108), Word("Date", 74, 92, 100, 108),
    Word("Description", 130, 178, 100, 108),
    Word("Credit", 378, 400, 100, 108),
    Word("Debit", 450, 470, 100, 108),
    Word("Available", 500, 534, 100, 108), Word("Balance", 536, 555, 100, 108),
]
ROLES = {"date": "Booking Date", "description": "Description",
         "credit": "Credit", "debit": "Debit", "balance": "Available Balance"}
ALIGNS = {"date": "left", "description": "left", "credit": "right",
          "debit": "right", "balance": "right"}


def _bands():
    return build_bands(HEADER, ROLES, ALIGNS)


def test_builds_one_band_per_role():
    assert {b.role for b in _bands()} == set(ROLES)


def test_multiword_header_label_is_matched():
    # "Booking Date" and "Available Balance" each span two words.
    bands = {b.role: b for b in _bands()}
    assert bands["date"].x0 <= 40
    assert bands["balance"].x1 >= 555


def test_missing_header_label_raises_naming_it():
    with pytest.raises(BandError, match="Credit"):
        build_bands([w for w in HEADER if w.text != "Credit"], ROLES, ALIGNS)


def test_right_aligned_amount_goes_to_the_nearest_header_right_edge():
    assert assign(Word("500.00", 372, 400, 120, 128), _bands()) == "credit"
    assert assign(Word("200.00", 442, 470, 120, 128), _bands()) == "debit"


def test_every_word_of_a_multiword_description_assigns():
    # A tolerance-only assign() claims the first word and orphans the rest,
    # which turns every row into an unresolved row and fails every statement.
    # A text column must claim by containment, not by edge proximity.
    bands = _bands()
    for i, text in enumerate(["TRANSF", "CR/ICT/", "Top-up", "from", "SOMEONE"]):
        x0 = 130 + i * 36
        assert assign(Word(text, x0, x0 + 30, 120, 128), bands) == "description", text


def test_a_long_description_stops_at_the_first_money_column():
    # It must not bleed into Credit, whose band starts at 378.
    bands = _bands()
    assert assign(Word("tail", 360, 376, 120, 128), bands) == "description"
    assert assign(Word("tail", 380, 396, 120, 128), bands) != "description"


def test_a_date_assigns_across_its_own_width():
    bands = _bands()
    assert assign(Word("01", 40, 52, 120, 128), bands) == "date"
    assert assign(Word("Jul", 54, 70, 120, 128), bands) == "date"
    assert assign(Word("2025", 72, 90, 120, 128), bands) == "date"


def test_a_money_column_still_wins_over_the_text_span_containing_it():
    # Credit's band sits inside the description column's span; the numeric
    # edge test must be tried first or every amount becomes description text.
    assert assign(Word("500.00", 372, 400, 120, 128), _bands()) == "credit"


def test_an_amount_between_two_columns_is_ambiguous_not_guessed():
    # x1 = 435 sits 35pt from Credit's 400 and 35pt from Debit's 470.
    assert assign(Word("300.00", 407, 435, 120, 128), _bands()) is None


def test_an_amount_outside_every_band_is_ambiguous():
    assert assign(Word("999.00", 700, 740, 120, 128), _bands()) is None


def test_tolerance_is_respected_at_its_edge():
    bands = _bands()
    assert assign(Word("1.00", 380, 405, 120, 128), bands, tolerance=6.0) == "credit"
    assert assign(Word("1.00", 380, 412, 120, 128), bands, tolerance=6.0) is None


def test_left_aligned_text_assigns_by_left_edge():
    assert assign(Word("ATM", 130, 150, 120, 128), _bands()) == "description"
    assert assign(Word("01", 40, 52, 120, 128), _bands()) == "date"


def test_group_lines_keeps_printed_order():
    words = [
        Word("row2", 40, 60, 140, 148),
        Word("row1", 40, 60, 120, 128),
        Word("row1b", 130, 160, 121, 129),
    ]
    lines = group_lines(words)
    assert [w.text for w in lines[0]] == ["row1", "row1b"]
    assert [w.text for w in lines[1]] == ["row2"]


def test_group_lines_sorts_each_line_left_to_right():
    words = [Word("b", 200, 220, 120, 128), Word("a", 40, 60, 120, 128)]
    assert [w.text for w in group_lines(words)[0]] == ["a", "b"]


def test_y_tolerance_merges_slightly_offset_words():
    words = [Word("a", 40, 60, 120.0, 128.0), Word("b", 200, 220, 122.0, 130.0)]
    assert len(group_lines(words, y_tolerance=3.0)) == 1
    assert len(group_lines(words, y_tolerance=1.0)) == 2


def test_word_converts_from_a_pdfplumber_dict():
    w = Word.from_dict({"text": "x", "x0": 1.0, "x1": 2.0, "top": 3.0, "bottom": 4.0})
    assert (w.text, w.x0, w.x1, w.top, w.bottom) == ("x", 1.0, 2.0, 3.0, 4.0)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_bands.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'fbr.engines._bands'`

- [ ] **Step 3: Write the implementation**

```python
# src/fbr/engines/_bands.py
"""Column-band geometry for the PDF engine.

A bank's money columns are right-aligned, so an amount's RIGHT edge lines up
with its header's right edge. That is the signal used here. A token that is
outside every band, or equally close to two, returns None and becomes an
unresolved row - never a guess, because a guess on Meezan's unsigned
Credit/Debit pair is a silent sign inversion.

No pdfplumber import: this is arithmetic, and it is tested as arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass


class BandError(RuntimeError):
    """The header does not contain a label the profile requires."""


@dataclass(frozen=True, slots=True)
class Word:
    text: str
    x0: float
    x1: float
    top: float
    bottom: float

    @classmethod
    def from_dict(cls, d: dict) -> "Word":
        return cls(d["text"], float(d["x0"]), float(d["x1"]),
                   float(d["top"]), float(d["bottom"]))


@dataclass(frozen=True, slots=True)
class Band:
    role: str
    x0: float
    x1: float
    align: str


def _find_label(header: list[Word], label: str) -> tuple[float, float]:
    """Locate a possibly multi-word header label, returning its x span."""
    wanted = label.split()
    lowered = [w.text.strip().lower() for w in header]
    target = [t.lower() for t in wanted]
    for i in range(len(lowered) - len(target) + 1):
        if lowered[i:i + len(target)] == target:
            return header[i].x0, header[i + len(target) - 1].x1
    raise BandError(f"header has no label {label!r}; header reads "
                    f"{' '.join(w.text for w in header)!r}")


def build_bands(
    header: list[Word], roles: dict[str, str], aligns: dict[str, str]
) -> tuple[Band, ...]:
    """Build one band per role from the header row's word boxes.

    A numeric column keeps its header label's own narrow box, because an
    amount is matched on its right edge. A text column instead spans from its
    own left edge to wherever the next column begins: a description is many
    words wide, and matching it on an edge would orphan every word but the
    first.
    """
    raw = sorted(
        (
            (role, *_find_label(header, label), aligns.get(role, "right"))
            for role, label in roles.items()
        ),
        key=lambda r: r[1],
    )
    bands: list[Band] = []
    for i, (role, x0, x1, align) in enumerate(raw):
        if align == "left":
            next_x0 = raw[i + 1][1] if i + 1 < len(raw) else float("inf")
            bands.append(Band(role, x0, next_x0, align))
        else:
            bands.append(Band(role, x0, x1, align))
    return tuple(bands)


def _edge(word: Word, align: str) -> float:
    if align == "left":
        return word.x0
    if align == "center":
        return (word.x0 + word.x1) / 2
    return word.x1


def _band_edge(band: Band) -> float:
    if band.align == "center":
        return (band.x0 + band.x1) / 2
    return band.x1


def assign(
    word: Word, bands: tuple[Band, ...], *, tolerance: float = 6.0
) -> str | None:
    """Return the role this word belongs to, or None when it is not clear.

    Two stages, and the order matters:

    1. A numeric column claims the word by edge proximity. This is the test
       that separates Meezan's unsigned Credit from its Debit, and it runs
       first because a money column's band sits inside the description
       column's span - reversed, every amount would be read as description
       text.
    2. Otherwise a text column claims it by containment, since a description
       is many words wide.

    None is a deliberate outcome: the caller turns it into an unresolved row,
    which fails the statement. That is far better than assigning an amount to
    the wrong side of the ledger, which reconciles against itself and reports
    a confidently wrong figure.
    """
    scored: list[tuple[float, str]] = []
    for band in bands:
        if band.align == "left":
            continue
        distance = abs(_edge(word, band.align) - _band_edge(band))
        if distance <= tolerance:
            scored.append((distance, band.role))
    if scored:
        scored.sort()
        if len(scored) > 1 and abs(scored[0][0] - scored[1][0]) < 1e-9:
            return None          # equally close to two money columns
        return scored[0][1]

    for band in bands:
        if band.align == "left" and band.x0 - tolerance <= word.x0 < band.x1:
            return band.role
    return None


def group_lines(
    words: list[Word], *, y_tolerance: float = 3.0
) -> list[list[Word]]:
    """Group words into visual lines, in printed order, each sorted left to right.

    Printed order, not sorted-by-date order: a bank may list same-day rows by
    posting sequence, and the running-balance check walks the printed sequence.
    """
    lines: list[list[Word]] = []
    for word in sorted(words, key=lambda w: (round(w.top, 1), w.x0)):
        for line in lines:
            if abs(line[0].top - word.top) <= y_tolerance:
                line.append(word)
                break
        else:
            lines.append([word])
    for line in lines:
        line.sort(key=lambda w: w.x0)
    return lines
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_bands.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/fbr/engines/_bands.py tests/test_bands.py
git commit -m "$(cat <<'EOF'
feat: add column-band geometry for the PDF engine

Right-aligned money columns are matched on their right edges. A token
outside every band, or equally close to two, returns None so the caller
raises an unresolved row rather than guessing - a guess on Meezan's
unsigned Credit/Debit pair is a silent sign inversion.

Kept free of pdfplumber so it is tested as arithmetic.
EOF
)"
```

---

## Task 3: The PDF engine

**Files:**
- Create: `src/fbr/engines/pdf.py`
- Test: `tests/test_pdf_engine.py`

**Interfaces:**
- Consumes: `fbr.engines._bands` (Task 2); `fbr.money` — `parse_paisa`, `AmountError`; `fbr.model` — `Transaction`, `Provenance`, `Document`, `DocumentSummary`, `assign_occurrences`, `make_txn_id`, `tax_year_for`; `fbr.config.schema_profile` — `Profile`; `fbr.engines.tabular` — `ParseResult`, `UnresolvedRow`, `ParseError` (reused, not redefined)
- Produces:
  - `parse_pdf(data: bytes, profile: Profile, *, sha256: str, filename: str, account_id: str | None, password: str | None = None) -> ParseResult`
  - `pdf_row_samples(data: bytes, profile: Profile, *, password: str | None = None, limit: int = 5) -> list[dict[str, str]]` — labelled rows, so a PDF profile's `selftest` can run through `parse_row`
  - `class PdfPasswordError(ParseError)`, `class PdfNotTextual(ParseError)`

**Reuses `ParseResult` and `UnresolvedRow` from the tabular engine on purpose** — `reconcile.check_statement` already consumes them, and a second parallel type would mean a second set of checks.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pdf_engine.py
"""The PDF engine, exercised against PDFs whose geometry we chose.

Two behaviours carry the weight: an unsigned amount is assigned to Credit or
Debit by position and never by guess, and anything unclear becomes an
UnresolvedRow so the statement fails rather than reporting a wrong figure.
"""
from datetime import date

import pytest

from fbr.config.schema_profile import Profile
from fbr.engines.pdf import PdfNotTextual, PdfPasswordError, parse_pdf, pdf_row_samples
from fbr.engines.tabular import parse_row
from fbr.reconcile import check_statement, statement_usable
from tests.fixtures.synth import SynthTxn, build_statement
from tests.fixtures.synth_pdf import (
    encrypt_pdf,
    write_meezan_pdf,
    write_sadapay_pdf,
    write_wrapped_description_pdf,
)

SADAPAY = Profile.model_validate({
    "id": "sadapay.pdf.v1", "institution": "SadaPay", "container": "pdf",
    "valid_from": date(2025, 7, 1),
    "detect": {"header_contains": ["Date", "Description", "Debit/Credit"]},
    "columns": {"date": "Date", "description": "Description",
                "amount": "Debit/Credit",
                "align": {"amount": "right"}},
    "formats": {"dates": ["%d %b, %Y"], "sign": "signed"},
    "rows": {"footer": [r"(?i)system generated"], "row_anchor": "date"},
    "summary": {
        "total_debit": r"(?i)Total\s+debit[^\d\n]+?(?P<value>-?[\d,]+\.\d{2})",
        "total_credit": r"(?i)Total\s+credit[^\d\n]+?(?P<value>-?[\d,]+\.\d{2})",
        "period_from": r"(?i)Statement\s+Period[^\d\n]+?(?P<value>\d{2} \w{3}, \d{4})",
        "period_to": r"(?i)to\s+(?P<value>\d{2} \w{3}, \d{4})",
    },
    "balance": {"semantics": "none"},
    "selftest": {"cases": [{
        "row": {"Date": "01 Jul, 2025", "Description": "Top-up",
                "Debit/Credit": "+1,000.00"},
        "expect_date": date(2025, 7, 1), "expect_amount": 100000}]},
})

MEEZAN_PDF = Profile.model_validate({
    "id": "meezan.pdf.v1", "institution": "Meezan Bank Limited", "container": "pdf",
    "valid_from": date(2025, 7, 1),
    "detect": {"header_contains": ["Booking Date", "Credit", "Debit"]},
    "columns": {"date": "Booking Date", "description": "Description",
                "credit": "Credit", "debit": "Debit",
                "balance": "Available Balance",
                "align": {"credit": "right", "debit": "right", "balance": "right"}},
    "formats": {"dates": ["%d %b %Y"], "sign": "columns"},
    "rows": {"row_anchor": "date", "continuation": "below"},
    "summary": {
        "opening": r"(?i)OPENING\s+BALANCE[^\d\n]+?(?P<value>-?[\d,]+\.\d{2})",
        "closing": r"(?i)CLOSING\s+BALANCE[^\d\n]+?(?P<value>-?[\d,]+\.\d{2})",
        "period_from": r"(?i)From\s+Date[^\d\n]+?(?P<value>\d{2} \w{3} \d{4})",
        "period_to": r"(?i)To\s+Date[^\d\n]+?(?P<value>\d{2} \w{3} \d{4})",
    },
    "balance": {"semantics": "running", "kind": "available"},
    "selftest": {"cases": [{
        "row": {"Booking Date": "01 Jul 2025", "Description": "Top-up",
                "Credit": "1,000.00", "Debit": "", "Available Balance": "1,000.00"},
        "expect_date": date(2025, 7, 1), "expect_amount": 100000}]},
})


def _parse(data, profile, password=None, account_id="acct"):
    return parse_pdf(data, profile, sha256="a" * 64, filename="x.pdf",
                     account_id=account_id, password=password)


def test_parses_a_sadapay_statement():
    stmt = build_statement(seed=11)
    res = _parse(write_sadapay_pdf(stmt), SADAPAY)
    assert res.unresolved == ()
    assert [t.amount for t in res.transactions] == [t.amount for t in stmt.txns]


def test_reads_sadapay_printed_totals_and_period():
    stmt = build_statement(seed=12)
    res = _parse(write_sadapay_pdf(stmt), SADAPAY)
    assert res.document.summary.total_credit == stmt.total_credit
    assert res.document.summary.total_debit == stmt.total_debit
    assert res.document.summary.period_start == stmt.period_start


def test_sadapay_reconciles_against_its_printed_totals():
    stmt = build_statement(seed=13)
    res = _parse(write_sadapay_pdf(stmt), SADAPAY)
    checks = check_statement(res, SADAPAY)
    assert statement_usable(checks)
    assert any(c.kind == "printed_totals" and c.status == "pass" for c in checks)


def test_meezan_unsigned_columns_get_the_right_sign_from_position():
    # The core risk: a positional mistake here inverts every sign while the
    # statement still reconciles against itself.
    stmt = build_statement(
        opening=100000,
        rows=[SynthTxn(date(2025, 7, 2), "Money Received", 50000, None),
              SynthTxn(date(2025, 7, 3), "ATM Cash Withdrawal", -20000, None)],
    )
    res = _parse(write_meezan_pdf(stmt), MEEZAN_PDF)
    assert [t.amount for t in res.transactions] == [50000, -20000]
    assert {t.provenance.sign_source for t in res.transactions} == {"column"}


def test_meezan_pdf_running_balance_reconciles():
    stmt = build_statement(seed=14, opening=500000)
    res = _parse(write_meezan_pdf(stmt), MEEZAN_PDF)
    checks = check_statement(res, MEEZAN_PDF)
    assert statement_usable(checks), [c for c in checks if c.status == "fail"]
    assert any(c.kind == "running_balance" and c.status == "pass" for c in checks)


def test_a_repeated_header_on_later_pages_is_not_a_transaction():
    stmt = build_statement(seed=15, count=60)
    res = _parse(write_sadapay_pdf(stmt), SADAPAY)
    assert len(res.transactions) == len(stmt.txns)


def test_a_footer_line_is_not_a_transaction():
    stmt = build_statement(seed=16)
    res = _parse(write_sadapay_pdf(stmt), SADAPAY)
    assert not any("system generated" in t.description.lower()
                   for t in res.transactions)


def test_a_wrapped_description_is_joined_onto_its_row():
    res = _parse(write_wrapped_description_pdf(build_statement(seed=17, count=4)),
                 MEEZAN_PDF)
    assert res.unresolved == ()
    assert any("CONTINUATION" in t.description for t in res.transactions)
    # The continuation line must not become its own transaction.
    assert len([t for t in res.transactions if t.description.startswith("CONTINUATION")]) == 0


def test_rows_stay_in_printed_order():
    stmt = build_statement(
        opening=100000,
        rows=[SynthTxn(date(2025, 7, 9), "Later first", 50000, None),
              SynthTxn(date(2025, 7, 5), "Earlier second", -20000, None)],
    )
    res = _parse(write_meezan_pdf(stmt), MEEZAN_PDF)
    assert [t.date for t in res.transactions] == [date(2025, 7, 9), date(2025, 7, 5)]


def test_an_encrypted_pdf_opens_with_its_password():
    stmt = build_statement(seed=18)
    data = encrypt_pdf(write_sadapay_pdf(stmt), "s3cret")
    res = _parse(data, SADAPAY, password="s3cret")
    assert len(res.transactions) == len(stmt.txns)


def test_wrong_password_reprompts_without_leaking_it():
    # Review Focus #1: the password must not reach the exception text.
    data = encrypt_pdf(write_sadapay_pdf(build_statement(seed=19)), "s3cret")
    with pytest.raises(PdfPasswordError) as exc:
        _parse(data, SADAPAY, password="wrong-pass-9999")
    message = str(exc.value)
    assert "wrong-pass-9999" not in message
    assert "s3cret" not in message
    assert "password" in message.lower()


def test_missing_password_on_an_encrypted_pdf_raises_password_error():
    data = encrypt_pdf(write_sadapay_pdf(build_statement(seed=20)), "s3cret")
    with pytest.raises(PdfPasswordError):
        _parse(data, SADAPAY, password=None)


def test_password_on_unencrypted_pdf_is_harmless():
    # Review Focus #1: an owner who types a password for a file that needs none
    # must not be punished for it.
    stmt = build_statement(seed=21)
    res = _parse(write_sadapay_pdf(stmt), SADAPAY, password="irrelevant")
    assert len(res.transactions) == len(stmt.txns)


def test_a_pdf_with_no_text_layer_is_refused():
    minimal = (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
               b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
               b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
               b"trailer<</Root 1 0 R>>")
    with pytest.raises((PdfNotTextual, Exception)):
        _parse(minimal, SADAPAY)


def test_an_amount_between_two_columns_is_unresolved_not_guessed():
    # Draw an amount deliberately midway between Credit and Debit.
    import io
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 8)
    y = A4[1] - 60
    c.drawString(40, y, "OPENING BALANCE  PKR 1,000.00")
    y -= 24
    c.setFont("Helvetica-Bold", 8)
    c.drawString(40, y, "Booking Date"); c.drawString(130, y, "Description")
    c.drawRightString(400, y, "Credit"); c.drawRightString(470, y, "Debit")
    c.drawRightString(555, y, "Available Balance")
    c.setFont("Helvetica", 8)
    y -= 16
    c.drawString(40, y, "02 Jul 2025"); c.drawString(130, y, "Ambiguous")
    c.drawRightString(435, y, "500.00")          # midway between 400 and 470
    c.drawRightString(555, y, "1,500.00")
    c.save()
    res = _parse(buf.getvalue(), MEEZAN_PDF)
    assert res.transactions == ()
    assert len(res.unresolved) == 1
    assert "ambiguous" in res.unresolved[0].reason.lower()


def test_pdf_row_samples_feed_parse_row_for_a_selftest():
    stmt = build_statement(seed=22)
    samples = pdf_row_samples(write_sadapay_pdf(stmt), SADAPAY, limit=3)
    assert samples and set(samples[0]) >= {"Date", "Description", "Debit/Credit"}
    d, amount = parse_row(SADAPAY, samples[0])
    assert d == stmt.txns[0].date
    assert amount == stmt.txns[0].amount


def test_transactions_carry_page_and_position_provenance():
    res = _parse(write_sadapay_pdf(build_statement(seed=23)), SADAPAY)
    loc = res.transactions[0].provenance.locator
    assert loc.startswith("page:") and ",y:" in loc
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_pdf_engine.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'fbr.engines.pdf'`

- [ ] **Step 3: Write the implementation**

```python
# src/fbr/engines/pdf.py
"""PDF statement engine: positioned words in, typed transactions out.

Emits the same ParseResult the tabular engine does, so reconcile.py's five
checks apply unchanged. Two rules carry the weight:

  * An unsigned amount's column is decided by geometry (_bands), never by
    guess. Ambiguity becomes an UnresolvedRow, which fails the statement.
  * Rows keep printed order, because the running-balance check walks the
    printed sequence.

Encrypted files are decrypted in memory with a password held only in a local
variable - never written to disk, a log, or a command line. The password is
also kept out of every exception message, since those get displayed.
"""

from __future__ import annotations

import io
import re
from datetime import date, datetime

import pdfplumber

from fbr.config.schema_profile import Profile
from fbr.engines._bands import BandError, Word, assign, build_bands, group_lines
from fbr.engines.tabular import ParseError, ParseResult, UnresolvedRow
from fbr.model import (
    Document,
    DocumentSummary,
    Provenance,
    Transaction,
    assign_occurrences,
    make_txn_id,
    tax_year_for,
)
from fbr.money import AmountError, parse_paisa

_EMPTY = {"", "-", "--", "—", "–", "n/a", "na", "nil"}


class PdfPasswordError(ParseError):
    """The file is encrypted and the supplied password did not open it."""


class PdfNotTextual(ParseError):
    """The file has no extractable text layer, or unmapped fonts."""


def _open(data: bytes, password: str | None):
    """Open a PDF, decrypting in memory. Never puts the password in an error."""
    try:
        return pdfplumber.open(io.BytesIO(data), password=password or "")
    except Exception as exc:                        # noqa: BLE001
        text = str(exc).lower()
        if "password" in text or "decrypt" in text or "incorrect" in text:
            raise PdfPasswordError(
                "this PDF is encrypted and the password did not open it; "
                "check the password and try again"
            ) from None                             # `from None`: the original
                                                    # may echo the password
        raise ParseError(f"cannot open this PDF: {type(exc).__name__}") from None


def _page_words(page) -> list[Word]:
    raw = page.extract_words(use_text_flow=False, keep_blank_chars=False,
                             extra_attrs=[])
    return [Word.from_dict(w) for w in raw]


def _labels(spec) -> list[str]:
    if spec is None:
        return []
    return [spec] if isinstance(spec, str) else list(spec)


def _roles_and_aligns(profile: Profile) -> tuple[dict[str, str], dict[str, str]]:
    roles: dict[str, str] = {}
    for role in ("date", "value_date", "description", "reference", "debit",
                 "credit", "amount", "balance", "type"):
        labels = _labels(getattr(profile.columns, role, None))
        if labels:
            roles[role] = labels[0]
    align = profile.columns.align
    aligns = {
        "date": "left", "value_date": "left", "description": "left",
        "reference": "left", "type": "left",
        "debit": align.debit, "credit": align.credit,
        "amount": align.amount, "balance": align.balance,
    }
    return roles, aligns


def _find_header(lines: list[list[Word]], profile: Profile) -> int | None:
    wanted = [t.strip().lower() for t in profile.detect.header_contains]
    for i, line in enumerate(lines):
        joined = " ".join(w.text for w in line).lower()
        if all(t in joined for t in wanted):
            return i
    return None


def _parse_date(text: str, profile: Profile) -> date:
    for fmt in profile.formats.dates:
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"date {text!r} matches none of {profile.formats.dates}")


def _strip_suffix(text: str, profile: Profile) -> tuple[str, int]:
    cleaned = text.strip()
    for token in profile.formats.credit_tokens:
        if cleaned.lower().endswith(token.lower()):
            return cleaned[: -len(token)].strip(" ."), 1
    for token in profile.formats.debit_tokens:
        if cleaned.lower().endswith(token.lower()):
            return cleaned[: -len(token)].strip(" ."), -1
    raise ValueError(f"amount {text!r} carries no Dr/Cr token")


def _amount_from_cells(cells: dict[str, str], profile: Profile) -> tuple[int, str]:
    mode = profile.formats.sign
    dec = profile.formats.decimals
    if mode == "columns":
        debit, credit = cells.get("debit", ""), cells.get("credit", "")
        d_empty = debit.strip().lower() in _EMPTY
        c_empty = credit.strip().lower() in _EMPTY
        if d_empty and c_empty:
            raise ValueError("row has no amount in either the debit or credit column")
        if not d_empty and not c_empty:
            raise ValueError(f"row has amounts in both columns: {debit!r} and {credit!r}")
        if c_empty:
            return -parse_paisa(debit, decimals=dec), "column"
        return parse_paisa(credit, decimals=dec), "column"
    raw = cells.get("amount", "")
    if raw.strip().lower() in _EMPTY:
        raise ValueError("row has no amount")
    if mode == "suffix":
        number, direction = _strip_suffix(raw, profile)
        return direction * abs(parse_paisa(number, decimals=dec)), "suffix"
    return parse_paisa(raw, decimals=dec), "signed"


def _read_summary(text: str, profile: Profile) -> DocumentSummary:
    found: dict[str, object] = {}
    for name, pattern in profile.summary.compiled().items():
        m = pattern.search(text)
        if not m:
            continue
        value = m.group("value")
        if name in ("opening", "closing", "total_credit", "total_debit"):
            try:
                found[name] = parse_paisa(value, decimals=profile.formats.decimals)
            except AmountError:
                continue
        elif name in ("period_from", "period_to"):
            try:
                found["period_start" if name == "period_from" else "period_end"] = (
                    _parse_date(value, profile)
                )
            except ValueError:
                continue
        else:
            found["account_identifier"] = value.strip()
    return DocumentSummary(**found)          # type: ignore[arg-type]


def _rows_from_pdf(
    pdf, profile: Profile
) -> tuple[list[dict], list[UnresolvedRow], str, int]:
    """Walk every page, returning staged row dicts and unresolved rows."""
    roles, aligns = _roles_and_aligns(profile)
    skip_res = [re.compile(p) for p in profile.rows.skip]
    summary_res = [re.compile(p) for p in profile.rows.summary]
    footer_res = [re.compile(p) for p in profile.rows.footer]

    staged: list[dict] = []
    unresolved: list[UnresolvedRow] = []
    preamble_parts: list[str] = []
    bands = None
    empty_pages = 0

    for page_no, page in enumerate(pdf.pages, start=1):
        words = _page_words(page)
        if not words:
            empty_pages += 1
            continue
        if any("(cid:" in w.text for w in words):
            raise PdfNotTextual(
                f"page {page_no} has unmapped fonts ((cid:) glyphs); this PDF "
                "cannot be read as text"
            )
        lines = group_lines(words)
        header_i = _find_header(lines, profile)
        if header_i is not None:
            preamble_parts.append(
                "\n".join(" ".join(w.text for w in l) for l in lines[:header_i])
            )
            try:
                bands = build_bands(lines[header_i], roles, aligns)
            except BandError as exc:
                raise ParseError(str(exc)) from None
            body = lines[header_i + 1:]
        else:
            if bands is None:
                continue          # a cover page before any header
            body = lines

        open_row: dict | None = None
        for line in body:
            raw = " ".join(w.text for w in line)
            if any(r.search(raw) for r in footer_res):
                break
            if any(r.search(raw) for r in skip_res) or any(
                r.search(raw) for r in summary_res
            ):
                continue

            cells: dict[str, str] = {}
            ambiguous: list[str] = []
            for word in line:
                role = assign(word, bands)
                if role is None:
                    ambiguous.append(word.text)
                    continue
                cells[role] = (cells.get(role, "") + " " + word.text).strip()

            locator = f"page:{page_no},y:{round(line[0].top)}"
            date_text = cells.get("date", "")
            has_date = bool(date_text) and date_text.strip().lower() not in _EMPTY

            if profile.rows.row_anchor == "date" and not has_date:
                # A continuation line: append its description to the open row.
                if open_row is not None and cells.get("description"):
                    open_row["description"] = (
                        open_row["description"] + " " + cells["description"]
                    ).strip()
                    open_row["raw"] = open_row["raw"] + " / " + raw
                continue

            if ambiguous:
                unresolved.append(UnresolvedRow(
                    locator, raw,
                    f"ambiguous column for {ambiguous!r}: a token sat outside "
                    "every column band or equally close to two",
                ))
                open_row = None
                continue

            try:
                d = _parse_date(date_text, profile)
            except ValueError as exc:
                unresolved.append(UnresolvedRow(locator, raw, f"unreadable date: {exc}"))
                open_row = None
                continue

            try:
                amount, sign_source = _amount_from_cells(cells, profile)
            except (ValueError, AmountError) as exc:
                unresolved.append(UnresolvedRow(locator, raw, str(exc)))
                open_row = None
                continue

            balance: int | None = None
            balance_text = cells.get("balance", "")
            if profile.balance.semantics == "running" and balance_text.strip().lower() not in _EMPTY:
                try:
                    balance = parse_paisa(balance_text,
                                          decimals=profile.formats.decimals)
                except AmountError as exc:
                    unresolved.append(UnresolvedRow(
                        locator, raw, f"unreadable balance: {exc}"))
                    open_row = None
                    continue

            open_row = {
                "date": d,
                "value_date": None,
                "amount": amount,
                "balance_after": balance,
                "description": cells.get("description", ""),
                "reference": cells.get("reference") or None,
                "sign_source": sign_source,
                "locator": locator,
                "raw": raw,
            }
            staged.append(open_row)

    return staged, unresolved, "\n".join(preamble_parts), empty_pages


def parse_pdf(
    data: bytes,
    profile: Profile,
    *,
    sha256: str,
    filename: str,
    account_id: str | None,
    password: str | None = None,
) -> ParseResult:
    """Parse a PDF statement into a Document and its Transactions."""
    with _open(data, password) as pdf:
        pages = len(pdf.pages)
        staged, unresolved, preamble, empty_pages = _rows_from_pdf(pdf, profile)

    if not staged and not unresolved and empty_pages == pages:
        raise PdfNotTextual(
            "this PDF has no extractable text on any page; it is probably a "
            "scan, which is not supported"
        )

    summary = _read_summary(preamble, profile)
    occurrences = assign_occurrences(staged)
    transactions = tuple(
        Transaction(
            txn_id=make_txn_id(account_id or "unassigned", s["date"], s["amount"],
                               s["balance_after"], s["description"], occ),
            account_id=account_id or "unassigned",
            date=s["date"],
            value_date=s["value_date"],
            amount=s["amount"],
            balance_after=s["balance_after"],
            description=s["description"],
            reference=s["reference"],
            tax_year=tax_year_for(s["date"]),
            provenance=Provenance(sha256=sha256, locator=s["locator"],
                                  raw_text=s["raw"], sign_source=s["sign_source"]),
        )
        for s, occ in zip(staged, occurrences, strict=True)
    )

    document = Document(
        sha256=sha256, filename=filename, kind="statement", container="pdf",
        layout_id=profile.id, account_id=account_id,
        period_start=summary.period_start or (transactions[0].date if transactions else None),
        period_end=summary.period_end or (transactions[-1].date if transactions else None),
        pages=pages, encrypted=bool(password), summary=summary,
    )
    return ParseResult(document, transactions, tuple(unresolved))


def pdf_row_samples(
    data: bytes,
    profile: Profile,
    *,
    password: str | None = None,
    limit: int = 5,
) -> list[dict[str, str]]:
    """Return labelled cell dicts for the first rows, keyed by header label.

    This is what lets a PDF profile's `selftest` cases run through the same
    `parse_row` the tabular engine uses - so a PDF profile proves it can read
    its own sample rows before it is trusted on a real statement.
    """
    roles, _ = _roles_and_aligns(profile)
    role_to_label = dict(roles)
    with _open(data, password) as pdf:
        staged, _, _, _ = _rows_from_pdf(pdf, profile)

    out: list[dict[str, str]] = []
    for s in staged[:limit]:
        row: dict[str, str] = {}
        for role, label in role_to_label.items():
            if role == "date":
                row[label] = s["date"].strftime(profile.formats.dates[0])
            elif role == "description":
                row[label] = s["description"]
            elif role in ("amount", "credit", "debit", "balance"):
                row[label] = ""
        # Re-render the amount in the profile's own shape.
        from fbr.money import format_paisa
        if profile.formats.sign == "columns":
            if s["amount"] > 0:
                row[role_to_label["credit"]] = format_paisa(s["amount"])
            else:
                row[role_to_label["debit"]] = format_paisa(-s["amount"])
            if "balance" in role_to_label and s["balance_after"] is not None:
                row[role_to_label["balance"]] = format_paisa(s["balance_after"])
        else:
            sign = "+" if s["amount"] > 0 else "-"
            row[role_to_label["amount"]] = f"{sign}{format_paisa(abs(s['amount']))}"
        out.append(row)
    return out
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_pdf_engine.py -v`
Expected: PASS. Two likely adjustments, both in the test's favour — do not weaken an assertion to make them go away:
- if `_find_header` misses because reportlab splits `Debit/Credit` into separate words, widen the joined-line match rather than changing the profile;
- if `test_a_pdf_with_no_text_layer_is_refused` raises a pdfplumber error before reaching `PdfNotTextual`, that still satisfies the test's `(PdfNotTextual, Exception)`; note in your report which path fired.

- [ ] **Step 5: Run the whole suite**

Run: `uv run pytest -q`
Expected: PASS — 313 existing plus everything added.

- [ ] **Step 6: Commit**

```bash
git add src/fbr/engines/pdf.py tests/test_pdf_engine.py
git commit -m "$(cat <<'EOF'
feat: add the PDF statement engine

Positioned words in, the same ParseResult the tabular engine produces out,
so reconcile.py's five checks apply unchanged. Unsigned Credit/Debit
columns are resolved by geometry and an ambiguous token becomes an
unresolved row rather than a guessed sign. Encrypted files decrypt in
memory, and the password never reaches an exception message.
EOF
)"
```

---

## Task 4: SadaPay profile, PDF wiring, and self-tests that exercise summary patterns

**Files:**
- Create: `profiles/sadapay.pdf.v1.toml`
- Modify: `src/fbr/config/loader.py` (`run_selftest`), `src/fbr/ingest.py` (`detect_layout`, `usable_profiles`), `src/fbr/pipeline.py` (`InputFile`, `load_files`), `tools/dump_layout.py` (`main`, add `dump_pdf`), `app/pages/2_Load.py`
- Test: `tests/test_pdf_wiring.py`, and extend `tests/test_profiles_ship.py`

**Interfaces:**
- Consumes: `fbr.engines.pdf` — `parse_pdf`, `pdf_row_samples`, `PdfPasswordError`, `PdfNotTextual` (Task 3); `fbr.engines._bands` (Task 2); `tests/fixtures/synth_pdf` (Task 1)
- Produces:
  - `loader.run_selftest(profile, parse_row, *, summary_text: str | None = None) -> ProfileStatus` — when `summary_text` is given, every declared summary pattern must match it
  - `schema_profile.SelfTest.summary_sample: str = ""` — the preamble text a profile's summary patterns must match
  - `ingest.detect_layout(..., password: str | None = None)` and `ingest.usable_profiles` unchanged in signature
  - `pipeline.InputFile(name, data, account_id=None, password=None)`
  - `tools.dump_layout.dump_pdf(data, *, allowlist, pages, hide_magnitude, password=None) -> tuple[str, Counter]`

**Why the self-test change matters:** a shipped Meezan XLSX profile carried doubled backslashes in TOML literal strings, so all four of its summary patterns silently never matched — disabling the opening/closing cross-check on a real statement while 313 tests passed. A self-test that only exercises `parse_row` cannot catch that class of bug. This task closes it for every profile, CSV and PDF alike.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_pdf_wiring.py -v`
Expected: FAIL — no `sadapay.pdf.v1` profile, `run_selftest` has no `summary_text`, `InputFile` has no `password`.

- [ ] **Step 3: Add `summary_sample` to the self-test schema**

In `src/fbr/config/schema_profile.py`, add one field to `SelfTest`:

```python
class SelfTest(BaseModel):
    model_config = _STRICT
    cases: list[SelfTestCase]
    # Preamble text that every declared summary pattern must match. Without
    # this, a profile's self-test exercises only parse_row, and a summary
    # pattern that never matches ships silently - which is exactly how a
    # shipped Meezan XLSX profile spent a release with four dead patterns
    # and a disabled opening/closing check.
    summary_sample: str = ""

    @field_validator("cases")
    @classmethod
    def _at_least_one(cls, v: list[SelfTestCase]) -> list[SelfTestCase]:
        if not v:
            raise ValueError("a profile must carry at least one selftest case")
        return v
```

- [ ] **Step 4: Extend `run_selftest` in `src/fbr/config/loader.py`**

Replace the function, keeping its existing row-case behaviour and adding the summary pass:

```python
def run_selftest(
    profile: Profile,
    parse_row: Callable[[Profile, dict], tuple],
    *,
    summary_text: str | None = None,
) -> ProfileStatus:
    """Run a profile's own sample rows, and its summary patterns, through the code.

    A profile that cannot parse its own samples is excluded from detection: it
    would otherwise fail silently on the real statement it was written for.

    `summary_text` closes a second hole. Summary patterns are regexes in a TOML
    file and nothing else executes them, so a mistake - doubled backslashes in
    a literal string, say - leaves a pattern that never matches. The statement
    still parses, but a reconciliation check quietly stops running. When a
    sample is supplied, every declared pattern must match it.
    """
    for i, case in enumerate(profile.selftest.cases, start=1):
        try:
            got_date, got_amount = parse_row(profile, case.row)
        except Exception as exc:  # noqa: BLE001 - any failure is a failed self-test
            return ProfileStatus(profile.id, "", False, f"selftest case {i} raised: {exc}")
        if got_date != case.expect_date:
            return ProfileStatus(
                profile.id, "", False,
                f"selftest case {i}: date {got_date} != expected {case.expect_date}",
            )
        if got_amount != case.expect_amount:
            return ProfileStatus(
                profile.id, "", False,
                f"selftest case {i}: amount {got_amount} != expected {case.expect_amount}",
            )

    if summary_text:
        compiled = profile.summary.compiled()
        dead = [name for name, pattern in compiled.items()
                if not pattern.search(summary_text)]
        if dead:
            return ProfileStatus(
                profile.id, "", False,
                f"summary pattern(s) {', '.join(sorted(dead))} match nothing in "
                "the profile's own summary_sample; a pattern that never matches "
                "silently disables a reconciliation check",
            )
        return ProfileStatus(
            profile.id, "", True,
            f"{len(profile.selftest.cases)} selftest case(s) and "
            f"{len(compiled)} summary pattern(s) pass",
        )

    return ProfileStatus(
        profile.id, "", True,
        f"{len(profile.selftest.cases)} selftest case(s) pass",
    )
```

- [ ] **Step 5: Route PDFs in `src/fbr/ingest.py`**

`usable_profiles` must pass each profile's own sample, and `detect_layout` must read a PDF's text. Change `_head_text` and `usable_profiles`:

```python
def usable_profiles(
    profiles: ProfileSet, container: str
) -> tuple[tuple[Profile, ...], tuple[ProfileStatus, ...]]:
    """Profiles for this container that pass their own self-tests."""
    candidates = profiles.for_container(container)
    ok: list[Profile] = []
    report: list[ProfileStatus] = []
    for profile in candidates:
        status = run_selftest(
            profile, parse_row,
            summary_text=profile.selftest.summary_sample or None,
        )
        report.append(status)
        if status.ok:
            ok.append(profile)
    return tuple(ok), tuple(report)


def _head_text(data: bytes, container: str, rows: int = 30,
               password: str | None = None) -> str:
    """The first rows of a file as text, for layout detection.

    Any failure to read the bytes as the claimed container is reported as an
    unreadable file rather than an unknown layout, because the advice differs:
    an unknown layout needs a masked dump, a corrupt file needs re-downloading.
    """
    if container == "pdf":
        import io
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(data), password=password or "") as pdf:
                pages = pdf.pages[:2]
                return "\n".join((p.extract_text() or "") for p in pages)
        except Exception as exc:                    # noqa: BLE001
            text = str(exc).lower()
            if "password" in text or "decrypt" in text or "incorrect" in text:
                raise LayoutUnknown(
                    "this PDF is encrypted; supply its password on the Load page"
                ) from None
            raise LayoutUnknown(
                f"this file could not be read as a pdf file ({type(exc).__name__}); "
                "try re-downloading it"
            ) from None
    try:
        parsed = read_rows(data, container)
    except Exception as exc:                        # noqa: BLE001
        raise LayoutUnknown(
            f"this file could not be read as a {container} file ({exc}); "
            "try re-downloading it"
        ) from None
    return "\n".join(",".join(r) for r in parsed[:rows])
```

Then give `detect_layout` a `password` keyword and pass it through to `_head_text`:

```python
def detect_layout(
    data: bytes,
    profiles: ProfileSet,
    container: str,
    *,
    on: date | None = None,
    password: str | None = None,
) -> Profile:
    """Return the single profile that matches this file."""
    candidates, _ = usable_profiles(profiles, container)
    if on is not None:
        candidates = tuple(
            p for p in candidates
            if p.valid_from <= on and (p.valid_to is None or on <= p.valid_to)
        )
    head = _head_text(data, container, password=password)
    matched = [p for p in candidates if _matches(p, head)]
    if not matched:
        raise LayoutUnknown(
            f"no {container} profile matches this file. Run `fbr-dump <file>` and "
            "send the masked dump so a profile can be written for this layout."
        )
    if len(matched) > 1:
        ids = ", ".join(sorted(p.id for p in matched))
        raise LayoutAmbiguous(
            f"{len(matched)} profiles match this file ({ids}); tighten their "
            "[detect] signatures so exactly one matches"
        )
    return matched[0]
```

- [ ] **Step 6: Carry a password through `src/fbr/pipeline.py`**

Add `password` to `InputFile`, drop the `unsupported` short-circuit for PDFs, and dispatch on container:

```python
@dataclass(frozen=True, slots=True)
class InputFile:
    name: str
    data: bytes
    account_id: str | None = None      # set by the owner when detection fails
    password: str | None = None        # held in memory only, never stored
```

In `load_files`, replace the PDF short-circuit with a dispatch. Where the body currently reads:

```python
        container = sniff_container(item.data)
        if container == "pdf":
            outcomes.append(FileOutcome(
                item.name, digest, "unsupported", None, None,
                "PDF statements arrive in phase 2; export CSV or XLSX for now", 0,
            ))
            continue
```

use instead:

```python
        container = sniff_container(item.data)
```

and define a small parse dispatcher near the top of the module:

```python
def _parse_for(container: str):
    """Pick the engine for a container. Both return the same ParseResult."""
    if container == "pdf":
        from fbr.engines.pdf import parse_pdf

        def run(data, profile, *, sha256, filename, account_id, password=None):
            return parse_pdf(data, profile, sha256=sha256, filename=filename,
                             account_id=account_id, password=password)
        return run

    def run(data, profile, *, sha256, filename, account_id, password=None):
        return parse_tabular(data, profile, sha256=sha256, filename=filename,
                             account_id=account_id)
    return run
```

Then every `detect_layout(...)` call gains `password=item.password`, and both `parse_tabular(...)` call sites become `_parse_for(container)(item.data, profile, sha256=digest, filename=item.name, account_id=..., password=item.password)`. Wrap them so a `PdfPasswordError` becomes a per-file outcome rather than an exception:

```python
        try:
            result = _parse_for(container)(
                item.data, profile, sha256=digest, filename=item.name,
                account_id=account_id, password=item.password,
            )
        except ParseError as exc:
            # PdfPasswordError subclasses ParseError. Its message never contains
            # the password - that is asserted by a test in tests/test_pdf_engine.py.
            outcomes.append(FileOutcome(
                item.name, digest, "unreadable", profile.id, account_id, str(exc), 0))
            continue
```

Import `ParseError` from `fbr.engines.tabular` at the top if it is not already imported.

- [ ] **Step 7: Write `profiles/sadapay.pdf.v1.toml`**

```toml
# SadaPay in-app PDF statement.
#
# STATUS: written against the synthetic fixture in tests/fixtures/synth_pdf.py,
# because no real SadaPay dump has been supplied yet. Every line marked VERIFY
# must be confirmed against a real `fbr-dump` before this is trusted.
#
# Known from research 03: SadaPay prints Date | Description | a signed amount,
# a Total debit / Total credit summary, and NO balance column anywhere. The
# statement can be generated for any date range from 1 Jul 2023, so request
# exactly 1 Jul - 30 Jun and anchor the opening balance by hand.
#
# Every regex below uses [^\d\n] rather than \D as its separator: \D matches a
# newline, so it can harvest a value from an unrelated preamble row. Write \s
# and \d with ONE backslash - these are TOML literal strings and are not
# unescaped, and doubling them was a real shipped bug.

id          = "sadapay.pdf.v1"
institution = "SadaPay"
container   = "pdf"
valid_from  = 2025-07-01
notes       = "In-app PDF: More -> Documents -> Account Statement."

[detect]
header_contains = ["Date", "Description", "Debit/Credit"]   # VERIFY

[columns]
date        = "Date"                                        # VERIFY
description = "Description"                                 # VERIFY
amount      = "Debit/Credit"                                # VERIFY

[columns.align]
amount = "right"                                            # VERIFY

[formats]
dates = ["%d %b, %Y", "%d %b %Y", "%d/%m/%Y"]               # VERIFY which one
sign  = "signed"

[rows]
row_anchor = "date"
footer     = ['(?i)system\s+generated', '(?i)^\s*page\s+\d+']

[summary]
total_debit  = '(?i)Total\s+debit[^\d\n]+?(?P<value>-?[\d,]+\.\d{2})'    # VERIFY
total_credit = '(?i)Total\s+credit[^\d\n]+?(?P<value>-?[\d,]+\.\d{2})'  # VERIFY
period_from  = '(?i)Statement\s+Period[^\d\n]+?(?P<value>\d{2} \w{3}, \d{4})'  # VERIFY
period_to    = '(?i)to\s+(?P<value>\d{2} \w{3}, \d{4})'                 # VERIFY

[balance]
# SadaPay prints no balance at all. Boundary balances therefore come from the
# owner's manual anchor, and the only parse check available is the printed
# Total debit / Total credit pair - which is why those patterns matter.
semantics = "none"

[selftest]
summary_sample = """
Account Statement
Account Currency  PK00TEST0000000000000000  PKR
Total debit  2,500.00
Total credit  1,000.00
Statement Period  01 Jul, 2025 to 30 Jun, 2026
"""

[[selftest.cases]]
row = { "Date" = "01 Jul, 2025", "Description" = "TRANSF CR/ICT/ Top-up", "Debit/Credit" = "+1,000.00" }
expect_date   = 2025-07-01
expect_amount = 100000

[[selftest.cases]]
row = { "Date" = "15 Jan, 2026", "Description" = "PUR/ Shop", "Debit/Credit" = "-2,500.00" }
expect_date   = 2026-01-15
expect_amount = -250000
```

- [ ] **Step 8: Add `summary_sample` to the five existing profiles**

Each already-shipped profile has summary patterns, so `test_every_shipped_profile_declares_a_summary_sample` now requires a sample. For each of `profiles/meezan.csv.v1.toml`, `mcb.csv.v1.toml`, `nayapay.csv.v1.toml`, `meezan.xlsx.v1.toml`, `mcb.xlsx.v1.toml`, add a `summary_sample` to its `[selftest]` table containing preamble text that its own patterns match. Derive each sample from what its synthetic writer actually prints — run the writer and copy the preamble rather than inventing text. For example, for `meezan.csv.v1`:

```toml
[selftest]
summary_sample = """
PK00TEST0000000000000000,ACCOUNT TITLE
OPENING BALANCE,PKR 5,000.00
CLOSING BALANCE,PKR 2,500.00
Total Credit,1,000.00
Total Debit,3,500.00
Statement Period,01 Jul 2025,30 Jun 2026
Currency,PKR
"""
```

Then confirm each one actually exercises its patterns:

```bash
cd /Users/faizanhasnaat/Documents/Github/fbr-tax-return
uv run python - <<'PY'
from pathlib import Path
from fbr.config.loader import load_profiles, run_selftest
from fbr.engines.tabular import parse_row
for p in load_profiles(Path("profiles")).profiles:
    st = run_selftest(p, parse_row, summary_text=p.selftest.summary_sample or None)
    print(f"{p.id:22} ok={st.ok}  {st.message}")
PY
```

Every line must read `ok=True` and mention its summary patterns. A profile reporting `ok=False` has a dead pattern — fix the pattern, not the sample.

- [ ] **Step 9: Add PDF support to `tools/dump_layout.py`**

Add a `dump_pdf` alongside `dump_tabular`, and route to it in `main` instead of exiting:

```python
def dump_pdf(
    data: bytes,
    *,
    allowlist: set[str],
    pages: int,
    hide_magnitude: bool,
    password: str | None = None,
) -> tuple[str, Counter]:
    """Render a masked dump of a PDF: word shapes with their coordinates.

    A profile author needs geometry - which column an amount sits under, how
    columns are ordered, what the date and amount formats look like. Coordinates
    are geometry, not content, so they are printed as-is; every word is masked.
    """
    import io

    import pdfplumber

    counts: Counter = Counter()
    lines_out: list[str] = []
    with pdfplumber.open(io.BytesIO(data), password=password or "") as pdf:
        total = len(pdf.pages)
        chosen = list(range(min(pages, total)))
        if total > pages:
            chosen.append(total - 1)
        lines_out += [
            "# Masked layout dump (PDF)",
            "",
            f"- pages: {total}",
            f"- pages shown: {[i + 1 for i in chosen]}",
            f"- encrypted: {bool(password)}",
            f"- magnitude hidden: {hide_magnitude}",
            "",
            "Every token is a SHAPE (letters -> X/x, digits -> 9) unless it is",
            "non-personal banking vocabulary. Coordinates are rounded to 1pt and",
            "are geometry, not content: they are what a profile's column bands",
            "are built from.",
            "",
        ]
        for i in chosen:
            page = pdf.pages[i]
            words = page.extract_words()
            if any("(cid:" in w["text"] for w in words):
                lines_out.append(f"## Page {i + 1}: UNMAPPED FONTS ((cid:) glyphs)")
                continue
            lines_out += [f"## Page {i + 1} ({len(words)} words)", "", FENCE]
            rows: dict[int, list[str]] = {}
            for w in words:
                shaped = mask_text(w["text"], allowlist=allowlist,
                                   hide_magnitude=hide_magnitude, counts=counts)
                rows.setdefault(round(w["top"]), []).append(
                    f"{shaped}@{round(w['x0'])}-{round(w['x1'])}"
                )
            for top in sorted(rows):
                lines_out.append(f"y={top}: " + "  ".join(rows[top]))
            lines_out += [FENCE, ""]
    return "\n".join(lines_out), counts
```

In `main`, replace the PDF refusal with:

```python
    allowlist = load_allowlist()
    if container == "pdf":
        password = getpass.getpass("PDF password (blank if none): ") or None
        text, counts = dump_pdf(
            data, allowlist=allowlist, pages=2,
            hide_magnitude=args.hide_magnitude, password=password,
        )
    else:
        text, counts = dump_tabular(
            data, container, allowlist=allowlist,
            rows=args.rows, hide_magnitude=args.hide_magnitude,
        )
```

Add `import getpass` at the top. Keep `--password` accepted for compatibility; prompting unconditionally for a PDF is simpler and never puts a password in shell history. **The prompt must use `getpass`, never `input`.**

- [ ] **Step 10: Prompt for a PDF password in `app/pages/2_Load.py`**

After the files are gathered and before the Parse button, add:

```python
pdf_names = [f.name for f in files if f.data[:4] == b"%PDF"]
passwords: dict[str, str] = {}
if pdf_names:
    st.caption(
        "PDF statements may be password-protected. A password typed here is "
        "held in memory for this run only: it is never written to disk, never "
        "logged, and never placed on a command line."
    )
    shared = st.text_input("PDF password (leave blank if none)", type="password")
    if shared:
        passwords = {name: shared for name in pdf_names}
```

Then, where `InputFile`s are built for the Parse call, attach the password:

```python
    files = [
        InputFile(f.name, f.data, account_id=f.account_id,
                  password=passwords.get(f.name))
        for f in files
    ]
```

- [ ] **Step 11: Run the tests**

Run: `uv run pytest tests/test_pdf_wiring.py tests/test_profiles_ship.py -v`
Expected: PASS.

- [ ] **Step 12: Run the whole suite**

Run: `uv run pytest -q`
Expected: PASS — everything from phases 0–1 plus this phase.

- [ ] **Step 13: Verify the dump tool by hand on a synthetic PDF**

```bash
cd /Users/faizanhasnaat/Documents/Github/fbr-tax-return
uv run python - <<'PY'
from tests.fixtures.synth import build_statement
from tests.fixtures.synth_pdf import write_sadapay_pdf
open("/tmp/synthetic_sadapay.pdf", "wb").write(write_sadapay_pdf(build_statement(seed=99)))
print("wrote /tmp/synthetic_sadapay.pdf")
PY
uv run fbr-dump /tmp/synthetic_sadapay.pdf          # press Enter at the password prompt
```

Expected: it prints only a path and counts. Then open the written dump and confirm it contains `y=` lines with `@x0-x1` coordinates, that header labels survive as words, and that no invented name or amount from the fixture is readable. Delete `/tmp/synthetic_sadapay.pdf` afterwards.

- [ ] **Step 14: Commit**

```bash
git add profiles/sadapay.pdf.v1.toml profiles/meezan.csv.v1.toml \
        profiles/mcb.csv.v1.toml profiles/nayapay.csv.v1.toml \
        profiles/meezan.xlsx.v1.toml profiles/mcb.xlsx.v1.toml \
        src/fbr/config/schema_profile.py src/fbr/config/loader.py \
        src/fbr/ingest.py src/fbr/pipeline.py tools/dump_layout.py \
        app/pages/2_Load.py tests/test_pdf_wiring.py tests/test_profiles_ship.py
git commit -m "$(cat <<'EOF'
feat: wire PDFs through detection, the pipeline and fbr-dump

Ships the SadaPay PDF profile and routes PDFs to the new engine, with a
password carried per file and held only in memory. fbr-dump now produces
masked PDF dumps carrying word shapes and coordinates, which is the
geometry a profile author needs.

Also closes the gap that let a real bug ship: a profile's self-test now
exercises its summary patterns against its own sample, not only parse_row.
A shipped Meezan XLSX profile had four dead patterns and a disabled
opening/closing check while the whole suite passed.
EOF
)"
```

---

## Phase exit criteria

1. `uv run pytest` passes with no failures.
2. Every shipped profile — six now — passes a self-test that exercises **both** its sample rows and its summary patterns.
3. A synthetic SadaPay PDF parses, reconciles against its printed totals, and reaches a ledger through `load_files`.
4. A synthetic Meezan PDF's unsigned Credit/Debit columns produce the correct signs, and an amount drawn between the two columns becomes an unresolved row rather than a guess.
5. An encrypted PDF opens with its password; a wrong password is reported per file with the password absent from the message.
6. `uv run fbr-dump` on a PDF writes a masked dump with coordinates and prints only a path and counts.

**Then, before phase 3:** the owner supplies a masked dump of a real SadaPay PDF covering 1 Jul 2025 – 30 Jun 2026, which replaces every `# VERIFY` value in `profiles/sadapay.pdf.v1.toml`. Until then the profile parses synthetic fixtures only, and no figure from a real SadaPay statement should be trusted.
