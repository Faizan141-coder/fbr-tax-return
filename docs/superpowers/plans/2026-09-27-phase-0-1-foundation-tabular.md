# FBR Aggregator — Phases 0–1 (Foundation + Tabular Engine) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the project foundation (typed model, money arithmetic, config loaders, reconciliation engine, masking tool) and the CSV/XLSX parsing engine, so that statements from Meezan, MCB Live and NayaPay parse, reconcile and display with a full audit trail.

**Architecture:** A pure-Python core library (`src/fbr/`) of stage functions over frozen dataclasses, with no Streamlit imports, plus a thin Streamlit shell (`app/`) that only calls the library. Statement layouts are declarative TOML profiles (`profiles/*.toml`) read by generic engines, so a bank changing its format next year means editing TOML, not code. All money is integer paisa; all regexes run through Python `re`.

**Tech Stack:** Python 3.14 (Homebrew), uv, pydantic 2, pandas 3, Streamlit 1.64, openpyxl (read-only, XLSX input), pdfplumber (phase 2, installed now), XlsxWriter (phase 5), pytest, reportlab (test fixtures only).

**Spec:** [docs/superpowers/specs/2026-09-27-fbr-aggregator-design.md](../specs/2026-09-27-fbr-aggregator-design.md) — read §§3–6 and §9 before starting. This plan covers spec §11 phases 0 and 1 only.

**Scope note:** Phases 2–6 (PDF engine, classification, transfer matching, IRIS summary, Excel export) get their own plans. Do not build them here. Where this plan creates a seam for later phases (e.g. `Classification` is referenced in the Raw transactions view), the seam is explicit in the task.

## Global Constraints

Copied verbatim from the spec. Every task's requirements implicitly include this section.

- **Python:** CPython 3.14 (Homebrew `python3.14`). Declare `requires-python = ">=3.12"`. System Python 3.9.6 must never be used.
- **Money:** integer paisa everywhere. `Decimal` only while parsing text. Never `float` for money. Never `astype(float)` on a money column.
- **Regex:** always Python `re`, applied directly. Never through pandas `.str` methods (they may use RE2 semantics).
- **Types:** all model types are frozen dataclasses. Dates are `datetime.date`.
- **Config validation:** pydantic with `ConfigDict(extra="forbid")`. A typo in a config key is an error, never silently ignored.
- **Fail closed:** a statement that fails any `fail`-level check contributes nothing to any total.
- **Privacy — repo:** no real statement data in the repo, ever. Test fixtures are generated at test time. Fake IBANs use the `PK00TEST` prefix exclusively.
- **Privacy — runtime:** `.streamlit/config.toml` per spec §9.1: `gatherUsageStats=false`, `server.address="127.0.0.1"`, `headless=true`, `showEmailPrompt=false`, `allowedHosts=["127.0.0.1","localhost"]`, `maxUploadSize=25`, `toolbarMode="viewer"`. State in `st.session_state` only — never `st.cache_data` / `st.cache_resource`. Never `page_icon=":material/…"`, never map elements.
- **Privacy — Claude's rule:** Claude reads only `~/fbr-private/dumps/`. Never statements, `dump-candidates/`, `accounts.toml`, decisions or manual inputs. Never print raw extraction output to stdout.
- **Private folder:** default `~/fbr-private/`, overridden by `FBR_PRIVATE_DIR`. Never inside the repo. Never under `~/Documents` or `~/Desktop`.
- **Commits:** end every commit message with `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`. Do not push. Do not create PRs.

## Review Focus

Input classes the spec implies but no single task's happy-path tests would exercise. Each line names the input and the expected behavior; each has a test pinned to the task that owns the code.

1. **A CSV whose amount column holds an empty string, a dash, or `-` as a placeholder for "no amount this side"** — common in Debit/Credit column layouts where one side is always blank. Must parse as "no amount on this side", never as zero, and never raise. *(Task 8: `test_blank_unused_side_is_not_treated_as_zero`, `test_both_sides_blank_is_unresolved_not_zero`, `test_dash_placeholder_counts_as_no_amount`)*
2. **A statement whose rows are not in date order** (value-date sorting, or a bank listing same-day rows by posting sequence) — the running-balance check walks printed order, so it must not assume ascending dates, and must not "fix" the order. *(Task 8: `test_rows_keep_printed_order_even_when_dates_are_not_ascending`; Task 10: `test_running_balance_walks_printed_order_not_date_order`)*
3. **A duplicate `id` across two profile files, or two profiles matching one file** — silent first-wins selection would attach a wrong layout to a real statement. Loading must fail loudly on duplicate ids; detection must report ambiguity rather than pick. *(Task 6: `test_duplicate_ids_across_files_are_rejected`; Task 9: `test_two_matching_profiles_raise_rather_than_guess`; Task 14: `test_no_two_shipped_profiles_match_the_same_file`)*
4. **An amount with more than 2 decimal places, or a thousands separator in the wrong place** (`1,23.456`) — must be rejected as unresolved, not silently rounded into a wrong figure. *(Task 2: `test_rejects_malformed_amounts`; Task 8: `test_a_malformed_amount_is_unresolved`)*
5. **A tax year with zero transactions for an account that has a statement** (dormant account) — opening and closing must still resolve from the printed balances, and the account must report ✅, not crash or report ❌. *(Task 11: `test_a_dormant_account_still_reports_boundaries`)*

---

## File Structure

| File | Responsibility |
|---|---|
| `pyproject.toml`, `uv.lock`, `.python-version` | Project metadata, pinned dependency lockfile, Python pin |
| `.streamlit/config.toml` | Privacy lockdown (spec §9.1) |
| `run` | Launcher; repeats privacy flags on the command line |
| `.gitignore`, `.githooks/pre-commit` | Repo guardrails (spec §9.2) |
| `src/fbr/money.py` | Text → integer paisa, paisa → display string. No other module parses amounts. |
| `src/fbr/model.py` | Frozen dataclasses: `Provenance`, `Transaction`, `Document`, `DocumentSummary`, `Check`, `Account`, `Owner`, `Registry`. Plus `txn_id` derivation. |
| `src/fbr/paths.py` | Private-folder resolution and subpath helpers. Single source of truth for where owner data lives. |
| `src/fbr/config/schema_profile.py` | pydantic schema for a layout profile |
| `src/fbr/config/schema_registry.py` | pydantic schema for `accounts.toml` |
| `src/fbr/config/schema_taxyear.py` | pydantic schema for `taxyears/TY*.toml` |
| `src/fbr/config/loader.py` | TOML reading, directory scanning, duplicate-id detection, profile self-test enforcement |
| `src/fbr/ingest.py` | Container sniffing, decoding, layout detection, account resolution |
| `src/fbr/engines/tabular.py` | CSV/XLSX → `Document` + `list[Transaction]` |
| `src/fbr/reconcile.py` | Per-statement checks, multi-statement merge, tax-year boundary balances, account status |
| `src/fbr/pipeline.py` | Wires ingest → parse → reconcile for a set of files; the single entry point the UI calls |
| `tools/dump_layout.py` | Masking tool (`fbr-dump`) |
| `tools/dump_allowlist.txt` | Shipped non-personal banking vocabulary |
| `profiles/*.toml` | One per layout: `meezan.csv.v1`, `mcb.csv.v1`, `nayapay.csv.v1` |
| `taxyears/TY2026.toml` | IRIS codes, thresholds, rates, templates |
| `app/main.py`, `app/pages/*.py` | Streamlit shell: Setup, Load, Checks |
| `tests/fixtures/synth.py` | Synthetic statement model + CSV/XLSX writers |
| `tests/test_*.py` | One test module per source module |

---

## Task 1: Project scaffolding and privacy guardrails

**Files:**
- Create: `pyproject.toml`, `.python-version`, `.gitignore`, `.streamlit/config.toml`, `run`, `.githooks/pre-commit`, `src/fbr/__init__.py`, `tests/__init__.py`
- Test: `tests/test_guardrails.py`

**Interfaces:**
- Consumes: nothing (first task)
- Produces: a working `uv run pytest`; package importable as `fbr`; `fbr.__version__` (a string, used in `Decision.tool_version` later)

- [ ] **Step 1: Verify the toolchain and create the project**

```bash
cd /Users/faizanhasnaat/Documents/Github/fbr-tax-return
python3.14 --version          # expect 3.14.x — do NOT proceed with 3.9
command -v uv || brew install uv
uv --version
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[project]
name = "fbr-tax-return"
version = "0.1.0"
description = "Local-only aggregator for Pakistani FBR individual tax return data"
requires-python = ">=3.12"
dependencies = [
  "pydantic>=2.13",
  "pandas>=3.0",
  "streamlit>=1.64",
  "openpyxl>=3.1.5",
  "pdfplumber>=0.11.10",
  "xlsxwriter>=3.2.9",
]

[project.scripts]
fbr-dump = "tools.dump_layout:main"

[dependency-groups]
dev = ["pytest>=9.1", "reportlab>=5.0", "pypdf[crypto]>=6.19"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/fbr", "tools"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"

[tool.uv]
python-downloads = "manual"
```

- [ ] **Step 3: Create the package skeleton and pin Python**

```bash
mkdir -p src/fbr/config src/fbr/engines tools tests/fixtures .streamlit .githooks app/pages profiles taxyears
printf '__version__ = "0.1.0"\n' > src/fbr/__init__.py
: > src/fbr/config/__init__.py
: > src/fbr/engines/__init__.py
: > tools/__init__.py
: > tests/__init__.py
: > tests/fixtures/__init__.py
uv python pin 3.14
uv sync
uv run python -c "import fbr; print(fbr.__version__)"    # expect 0.1.0
```

- [ ] **Step 4: Write `.gitignore`**

```gitignore
.venv/
__pycache__/
*.pyc
.pytest_cache/
.streamlit/secrets.toml
tests/private/

# Statement data must never enter the repo (spec §9.2).
# Exception: tests/fixtures/** holds only generator OUTPUT, created at test time.
*.pdf
*.csv
*.xlsx
*.xls
!tests/fixtures/**
```

- [ ] **Step 5: Write `.streamlit/config.toml` (spec §9.1, values exact)**

```toml
[browser]
gatherUsageStats = false
serverAddress = "127.0.0.1"

[server]
address = "127.0.0.1"
port = 8501
headless = true
showEmailPrompt = false
enableXsrfProtection = true
enableCORS = true
allowedHosts = ["127.0.0.1", "localhost"]
maxUploadSize = 25
runOnSave = false

[client]
toolbarMode = "viewer"
```

- [ ] **Step 6: Write the `run` launcher**

```bash
#!/usr/bin/env bash
# Launch the local UI. Privacy flags are repeated here so they apply even if
# .streamlit/config.toml is missing or overridden (spec §9.1).
set -euo pipefail
cd "$(dirname "$0")"
exec uv run streamlit run app/main.py \
  --browser.gatherUsageStats false \
  --server.address 127.0.0.1 \
  --server.headless true \
  --client.toolbarMode viewer
```

Then: `chmod +x run`

- [ ] **Step 7: Write `.githooks/pre-commit`**

```bash
#!/usr/bin/env bash
# Block IBAN- and CNIC-shaped strings from entering the repo (spec §9.2).
# PK00TEST is the reserved synthetic prefix and is allowed.
set -uo pipefail

staged=$(git diff --cached --name-only --diff-filter=ACM)
[ -z "$staged" ] && exit 0

fail=0
while IFS= read -r f; do
  [ -f "$f" ] || continue
  if git show ":$f" | grep -nE 'PK[0-9]{2}[A-Z]{4}[0-9]{16}' | grep -v 'PK00TEST'; then
    echo "pre-commit: IBAN-shaped string in $f" >&2; fail=1
  fi
  if git show ":$f" | grep -nE '[0-9]{5}-[0-9]{7}-[0-9]'; then
    echo "pre-commit: CNIC-shaped string in $f" >&2; fail=1
  fi
done <<< "$staged"

if [ "$fail" -ne 0 ]; then
  echo "pre-commit: refusing commit. Remove the data or use the PK00TEST prefix." >&2
  exit 1
fi
exit 0
```

Then:

```bash
chmod +x .githooks/pre-commit
git config core.hooksPath .githooks
```

- [ ] **Step 8: Write the failing guardrail test**

```python
# tests/test_guardrails.py
"""The repo's own privacy guardrails are themselves tested, because a silent
regression here is how real statement data would reach git."""
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_streamlit_config_locks_down_telemetry_and_binding():
    cfg = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text())
    assert cfg["browser"]["gatherUsageStats"] is False
    assert cfg["server"]["address"] == "127.0.0.1"
    assert cfg["server"]["headless"] is True
    assert cfg["server"]["showEmailPrompt"] is False
    assert cfg["server"]["allowedHosts"] == ["127.0.0.1", "localhost"]


def test_gitignore_excludes_statement_file_types():
    text = (ROOT / ".gitignore").read_text()
    for pattern in ("*.pdf", "*.csv", "*.xlsx"):
        assert pattern in text


def test_precommit_hook_rejects_an_iban_but_allows_the_test_prefix():
    hook = ROOT / ".githooks" / "pre-commit"
    assert hook.exists() and hook.stat().st_mode & 0o111, "hook must be executable"
    body = hook.read_text()
    assert "PK00TEST" in body, "hook must exempt the synthetic prefix"
    # Built from parts on purpose: a literal IBAN here would make this very
    # file uncommittable under the hook it tests.
    real = "PK" + "96" + "MEZN" + "0003070112153474"
    test = "PK00TEST0000000000000000"
    pattern = r'PK[0-9]{2}[A-Z]{4}[0-9]{16}'
    assert subprocess.run(["grep", "-qE", pattern], input=real, text=True).returncode == 0
    assert subprocess.run(
        ["grep", "-E", pattern], input=test, text=True, capture_output=True
    ).stdout.strip() == test, "test prefix matches the shape; the hook's grep -v exempts it"


def test_python_floor_is_at_least_3_12():
    meta = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert meta["project"]["requires-python"] == ">=3.12"
```

- [ ] **Step 9: Run the tests**

Run: `uv run pytest tests/test_guardrails.py -v`
Expected: PASS (4 tests). If `test_precommit_hook_*` fails, the hook regex differs from the test's — fix the hook, not the test.

- [ ] **Step 10: Verify the hook actually blocks a commit**

```bash
# Assembled at runtime so this plan file holds no IBAN-shaped literal.
printf 'PK%s%s%s\n' '96' 'MEZN' '0003070112153474' > ./probe.txt
git add probe.txt
git commit -m "probe" ; echo "exit=$?"     # expect exit=1 and an "IBAN-shaped string" message
git reset HEAD probe.txt && rm -f probe.txt
```

Expected: the commit is refused with exit 1. If it succeeds, the hook is not active — re-run `git config core.hooksPath .githooks`.

- [ ] **Step 11: Commit**

```bash
git add pyproject.toml uv.lock .python-version .gitignore .streamlit/config.toml run \
        .githooks/pre-commit src tools tests app profiles taxyears
git commit -m "$(cat <<'EOF'
chore: scaffold project with privacy guardrails

uv + Python 3.14 project, locked-down Streamlit config, gitignore for
statement file types, and a pre-commit hook blocking IBAN/CNIC patterns.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Money — text to integer paisa

**Files:**
- Create: `src/fbr/money.py`
- Test: `tests/test_money.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `parse_paisa(text: str, *, decimals: int = 2) -> int` — raises `AmountError` on anything malformed
  - `format_paisa(paisa: int) -> str` — `"1,234.56"`, negatives as `"-1,234.56"`
  - `class AmountError(ValueError)`
  - `PAISA_PER_RUPEE: int = 100`

**Why its own module:** every engine and check funnels through one amount grammar, so a format surprise is fixed in one place and cannot be half-fixed in three.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_money.py
import pytest
from fbr.money import AmountError, format_paisa, parse_paisa


@pytest.mark.parametrize(
    "text,expected",
    [
        ("1234.56", 123456),
        ("1,234.56", 123456),
        ("1,234", 123400),
        ("0.01", 1),
        ("0", 0),
        ("12,34,567.89", 123456789),   # lakh-style grouping
        ("PKR 1,234.56", 123456),
        ("Rs. 1,234.56", 123456),
        ("Rs1,234.56", 123456),
        ("1,234.5", 123450),           # one decimal place is valid
        ("  1,234.56  ", 123456),      # surrounding whitespace
        ("1 234.56", 123456),     # non-breaking space as separator
    ],
)
def test_parses_valid_amounts(text, expected):
    assert parse_paisa(text) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("-1,234.56", -123456),
        ("+1,234.56", 123456),
        ("−1,234.56", -123456),   # Unicode minus
        ("(1,234.56)", -123456),       # accounting negative
        ("1,234.56-", -123456),        # trailing minus
    ],
)
def test_parses_signed_amounts(text, expected):
    assert parse_paisa(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "abc",
        "1.2.3",
        "1,234.567",      # 3 decimals — Review Focus #4
        "1,23.456",       # misplaced separator + 3 decimals — Review Focus #4
        "1,2345.00",      # 4-digit group after a separator
        "(1,234.56",      # unbalanced parenthesis
        "1,234.56)",
        "--1234",
        "1,234.56Dr",     # Dr/Cr is the profile's job, not the grammar's
        "1 234 56",
    ],
)
def test_rejects_malformed_amounts(text):
    with pytest.raises(AmountError):
        parse_paisa(text)


def test_never_uses_float():
    # 0.1 + 0.2 in float is 0.30000000000000004; in paisa it must be exact.
    assert parse_paisa("0.10") + parse_paisa("0.20") == parse_paisa("0.30")


def test_large_amount_is_exact():
    assert parse_paisa("99,999,999.99") == 9999999999


@pytest.mark.parametrize(
    "paisa,expected",
    [(123456, "1,234.56"), (-123456, "-1,234.56"), (0, "0.00"), (1, "0.01")],
)
def test_formats_paisa(paisa, expected):
    assert format_paisa(paisa) == expected


def test_round_trips():
    for text in ("1,234.56", "0.01", "12,34,567.89"):
        assert parse_paisa(format_paisa(parse_paisa(text))) == parse_paisa(text)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_money.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'fbr.money'`

- [ ] **Step 3: Write the implementation**

```python
# src/fbr/money.py
"""Money is integer paisa everywhere in this codebase (spec Global Constraints).

Decimal appears only inside parse_paisa, where text becomes an integer. No
other module parses an amount, and no money value is ever a float: a float
rupee figure cannot represent 0.10 exactly, and a tax return must reconcile
to the paisa.
"""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation

PAISA_PER_RUPEE = 100


class AmountError(ValueError):
    """The text is not an amount this grammar accepts.

    Raised rather than guessed: a silently coerced amount is a wrong number on
    a tax return, which is worse than a row the operator must look at.
    """


# Groups are 2 or 3 digits to accept both 1,234,567 and lakh-style 12,34,567.
_AMOUNT = re.compile(
    r"""(?x) ^
    (?P<lparen>\()?
    (?P<sign>[-+])?
    \s*
    (?:(?:PKR|Rs)\.?)?
    \s*
    (?P<int>[0-9]{1,3}(?:,[0-9]{2,3})*|[0-9]+)
    (?:\.(?P<frac>[0-9]{1,2}))?
    \s*
    (?P<rparen>\))?
    (?P<trailing>-)?
    $""",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    """NFKC-fold, map the Unicode minus to ASCII, and drop separator spaces.

    Statement PDFs and CSVs carry non-breaking spaces and U+2212 freely; both
    mean what their ASCII lookalikes mean.
    """
    s = unicodedata.normalize("NFKC", text)
    s = s.replace("−", "-")
    return re.sub(r"\s+", "", s)


def parse_paisa(text: str, *, decimals: int = 2) -> int:
    """Parse an amount into signed integer paisa.

    Accepts optional PKR/Rs prefix, comma grouping (3- or 2-digit groups),
    up to `decimals` decimal places, and a sign expressed as a leading -/+,
    surrounding parentheses, or a trailing minus.

    Rejects Dr/Cr suffixes: direction is the layout profile's job, because
    only the profile knows which token that bank uses for which direction.
    """
    if text is None:
        raise AmountError("amount is None")
    s = _normalize(str(text))
    if not s:
        raise AmountError("empty amount")

    m = _AMOUNT.match(s)
    if m is None:
        raise AmountError(f"unparseable amount: {text!r}")

    if bool(m.group("lparen")) != bool(m.group("rparen")):
        raise AmountError(f"unbalanced parentheses: {text!r}")

    signs = [
        m.group("sign") == "-",
        bool(m.group("lparen")),
        bool(m.group("trailing")),
    ]
    if sum(signs) > 1:
        raise AmountError(f"more than one negative marker: {text!r}")
    negative = any(signs)

    frac = m.group("frac") or ""
    if len(frac) > decimals:
        raise AmountError(f"more than {decimals} decimal places: {text!r}")

    digits = m.group("int").replace(",", "")
    try:
        value = Decimal(digits) * PAISA_PER_RUPEE + Decimal(frac.ljust(decimals, "0") or 0)
    except InvalidOperation as exc:  # pragma: no cover - guarded by the regex
        raise AmountError(f"unparseable amount: {text!r}") from exc

    paisa = int(value)
    return -paisa if negative else paisa


def format_paisa(paisa: int) -> str:
    """Render integer paisa as a grouped decimal string for display and export."""
    sign = "-" if paisa < 0 else ""
    whole, frac = divmod(abs(paisa), PAISA_PER_RUPEE)
    return f"{sign}{whole:,}.{frac:02d}"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_money.py -v`
Expected: PASS (all parametrized cases)

- [ ] **Step 5: Commit**

```bash
git add src/fbr/money.py tests/test_money.py
git commit -m "$(cat <<'EOF'
feat: add integer-paisa money parsing and formatting

Single amount grammar for every engine: PKR/Rs prefixes, 3- and 2-digit
comma grouping, and signs via -/+, parentheses or trailing minus. Rejects
>2 decimals and Dr/Cr suffixes rather than guessing.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Core model and stable transaction IDs

**Files:**
- Create: `src/fbr/model.py`
- Test: `tests/test_model.py`

**Interfaces:**
- Consumes: `fbr.money` (Task 2)
- Produces (all frozen dataclasses unless noted):
  - `Provenance(sha256: str, locator: str, raw_text: str, sign_source: str)` — `locator` is `"row:12"` or `"page:2,y:341"`; `sign_source` ∈ `{"column","suffix","signed","balance"}`
  - `Transaction(txn_id, account_id, date, value_date, amount, balance_after, description, reference, tax_year, provenance)` — `amount` signed paisa; `balance_after: int | None`
  - `DocumentSummary(opening, closing, total_credit, total_debit, period_start, period_end, account_identifier)` — every field optional
  - `Document(sha256, filename, kind, container, layout_id, account_id, period_start, period_end, pages, encrypted, summary)`
  - `Check(check_id, scope, kind, status, expected, actual, detail, locator)` — `status` ∈ `{"pass","warn","fail"}`
  - `Account`, `Owner`, `Registry` (registry types; validated in Task 5)
  - `tax_year_for(d: date) -> str` — `"TY2026"` for 2025-07-01..2026-06-30
  - `normalize_description(s: str) -> str`
  - `make_txn_id(account_id, date, amount, balance_after, description, occurrence) -> str`
  - `assign_occurrences(rows: list[dict]) -> list[int]`

**Why occurrence numbering lives here:** `txn_id` stability is what lets a saved review decision survive a re-run (spec §4.1). Two genuine identical same-day transactions must get different ids, and re-loading the same file must reproduce both ids exactly.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_model.py
from datetime import date

import pytest

from fbr.model import (
    Account,
    Check,
    Document,
    DocumentSummary,
    Owner,
    Provenance,
    Registry,
    Transaction,
    assign_occurrences,
    make_txn_id,
    normalize_description,
    tax_year_for,
)


@pytest.mark.parametrize(
    "d,expected",
    [
        (date(2025, 7, 1), "TY2026"),    # first day of TY2026
        (date(2026, 6, 30), "TY2026"),   # last day
        (date(2025, 6, 30), "TY2025"),   # day before
        (date(2026, 7, 1), "TY2027"),    # day after
        (date(2026, 1, 15), "TY2026"),   # mid-year, across the calendar boundary
    ],
)
def test_tax_year_runs_july_to_june(d, expected):
    assert tax_year_for(d) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("  IBFT  In   from  Thunes ", "IBFT IN FROM THUNES"),
        ("ibft in", "IBFT IN"),
        ("IBFT In", "IBFT IN"),          # NBSP folds to a space
        ("IBFT\nIn", "IBFT IN"),              # wrapped line
    ],
)
def test_normalize_description(raw, expected):
    assert normalize_description(raw) == expected


def test_txn_id_is_stable_across_runs():
    args = ("meezan-main", date(2026, 1, 5), 123456, 500000, "Payment of Profit", 1)
    assert make_txn_id(*args) == make_txn_id(*args)


def test_txn_id_ignores_description_whitespace_and_case():
    base = ("meezan-main", date(2026, 1, 5), 123456, 500000)
    assert make_txn_id(*base, "Payment of Profit", 1) == make_txn_id(
        *base, "  payment   of  profit ", 1
    )


@pytest.mark.parametrize(
    "changed",
    [
        {"account_id": "mcb-main"},
        {"d": date(2026, 1, 6)},
        {"amount": 123457},
        {"balance_after": 500001},
        {"description": "Payment of Prof1t"},
        {"occurrence": 2},
    ],
)
def test_txn_id_changes_when_any_component_changes(changed):
    base = dict(
        account_id="meezan-main",
        d=date(2026, 1, 5),
        amount=123456,
        balance_after=500000,
        description="Payment of Profit",
        occurrence=1,
    )
    other = {**base, **changed}
    mk = lambda a: make_txn_id(
        a["account_id"], a["d"], a["amount"], a["balance_after"],
        a["description"], a["occurrence"],
    )
    assert mk(base) != mk(other)


def test_txn_id_handles_missing_balance():
    # SadaPay has no balance column; None must be distinct from 0.
    base = ("sadapay", date(2026, 1, 5), 123456)
    assert make_txn_id(*base, None, "PUR/SHOP", 1) != make_txn_id(*base, 0, "PUR/SHOP", 1)


def test_identical_same_day_rows_get_different_occurrences():
    # Two genuine Rs 1,000 top-ups on one day are both real (spec §6.2).
    rows = [
        {"date": date(2026, 1, 5), "amount": 100000, "balance_after": None, "description": "TOPUP"},
        {"date": date(2026, 1, 5), "amount": 100000, "balance_after": None, "description": "TOPUP"},
        {"date": date(2026, 1, 5), "amount": 200000, "balance_after": None, "description": "TOPUP"},
    ]
    assert assign_occurrences(rows) == [1, 2, 1]


def test_occurrence_numbering_follows_printed_order_not_sorted_order():
    rows = [
        {"date": date(2026, 1, 9), "amount": 100000, "balance_after": None, "description": "A"},
        {"date": date(2026, 1, 5), "amount": 100000, "balance_after": None, "description": "A"},
        {"date": date(2026, 1, 9), "amount": 100000, "balance_after": None, "description": "A"},
    ]
    assert assign_occurrences(rows) == [1, 1, 2]


def test_model_types_are_frozen():
    p = Provenance(sha256="a" * 64, locator="row:1", raw_text="x", sign_source="column")
    with pytest.raises(Exception):
        p.locator = "row:2"


def test_transaction_round_trips_its_fields():
    p = Provenance(sha256="a" * 64, locator="row:3", raw_text="raw", sign_source="column")
    t = Transaction(
        txn_id="deadbeefdeadbeef",
        account_id="meezan-main",
        date=date(2026, 1, 5),
        value_date=date(2026, 1, 5),
        amount=-25000,
        balance_after=475000,
        description="ATM Cash Withdrawal",
        reference="STAN 123456",
        tax_year="TY2026",
        provenance=p,
    )
    assert t.amount == -25000 and t.tax_year == "TY2026"
    assert t.provenance.sign_source == "column"


def test_check_and_document_construct():
    c = Check(
        check_id="c1", scope="document", kind="running_balance", status="fail",
        expected="500000", actual="499000", detail="row 12", locator="row:12",
    )
    assert c.status == "fail"
    d = Document(
        sha256="b" * 64, filename="x.csv", kind="statement", container="csv",
        layout_id="meezan.csv.v1", account_id="meezan-main",
        period_start=date(2025, 7, 1), period_end=date(2026, 6, 30),
        pages=1, encrypted=False,
        summary=DocumentSummary(
            opening=100000, closing=200000, total_credit=500000, total_debit=400000,
            period_start=date(2025, 7, 1), period_end=date(2026, 6, 30),
            account_identifier="PK00TEST0000000000000000",
        ),
    )
    assert d.summary.opening == 100000


def test_registry_types_construct():
    acct = Account(
        id="meezan-main", institution="Meezan Bank Limited", kind="bank",
        iban="PK00TEST0000000000000000", account_number="0000000000",
        wallet_number="", title="ACCOUNT TITLE", type="Saving", ownership="Self",
        currency="PKR", statement_expected=True, match_hints=["MEEZAN"],
        opened_on=None, closed_on=None,
    )
    reg = Registry(owner=Owner(name="OWNER NAME"), accounts=(acct,))
    assert reg.accounts[0].id == "meezan-main"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_model.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'fbr.model'`

- [ ] **Step 3: Write the implementation**

```python
# src/fbr/model.py
"""Frozen types for every stage of the pipeline.

Frozen because a transaction that changes after a check has passed would
make the audit trail a lie: the Excel export must be able to say that this
figure came from that row, and that row must still be what was checked.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

SignSource = Literal["column", "suffix", "signed", "balance"]
CheckStatus = Literal["pass", "warn", "fail"]
CheckScope = Literal["document", "account", "tax_year"]
Container = Literal["csv", "xlsx", "pdf"]
DocKind = Literal["statement", "wht_certificate", "prc_statement"]


def tax_year_for(d: date) -> str:
    """Return the FBR tax year label for a date.

    A tax year runs 1 July to 30 June and is named for the June it ends in
    (spec §4.3), so 2025-07-01 through 2026-06-30 are all TY2026.
    """
    year = d.year + 1 if d.month >= 7 else d.year
    return f"TY{year}"


_WS = re.compile(r"\s+")


def normalize_description(s: str) -> str:
    """Fold a description to a stable key: NFKC, upper case, collapsed spaces.

    Used only for id derivation, never for display or classification, which
    both need the original text.
    """
    return _WS.sub(" ", unicodedata.normalize("NFKC", s)).strip().upper()


def make_txn_id(
    account_id: str,
    d: date,
    amount: int,
    balance_after: int | None,
    description: str,
    occurrence: int,
) -> str:
    """Derive a stable 16-hex-character transaction id (spec §4.1).

    Stability is the point: a review decision saved last week must still
    attach to the same row when the same file is loaded again. `None` and `0`
    balances hash differently, because a wallet with no balance column is not
    an account that happened to hit zero.
    """
    balance = "none" if balance_after is None else str(balance_after)
    payload = "\x1f".join(
        [
            account_id,
            d.isoformat(),
            str(amount),
            balance,
            normalize_description(description),
            str(occurrence),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def assign_occurrences(rows: list[dict]) -> list[int]:
    """Number rows that share (date, amount, balance, description) 1, 2, ...

    Numbering follows printed order, not sorted order, so that a statement
    listing same-day rows by posting sequence still yields the same ids on
    every run (Review Focus #2).
    """
    seen: Counter[tuple] = Counter()
    out: list[int] = []
    for r in rows:
        key = (
            r["date"],
            r["amount"],
            r.get("balance_after"),
            normalize_description(r["description"]),
        )
        seen[key] += 1
        out.append(seen[key])
    return out


@dataclass(frozen=True, slots=True)
class Provenance:
    """Where a value came from, precisely enough to find it again by hand."""

    sha256: str
    locator: str          # "row:12" (tabular) or "page:2,y:341" (pdf)
    raw_text: str
    sign_source: SignSource


@dataclass(frozen=True, slots=True)
class Transaction:
    txn_id: str
    account_id: str
    date: date            # booking date; drives tax_year
    value_date: date | None
    amount: int           # signed paisa: + credit, - debit
    balance_after: int | None
    description: str      # complete; wrapped lines already joined
    reference: str | None
    tax_year: str
    provenance: Provenance


@dataclass(frozen=True, slots=True)
class DocumentSummary:
    """Figures the statement prints about itself. Every field is optional,
    because SadaPay prints totals with no balances and others do the reverse."""

    opening: int | None = None
    closing: int | None = None
    total_credit: int | None = None
    total_debit: int | None = None
    period_start: date | None = None
    period_end: date | None = None
    account_identifier: str | None = None


@dataclass(frozen=True, slots=True)
class Document:
    sha256: str
    filename: str
    kind: DocKind
    container: Container
    layout_id: str
    account_id: str | None
    period_start: date | None
    period_end: date | None
    pages: int
    encrypted: bool
    summary: DocumentSummary


@dataclass(frozen=True, slots=True)
class Check:
    check_id: str
    scope: CheckScope
    kind: str
    status: CheckStatus
    expected: str
    actual: str
    detail: str
    locator: str | None = None


@dataclass(frozen=True, slots=True)
class Account:
    id: str
    institution: str
    kind: Literal["bank", "wallet", "foreign"]
    iban: str
    account_number: str
    wallet_number: str
    title: str
    type: str
    ownership: str
    currency: str
    statement_expected: bool
    match_hints: tuple[str, ...] | list[str] = field(default_factory=tuple)
    opened_on: date | None = None
    closed_on: date | None = None


@dataclass(frozen=True, slots=True)
class Owner:
    name: str


@dataclass(frozen=True, slots=True)
class Registry:
    owner: Owner
    accounts: tuple[Account, ...]

    def by_id(self, account_id: str) -> Account | None:
        return next((a for a in self.accounts if a.id == account_id), None)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_model.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/fbr/model.py tests/test_model.py
git commit -m "$(cat <<'EOF'
feat: add core model types and stable transaction ids

Frozen dataclasses for transactions, documents, checks and the account
registry, plus txn_id derivation with printed-order occurrence numbering
so saved review decisions survive a re-run.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Private-folder paths

**Files:**
- Create: `src/fbr/paths.py`
- Test: `tests/test_paths.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `private_root() -> Path` — honours `FBR_PRIVATE_DIR`, defaults to `~/fbr-private`
  - `statements_dir(tax_year: str) -> Path`, `dumps_dir() -> Path`, `dump_candidates_dir() -> Path`, `decisions_path(tax_year: str) -> Path`, `manual_path(tax_year: str) -> Path`, `registry_path() -> Path`, `local_rules_path() -> Path`, `dump_allowlist_path() -> Path`
  - `ensure_private_layout() -> Path` — creates missing subfolders, returns the root
  - `class PrivatePathError(RuntimeError)`
  - `describe_private_layout() -> list[tuple[str, bool]]` — (path, exists) pairs for the Setup page

**Why:** one module decides where owner data lives, so no other module can accidentally write a statement into the repo. `ensure_private_layout` refuses a root inside the repo or under a cloud-synced folder.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_paths.py
from pathlib import Path

import pytest

from fbr import paths


def test_defaults_to_home_fbr_private(monkeypatch):
    monkeypatch.delenv("FBR_PRIVATE_DIR", raising=False)
    assert paths.private_root() == Path.home() / "fbr-private"


def test_env_var_overrides_root(monkeypatch, tmp_path):
    monkeypatch.setenv("FBR_PRIVATE_DIR", str(tmp_path / "elsewhere"))
    assert paths.private_root() == tmp_path / "elsewhere"


def test_subpaths_hang_off_the_root(monkeypatch, tmp_path):
    monkeypatch.setenv("FBR_PRIVATE_DIR", str(tmp_path))
    assert paths.statements_dir("TY2026") == tmp_path / "statements" / "TY2026"
    assert paths.dumps_dir() == tmp_path / "dumps"
    assert paths.dump_candidates_dir() == tmp_path / "dump-candidates"
    assert paths.decisions_path("TY2026") == tmp_path / "decisions" / "TY2026.json"
    assert paths.manual_path("TY2026") == tmp_path / "manual" / "TY2026.toml"
    assert paths.registry_path() == tmp_path / "accounts.toml"
    assert paths.local_rules_path() == tmp_path / "rules.local.toml"


def test_ensure_creates_the_expected_layout(monkeypatch, tmp_path):
    monkeypatch.setenv("FBR_PRIVATE_DIR", str(tmp_path / "priv"))
    root = paths.ensure_private_layout()
    for sub in ("statements", "dumps", "dump-candidates", "decisions", "manual"):
        assert (root / sub).is_dir()


def test_refuses_a_root_inside_the_repo(monkeypatch):
    repo_child = Path(__file__).resolve().parents[1] / "private"
    monkeypatch.setenv("FBR_PRIVATE_DIR", str(repo_child))
    with pytest.raises(paths.PrivatePathError, match="inside the repository"):
        paths.ensure_private_layout()


@pytest.mark.parametrize("folder", ["Documents", "Desktop"])
def test_refuses_cloud_synced_folders(monkeypatch, folder):
    monkeypatch.setenv("FBR_PRIVATE_DIR", str(Path.home() / folder / "fbr-private"))
    with pytest.raises(paths.PrivatePathError, match="may be synced"):
        paths.ensure_private_layout()


def test_describe_reports_existence(monkeypatch, tmp_path):
    monkeypatch.setenv("FBR_PRIVATE_DIR", str(tmp_path / "priv"))
    before = dict(paths.describe_private_layout())
    assert all(exists is False for exists in before.values())
    paths.ensure_private_layout()
    after = dict(paths.describe_private_layout())
    assert any(exists for exists in after.values())
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_paths.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'fbr.paths'`

- [ ] **Step 3: Write the implementation**

```python
# src/fbr/paths.py
"""Where the owner's data lives.

Every read and write of owner data goes through this module, so that no
other module can put a statement inside the repository by accident. The
guards below are cheap and catch the two mistakes that would matter:
pointing the private folder at the repo (git would see statements) or at a
cloud-synced folder (the brief requires that nothing leaves the machine).
"""

from __future__ import annotations

import os
from pathlib import Path

_DEFAULT = "fbr-private"
_SUBDIRS = ("statements", "dumps", "dump-candidates", "decisions", "manual")
# macOS syncs these to iCloud Drive when Desktop & Documents sync is on.
_CLOUD_SYNCED = ("Documents", "Desktop")


class PrivatePathError(RuntimeError):
    """The configured private folder is not a safe place for owner data."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def private_root() -> Path:
    env = os.environ.get("FBR_PRIVATE_DIR")
    return Path(env).expanduser() if env else Path.home() / _DEFAULT


def statements_dir(tax_year: str) -> Path:
    return private_root() / "statements" / tax_year


def dumps_dir() -> Path:
    return private_root() / "dumps"


def dump_candidates_dir() -> Path:
    return private_root() / "dump-candidates"


def decisions_path(tax_year: str) -> Path:
    return private_root() / "decisions" / f"{tax_year}.json"


def manual_path(tax_year: str) -> Path:
    return private_root() / "manual" / f"{tax_year}.toml"


def registry_path() -> Path:
    return private_root() / "accounts.toml"


def local_rules_path() -> Path:
    return private_root() / "rules.local.toml"


def dump_allowlist_path() -> Path:
    return private_root() / "dump-allowlist.txt"


def _validate(root: Path) -> None:
    resolved = root.expanduser().resolve()
    repo = _repo_root()
    if resolved == repo or repo in resolved.parents:
        raise PrivatePathError(
            f"{resolved} is inside the repository; git would see owner data. "
            "Set FBR_PRIVATE_DIR to a folder outside the repo."
        )
    home = Path.home().resolve()
    for name in _CLOUD_SYNCED:
        synced = home / name
        if resolved == synced or synced in resolved.parents:
            raise PrivatePathError(
                f"{resolved} is under ~/{name}, which may be synced to iCloud. "
                "Choose a folder that stays on this machine."
            )


def ensure_private_layout() -> Path:
    """Create the private folder layout, refusing unsafe locations."""
    root = private_root()
    _validate(root)
    for sub in _SUBDIRS:
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


def describe_private_layout() -> list[tuple[str, bool]]:
    """(path, exists) pairs for the Setup page. Never lists file contents."""
    root = private_root()
    entries = [(str(root), root.is_dir())]
    entries += [(str(root / s), (root / s).is_dir()) for s in _SUBDIRS]
    entries.append((str(registry_path()), registry_path().is_file()))
    return entries
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_paths.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/fbr/paths.py tests/test_paths.py
git commit -m "$(cat <<'EOF'
feat: add private-folder path resolution

Single source of truth for where owner data lives, honouring
FBR_PRIVATE_DIR and refusing roots inside the repo or under
cloud-synced folders.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Config schemas (profile, registry, tax year)

**Files:**
- Create: `src/fbr/config/schema_profile.py`, `src/fbr/config/schema_registry.py`, `src/fbr/config/schema_taxyear.py`
- Test: `tests/test_schemas.py`

**Interfaces:**
- Consumes: `fbr.model` (Task 3)
- Produces:
  - `schema_profile.Profile` with `.id`, `.institution`, `.container`, `.valid_from`, `.valid_to`, `.detect`, `.columns`, `.formats`, `.rows`, `.summary`, `.balance`, `.selftest`
  - `schema_profile.Detect`, `Columns`, `Formats`, `Rows`, `SummaryPatterns`, `BalanceSpec`, `SelfTestCase`
  - `schema_registry.RegistryFile` with `.to_model() -> fbr.model.Registry`
  - `schema_taxyear.TaxYear` with `.codes: dict[str, CodeEntry]`, `.thresholds`, `.rates`, `.templates`, `.period_start`, `.period_end`
  - `schema_taxyear.CodeEntry` with `.code`, `.label`, `.tab`, `.columns`, `.source`, `.verification`

**Why pydantic with `extra="forbid"`:** a typo like `header_contian` in a profile would otherwise be silently ignored, and the profile would quietly stop detecting the statement it was written for.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_schemas.py
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_schemas.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'fbr.config.schema_profile'`

- [ ] **Step 3: Write `schema_profile.py`**

```python
# src/fbr/config/schema_profile.py
"""Schema for a layout profile: one TOML file per statement layout.

`extra="forbid"` throughout. A mistyped key in a profile must fail loudly at
load time, not silently disable the setting and let a real statement parse
with the wrong rules.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_STRICT = ConfigDict(extra="forbid", frozen=True)


def _compile(pattern: str, *, require_group: str | None = None) -> re.Pattern:
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"invalid regex {pattern!r}: {exc}") from exc
    if require_group and require_group not in compiled.groupindex:
        raise ValueError(f"regex {pattern!r} must define a (?P<{require_group}>...) group")
    return compiled


class Detect(BaseModel):
    model_config = _STRICT
    header_contains: list[str] = Field(min_length=1)
    title_regex: str | None = None

    @field_validator("title_regex")
    @classmethod
    def _valid_regex(cls, v: str | None) -> str | None:
        if v is not None:
            _compile(v)
        return v


class ColumnAlign(BaseModel):
    model_config = _STRICT
    debit: Literal["left", "right", "center"] = "right"
    credit: Literal["left", "right", "center"] = "right"
    amount: Literal["left", "right", "center"] = "right"
    balance: Literal["left", "right", "center"] = "right"


class Columns(BaseModel):
    """Role -> header label. A list of labels means "any of these"."""

    model_config = _STRICT
    date: str | list[str]
    value_date: str | list[str] | None = None
    description: str | list[str]
    reference: str | list[str] | None = None
    debit: str | list[str] | None = None
    credit: str | list[str] | None = None
    amount: str | list[str] | None = None
    balance: str | list[str] | None = None
    type: str | list[str] | None = None
    align: ColumnAlign = ColumnAlign()


class Formats(BaseModel):
    model_config = _STRICT
    dates: list[str] = Field(min_length=1)
    sign: Literal["columns", "suffix", "signed"]
    debit_tokens: list[str] = Field(default_factory=list)
    credit_tokens: list[str] = Field(default_factory=list)
    decimals: int = 2

    @field_validator("dates")
    @classmethod
    def _formats_include_a_year(cls, v: list[str]) -> list[str]:
        for fmt in v:
            if "%Y" not in fmt and "%y" not in fmt:
                raise ValueError(
                    f"date format {fmt!r} has no year directive; Python defaults the "
                    "year to 1900, which would silently mis-date every row"
                )
        return v


class Rows(BaseModel):
    model_config = _STRICT
    skip: list[str] = Field(default_factory=list)
    summary: list[str] = Field(default_factory=list)
    footer: list[str] = Field(default_factory=list)
    continuation: Literal["below", "nearest"] = "below"
    row_anchor: Literal["date", "amount"] = "date"

    @model_validator(mode="after")
    def _regexes_compile(self) -> "Rows":
        for group in (self.skip, self.summary, self.footer):
            for pattern in group:
                _compile(pattern)
        return self


class SummaryPatterns(BaseModel):
    """Regexes over the preamble/page text. Each must expose a `value` group."""

    model_config = _STRICT
    opening: str | None = None
    closing: str | None = None
    total_credit: str | None = None
    total_debit: str | None = None
    period_from: str | None = None
    period_to: str | None = None
    account_id: str | None = None

    @model_validator(mode="after")
    def _all_expose_value(self) -> "SummaryPatterns":
        for name in self.model_fields:
            pattern = getattr(self, name)
            if pattern is not None:
                _compile(pattern, require_group="value")
        return self

    def compiled(self) -> dict[str, re.Pattern]:
        return {
            name: _compile(getattr(self, name))
            for name in self.model_fields
            if getattr(self, name) is not None
        }


class BalanceSpec(BaseModel):
    model_config = _STRICT
    semantics: Literal["running", "none"] = "running"
    kind: Literal["ledger", "available"] = "ledger"


class SelfTestCase(BaseModel):
    model_config = _STRICT
    row: dict[str, str]
    expect_date: date
    expect_amount: int          # signed paisa


class SelfTest(BaseModel):
    model_config = _STRICT
    cases: list[SelfTestCase]

    @field_validator("cases")
    @classmethod
    def _at_least_one(cls, v: list[SelfTestCase]) -> list[SelfTestCase]:
        if not v:
            raise ValueError("a profile must carry at least one selftest case")
        return v


class Profile(BaseModel):
    model_config = _STRICT
    id: str
    institution: str
    container: Literal["csv", "xlsx", "pdf"]
    valid_from: date
    valid_to: date | None = None
    notes: str = ""
    detect: Detect
    columns: Columns
    formats: Formats
    rows: Rows = Rows()
    summary: SummaryPatterns = SummaryPatterns()
    balance: BalanceSpec = BalanceSpec()
    selftest: SelfTest

    @model_validator(mode="after")
    def _columns_match_sign_mode(self) -> "Profile":
        c, mode = self.columns, self.formats.sign
        if mode == "columns":
            if not (c.debit and c.credit):
                raise ValueError("sign='columns' needs both debit and credit columns")
            if c.amount:
                raise ValueError("sign='columns' must not also define an amount column")
        else:
            if not c.amount:
                raise ValueError(f"sign={mode!r} needs a single amount column")
            if c.debit or c.credit:
                raise ValueError(f"sign={mode!r} must not define debit/credit columns")
        if mode == "suffix" and not (self.formats.debit_tokens and self.formats.credit_tokens):
            raise ValueError("sign='suffix' needs debit_tokens and credit_tokens")
        return self
```

- [ ] **Step 4: Write `schema_registry.py`**

```python
# src/fbr/config/schema_registry.py
"""Schema for ~/fbr-private/accounts.toml, the owner's account registry."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from fbr.model import Account, Owner, Registry

_STRICT = ConfigDict(extra="forbid")


class OwnerEntry(BaseModel):
    model_config = _STRICT
    name: str


class AccountEntry(BaseModel):
    model_config = _STRICT
    id: str
    institution: str
    kind: Literal["bank", "wallet", "foreign"]
    iban: str = ""
    account_number: str = ""
    wallet_number: str = ""
    title: str
    type: str = ""
    ownership: str = "Self"
    currency: str = "PKR"
    statement_expected: bool = True
    match_hints: list[str] = Field(default_factory=list)
    opened_on: date | None = None
    closed_on: date | None = None

    @model_validator(mode="after")
    def _has_an_identifier(self) -> "AccountEntry":
        # Without one of these, a parsed statement can never be linked to this
        # account automatically, and internal-transfer matching has nothing to
        # match on.
        if not (self.iban or self.account_number or self.wallet_number):
            raise ValueError(
                f"account {self.id!r} needs an identifier: iban, account_number "
                "or wallet_number"
            )
        return self


class RegistryFile(BaseModel):
    model_config = _STRICT
    owner: OwnerEntry
    account: list[AccountEntry] = Field(min_length=1)

    @model_validator(mode="after")
    def _ids_are_unique(self) -> "RegistryFile":
        seen: set[str] = set()
        for a in self.account:
            if a.id in seen:
                raise ValueError(f"duplicate account id {a.id!r}")
            seen.add(a.id)
        return self

    def to_model(self) -> Registry:
        return Registry(
            owner=Owner(name=self.owner.name),
            accounts=tuple(
                Account(
                    id=a.id, institution=a.institution, kind=a.kind, iban=a.iban,
                    account_number=a.account_number, wallet_number=a.wallet_number,
                    title=a.title, type=a.type, ownership=a.ownership,
                    currency=a.currency, statement_expected=a.statement_expected,
                    match_hints=tuple(a.match_hints),
                    opened_on=a.opened_on, closed_on=a.closed_on,
                )
                for a in self.account
            ),
        )
```

- [ ] **Step 5: Write `schema_taxyear.py`**

```python
# src/fbr/config/schema_taxyear.py
"""Schema for taxyears/TY*.toml: IRIS codes, thresholds, rates, templates.

Codes live in per-year config because FBR regrouped the wealth statement
between TY2025 and TY2026, and the live IRIS form can differ from the
published one. Each code carries how it was verified, so the UI can mark a
figure the owner still has to confirm.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_STRICT = ConfigDict(extra="forbid", frozen=True)

Verification = Literal[
    "iris_verified",        # owner confirmed in live IRIS        -> shown as tick
    "form_text",            # read from a form's text layer       -> shown as warn
    "form_scan",            # read by OCR from a scanned form     -> shown as warn
    "prior_year_assumed",   # carried over from the year before   -> shown as warn
    "unknown",              # code not known                      -> shown as cross
]


class CodeEntry(BaseModel):
    model_config = _STRICT
    code: str
    label: str
    tab: str
    columns: dict[str, str] = Field(default_factory=dict)
    source: str
    verification: Verification

    @model_validator(mode="after")
    def _blank_code_means_unknown(self) -> "CodeEntry":
        if not self.code and self.verification != "unknown":
            raise ValueError(
                f"{self.label!r} has a blank code but verification="
                f"{self.verification!r}; a blank code must be marked 'unknown'"
            )
        return self


class Thresholds(BaseModel):
    model_config = _STRICT
    profit_final_regime_max: int        # paisa
    s111_4_cap: int                     # paisa
    review_threshold: int               # paisa
    wht_ratio_tolerance_pp: float
    profit_wht_window_days: int
    tax154a_window_days: int
    tax154a_amount_tolerance: int       # paisa
    transfer_window_days: int
    transfer_fee_tolerance: int         # paisa
    reversal_window_days: int


class Rates(BaseModel):
    model_config = _STRICT
    s151_atl: float
    s151_non_atl: float
    s7b: float
    s236y_atl: float
    s236y_non_atl: float
    s231ab_non_atl: float
    s154a: float
    s154a_pseb: float


class Templates(BaseModel):
    model_config = _STRICT
    wealth_line: str
    profit_line: str


class TaxYear(BaseModel):
    model_config = _STRICT
    name: str
    period_start: date
    period_end: date
    atl: bool = True
    codes: dict[str, CodeEntry]
    thresholds: Thresholds
    rates: Rates
    templates: Templates

    @model_validator(mode="after")
    def _period_is_a_fiscal_year(self) -> "TaxYear":
        if (self.period_start.month, self.period_start.day) != (7, 1):
            raise ValueError("period_start must be 1 July")
        if (self.period_end.month, self.period_end.day) != (6, 30):
            raise ValueError("period_end must be 30 June")
        if self.period_end.year != self.period_start.year + 1:
            raise ValueError("a tax year spans exactly one 1 July to 30 June")
        return self
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_schemas.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/fbr/config/schema_profile.py src/fbr/config/schema_registry.py \
        src/fbr/config/schema_taxyear.py tests/test_schemas.py
git commit -m "$(cat <<'EOF'
feat: add pydantic schemas for profiles, registry and tax years

Strict validation (extra="forbid") so a mistyped config key fails at load
time. Profiles must define columns consistent with their sign mode, date
formats must include a year, and blank IRIS codes must be marked unknown.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Config loader with profile self-tests

**Files:**
- Create: `src/fbr/config/loader.py`
- Test: `tests/test_loader.py`

**Interfaces:**
- Consumes: Task 5 schemas, `fbr.paths` (Task 4)
- Produces:
  - `load_profiles(directory: Path) -> ProfileSet`
  - `class ProfileSet` with `.profiles: tuple[Profile, ...]`, `.for_container(c) -> tuple[Profile, ...]`, `.by_id(id) -> Profile | None`, `.report: tuple[ProfileStatus, ...]`
  - `class ProfileStatus(profile_id, path, ok, message)`
  - `load_registry(path=None) -> Registry`
  - `load_tax_year(name: str, directory=None) -> TaxYear`
  - `class ConfigError(RuntimeError)`
  - `run_selftest(profile, parse_row) -> ProfileStatus` — the hook the engine calls (Task 8)

**Design note:** `load_profiles` validates structure and duplicate ids; it cannot run a profile's self-test cases, because executing them needs the engine. Task 8 supplies `parse_row` and the Setup page shows the result. A profile whose self-test fails is excluded from detection (spec §5.4).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_loader.py
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_loader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'fbr.config.loader'`

- [ ] **Step 3: Write the implementation**

```python
# src/fbr/config/loader.py
"""Load and validate TOML configuration.

Every error names the file it came from. A profile problem discovered at
load time is cheap; the same problem discovered halfway through a tax return
is not.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from pydantic import ValidationError

from fbr import paths
from fbr.config.schema_profile import Profile
from fbr.config.schema_registry import RegistryFile
from fbr.config.schema_taxyear import TaxYear
from fbr.model import Registry


class ConfigError(RuntimeError):
    """Configuration is missing, malformed or contradictory."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _read_toml(path: Path) -> dict:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path.name}: malformed TOML: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"{path}: cannot read: {exc}") from exc


@dataclass(frozen=True, slots=True)
class ProfileStatus:
    """A profile's readiness, shown on the Setup page."""

    profile_id: str
    path: str
    ok: bool
    message: str


@dataclass(frozen=True, slots=True)
class ProfileSet:
    profiles: tuple[Profile, ...]
    report: tuple[ProfileStatus, ...]

    def for_container(self, container: str) -> tuple[Profile, ...]:
        return tuple(p for p in self.profiles if p.container == container)

    def by_id(self, profile_id: str) -> Profile | None:
        return next((p for p in self.profiles if p.id == profile_id), None)


def load_profiles(directory: Path | None = None) -> ProfileSet:
    """Load every *.toml profile in `directory`, rejecting duplicate ids."""
    directory = Path(directory) if directory else _repo_root() / "profiles"
    if not directory.is_dir():
        raise ConfigError(f"no profile directory at {directory}")

    files = sorted(directory.glob("*.toml"))
    if not files:
        raise ConfigError(f"no profiles found in {directory}")

    profiles: list[Profile] = []
    report: list[ProfileStatus] = []
    seen: dict[str, Path] = {}

    for path in files:
        data = _read_toml(path)
        try:
            profile = Profile.model_validate(data)
        except ValidationError as exc:
            raise ConfigError(f"{path.name}: invalid profile: {exc}") from exc
        if profile.id in seen:
            raise ConfigError(
                f"duplicate profile id {profile.id!r} in {path.name} and "
                f"{seen[profile.id].name}; ids must be unique so a statement "
                "cannot match two layouts"
            )
        seen[profile.id] = path
        profiles.append(profile)
        report.append(ProfileStatus(profile.id, str(path), True, "loaded"))

    return ProfileSet(tuple(profiles), tuple(report))


def run_selftest(profile: Profile, parse_row: Callable[[Profile, dict], tuple]) -> ProfileStatus:
    """Run a profile's own sample rows through the engine.

    A profile that cannot parse its own samples is excluded from detection:
    it would otherwise fail silently on the real statement it was written for.
    `parse_row` returns (date, signed_paisa).
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
    return ProfileStatus(profile.id, "", True, f"{len(profile.selftest.cases)} selftest case(s) pass")


def load_registry(path: Path | None = None) -> Registry:
    path = Path(path) if path else paths.registry_path()
    if not path.is_file():
        raise ConfigError(
            f"no account registry at {path}. Create accounts.toml there with an "
            "[owner] name and one [[account]] block per account."
        )
    try:
        return RegistryFile.model_validate(_read_toml(path)).to_model()
    except ValidationError as exc:
        raise ConfigError(f"{path.name}: invalid registry: {exc}") from exc


def load_tax_year(name: str, directory: Path | None = None) -> TaxYear:
    directory = Path(directory) if directory else _repo_root() / "taxyears"
    path = directory / f"{name}.toml"
    if not path.is_file():
        available = ", ".join(sorted(p.stem for p in directory.glob("TY*.toml"))) or "none"
        raise ConfigError(f"no config for {name}; available: {available}")
    try:
        return TaxYear.model_validate(_read_toml(path))
    except ValidationError as exc:
        raise ConfigError(f"{path.name}: invalid tax year config: {exc}") from exc
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_loader.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/fbr/config/loader.py tests/test_loader.py
git commit -m "$(cat <<'EOF'
feat: add config loader for profiles, registry and tax years

Every error names its file. Duplicate profile ids are rejected so a
statement cannot match two layouts, and run_selftest gives the engine a
hook to exclude profiles that fail their own sample rows.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Synthetic statement fixtures

**Files:**
- Create: `tests/fixtures/synth.py`
- Test: `tests/test_synth.py`

**Interfaces:**
- Consumes: `fbr.money` (Task 2)
- Produces:
  - `SynthTxn(date, description, amount, balance_after)` — `amount` signed paisa
  - `SynthStatement(account_title, account_id, period_start, period_end, opening, txns)` with `.closing`, `.total_credit`, `.total_debit`
  - `build_statement(*, opening=..., rows=..., start=..., seed=...) -> SynthStatement` — balances computed, never hand-written
  - `write_meezan_csv(stmt) -> bytes`, `write_mcb_csv(stmt) -> bytes`, `write_nayapay_csv(stmt) -> bytes`, `write_xlsx(stmt, layout="meezan") -> bytes`
  - `corrupt(data: bytes, how: str) -> bytes` — `how` ∈ `{"drop_row","flip_sign","wrong_total","bad_amount","blank_debit_and_credit","unsorted_dates"}`

**Why generated, not committed:** the repo must never hold statement files (Global Constraints). Generating them at test time also means a layout tweak updates every fixture at once. Balances are computed from the transactions, so a fixture cannot itself contain an arithmetic mistake that masks a parser bug.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_synth.py
import csv
import io
from datetime import date

from tests.fixtures.synth import (
    SynthTxn,
    build_statement,
    corrupt,
    write_meezan_csv,
    write_mcb_csv,
    write_nayapay_csv,
    write_xlsx,
)


def test_balances_are_computed_from_transactions():
    stmt = build_statement(
        opening=100000,
        rows=[
            SynthTxn(date(2025, 7, 2), "Top-up", 50000, None),
            SynthTxn(date(2025, 7, 3), "ATM withdrawal", -20000, None),
        ],
    )
    assert [t.balance_after for t in stmt.txns] == [150000, 130000]
    assert stmt.closing == 130000
    assert stmt.total_credit == 50000
    assert stmt.total_debit == 20000


def test_generated_statement_is_reproducible_from_a_seed():
    a = build_statement(seed=7)
    b = build_statement(seed=7)
    assert [(t.date, t.amount, t.description) for t in a.txns] == [
        (t.date, t.amount, t.description) for t in b.txns
    ]


def test_meezan_csv_has_preamble_then_header_then_rows():
    stmt = build_statement(seed=1)
    rows = list(csv.reader(io.StringIO(write_meezan_csv(stmt).decode("utf-8"))))
    joined = "\n".join(",".join(r) for r in rows[:6])
    assert "OPENING BALANCE" in joined and "CLOSING BALANCE" in joined
    header = next(r for r in rows if r and r[0] == "Booking Date")
    # Meezan's CSV puts Debit BEFORE Credit - the reverse of its PDF.
    assert header.index("Debit") < header.index("Credit")


def test_meezan_csv_leaves_the_unused_side_blank():
    # Review Focus #1: a credit row must leave Debit empty, not "0.00".
    stmt = build_statement(
        opening=0, rows=[SynthTxn(date(2025, 7, 2), "Top-up", 50000, None)]
    )
    rows = list(csv.reader(io.StringIO(write_meezan_csv(stmt).decode("utf-8"))))
    header = next(r for r in rows if r and r[0] == "Booking Date")
    body = rows[rows.index(header) + 1]
    assert body[header.index("Debit")] == ""
    assert body[header.index("Credit")] == "500.00"


def test_mcb_csv_uses_a_dr_cr_suffix():
    stmt = build_statement(
        opening=100000, rows=[SynthTxn(date(2025, 7, 2), "Cash withdrawal", -20000, None)]
    )
    text = write_mcb_csv(stmt).decode("utf-8")
    assert "200.00Dr" in text


def test_nayapay_csv_uses_signed_amounts():
    stmt = build_statement(
        opening=100000, rows=[SynthTxn(date(2025, 7, 2), "IBFT In", 50000, None)]
    )
    text = write_nayapay_csv(stmt).decode("utf-8")
    assert "+500.00" in text or "500.00" in text


def test_xlsx_is_a_zip_container():
    stmt = build_statement(seed=2)
    assert write_xlsx(stmt).startswith(b"PK\x03\x04")


def test_fake_ibans_use_the_reserved_prefix():
    # Global Constraints: only PK00TEST may appear in the repo.
    stmt = build_statement(seed=3)
    assert stmt.account_id.startswith("PK00TEST")


def test_corrupt_produces_different_bytes_for_each_mode():
    stmt = build_statement(seed=4)
    clean = write_meezan_csv(stmt)
    for how in ("drop_row", "flip_sign", "wrong_total", "bad_amount",
                "blank_debit_and_credit", "unsorted_dates"):
        assert corrupt(clean, how) != clean, how
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_synth.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tests.fixtures.synth'`

- [ ] **Step 3: Write the implementation**

```python
# tests/fixtures/synth.py
"""Generate look-alike statements for tests.

Real statements never enter this repository (Global Constraints). These
fixtures reproduce the *shape* of each layout - column order, separators,
Dr/Cr tokens, blank unused sides - with invented values. Balances are
computed from the transactions, so a fixture can never contain an
arithmetic error that hides a parser bug.
"""

from __future__ import annotations

import csv
import io
import random
import zipfile
from dataclasses import dataclass, replace
from datetime import date, timedelta

from fbr.money import format_paisa

TEST_IBAN = "PK00TEST0000000000000000"

_DESCRIPTIONS = [
    "IBFT In from THUNES STAN 123456",
    "Payment of Profit",
    "Withholding Tax Debit",
    "ATM Cash Withdrawal STAN 654321",
    "Raast P2P Fund transfer",
    "POS Transaction STAN 222333",
    "Money Transferred To",
]


@dataclass(frozen=True, slots=True)
class SynthTxn:
    date: date
    description: str
    amount: int                 # signed paisa
    balance_after: int | None   # filled in by build_statement


@dataclass(frozen=True, slots=True)
class SynthStatement:
    account_title: str
    account_id: str
    period_start: date
    period_end: date
    opening: int
    txns: tuple[SynthTxn, ...]

    @property
    def closing(self) -> int:
        return self.txns[-1].balance_after if self.txns else self.opening

    @property
    def total_credit(self) -> int:
        return sum(t.amount for t in self.txns if t.amount > 0)

    @property
    def total_debit(self) -> int:
        return -sum(t.amount for t in self.txns if t.amount < 0)


def build_statement(
    *,
    opening: int = 500000,
    rows: list[SynthTxn] | None = None,
    start: date = date(2025, 7, 1),
    end: date | None = None,
    count: int = 8,
    seed: int = 0,
    account_title: str = "ACCOUNT TITLE",
    account_id: str = TEST_IBAN,
) -> SynthStatement:
    """Build a statement whose running balances are computed, not asserted."""
    if rows is None:
        rng = random.Random(seed)
        rows = []
        day = start
        for _ in range(count):
            day = day + timedelta(days=rng.randint(1, 20))
            amount = rng.randrange(5000, 2_000_000)
            if rng.random() < 0.5:
                amount = -amount
            rows.append(SynthTxn(day, rng.choice(_DESCRIPTIONS), amount, None))

    running = opening
    filled: list[SynthTxn] = []
    for t in rows:
        running += t.amount
        filled.append(replace(t, balance_after=running))

    return SynthStatement(
        account_title=account_title,
        account_id=account_id,
        period_start=start,
        period_end=end or (filled[-1].date if filled else start),
        opening=opening,
        txns=tuple(filled),
    )


def _csv_bytes(rows: list[list[str]]) -> bytes:
    buf = io.StringIO(newline="")
    csv.writer(buf, lineterminator="\r\n").writerows(rows)
    return buf.getvalue().encode("utf-8")


def write_meezan_csv(stmt: SynthStatement) -> bytes:
    """Meezan CSV: preamble rows, then a header with Debit BEFORE Credit."""
    rows: list[list[str]] = [
        [stmt.account_id, stmt.account_title],
        ["OPENING BALANCE", f"PKR {format_paisa(stmt.opening)}"],
        ["CLOSING BALANCE", f"PKR {format_paisa(stmt.closing)}"],
        ["Currency", "PKR"],
        ["Booking Date", "Value Date", "Doc No", "Description",
         "Debit", "Credit", "Available Balance"],
    ]
    for i, t in enumerate(stmt.txns, start=1):
        stamp = t.date.strftime("%d %b %Y")
        rows.append([
            stamp, stamp, f"D{i:05d}", t.description,
            format_paisa(-t.amount) if t.amount < 0 else "",
            format_paisa(t.amount) if t.amount > 0 else "",
            format_paisa(t.balance_after),
        ])
    return _csv_bytes(rows)


def write_mcb_csv(stmt: SynthStatement) -> bytes:
    """MCB CSV: one Amount column carrying a glued Dr/Cr suffix."""
    rows: list[list[str]] = [
        ["Account Number", stmt.account_id],
        ["Opening Balance", format_paisa(stmt.opening)],
        ["Closing Balance", format_paisa(stmt.closing)],
        ["Date", "Description", "Reference Number", "Amount", "Balance"],
    ]
    for i, t in enumerate(stmt.txns, start=1):
        suffix = "Cr" if t.amount > 0 else "Dr"
        rows.append([
            t.date.strftime("%d %b %Y"), t.description, f"{1000000000 + i}",
            f"{format_paisa(abs(t.amount))}{suffix}",
            format_paisa(t.balance_after),
        ])
    return _csv_bytes(rows)


def write_nayapay_csv(stmt: SynthStatement) -> bytes:
    """NayaPay CSV: signed amounts and a running balance."""
    rows: list[list[str]] = [
        ["Account", stmt.account_id],
        ["Opening Balance", format_paisa(stmt.opening)],
        ["Closing Balance", format_paisa(stmt.closing)],
        ["Total Income", format_paisa(stmt.total_credit)],
        ["Total Spent", format_paisa(stmt.total_debit)],
        ["Date", "Time", "Type", "Description", "Amount", "Balance"],
    ]
    for t in stmt.txns:
        sign = "+" if t.amount > 0 else "-"
        rows.append([
            t.date.strftime("%d %b %Y"), "10:15 AM",
            "IBFT In" if t.amount > 0 else "IBFT Out", t.description,
            f"{sign}Rs. {format_paisa(abs(t.amount))}",
            f"Rs. {format_paisa(t.balance_after)}",
        ])
    return _csv_bytes(rows)


def write_xlsx(stmt: SynthStatement, layout: str = "meezan") -> bytes:
    """Minimal .xlsx with one sheet of inline strings, readable by openpyxl."""
    writer = {"meezan": write_meezan_csv, "mcb": write_mcb_csv,
              "nayapay": write_nayapay_csv}[layout]
    rows = list(csv.reader(io.StringIO(writer(stmt).decode("utf-8"))))

    def esc(s: str) -> str:
        return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    def col(i: int) -> str:
        name, i = "", i + 1
        while i:
            i, r = divmod(i - 1, 26)
            name = chr(65 + r) + name
        return name

    body = []
    for r, row in enumerate(rows, start=1):
        cells = "".join(
            f'<c r="{col(c)}{r}" t="inlineStr"><is><t xml:space="preserve">'
            f"{esc(v)}</t></is></c>"
            for c, v in enumerate(row)
        )
        body.append(f'<row r="{r}">{cells}</row>')

    sheet = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(body)}</sheetData></worksheet>"
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Statement" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Target="worksheets/sheet1.xml" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/>'
        "</Relationships>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-'
        'officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.'
        'openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>'
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Target="xl/workbook.xml" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
        'officeDocument"/></Relationships>'
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", rels)
        z.writestr("xl/worksheets/sheet1.xml", sheet)
    return buf.getvalue()


def corrupt(data: bytes, how: str) -> bytes:
    """Damage a CSV in one specific way, for fault-injection tests."""
    rows = list(csv.reader(io.StringIO(data.decode("utf-8"))))
    header_i = next(i for i, r in enumerate(rows) if r and r[0] in ("Booking Date", "Date"))
    body = rows[header_i + 1:]
    if not body:
        raise ValueError("nothing to corrupt")

    if how == "drop_row":
        del rows[header_i + 1 + len(body) // 2]
    elif how == "flip_sign":
        r = rows[header_i + 1]
        hdr = rows[header_i]
        if "Debit" in hdr and "Credit" in hdr:
            d, c = hdr.index("Debit"), hdr.index("Credit")
            r[d], r[c] = r[c], r[d]
        else:
            a = hdr.index("Amount")
            r[a] = r[a].replace("Dr", "Cr") if "Dr" in r[a] else r[a].replace("Cr", "Dr")
    elif how == "wrong_total":
        for r in rows[:header_i]:
            if r and r[0] in ("CLOSING BALANCE", "Closing Balance", "Total Income"):
                r[1] = "PKR 1.00" if r[1].startswith("PKR") else "1.00"
    elif how == "bad_amount":
        hdr = rows[header_i]
        idx = hdr.index("Credit") if "Credit" in hdr else hdr.index("Amount")
        rows[header_i + 1][idx] = "1,23.456"
    elif how == "blank_debit_and_credit":
        hdr = rows[header_i]
        if "Debit" in hdr and "Credit" in hdr:
            rows[header_i + 1][hdr.index("Debit")] = ""
            rows[header_i + 1][hdr.index("Credit")] = ""
        else:
            rows[header_i + 1][hdr.index("Amount")] = ""
    elif how == "unsorted_dates":
        if len(body) >= 2:
            rows[header_i + 1], rows[header_i + 2] = rows[header_i + 2], rows[header_i + 1]
    else:
        raise ValueError(f"unknown corruption {how!r}")
    return _csv_bytes(rows)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_synth.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/synth.py tests/test_synth.py
git commit -m "$(cat <<'EOF'
test: add synthetic statement generators

Look-alike Meezan/MCB/NayaPay CSV and XLSX writers with computed running
balances, plus a corrupt() helper for fault injection. No real statement
data enters the repo; fixtures are built at test time.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Tabular engine (CSV/XLSX)

**Files:**
- Create: `src/fbr/engines/tabular.py`
- Test: `tests/test_tabular.py`

**Interfaces:**
- Consumes: `fbr.money`, `fbr.model`, `fbr.config.schema_profile` (Tasks 2, 3, 5); `tests.fixtures.synth` in tests
- Produces:
  - `parse_tabular(data: bytes, profile: Profile, *, sha256: str, filename: str, account_id: str | None) -> ParseResult`
  - `class ParseResult(document: Document, transactions: tuple[Transaction, ...], unresolved: tuple[UnresolvedRow, ...])`
  - `class UnresolvedRow(locator: str, raw: str, reason: str)`
  - `parse_row(profile: Profile, row: dict[str, str]) -> tuple[date, int]` — the callable `run_selftest` (Task 6) expects
  - `read_rows(data: bytes, container: str) -> list[list[str]]`
  - `class ParseError(RuntimeError)`

**Key rules:** columns are mapped by header *name*, never index, because Meezan's CSV orders Debit before Credit while its PDF does the reverse. An amount that fails the grammar produces an `UnresolvedRow`, never a zero.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tabular.py
from datetime import date

import pytest

from fbr.config.schema_profile import Profile
from fbr.engines.tabular import ParseError, parse_row, parse_tabular
from tests.fixtures.synth import (
    SynthTxn,
    build_statement,
    corrupt,
    write_meezan_csv,
    write_mcb_csv,
    write_nayapay_csv,
    write_xlsx,
)

MEEZAN = Profile.model_validate({
    "id": "meezan.csv.v1", "institution": "Meezan Bank Limited", "container": "csv",
    "valid_from": date(2025, 7, 1),
    "detect": {"header_contains": ["Booking Date", "Value Date"]},
    "columns": {"date": "Booking Date", "value_date": "Value Date",
                "description": "Description", "reference": "Doc No",
                "debit": "Debit", "credit": "Credit", "balance": "Available Balance"},
    "formats": {"dates": ["%d %b %Y"], "sign": "columns"},
    "summary": {
        "opening": r"(?i)OPENING\s+BALANCE\D+(?P<value>[\d,]+\.\d{2})",
        "closing": r"(?i)CLOSING\s+BALANCE\D+(?P<value>[\d,]+\.\d{2})",
    },
    "balance": {"semantics": "running", "kind": "available"},
    "selftest": {"cases": [{
        "row": {"Booking Date": "01 Jul 2025", "Value Date": "01 Jul 2025",
                "Doc No": "D00001", "Description": "Top-up", "Debit": "",
                "Credit": "1,000.00", "Available Balance": "1,000.00"},
        "expect_date": date(2025, 7, 1), "expect_amount": 100000}]},
})

MCB = Profile.model_validate({
    "id": "mcb.csv.v1", "institution": "MCB Bank Limited", "container": "csv",
    "valid_from": date(2025, 7, 1),
    "detect": {"header_contains": ["Date", "Reference Number", "Amount"]},
    "columns": {"date": "Date", "description": "Description",
                "reference": "Reference Number", "amount": "Amount", "balance": "Balance"},
    "formats": {"dates": ["%d %b %Y"], "sign": "suffix",
                "debit_tokens": ["Dr"], "credit_tokens": ["Cr"]},
    "summary": {
        "opening": r"(?i)Opening\s+Balance\D+(?P<value>[\d,]+\.\d{2})",
        "closing": r"(?i)Closing\s+Balance\D+(?P<value>[\d,]+\.\d{2})",
    },
    "balance": {"semantics": "running", "kind": "ledger"},
    "selftest": {"cases": [{
        "row": {"Date": "01 Jul 2025", "Description": "Cash", "Reference Number": "1",
                "Amount": "200.00Dr", "Balance": "800.00"},
        "expect_date": date(2025, 7, 1), "expect_amount": -20000}]},
})

NAYAPAY = Profile.model_validate({
    "id": "nayapay.csv.v1", "institution": "NayaPay", "container": "csv",
    "valid_from": date(2025, 7, 1),
    "detect": {"header_contains": ["Date", "Type", "Amount", "Balance"]},
    "columns": {"date": "Date", "description": "Description", "type": "Type",
                "amount": "Amount", "balance": "Balance"},
    "formats": {"dates": ["%d %b %Y"], "sign": "signed"},
    "summary": {
        "total_credit": r"(?i)Total\s+Income\D+(?P<value>[\d,]+\.\d{2})",
        "total_debit": r"(?i)Total\s+Spent\D+(?P<value>[\d,]+\.\d{2})",
    },
    "balance": {"semantics": "running", "kind": "ledger"},
    "selftest": {"cases": [{
        "row": {"Date": "01 Jul 2025", "Time": "10:15 AM", "Type": "IBFT In",
                "Description": "x", "Amount": "+Rs. 500.00", "Balance": "Rs. 1,500.00"},
        "expect_date": date(2025, 7, 1), "expect_amount": 50000}]},
})


def _parse(data, profile, account_id="acct"):
    return parse_tabular(data, profile, sha256="a" * 64,
                         filename="x.csv", account_id=account_id)


def test_parses_a_meezan_statement_end_to_end():
    stmt = build_statement(seed=11)
    res = _parse(write_meezan_csv(stmt), MEEZAN)
    assert len(res.transactions) == len(stmt.txns)
    assert res.unresolved == ()
    assert [t.amount for t in res.transactions] == [t.amount for t in stmt.txns]
    assert [t.balance_after for t in res.transactions] == [t.balance_after for t in stmt.txns]


def test_reads_summary_values_from_the_preamble():
    stmt = build_statement(seed=12)
    res = _parse(write_meezan_csv(stmt), MEEZAN)
    assert res.document.summary.opening == stmt.opening
    assert res.document.summary.closing == stmt.closing


def test_columns_are_mapped_by_name_not_position():
    # Meezan's CSV has Debit BEFORE Credit; a positional parser would invert
    # every sign here.
    stmt = build_statement(
        opening=0,
        rows=[SynthTxn(date(2025, 7, 2), "Top-up", 50000, None),
              SynthTxn(date(2025, 7, 3), "Withdrawal", -20000, None)],
    )
    res = _parse(write_meezan_csv(stmt), MEEZAN)
    assert [t.amount for t in res.transactions] == [50000, -20000]


def test_blank_unused_side_is_not_treated_as_zero():
    # Review Focus #1
    stmt = build_statement(opening=0, rows=[SynthTxn(date(2025, 7, 2), "Top-up", 50000, None)])
    res = _parse(write_meezan_csv(stmt), MEEZAN)
    assert res.transactions[0].amount == 50000


def test_both_sides_blank_is_unresolved_not_zero():
    # Review Focus #1: a row with no amount at all must be flagged, never
    # silently contribute 0 to a total.
    stmt = build_statement(seed=13)
    data = corrupt(write_meezan_csv(stmt), "blank_debit_and_credit")
    res = _parse(data, MEEZAN)
    assert len(res.unresolved) == 1
    assert "no amount" in res.unresolved[0].reason.lower()


def test_dash_placeholder_counts_as_no_amount():
    # Review Focus #1: some exports print "-" for the unused side.
    stmt = build_statement(opening=0, rows=[SynthTxn(date(2025, 7, 2), "Top-up", 50000, None)])
    data = write_meezan_csv(stmt).replace(b',,500.00', b',-,500.00')
    res = _parse(data, MEEZAN)
    assert res.transactions[0].amount == 50000
    assert res.unresolved == ()


def test_a_malformed_amount_is_unresolved():
    # Review Focus #4
    stmt = build_statement(seed=14)
    res = _parse(corrupt(write_meezan_csv(stmt), "bad_amount"), MEEZAN)
    assert len(res.unresolved) == 1
    assert "1,23.456" in res.unresolved[0].raw


def test_mcb_dr_cr_suffix_sets_direction():
    stmt = build_statement(
        opening=100000,
        rows=[SynthTxn(date(2025, 7, 2), "Cash", -20000, None),
              SynthTxn(date(2025, 7, 3), "Salary", 300000, None)],
    )
    res = _parse(write_mcb_csv(stmt), MCB)
    assert [t.amount for t in res.transactions] == [-20000, 300000]
    assert {t.provenance.sign_source for t in res.transactions} == {"suffix"}


def test_nayapay_signed_amounts():
    stmt = build_statement(
        opening=100000,
        rows=[SynthTxn(date(2025, 7, 2), "IBFT In", 50000, None),
              SynthTxn(date(2025, 7, 3), "IBFT Out", -30000, None)],
    )
    res = _parse(write_nayapay_csv(stmt), NAYAPAY)
    assert [t.amount for t in res.transactions] == [50000, -30000]
    assert {t.provenance.sign_source for t in res.transactions} == {"signed"}
    assert res.document.summary.total_credit == 50000


def test_xlsx_parses_identically_to_csv():
    stmt = build_statement(seed=15)
    from_csv = _parse(write_meezan_csv(stmt), MEEZAN)
    from_xlsx = parse_tabular(write_xlsx(stmt, "meezan"), MEEZAN.model_copy(
        update={"container": "xlsx"}), sha256="b" * 64, filename="x.xlsx", account_id="acct")
    assert [t.amount for t in from_xlsx.transactions] == [t.amount for t in from_csv.transactions]


def test_rows_keep_printed_order_even_when_dates_are_not_ascending():
    # Review Focus #2: the engine must not sort.
    stmt = build_statement(seed=16)
    res = _parse(corrupt(write_meezan_csv(stmt), "unsorted_dates"), MEEZAN)
    dates = [t.date for t in res.transactions]
    assert dates != sorted(dates), "engine must preserve printed order"


def test_transactions_carry_provenance_and_tax_year():
    stmt = build_statement(opening=0, rows=[SynthTxn(date(2025, 7, 2), "Top-up", 50000, None)])
    t = _parse(write_meezan_csv(stmt), MEEZAN).transactions[0]
    assert t.tax_year == "TY2026"
    assert t.provenance.sha256 == "a" * 64
    assert t.provenance.locator.startswith("row:")
    assert "Top-up" in t.provenance.raw_text


def test_identical_rows_get_distinct_ids():
    stmt = build_statement(
        opening=0,
        rows=[SynthTxn(date(2025, 7, 2), "TOPUP", 100000, None),
              SynthTxn(date(2025, 7, 2), "TOPUP", 100000, None)],
    )
    # Balances differ here, so also check the no-balance case via parse_row ids.
    res = _parse(write_meezan_csv(stmt), MEEZAN)
    assert len({t.txn_id for t in res.transactions}) == 2


def test_missing_header_raises_with_a_useful_message():
    with pytest.raises(ParseError, match="header"):
        _parse(b"nothing,useful\n1,2\n", MEEZAN)


def test_missing_mapped_column_names_the_column():
    stmt = build_statement(seed=17)
    data = write_meezan_csv(stmt).replace(b"Available Balance", b"Closing Bal")
    with pytest.raises(ParseError, match="Available Balance"):
        _parse(data, MEEZAN)


def test_parse_row_supports_profile_selftests():
    for profile in (MEEZAN, MCB, NAYAPAY):
        case = profile.selftest.cases[0]
        assert parse_row(profile, case.row) == (case.expect_date, case.expect_amount)


def test_unknown_date_format_is_unresolved():
    stmt = build_statement(seed=18)
    data = write_meezan_csv(stmt).replace(b"01 Jul 2025", b"2025/07/01")
    res = _parse(data, MEEZAN)
    assert any("date" in u.reason.lower() for u in res.unresolved)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_tabular.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'fbr.engines.tabular'`

- [ ] **Step 3: Write the implementation**

```python
# src/fbr/engines/tabular.py
"""CSV/XLSX statement engine.

Columns are found by header NAME, never by index: Meezan's CSV export puts
Debit before Credit while its PDF puts Credit first, so a positional parser
would invert the sign of every row in one of them and reconcile perfectly
against nothing.

Rows stay in printed order. Anything this engine cannot read becomes an
UnresolvedRow, which fails the statement in reconcile.py, rather than a
silent zero.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime

from fbr.config.schema_profile import Profile
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

# Values a bank prints to mean "nothing on this side of the ledger".
_EMPTY_MARKERS = {"", "-", "--", "—", "–", "n/a", "na", "nil"}


class ParseError(RuntimeError):
    """The file cannot be parsed with this profile at all."""


@dataclass(frozen=True, slots=True)
class UnresolvedRow:
    locator: str
    raw: str
    reason: str


@dataclass(frozen=True, slots=True)
class ParseResult:
    document: Document
    transactions: tuple[Transaction, ...]
    unresolved: tuple[UnresolvedRow, ...]


def read_rows(data: bytes, container: str) -> list[list[str]]:
    """Decode a CSV or XLSX file into a list of string rows."""
    if container == "xlsx":
        return _read_xlsx(data)
    text = _decode_csv(data)
    return [row for row in csv.reader(io.StringIO(text))]


def _decode_csv(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ParseError("cannot decode file as UTF-8 or CP1252")


def _read_xlsx(data: bytes) -> list[list[str]]:
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    try:
        ws = wb[wb.sheetnames[0]]
        return [
            ["" if c is None else str(c) for c in row]
            for row in ws.iter_rows(values_only=True)
        ]
    finally:
        wb.close()


def _labels(spec: str | list[str] | None) -> list[str]:
    if spec is None:
        return []
    return [spec] if isinstance(spec, str) else list(spec)


def _find_header(rows: list[list[str]], profile: Profile) -> int:
    """Return the index of the header row, searching the first 30 rows."""
    wanted = [w.strip().lower() for w in profile.detect.header_contains]
    for i, row in enumerate(rows[:30]):
        cells = [c.strip().lower() for c in row]
        if all(any(w == c for c in cells) for w in wanted):
            return i
    raise ParseError(
        f"header row not found for profile {profile.id!r}; expected all of "
        f"{profile.detect.header_contains}"
    )


def _map_columns(header: list[str], profile: Profile) -> dict[str, int]:
    """Map each profile role to a column index by header name."""
    normalized = {c.strip().lower(): i for i, c in enumerate(header)}
    mapping: dict[str, int] = {}
    roles = ("date", "value_date", "description", "reference", "debit",
             "credit", "amount", "balance", "type")
    required = {"date", "description"}
    required |= ({"debit", "credit"} if profile.formats.sign == "columns" else {"amount"})

    for role in roles:
        for label in _labels(getattr(profile.columns, role, None)):
            idx = normalized.get(label.strip().lower())
            if idx is not None:
                mapping[role] = idx
                break
        else:
            if role in required:
                labels = _labels(getattr(profile.columns, role, None))
                raise ParseError(
                    f"profile {profile.id!r} expects column {labels!r} for role "
                    f"{role!r}; header has {header!r}"
                )
    return mapping


def _cell(row: list[str], mapping: dict[str, int], role: str) -> str:
    idx = mapping.get(role)
    if idx is None or idx >= len(row):
        return ""
    return row[idx].strip()


def _is_empty(value: str) -> bool:
    return value.strip().lower() in _EMPTY_MARKERS


def _parse_date(text: str, profile: Profile) -> date:
    for fmt in profile.formats.dates:
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"date {text!r} matches none of {profile.formats.dates}")


def _strip_suffix(text: str, profile: Profile) -> tuple[str, int]:
    """Split an MCB-style '1,234.00Dr' into its number and its direction."""
    cleaned = text.strip()
    for token in profile.formats.credit_tokens:
        if cleaned.lower().endswith(token.lower()):
            return cleaned[: -len(token)].strip(" ."), 1
    for token in profile.formats.debit_tokens:
        if cleaned.lower().endswith(token.lower()):
            return cleaned[: -len(token)].strip(" ."), -1
    raise ValueError(
        f"amount {text!r} has no direction token "
        f"({profile.formats.debit_tokens + profile.formats.credit_tokens})"
    )


def _amount_for(row: list[str], mapping: dict[str, int], profile: Profile) -> tuple[int, str]:
    """Return (signed paisa, sign_source). Raises ValueError if unreadable."""
    mode = profile.formats.sign

    if mode == "columns":
        debit, credit = _cell(row, mapping, "debit"), _cell(row, mapping, "credit")
        d_empty, c_empty = _is_empty(debit), _is_empty(credit)
        if d_empty and c_empty:
            raise ValueError("row has no amount in either the debit or credit column")
        if not d_empty and not c_empty:
            raise ValueError(f"row has amounts in both columns: {debit!r} and {credit!r}")
        if c_empty:
            return -parse_paisa(debit, decimals=profile.formats.decimals), "column"
        return parse_paisa(credit, decimals=profile.formats.decimals), "column"

    raw = _cell(row, mapping, "amount")
    if _is_empty(raw):
        raise ValueError("row has no amount")

    if mode == "suffix":
        number, direction = _strip_suffix(raw, profile)
        return direction * abs(parse_paisa(number, decimals=profile.formats.decimals)), "suffix"

    return parse_paisa(raw, decimals=profile.formats.decimals), "signed"


def parse_row(profile: Profile, row: dict[str, str]) -> tuple[date, int]:
    """Parse one labelled row. Used by profile self-tests (loader.run_selftest)."""
    header = list(row.keys())
    values = [row[k] for k in header]
    mapping = _map_columns(header, profile)
    d = _parse_date(_cell(values, mapping, "date"), profile)
    amount, _ = _amount_for(values, mapping, profile)
    return d, amount


def _read_summary(preamble_text: str, profile: Profile) -> DocumentSummary:
    """Pull opening/closing/totals/period out of the rows above the header."""
    found: dict[str, object] = {}
    for name, pattern in profile.summary.compiled().items():
        m = pattern.search(preamble_text)
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
    return DocumentSummary(**found)  # type: ignore[arg-type]


def parse_tabular(
    data: bytes,
    profile: Profile,
    *,
    sha256: str,
    filename: str,
    account_id: str | None,
) -> ParseResult:
    """Parse a CSV/XLSX statement into a Document and its Transactions."""
    rows = read_rows(data, profile.container)
    if not rows:
        raise ParseError("file is empty")

    header_i = _find_header(rows, profile)
    mapping = _map_columns(rows[header_i], profile)
    preamble = "\n".join(",".join(r) for r in rows[:header_i])
    summary = _read_summary(preamble, profile)

    skip = [p for p in profile.rows.skip]
    summary_patterns = [p for p in profile.rows.summary]
    import re as _re

    skip_res = [_re.compile(p) for p in skip]
    summary_res = [_re.compile(p) for p in summary_patterns]

    staged: list[dict] = []
    unresolved: list[UnresolvedRow] = []

    for offset, row in enumerate(rows[header_i + 1:], start=header_i + 2):
        raw = ",".join(row)
        locator = f"row:{offset}"
        if not any(cell.strip() for cell in row):
            continue
        if any(r.search(raw) for r in skip_res) or any(r.search(raw) for r in summary_res):
            continue

        date_text = _cell(row, mapping, "date")
        if _is_empty(date_text):
            unresolved.append(UnresolvedRow(locator, raw, "row has no date"))
            continue
        try:
            d = _parse_date(date_text, profile)
        except ValueError as exc:
            unresolved.append(UnresolvedRow(locator, raw, f"unreadable date: {exc}"))
            continue

        try:
            amount, sign_source = _amount_for(row, mapping, profile)
        except (ValueError, AmountError) as exc:
            unresolved.append(UnresolvedRow(locator, raw, str(exc)))
            continue

        balance_text = _cell(row, mapping, "balance")
        balance: int | None = None
        if profile.balance.semantics == "running" and not _is_empty(balance_text):
            try:
                balance = parse_paisa(balance_text, decimals=profile.formats.decimals)
            except AmountError as exc:
                unresolved.append(UnresolvedRow(locator, raw, f"unreadable balance: {exc}"))
                continue

        value_date_text = _cell(row, mapping, "value_date")
        value_date: date | None = None
        if not _is_empty(value_date_text):
            try:
                value_date = _parse_date(value_date_text, profile)
            except ValueError:
                value_date = None

        staged.append({
            "date": d,
            "value_date": value_date,
            "amount": amount,
            "balance_after": balance,
            "description": _cell(row, mapping, "description"),
            "reference": _cell(row, mapping, "reference") or None,
            "sign_source": sign_source,
            "locator": locator,
            "raw": raw,
        })

    occurrences = assign_occurrences(staged)
    transactions = tuple(
        Transaction(
            txn_id=make_txn_id(
                account_id or "unassigned", s["date"], s["amount"],
                s["balance_after"], s["description"], occ,
            ),
            account_id=account_id or "unassigned",
            date=s["date"],
            value_date=s["value_date"],
            amount=s["amount"],
            balance_after=s["balance_after"],
            description=s["description"],
            reference=s["reference"],
            tax_year=tax_year_for(s["date"]),
            provenance=Provenance(
                sha256=sha256, locator=s["locator"], raw_text=s["raw"],
                sign_source=s["sign_source"],
            ),
        )
        for s, occ in zip(staged, occurrences, strict=True)
    )

    document = Document(
        sha256=sha256,
        filename=filename,
        kind="statement",
        container=profile.container,
        layout_id=profile.id,
        account_id=account_id,
        period_start=summary.period_start or (transactions[0].date if transactions else None),
        period_end=summary.period_end or (transactions[-1].date if transactions else None),
        pages=1,
        encrypted=False,
        summary=summary,
    )
    return ParseResult(document, transactions, tuple(unresolved))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_tabular.py -v`
Expected: PASS. If `test_dash_placeholder_counts_as_no_amount` fails on the byte replacement, print the generated CSV and adjust the replacement to match the writer's exact output; do not weaken `_EMPTY_MARKERS`.

- [ ] **Step 5: Commit**

```bash
git add src/fbr/engines/tabular.py tests/test_tabular.py
git commit -m "$(cat <<'EOF'
feat: add CSV/XLSX statement engine

Columns mapped by header name (Meezan's CSV orders Debit before Credit,
its PDF the reverse), three sign modes, printed-order preservation, and
UnresolvedRow for anything unreadable rather than a silent zero.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Ingest — container sniffing, layout detection, account resolution

**Files:**
- Create: `src/fbr/ingest.py`
- Test: `tests/test_ingest.py`

**Interfaces:**
- Consumes: `fbr.config.loader` (Task 6), `fbr.engines.tabular` (Task 8), `fbr.model` (Task 3)
- Produces:
  - `sniff_container(data: bytes, filename: str) -> str` — `"csv" | "xlsx" | "pdf"`
  - `detect_layout(data: bytes, profiles: ProfileSet, container: str, *, on: date | None = None) -> Profile`
  - `class LayoutUnknown(RuntimeError)`, `class LayoutAmbiguous(RuntimeError)`
  - `resolve_account(summary: DocumentSummary, text: str, registry: Registry) -> str | None`
  - `sha256_of(data: bytes) -> str`
  - `usable_profiles(profiles: ProfileSet, container: str) -> tuple[tuple[Profile, ...], tuple[ProfileStatus, ...]]` — runs each profile's self-test and drops failures

**Rules:** the container comes from the file's bytes, not its extension, because a bank that emails `statement.csv` containing XLSX bytes would otherwise crash mid-parse. Ambiguous detection raises rather than picking (Review Focus #3).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ingest.py
from datetime import date

import pytest

from fbr.config.loader import ProfileSet, ProfileStatus
from fbr.config.schema_profile import Profile
from fbr.ingest import (
    LayoutAmbiguous,
    LayoutUnknown,
    detect_layout,
    resolve_account,
    sha256_of,
    sniff_container,
    usable_profiles,
)
from fbr.model import Account, DocumentSummary, Owner, Registry
from tests.fixtures.synth import build_statement, write_meezan_csv, write_mcb_csv, write_xlsx
from tests.test_tabular import MCB, MEEZAN


def _set(*profiles: Profile) -> ProfileSet:
    return ProfileSet(
        profiles,
        tuple(ProfileStatus(p.id, f"{p.id}.toml", True, "loaded") for p in profiles),
    )


def test_sniffs_csv_xlsx_and_pdf_from_bytes():
    stmt = build_statement(seed=21)
    assert sniff_container(write_meezan_csv(stmt), "x.csv") == "csv"
    assert sniff_container(write_xlsx(stmt), "x.xlsx") == "xlsx"
    assert sniff_container(b"%PDF-1.7\n...", "x.pdf") == "pdf"


def test_sniffing_ignores_a_misleading_extension():
    stmt = build_statement(seed=22)
    # A bank emailing XLSX bytes named .csv must not crash the CSV reader.
    assert sniff_container(write_xlsx(stmt), "statement.csv") == "xlsx"


def test_detects_the_matching_layout():
    stmt = build_statement(seed=23)
    got = detect_layout(write_meezan_csv(stmt), _set(MEEZAN, MCB), "csv")
    assert got.id == "meezan.csv.v1"


def test_unknown_layout_raises_with_guidance():
    with pytest.raises(LayoutUnknown, match="fbr-dump"):
        detect_layout(b"a,b\n1,2\n", _set(MEEZAN, MCB), "csv")


def test_two_matching_profiles_raise_rather_than_guess():
    # Review Focus #3: picking one silently would attach a wrong layout.
    twin = MEEZAN.model_copy(update={"id": "meezan.csv.v2"})
    stmt = build_statement(seed=24)
    with pytest.raises(LayoutAmbiguous, match="meezan.csv.v1.*meezan.csv.v2"):
        detect_layout(write_meezan_csv(stmt), _set(MEEZAN, twin), "csv")


def test_valid_from_narrows_candidates():
    future = MEEZAN.model_copy(update={"id": "meezan.csv.v2", "valid_from": date(2030, 7, 1)})
    stmt = build_statement(seed=25)
    got = detect_layout(write_meezan_csv(stmt), _set(MEEZAN, future), "csv", on=date(2026, 1, 1))
    assert got.id == "meezan.csv.v1"


def test_only_profiles_for_the_container_are_considered():
    pdf_profile = MEEZAN.model_copy(update={"id": "meezan.pdf.v1", "container": "pdf"})
    stmt = build_statement(seed=26)
    got = detect_layout(write_meezan_csv(stmt), _set(pdf_profile, MEEZAN), "csv")
    assert got.id == "meezan.csv.v1"


REGISTRY = Registry(
    owner=Owner(name="OWNER NAME"),
    accounts=(
        Account(
            id="meezan-main", institution="Meezan Bank Limited", kind="bank",
            iban="PK00TEST0000000000000000", account_number="0000000000",
            wallet_number="", title="ACCOUNT TITLE", type="Saving", ownership="Self",
            currency="PKR", statement_expected=True, match_hints=("MEEZAN",),
        ),
        Account(
            id="sadapay", institution="SadaPay", kind="wallet", iban="",
            account_number="", wallet_number="03001234567", title="ACCOUNT TITLE",
            type="", ownership="Self", currency="PKR", statement_expected=True,
            match_hints=("SADA",),
        ),
    ),
)


def test_resolves_an_account_by_iban():
    s = DocumentSummary(account_identifier="PK00TEST0000000000000000")
    assert resolve_account(s, "", REGISTRY) == "meezan-main"


def test_resolves_by_account_number_inside_free_text():
    assert resolve_account(DocumentSummary(), "Account No 0000000000", REGISTRY) == "meezan-main"


def test_resolves_by_wallet_number():
    assert resolve_account(DocumentSummary(), "Wallet 03001234567", REGISTRY) == "sadapay"


def test_iban_match_ignores_spacing_and_case():
    s = DocumentSummary(account_identifier="pk00 test 0000 0000 0000 0000")
    assert resolve_account(s, "", REGISTRY) == "meezan-main"


def test_returns_none_when_nothing_matches():
    assert resolve_account(DocumentSummary(), "no identifiers here", REGISTRY) is None


def test_sha256_is_stable():
    assert sha256_of(b"abc") == sha256_of(b"abc")
    assert len(sha256_of(b"abc")) == 64


def test_usable_profiles_drops_one_whose_selftest_fails():
    broken = MEEZAN.model_copy(update={
        "id": "broken.csv.v1",
        "selftest": MEEZAN.selftest.model_copy(update={
            "cases": [MEEZAN.selftest.cases[0].model_copy(update={"expect_amount": 999})]
        }),
    })
    usable, report = usable_profiles(_set(MEEZAN, broken), "csv")
    assert [p.id for p in usable] == ["meezan.csv.v1"]
    assert any(not s.ok and s.profile_id == "broken.csv.v1" for s in report)


def test_a_failing_profile_cannot_be_detected():
    broken = MEEZAN.model_copy(update={
        "id": "broken.csv.v1",
        "selftest": MEEZAN.selftest.model_copy(update={
            "cases": [MEEZAN.selftest.cases[0].model_copy(update={"expect_amount": 999})]
        }),
    })
    stmt = build_statement(seed=27)
    # Both would match by header; only the healthy one is a candidate.
    got = detect_layout(write_meezan_csv(stmt), _set(MEEZAN, broken), "csv")
    assert got.id == "meezan.csv.v1"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_ingest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'fbr.ingest'`

- [ ] **Step 3: Write the implementation**

```python
# src/fbr/ingest.py
"""Decide what a file is, which layout reads it, and whose account it is.

The container is sniffed from the bytes rather than the file name, and an
ambiguous layout match raises instead of picking: attaching the wrong layout
to a real statement is exactly the failure that would produce confident,
wrong numbers.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date

from fbr.config.loader import ProfileSet, ProfileStatus, run_selftest
from fbr.config.schema_profile import Profile
from fbr.engines.tabular import ParseError, parse_row, read_rows
from fbr.model import DocumentSummary, Registry

_XLSX_MAGIC = b"PK\x03\x04"
_PDF_MAGIC = b"%PDF"
_NON_ALNUM = re.compile(r"[^A-Za-z0-9]")


class LayoutUnknown(RuntimeError):
    """No profile matches this file."""


class LayoutAmbiguous(RuntimeError):
    """More than one profile matches; the signatures need tightening."""


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sniff_container(data: bytes, filename: str = "") -> str:
    """Identify the container from the file's own bytes."""
    if data.startswith(_PDF_MAGIC):
        return "pdf"
    if data.startswith(_XLSX_MAGIC):
        # .docx/.pptx share this magic, but only spreadsheets reach this tool.
        return "xlsx"
    return "csv"


def usable_profiles(
    profiles: ProfileSet, container: str
) -> tuple[tuple[Profile, ...], tuple[ProfileStatus, ...]]:
    """Profiles for this container that pass their own self-tests.

    A profile that cannot parse its own sample rows is excluded: it would
    otherwise fail silently on the statement it was written for (spec §5.4).
    """
    candidates = profiles.for_container(container)
    ok: list[Profile] = []
    report: list[ProfileStatus] = []
    for profile in candidates:
        status = run_selftest(profile, parse_row)
        report.append(status)
        if status.ok:
            ok.append(profile)
    return tuple(ok), tuple(report)


def _head_text(data: bytes, container: str, rows: int = 30) -> str:
    try:
        parsed = read_rows(data, container)
    except ParseError:
        return ""
    return "\n".join(",".join(r) for r in parsed[:rows])


def _matches(profile: Profile, head: str) -> bool:
    lowered = head.lower()
    if not all(token.strip().lower() in lowered for token in profile.detect.header_contains):
        return False
    if profile.detect.title_regex and not re.search(profile.detect.title_regex, head):
        return False
    return True


def detect_layout(
    data: bytes,
    profiles: ProfileSet,
    container: str,
    *,
    on: date | None = None,
) -> Profile:
    """Return the single profile that matches this file."""
    candidates, _ = usable_profiles(profiles, container)
    if on is not None:
        candidates = tuple(
            p for p in candidates
            if p.valid_from <= on and (p.valid_to is None or on <= p.valid_to)
        )

    head = _head_text(data, container)
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


def _squash(value: str) -> str:
    return _NON_ALNUM.sub("", value).upper()


def resolve_account(
    summary: DocumentSummary, text: str, registry: Registry
) -> str | None:
    """Link a statement to a registry account by IBAN, number or wallet.

    Comparison ignores spacing and case, because statements print IBANs
    grouped in fours as often as not.
    """
    haystack = _squash(f"{summary.account_identifier or ''} {text}")
    if not haystack:
        return None
    for account in registry.accounts:
        for identifier in (account.iban, account.account_number, account.wallet_number):
            if identifier and _squash(identifier) in haystack:
                return account.id
    return None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_ingest.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/fbr/ingest.py tests/test_ingest.py
git commit -m "$(cat <<'EOF'
feat: add container sniffing, layout detection and account resolution

Container comes from file bytes, not the extension. Ambiguous layout
matches raise rather than pick, and profiles failing their own self-tests
are excluded from detection.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Reconciliation — per-statement checks

**Files:**
- Create: `src/fbr/reconcile.py`
- Test: `tests/test_reconcile_statement.py`

**Interfaces:**
- Consumes: `fbr.model` (Task 3), `fbr.engines.tabular.ParseResult` (Task 8)
- Produces:
  - `check_statement(result: ParseResult, profile: Profile) -> tuple[Check, ...]`
  - `worst_status(checks) -> str` — `"pass" | "warn" | "fail"`
  - `statement_usable(checks) -> bool` — False if any check failed

**The five checks (spec §6.1):** `running_balance`, `opening_closing`, `printed_totals`, `unresolved_rows`, `date_range`. All arithmetic is exact integer; there is no tolerance, because a tolerance here would hide exactly the parser bugs these checks exist to catch.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_reconcile_statement.py
from datetime import date

from fbr.engines.tabular import parse_tabular
from fbr.reconcile import check_statement, statement_usable, worst_status
from tests.fixtures.synth import SynthTxn, build_statement, corrupt, write_meezan_csv
from tests.test_tabular import MEEZAN


def _checks(data, profile=MEEZAN):
    res = parse_tabular(data, profile, sha256="a" * 64, filename="x.csv",
                        account_id="meezan-main")
    return res, check_statement(res, profile)


def _kinds(checks, status=None):
    return {c.kind for c in checks if status is None or c.status == status}


def test_a_clean_statement_passes_every_check():
    _, checks = _checks(write_meezan_csv(build_statement(seed=31)))
    assert _kinds(checks, "fail") == set()
    assert statement_usable(checks) is True
    assert worst_status(checks) == "pass"


def test_all_five_checks_are_reported():
    _, checks = _checks(write_meezan_csv(build_statement(seed=32)))
    assert {"running_balance", "opening_closing", "unresolved_rows", "date_range"} <= _kinds(checks)


def test_a_dropped_row_breaks_the_running_balance():
    _, checks = _checks(corrupt(write_meezan_csv(build_statement(seed=33)), "drop_row"))
    assert "running_balance" in _kinds(checks, "fail")
    assert statement_usable(checks) is False


def test_a_flipped_sign_breaks_the_running_balance():
    _, checks = _checks(corrupt(write_meezan_csv(build_statement(seed=34)), "flip_sign"))
    assert "running_balance" in _kinds(checks, "fail")


def test_a_wrong_printed_closing_breaks_opening_closing():
    _, checks = _checks(corrupt(write_meezan_csv(build_statement(seed=35)), "wrong_total"))
    assert "opening_closing" in _kinds(checks, "fail")


def test_an_unresolved_row_fails_the_statement():
    _, checks = _checks(corrupt(write_meezan_csv(build_statement(seed=36)), "bad_amount"))
    assert "unresolved_rows" in _kinds(checks, "fail")
    assert statement_usable(checks) is False


def test_the_failing_check_locates_the_row():
    _, checks = _checks(corrupt(write_meezan_csv(build_statement(seed=37)), "drop_row"))
    failure = next(c for c in checks if c.kind == "running_balance" and c.status == "fail")
    assert failure.locator and failure.locator.startswith("row:")
    assert failure.expected != failure.actual


def test_running_balance_walks_printed_order_not_date_order():
    # Review Focus #2: a statement sorted by value date still reconciles,
    # because the balance chain follows the printed sequence.
    stmt = build_statement(
        opening=100000,
        rows=[SynthTxn(date(2025, 7, 9), "Later date first", 50000, None),
              SynthTxn(date(2025, 7, 5), "Earlier date second", -20000, None)],
    )
    _, checks = _checks(write_meezan_csv(stmt))
    assert "running_balance" not in _kinds(checks, "fail")


def test_a_date_outside_the_printed_period_fails():
    stmt = build_statement(
        opening=0, start=date(2025, 7, 1), end=date(2025, 7, 31),
        rows=[SynthTxn(date(2025, 7, 2), "In period", 50000, None),
              SynthTxn(date(2026, 3, 1), "Out of period", 10000, None)],
    )
    _, checks = _checks(write_meezan_csv(stmt))
    assert "date_range" in _kinds(checks, "fail")


def test_missing_opening_balance_warns_rather_than_fails():
    data = write_meezan_csv(build_statement(seed=38)).replace(b"OPENING BALANCE", b"NOT PRINTED")
    _, checks = _checks(data)
    assert "running_balance" in _kinds(checks, "warn")
    assert statement_usable(checks) is True


def test_no_balance_column_skips_the_balance_checks_without_failing():
    no_balance = MEEZAN.model_copy(update={
        "balance": MEEZAN.balance.model_copy(update={"semantics": "none"})
    })
    _, checks = _checks(write_meezan_csv(build_statement(seed=39)), no_balance)
    assert "running_balance" not in _kinds(checks, "fail")


def test_worst_status_prefers_fail_over_warn():
    _, clean = _checks(write_meezan_csv(build_statement(seed=40)))
    _, broken = _checks(corrupt(write_meezan_csv(build_statement(seed=40)), "drop_row"))
    assert worst_status(clean) in ("pass", "warn")
    assert worst_status(broken) == "fail"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_reconcile_statement.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'fbr.reconcile'`

- [ ] **Step 3: Write the implementation**

```python
# src/fbr/reconcile.py
"""Reconciliation: prove a parse before any figure is believed.

Every comparison is exact integer arithmetic. A tolerance would hide the
very bugs these checks exist to catch - a dropped row, a flipped sign, a
misread digit - and a tax return that is nearly right is wrong.

A statement with any failing check contributes nothing to any total
(spec §6.1, "fail closed").
"""

from __future__ import annotations

from fbr.config.schema_profile import Profile
from fbr.engines.tabular import ParseResult
from fbr.model import Check
from fbr.money import format_paisa

_ORDER = {"pass": 0, "warn": 1, "fail": 2}


def worst_status(checks: tuple[Check, ...] | list[Check]) -> str:
    return max((c.status for c in checks), key=lambda s: _ORDER[s], default="pass")


def statement_usable(checks: tuple[Check, ...] | list[Check]) -> bool:
    """False when any check failed: the statement's figures must not be used."""
    return not any(c.status == "fail" for c in checks)


def _check(kind, status, expected, actual, detail, locator=None, scope="document") -> Check:
    return Check(
        check_id=f"{scope}:{kind}",
        scope=scope,
        kind=kind,
        status=status,
        expected=expected,
        actual=actual,
        detail=detail,
        locator=locator,
    )


def _check_running_balance(result: ParseResult, profile: Profile) -> Check | None:
    """prev + amount == balance, walked in PRINTED order.

    Printed order, not date order: a bank may list same-day rows by posting
    sequence, and sorting first would break a chain that is actually correct.
    """
    if profile.balance.semantics != "running":
        return None
    txns = [t for t in result.transactions if t.balance_after is not None]
    if not txns:
        return _check("running_balance", "warn", "a balance column", "none",
                      "no row carried a balance; chain not verified")

    opening = result.document.summary.opening
    if opening is None:
        # Without a printed opening we can still verify every step after the
        # first, which catches dropped and flipped rows from row 2 onwards.
        previous = txns[0].balance_after - txns[0].amount
        note = "opening balance not printed; chain anchored on the first row"
        status_if_ok = "warn"
    else:
        previous = opening
        note = "chain verified from the printed opening balance"
        status_if_ok = "pass"

    for t in txns:
        expected = previous + t.amount
        if t.balance_after != expected:
            return _check(
                "running_balance", "fail",
                format_paisa(expected), format_paisa(t.balance_after),
                f"balance chain breaks at {t.date.isoformat()} "
                f"({t.description[:40]!r}); a row may be missing, merged or misread",
                locator=t.provenance.locator,
            )
        previous = t.balance_after

    return _check("running_balance", status_if_ok,
                  format_paisa(previous), format_paisa(previous), note)


def _check_opening_closing(result: ParseResult) -> Check | None:
    summary = result.document.summary
    if summary.opening is None or summary.closing is None:
        return _check("opening_closing", "warn", "printed opening and closing", "not both printed",
                      "statement does not print both balances; check skipped")
    total = sum(t.amount for t in result.transactions)
    expected = summary.opening + total
    status = "pass" if expected == summary.closing else "fail"
    return _check(
        "opening_closing", status,
        format_paisa(summary.closing), format_paisa(expected),
        "opening + credits - debits must equal the printed closing balance",
    )


def _check_printed_totals(result: ParseResult) -> Check | None:
    summary = result.document.summary
    if summary.total_credit is None and summary.total_debit is None:
        return None
    credits = sum(t.amount for t in result.transactions if t.amount > 0)
    debits = -sum(t.amount for t in result.transactions if t.amount < 0)
    problems = []
    if summary.total_credit is not None and summary.total_credit != credits:
        problems.append(
            f"credits: printed {format_paisa(summary.total_credit)}, "
            f"parsed {format_paisa(credits)}"
        )
    if summary.total_debit is not None and summary.total_debit != debits:
        problems.append(
            f"debits: printed {format_paisa(summary.total_debit)}, "
            f"parsed {format_paisa(debits)}"
        )
    return _check(
        "printed_totals", "fail" if problems else "pass",
        f"credits {format_paisa(summary.total_credit or credits)} / "
        f"debits {format_paisa(summary.total_debit or debits)}",
        f"credits {format_paisa(credits)} / debits {format_paisa(debits)}",
        "; ".join(problems) or "parsed totals match the statement's own totals",
    )


def _check_unresolved(result: ParseResult) -> Check:
    if not result.unresolved:
        return _check("unresolved_rows", "pass", "0", "0", "every row parsed")
    first = result.unresolved[0]
    return _check(
        "unresolved_rows", "fail", "0", str(len(result.unresolved)),
        f"{len(result.unresolved)} row(s) could not be parsed; first: {first.reason}",
        locator=first.locator,
    )


def _check_date_range(result: ParseResult) -> Check:
    doc = result.document
    start, end = doc.summary.period_start, doc.summary.period_end
    if start is None or end is None or not result.transactions:
        return _check("date_range", "warn", "a printed period", "not printed",
                      "statement does not print its period; dates not bounded")
    outside = [t for t in result.transactions if not (start <= t.date <= end)]
    if not outside:
        return _check("date_range", "pass", f"{start}..{end}", f"{start}..{end}",
                      "every transaction falls inside the printed period")
    t = outside[0]
    return _check(
        "date_range", "fail", f"{start}..{end}", t.date.isoformat(),
        f"{len(outside)} transaction(s) fall outside the printed period",
        locator=t.provenance.locator,
    )


def check_statement(result: ParseResult, profile: Profile) -> tuple[Check, ...]:
    """Run every per-statement check (spec §6.1)."""
    checks = [
        _check_running_balance(result, profile),
        _check_opening_closing(result),
        _check_printed_totals(result),
        _check_unresolved(result),
        _check_date_range(result),
    ]
    return tuple(c for c in checks if c is not None)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_reconcile_statement.py -v`
Expected: PASS

- [ ] **Step 5: Run the whole suite**

Run: `uv run pytest -v`
Expected: PASS — every test from Tasks 1–10

- [ ] **Step 6: Commit**

```bash
git add src/fbr/reconcile.py tests/test_reconcile_statement.py
git commit -m "$(cat <<'EOF'
feat: add per-statement reconciliation checks

Running balance walked in printed order, opening+credits-debits=closing,
printed totals, unresolved rows and date range. Exact integer arithmetic
with no tolerance; any failure makes the statement unusable.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Account merge and tax-year boundary balances

**Files:**
- Modify: `src/fbr/reconcile.py` (append; do not restructure Task 10's functions)
- Test: `tests/test_reconcile_account.py`

**Interfaces:**
- Consumes: Task 10's `check_statement`, `worst_status`, `statement_usable`
- Produces:
  - `merge_account(results: list[ParseResult], account: Account, tax_year: TaxYear, *, profiles: dict[str, Profile], anchor: int | None = None, prior_year_closing: int | None = None) -> AccountLedger`
    `profiles` maps `layout_id` to the Profile that parsed it, and is **required**: without it the per-statement checks could not run, and a broken statement would pass silently.
  - `class AccountLedger(account_id, transactions, checks, opening, closing, opening_source, closing_source, status)`
  - `class BalanceSource` — `"printed"`, `"computed"`, `"anchor"`, `"unknown"`
  - `tax_year_slice(txns, tax_year) -> tuple[Transaction, ...]`
  - `boundary_balances(txns, *, anchor: int | None, has_balance_column: bool, tax_year) -> tuple[int | None, str, int | None, str]`

**Rules (spec §6.2–6.4):** overlaps are resolved by period, never by matching individual rows across the year, because two identical top-ups on one day are both real. A missing anchor yields `None`, never `0`. `opened_on` and `closed_on` suppress false gap warnings.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_reconcile_account.py
from datetime import date

import pytest

from fbr.config.loader import load_tax_year
from fbr.engines.tabular import parse_tabular
from fbr.model import Account
from fbr.reconcile import merge_account
from tests.fixtures.synth import SynthTxn, build_statement, write_meezan_csv
from tests.test_loader import TAXYEAR_TOML
from tests.test_tabular import MEEZAN


@pytest.fixture
def ty(tmp_path):
    (tmp_path / "TY2026.toml").write_text(TAXYEAR_TOML)
    return load_tax_year("TY2026", tmp_path)


def _account(**over):
    base = dict(
        id="meezan-main", institution="Meezan Bank Limited", kind="bank",
        iban="PK00TEST0000000000000000", account_number="", wallet_number="",
        title="ACCOUNT TITLE", type="Saving", ownership="Self", currency="PKR",
        statement_expected=True, match_hints=("MEEZAN",), opened_on=None, closed_on=None,
    )
    return Account(**{**base, **over})


# merge_account requires the profile that parsed each statement, so the
# per-statement checks can run. Both variants keep the same layout id.
NO_BALANCE_PROFILE = MEEZAN.model_copy(update={
    "balance": MEEZAN.balance.model_copy(update={"semantics": "none"})
})
PROFILES = {"meezan.csv.v1": MEEZAN}
PROFILES_NB = {"meezan.csv.v1": NO_BALANCE_PROFILE}


def _result(stmt, profile=MEEZAN, sha="a" * 64):
    return parse_tabular(write_meezan_csv(stmt), profile, sha256=sha,
                         filename="x.csv", account_id="meezan-main")


def _kinds(ledger, status=None):
    return {c.kind for c in ledger.checks if status is None or c.status == status}


def test_single_full_year_statement_yields_printed_boundaries(ty):
    stmt = build_statement(
        opening=100000, start=date(2025, 7, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2025, 7, 2), "Top-up", 50000, None),
              SynthTxn(date(2026, 6, 29), "Withdrawal", -20000, None)],
    )
    led = merge_account([_result(stmt)], _account(), ty, profiles=PROFILES)
    assert led.opening == 100000 and led.opening_source == "printed"
    assert led.closing == 130000 and led.closing_source == "printed"
    assert led.status == "complete"


def test_two_contiguous_statements_merge(ty):
    first = build_statement(
        opening=100000, start=date(2025, 7, 1), end=date(2025, 12, 31),
        rows=[SynthTxn(date(2025, 8, 1), "A", 50000, None)],
    )
    second = build_statement(
        opening=first.closing, start=date(2026, 1, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2026, 2, 1), "B", -20000, None)],
    )
    led = merge_account([_result(first), _result(second, sha="b" * 64)], _account(), ty, profiles=PROFILES)
    assert len(led.transactions) == 2
    assert led.opening == 100000
    assert led.closing == 130000
    assert "gap" not in _kinds(led, "warn")


def test_a_gap_between_statements_warns_and_marks_incomplete(ty):
    first = build_statement(
        opening=100000, start=date(2025, 7, 1), end=date(2025, 9, 30),
        rows=[SynthTxn(date(2025, 8, 1), "A", 50000, None)],
    )
    third = build_statement(
        opening=999999, start=date(2026, 1, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2026, 2, 1), "B", -20000, None)],
    )
    led = merge_account([_result(first), _result(third, sha="b" * 64)], _account(), ty, profiles=PROFILES)
    assert "gap" in _kinds(led, "warn")
    assert led.status == "incomplete"


def test_a_missing_start_of_year_counts_as_a_gap(ty):
    stmt = build_statement(
        opening=100000, start=date(2025, 10, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2025, 10, 5), "A", 50000, None)],
    )
    led = merge_account([_result(stmt)], _account(), ty, profiles=PROFILES)
    assert "gap" in _kinds(led, "warn")


def test_an_account_opened_mid_year_has_no_false_gap(ty):
    stmt = build_statement(
        opening=0, start=date(2025, 10, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2025, 10, 5), "First ever credit", 50000, None)],
    )
    led = merge_account([_result(stmt)], _account(opened_on=date(2025, 10, 1)), ty, profiles=PROFILES)
    assert "gap" not in _kinds(led, "warn")
    assert led.status == "complete"


def test_identical_overlapping_statements_deduplicate_by_period(ty):
    stmt = build_statement(
        opening=100000, start=date(2025, 7, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2025, 8, 1), "A", 50000, None)],
    )
    led = merge_account([_result(stmt), _result(stmt, sha="b" * 64)], _account(), ty, profiles=PROFILES)
    assert len(led.transactions) == 1
    assert "overlap" not in _kinds(led, "fail")


def test_disagreeing_overlapping_statements_fail(ty):
    a = build_statement(
        opening=100000, start=date(2025, 7, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2025, 8, 1), "A", 50000, None)],
    )
    b = build_statement(
        opening=100000, start=date(2025, 7, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2025, 8, 1), "A", 60000, None)],
    )
    led = merge_account([_result(a), _result(b, sha="b" * 64)], _account(), ty, profiles=PROFILES)
    assert "overlap" in _kinds(led, "fail")
    assert led.status == "failed"


def test_two_identical_same_day_transactions_are_both_kept(ty):
    # Not duplicates: two genuine Rs 1,000 top-ups on one day.
    stmt = build_statement(
        opening=0, start=date(2025, 7, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2025, 8, 1), "TOPUP", 100000, None),
              SynthTxn(date(2025, 8, 1), "TOPUP", 100000, None)],
    )
    led = merge_account([_result(stmt)], _account(), ty, profiles=PROFILES)
    assert len(led.transactions) == 2
    assert led.closing == 200000


def test_transactions_outside_the_tax_year_are_excluded_from_boundaries(ty):
    stmt = build_statement(
        opening=100000, start=date(2025, 6, 1), end=date(2026, 7, 31),
        rows=[SynthTxn(date(2025, 6, 15), "Before TY", 10000, None),
              SynthTxn(date(2025, 8, 1), "In TY", 50000, None),
              SynthTxn(date(2026, 7, 15), "After TY", 70000, None)],
    )
    led = merge_account([_result(stmt)], _account(), ty, profiles=PROFILES)
    assert [t.description for t in led.transactions] == ["In TY"]
    assert led.opening == 110000          # balance after the pre-TY row
    assert led.opening_source == "computed"
    assert led.closing == 160000          # balance after the last in-TY row
    assert led.closing_source == "computed"


def test_a_dormant_account_still_reports_boundaries(ty):
    # Review Focus #5: no transactions in the year, but printed balances exist.
    stmt = build_statement(
        opening=250000, start=date(2025, 7, 1), end=date(2026, 6, 30), rows=[]
    )
    led = merge_account([_result(stmt)], _account(), ty, profiles=PROFILES)
    assert led.transactions == ()
    assert led.opening == 250000 and led.closing == 250000
    assert led.status == "complete"


def test_no_balance_column_uses_the_anchor(ty):
    stmt = build_statement(
        opening=0, start=date(2025, 7, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2025, 8, 1), "A", 50000, None),
              SynthTxn(date(2025, 9, 1), "B", -20000, None)],
    )
    res = parse_tabular(write_meezan_csv(stmt), NO_BALANCE_PROFILE, sha256="a" * 64,
                        filename="x.csv", account_id="meezan-main")
    led = merge_account([res], _account(), ty, anchor=500000, profiles=PROFILES_NB)
    assert led.opening == 500000 and led.opening_source == "anchor"
    assert led.closing == 530000 and led.closing_source == "computed"


def test_no_balance_column_and_no_anchor_yields_unknown_never_zero(ty):
    stmt = build_statement(
        opening=0, start=date(2025, 7, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2025, 8, 1), "A", 50000, None)],
    )
    res = parse_tabular(write_meezan_csv(stmt), NO_BALANCE_PROFILE, sha256="a" * 64,
                        filename="x.csv", account_id="meezan-main")
    led = merge_account([res], _account(), ty, profiles=PROFILES_NB)
    assert led.opening is None and led.opening_source == "unknown"
    assert led.closing is None and led.closing_source == "unknown"
    assert "anchor_missing" in _kinds(led, "warn")


def test_prior_year_mismatch_warns(ty):
    stmt = build_statement(
        opening=100000, start=date(2025, 7, 1), end=date(2026, 6, 30),
        rows=[SynthTxn(date(2025, 8, 1), "A", 50000, None)],
    )
    led = merge_account([_result(stmt)], _account(), ty, prior_year_closing=999999, profiles=PROFILES)
    assert "prior_year_mismatch" in _kinds(led, "warn")


def test_a_missing_profile_raises_rather_than_skipping_the_checks(ty):
    # Fail closed: silently skipping per-statement checks would let a broken
    # statement through.
    stmt = build_statement(seed=52, start=date(2025, 7, 1), end=date(2026, 6, 30))
    with pytest.raises(KeyError, match="no profile supplied"):
        merge_account([_result(stmt)], _account(), ty, profiles={})


def test_a_failed_statement_makes_the_account_failed(ty):
    from tests.fixtures.synth import corrupt
    stmt = build_statement(seed=51, start=date(2025, 7, 1), end=date(2026, 6, 30))
    bad = parse_tabular(corrupt(write_meezan_csv(stmt), "drop_row"), MEEZAN,
                        sha256="a" * 64, filename="x.csv", account_id="meezan-main")
    led = merge_account([bad], _account(), ty, profiles=PROFILES)
    assert led.status == "failed"
    assert led.transactions == ()      # fail closed: contributes nothing
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_reconcile_account.py -v`
Expected: FAIL — `ImportError: cannot import name 'merge_account' from 'fbr.reconcile'`

- [ ] **Step 3: Append the implementation to `src/fbr/reconcile.py`**

```python
# --- appended to src/fbr/reconcile.py ---------------------------------------
"""Account-level merge and tax-year boundary balances (spec §6.2-6.4)."""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from fbr.config.schema_taxyear import TaxYear
from fbr.model import Account, Transaction

BalanceSource = Literal["printed", "computed", "anchor", "unknown"]
AccountStatus = Literal["complete", "incomplete", "failed"]


@dataclass(frozen=True, slots=True)
class AccountLedger:
    account_id: str
    transactions: tuple[Transaction, ...]
    checks: tuple[Check, ...]
    opening: int | None
    closing: int | None
    opening_source: BalanceSource
    closing_source: BalanceSource
    status: AccountStatus


def tax_year_slice(txns: tuple[Transaction, ...], tax_year: TaxYear) -> tuple[Transaction, ...]:
    """Transactions whose booking date falls inside the tax year."""
    return tuple(
        t for t in txns if tax_year.period_start <= t.date <= tax_year.period_end
    )


def _row_key(t: Transaction) -> tuple:
    return (t.date, t.amount, t.balance_after, t.description.strip().upper())


def _dedupe_overlaps(
    results: list[ParseResult],
) -> tuple[list[Transaction], list[Check]]:
    """Resolve overlapping statements by PERIOD, never row by row.

    Two identical Rs 1,000 top-ups on one day are both real, so rows are
    never matched across the year. Instead, where two statements cover the
    same days, the overlapping window must tell the same story; if it does,
    one copy is kept, preferring CSV/XLSX over PDF and then the longer period.
    """
    checks: list[Check] = []
    ordered = sorted(
        results,
        key=lambda r: (
            r.document.period_start or date.min,
            0 if r.document.container in ("csv", "xlsx") else 1,
            -((r.document.period_end or date.min) - (r.document.period_start or date.min)).days,
        ),
    )

    kept: list[Transaction] = []
    covered: list[tuple[date, date]] = []

    for result in ordered:
        start = result.document.period_start
        end = result.document.period_end
        window = next(
            ((s, e) for s, e in covered if start and end and s <= start and end <= e), None
        )
        if window is not None:
            # Fully inside an already-accepted period: the stories must agree.
            existing = [t for t in kept if start <= t.date <= end]
            incoming = list(result.transactions)
            if [_row_key(t) for t in existing] != [_row_key(t) for t in incoming]:
                checks.append(
                    _check(
                        "overlap", "fail",
                        f"{len(existing)} row(s) for {start}..{end}",
                        f"{len(incoming)} row(s) from {result.document.filename}",
                        "two statements cover the same period but disagree; "
                        "re-download one of them",
                        scope="account",
                    )
                )
            else:
                checks.append(
                    _check("overlap", "pass", "identical", "identical",
                           f"{result.document.filename} duplicates {start}..{end}; "
                           "one copy kept", scope="account")
                )
            continue

        kept.extend(result.transactions)
        if start and end:
            covered.append((start, end))

    return kept, checks


def _check_continuity(
    results: list[ParseResult], account: Account, tax_year: TaxYear
) -> list[Check]:
    """Warn about days in the tax year that no statement covers."""
    periods = sorted(
        (r.document.period_start, r.document.period_end)
        for r in results
        if r.document.period_start and r.document.period_end
    )
    if not periods:
        return [
            _check("gap", "warn", "a printed period", "none",
                   "no statement printed its period; coverage not verified",
                   scope="account")
        ]

    window_start = max(tax_year.period_start, account.opened_on or tax_year.period_start)
    window_end = min(tax_year.period_end, account.closed_on or tax_year.period_end)

    gaps: list[str] = []
    cursor = window_start
    for start, end in periods:
        if start > cursor:
            missing_end = min(start - timedelta(days=1), window_end)
            if cursor <= missing_end:
                gaps.append(f"{cursor.isoformat()}..{missing_end.isoformat()}")
        cursor = max(cursor, end + timedelta(days=1))
    if cursor <= window_end:
        gaps.append(f"{cursor.isoformat()}..{window_end.isoformat()}")

    if gaps:
        return [
            _check("gap", "warn", f"{window_start}..{window_end}", "; ".join(gaps),
                   f"no statement covers {'; '.join(gaps)}; this account's "
                   "tax-year figures are incomplete", scope="account")
        ]
    return [
        _check("gap", "pass", f"{window_start}..{window_end}", "covered",
               "statements cover the whole tax year", scope="account")
    ]


def boundary_balances(
    all_txns: tuple[Transaction, ...],
    in_year: tuple[Transaction, ...],
    *,
    printed_opening: int | None,
    printed_closing: int | None,
    starts_on_first_day: bool,
    ends_on_last_day: bool,
    anchor: int | None,
    has_balance_column: bool,
) -> tuple[int | None, BalanceSource, int | None, BalanceSource]:
    """Resolve the 1 July and 30 June balances (spec §6.3)."""
    if has_balance_column:
        if in_year:
            first, last = in_year[0], in_year[-1]
            opening = (first.balance_after - first.amount
                       if first.balance_after is not None else None)
            closing = last.balance_after
        else:
            # Dormant in-year: fall back to the printed figures (Review Focus #5).
            opening = printed_opening
            closing = printed_closing if printed_closing is not None else printed_opening

        opening_source: BalanceSource = "unknown" if opening is None else (
            "printed" if starts_on_first_day and printed_opening is not None else "computed"
        )
        closing_source: BalanceSource = "unknown" if closing is None else (
            "printed" if ends_on_last_day and printed_closing is not None else "computed"
        )
        if not in_year and opening is not None:
            opening_source = "printed"
            closing_source = "printed"
        return opening, opening_source, closing, closing_source

    # No balance column (SadaPay): everything hangs off the owner's anchor.
    if anchor is None:
        return None, "unknown", None, "unknown"
    return anchor, "anchor", anchor + sum(t.amount for t in in_year), "computed"


def merge_account(
    results: list[ParseResult],
    account: Account,
    tax_year: TaxYear,
    *,
    profiles: dict[str, Profile],
    anchor: int | None = None,
    prior_year_closing: int | None = None,
) -> AccountLedger:
    """Merge one account's statements into a tax-year ledger."""
    checks: list[Check] = []

    # Per-statement checks first: a failed statement takes the account with it.
    any_failed = False
    for result in results:
        profile = profiles.get(result.document.layout_id)
        if profile is None:
            # Fail closed. Skipping the checks here would let a broken statement
            # through silently, which is the one outcome this tool must not have.
            raise KeyError(
                f"no profile supplied for layout {result.document.layout_id!r}; "
                "per-statement checks cannot run"
            )
        statement_checks = check_statement(result, profile)
        checks.extend(statement_checks)
        if not statement_usable(statement_checks):
            any_failed = True

    merged, overlap_checks = _dedupe_overlaps(results)
    checks.extend(overlap_checks)
    checks.extend(_check_continuity(results, account, tax_year))

    if any_failed or any(c.status == "fail" for c in checks):
        return AccountLedger(
            account_id=account.id, transactions=(), checks=tuple(checks),
            opening=None, closing=None, opening_source="unknown",
            closing_source="unknown", status="failed",
        )

    all_txns = tuple(merged)
    in_year = tax_year_slice(all_txns, tax_year)

    has_balance = any(t.balance_after is not None for t in all_txns)
    printed_opening = next(
        (r.document.summary.opening for r in results if r.document.summary.opening is not None),
        None,
    )
    printed_closing = next(
        (r.document.summary.closing for r in reversed(results)
         if r.document.summary.closing is not None),
        None,
    )
    starts_first = any(r.document.period_start == tax_year.period_start for r in results)
    ends_last = any(r.document.period_end == tax_year.period_end for r in results)

    opening, opening_source, closing, closing_source = boundary_balances(
        all_txns, in_year,
        printed_opening=printed_opening, printed_closing=printed_closing,
        starts_on_first_day=starts_first, ends_on_last_day=ends_last,
        anchor=anchor, has_balance_column=has_balance,
    )

    if opening_source == "unknown":
        checks.append(
            _check("anchor_missing", "warn", "an opening balance", "none",
                   f"{account.id} has no balance column and no anchor; enter the "
                   "1 July balance in manual inputs", scope="account")
        )

    if prior_year_closing is not None and opening is not None and opening != prior_year_closing:
        checks.append(
            _check("prior_year_mismatch", "warn",
                   format_paisa(prior_year_closing), format_paisa(opening),
                   "the computed 1 July balance differs from last year's declared "
                   "closing balance", scope="account")
        )

    status: AccountStatus = "incomplete" if any(
        c.status == "warn" and c.kind in ("gap", "anchor_missing") for c in checks
    ) else "complete"

    return AccountLedger(
        account_id=account.id, transactions=in_year, checks=tuple(checks),
        opening=opening, closing=closing, opening_source=opening_source,
        closing_source=closing_source, status=status,
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_reconcile_account.py -v`
Expected: PASS

- [ ] **Step 5: Run the whole suite**

Run: `uv run pytest`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/fbr/reconcile.py tests/test_reconcile_account.py
git commit -m "$(cat <<'EOF'
feat: add account merge and tax-year boundary balances

Overlaps resolved by period rather than row, so genuine identical same-day
transactions survive. Gaps respect opened_on/closed_on, a dormant account
still reports printed balances, and a missing anchor yields unknown rather
than zero.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Masking tool (`fbr-dump`)

**Files:**
- Create: `tools/dump_layout.py`, `tools/dump_allowlist.txt`
- Test: `tests/test_dump_layout.py`

**Interfaces:**
- Consumes: `fbr.paths` (Task 4), `fbr.ingest.sniff_container` + `sha256_of` (Task 9)
- Produces:
  - `shape(token: str, *, allowlist: set[str], hide_magnitude: bool = False) -> str`
  - `mask_text(text: str, *, allowlist, hide_magnitude=False) -> str`
  - `load_allowlist(extra: Path | None = None) -> set[str]`
  - `dump_tabular(data: bytes, container: str, *, allowlist, rows: int, hide_magnitude: bool) -> tuple[str, Counter]`
  - `main(argv: list[str] | None = None) -> int` — CLI entry point

**This is the privacy gate for Q2.** Claude reads only what this tool writes. The tool prints a path and counts to stdout, never content, so even running it in a shared terminal reveals nothing. PDF dumping is stubbed here with a clear message and lands in phase 2 with the PDF engine.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dump_layout.py
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
```

- [ ] **Step 2: Write `tools/dump_allowlist.txt`**

```text
# Non-personal vocabulary that may appear verbatim in a masked dump.
# One token per line, case-insensitive. Lines starting with # are comments.
# Add only words that cannot identify a person or an account.

# --- column headers and statement furniture
DATE
BOOKING
VALUE
DOC
NO
NUMBER
DESCRIPTION
PARTICULARS
REFERENCE
DEBIT
CREDIT
AMOUNT
BALANCE
AVAILABLE
OPENING
CLOSING
TOTAL
TOTALS
SPENT
INCOME
CURRENCY
PKR
RS
PAGE
OF
STATEMENT
ACCOUNT
TIME
TYPE
FROM
TO
PERIOD
GENERATED
CARRIED
FORWARD
B/F
TIT
SUMMARY

# --- months
JAN
FEB
MAR
APR
MAY
JUN
JUL
AUG
SEP
OCT
NOV
DEC
AM
PM

# --- payment rails and transaction types
IBFT
RAAST
P2P
POS
ATM
1LINK
1BILL
KUICKPAY
TRANSFER
TRANSF
FUND
FUNDS
PAYMENT
RECEIVED
SENT
INCOMING
OUTGOING
PURCHASE
PUR
REFUND
REVERSAL
REVERSED
TOPUP
TOP-UP
WITHDRAWAL
DEPOSIT
CASH
CARD
MERCHANT
BILL
STAN
INTERBANK
PEER
ONLINE
MISC
CDT
ICT
OGT
REC
TXN

# --- tax and charge vocabulary (needed to write classification rules)
PROFIT
LOSS
WITHHOLDING
WHT
TAX
TAXES
COLL
SEC
SECTION
151
154A
236Y
231AB
ZAKAT
USHR
FED
EXCISE
SALES
DUTY
CHARGES
CHARGE
FEE
FEES
GOVERNMENT
ADVANCE
DEDUCTION
DEDUCTED
CERTIFICATE

# --- counterparty brands used by classification rules
PAYONEER
THUNES
WISE
TRANSFERWISE
REMITLY
WESTERN
UNION
ACE
REMITTANCE
FOREIGN
INWARD
HOME
FREELANCE
EXPORT

# --- institutions
MEEZAN
BANK
LIMITED
MCB
SADAPAY
NAYAPAY
JAZZCASH
EASYPAISA
HBL
UBL
ALFALAH
ISLAMIC
SAVING
SAVINGS
CURRENT
PLS
TERM
FIXED
```

- [ ] **Step 3: Write the failing test run**

Run: `uv run pytest tests/test_dump_layout.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.dump_layout'`

- [ ] **Step 4: Write `tools/dump_layout.py`**

```python
# tools/dump_layout.py
"""Produce a masked layout dump of a statement.

This is the privacy gate for the whole project: Claude reads only what this
tool writes, never a real statement. Every token becomes its SHAPE - letters
to X/x, digits to 9, punctuation kept - unless it is on the allowlist of
non-personal banking vocabulary. That preserves exactly what a parser author
needs (column order, separators, date and amount formats, Dr/Cr tokens) and
nothing that identifies a person or an account.

stdout carries only a path and counts, so running this in a shared terminal
or pasting its output reveals nothing.
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from collections import Counter
from pathlib import Path

from fbr import paths
from fbr.ingest import sha256_of, sniff_container

_ALLOWLIST_FILE = Path(__file__).with_name("dump_allowlist.txt")
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9,._/-]*")
_STRIP = re.compile(r"[^A-Za-z0-9]")
_NUMERIC = re.compile(r"^[0-9][0-9,]*(\.[0-9]+)?$")
# Built from chr(96) rather than written literally, so this source can live
# inside a Markdown fence without closing it.
FENCE = chr(96) * 3


def load_allowlist(extra: Path | None = None) -> set[str]:
    """Shipped vocabulary, plus the owner's own additions if present."""
    words: set[str] = set()
    for source in (_ALLOWLIST_FILE, extra if extra is not None else paths.dump_allowlist_path()):
        if source and source.is_file():
            for line in source.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    words.add(_STRIP.sub("", line).upper())
    words.discard("")
    return words


def shape(token: str, *, allowlist: set[str], hide_magnitude: bool = False) -> str:
    """Replace a token with its shape, unless it is allowlisted.

    Punctuation is kept because separator style (1,234.56 vs 1234.56) and
    suffixes (Dr/Cr) are exactly what a profile author must know.
    """
    if _STRIP.sub("", token).upper() in allowlist:
        return token

    out: list[str] = []
    for ch in token:
        if ch.isdigit():
            out.append("9")
        elif ch.isupper():
            out.append("X")
        elif ch.islower():
            out.append("x")
        else:
            out.append(ch)
    shaped = "".join(out)

    if hide_magnitude and any(c.isdigit() for c in token):
        # Collapse the integer part to a fixed width so the number of digits
        # does not leak the size of a balance.
        shaped = re.sub(r"9[9,]*(?=(\.99)?(?!9))", "9,999", shaped, count=1)
    return shaped


def mask_text(text: str, *, allowlist: set[str], hide_magnitude: bool = False,
              counts: Counter | None = None) -> str:
    """Mask every token in a block of text, preserving its layout."""

    def replace(m: re.Match) -> str:
        token = m.group(0)
        masked = shape(token, allowlist=allowlist, hide_magnitude=hide_magnitude)
        if counts is not None and masked != token and not _NUMERIC.match(token):
            counts[_STRIP.sub("", token).upper()] += 1
        return masked

    return _TOKEN.sub(replace, text)


def _read_rows(data: bytes, container: str) -> list[list[str]]:
    from fbr.engines.tabular import read_rows

    return read_rows(data, container)


def dump_tabular(
    data: bytes,
    container: str,
    *,
    allowlist: set[str],
    rows: int,
    hide_magnitude: bool,
) -> tuple[str, Counter]:
    """Render a masked dump of a CSV/XLSX statement."""
    counts: Counter = Counter()
    parsed = _read_rows(data, container)
    total = len(parsed)

    def mask_row(row: list[str]) -> str:
        return ",".join(
            mask_text(cell, allowlist=allowlist, hide_magnitude=hide_magnitude, counts=counts)
            for cell in row
        )

    head = parsed[: min(rows, total)]
    tail = parsed[max(len(head), total - rows):]

    lines = [
        "# Masked layout dump",
        "",
        f"- container: `{container}`",
        f"- rows: {total}",
        f"- columns (first row): {len(parsed[0]) if parsed else 0}",
        f"- magnitude hidden: {hide_magnitude}",
        "",
        "Every token below is a SHAPE (letters -> X/x, digits -> 9) unless it is",
        "non-personal banking vocabulary. Separators, suffixes and column order",
        "are preserved exactly.",
        "",
        f"## First {len(head)} row(s)",
        "",
        FENCE,
        *[mask_row(r) for r in head],
        FENCE,
        "",
    ]

    if total > len(head):
        lines += [f"## Last {len(tail)} row(s)", "",
                  FENCE, *[mask_row(r) for r in tail], FENCE, ""]

    # A per-column shape histogram shows which columns are dates, amounts or text.
    width = max((len(r) for r in parsed), default=0)
    lines += ["## Per-column shape histogram", ""]
    for col in range(width):
        column_counts: Counter = Counter()
        for row in parsed[1:]:
            cell = row[col].strip() if col < len(row) else ""
            column_counts[
                mask_text(cell, allowlist=allowlist, hide_magnitude=hide_magnitude) or "(blank)"
            ] += 1
        top = ", ".join(f"`{s}` x{n}" for s, n in column_counts.most_common(4))
        lines.append(f"- col {col}: {top}")
    lines.append("")

    return "\n".join(lines), counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fbr-dump",
        description="Write a masked layout dump of a statement into the private folder.",
    )
    parser.add_argument("path", help="statement file to dump")
    parser.add_argument("--rows", type=int, default=15,
                        help="rows to show from the start and end (default 15)")
    parser.add_argument("--hide-magnitude", action="store_true",
                        help="also hide how many digits each amount has")
    parser.add_argument("--password", action="store_true",
                        help="prompt for a PDF password (phase 2)")
    args = parser.parse_args(argv)

    source = Path(args.path).expanduser()
    if not source.is_file():
        print(f"fbr-dump: file not found: {source}", file=sys.stderr)
        return 2

    data = source.read_bytes()
    container = sniff_container(data, source.name)
    if container == "pdf":
        print(
            "fbr-dump: PDF dumping arrives in phase 2 with the PDF engine. "
            "For now, export CSV or XLSX where the bank offers it.",
            file=sys.stderr,
        )
        return 2

    allowlist = load_allowlist()
    text, counts = dump_tabular(
        data, container, allowlist=allowlist,
        rows=args.rows, hide_magnitude=args.hide_magnitude,
    )

    paths.ensure_private_layout()
    digest = sha256_of(data)
    # Named by hash: the source filename may itself contain an account number.
    out = paths.dumps_dir() / f"{digest[:12]}.dump.md"
    out.write_text(text, encoding="utf-8")

    candidates = paths.dump_candidates_dir() / f"{digest[:12]}.txt"
    candidates.write_text(
        "# Masked words, most frequent first. Copy any that are safe, non-personal\n"
        "# vocabulary into ~/fbr-private/dump-allowlist.txt and re-run fbr-dump.\n"
        "# Claude never reads this file.\n"
        + "\n".join(f"{word}\t{n}" for word, n in counts.most_common(200)),
        encoding="utf-8",
    )

    print(f"wrote {out}: {len(text.splitlines())} lines, {sum(counts.values())} tokens masked")
    print(f"candidates: {candidates}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_dump_layout.py -v`
Expected: PASS. If `test_hide_magnitude_fixes_the_digit_count` fails, adjust the `re.sub` in `shape` until both inputs collapse to the same string; do not relax the test, because it is the guarantee that a dump cannot leak a balance's size.

- [ ] **Step 6: Verify the CLI end to end**

```bash
uv run fbr-dump --help                      # expect the usage text
```

- [ ] **Step 7: Commit**

```bash
git add tools/dump_layout.py tools/dump_allowlist.txt tests/test_dump_layout.py
git commit -m "$(cat <<'EOF'
feat: add fbr-dump masking tool

Tokens become shapes unless they are non-personal banking vocabulary, so a
dump carries column order, separators and date/amount formats but no names,
IBANs or figures. stdout prints only a path and counts.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: Pipeline — the single entry point the UI calls

**Files:**
- Create: `src/fbr/pipeline.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `fbr.ingest` (Task 9), `fbr.engines.tabular` (Task 8), `fbr.reconcile` (Tasks 10–11), `fbr.config.loader` (Task 6)
- Produces:
  - `load_files(files: list[InputFile], *, registry, profiles, tax_year, anchors=None, prior_year=None) -> RunResult`
  - `class InputFile(name: str, data: bytes)`
  - `class FileOutcome(name, sha256, status, layout_id, account_id, message, transactions_parsed)`
  - `class RunResult(outcomes, ledgers, account_status, all_checks, unassigned)`
  - `read_statement_dir(tax_year_name: str) -> list[InputFile]`

**Why a pipeline module:** the Streamlit pages must contain no business logic, so that every rule in this plan is testable without a browser. A page calls `load_files` and renders what comes back.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pipeline.py
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'fbr.pipeline'`

- [ ] **Step 3: Write the implementation**

```python
# src/fbr/pipeline.py
"""Wire ingest, parsing and reconciliation into one call.

The Streamlit pages hold no business logic: they call load_files and render
what comes back. That keeps every rule in this codebase testable without a
browser, and keeps the UI from quietly acquiring a rule of its own.

No file failure stops the run. Each file reports its own outcome, because a
statement that cannot be read is information the owner needs, not a crash.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from fbr import paths
from fbr.config.loader import ProfileSet
from fbr.config.schema_taxyear import TaxYear
from fbr.engines.tabular import ParseError, ParseResult, parse_tabular, read_rows
from fbr.ingest import (
    LayoutAmbiguous,
    LayoutUnknown,
    detect_layout,
    resolve_account,
    sha256_of,
    sniff_container,
)
from fbr.model import Check, Registry
from fbr.reconcile import AccountLedger, merge_account

_STATEMENT_SUFFIXES = {".csv", ".xlsx", ".xls", ".pdf"}


@dataclass(frozen=True, slots=True)
class InputFile:
    name: str
    data: bytes
    account_id: str | None = None      # set by the owner when detection fails


@dataclass(frozen=True, slots=True)
class FileOutcome:
    name: str
    sha256: str
    status: str            # ok | unknown_layout | ambiguous_layout | unassigned
                           # | unreadable | duplicate | unsupported
    layout_id: str | None
    account_id: str | None
    message: str
    transactions_parsed: int


@dataclass(frozen=True, slots=True)
class RunResult:
    outcomes: tuple[FileOutcome, ...]
    ledgers: dict[str, AccountLedger] = field(default_factory=dict)
    account_status: dict[str, str] = field(default_factory=dict)
    all_checks: tuple[Check, ...] = ()
    unassigned: tuple[InputFile, ...] = ()


def read_statement_dir(tax_year_name: str) -> list[InputFile]:
    """Read statements from the private folder rather than an upload.

    Preferred over Streamlit's uploader: Streamlit spools uploads over 1 MB
    to a temporary file on disk, and these files are already on disk where
    the owner put them.
    """
    folder = paths.statements_dir(tax_year_name)
    if not folder.is_dir():
        return []
    return [
        InputFile(p.name, p.read_bytes())
        for p in sorted(folder.iterdir())
        if p.is_file() and p.suffix.lower() in _STATEMENT_SUFFIXES
    ]


def _free_text(data: bytes, container: str) -> str:
    try:
        return "\n".join(",".join(r) for r in read_rows(data, container)[:30])
    except ParseError:
        return ""


def load_files(
    files: list[InputFile],
    *,
    registry: Registry,
    profiles: ProfileSet,
    tax_year: TaxYear,
    anchors: dict[str, int] | None = None,
    prior_year: dict[str, int] | None = None,
) -> RunResult:
    """Parse and reconcile a set of statement files."""
    outcomes: list[FileOutcome] = []
    unassigned: list[InputFile] = []
    by_account: dict[str, list[ParseResult]] = {}
    used_profiles: dict[str, object] = {}
    seen_hashes: set[str] = set()

    for item in files:
        digest = sha256_of(item.data)

        if digest in seen_hashes:
            outcomes.append(FileOutcome(
                item.name, digest, "duplicate", None, None,
                "identical to a file already loaded; ignored", 0,
            ))
            continue
        seen_hashes.add(digest)

        container = sniff_container(item.data, item.name)
        if container == "pdf":
            outcomes.append(FileOutcome(
                item.name, digest, "unsupported", None, None,
                "PDF statements arrive in phase 2; export CSV or XLSX for now", 0,
            ))
            continue

        try:
            profile = detect_layout(item.data, profiles, container)
        except LayoutUnknown as exc:
            outcomes.append(FileOutcome(
                item.name, digest, "unknown_layout", None, None, str(exc), 0))
            continue
        except LayoutAmbiguous as exc:
            outcomes.append(FileOutcome(
                item.name, digest, "ambiguous_layout", None, None, str(exc), 0))
            continue

        account_id = item.account_id
        if account_id is None:
            try:
                probe = parse_tabular(item.data, profile, sha256=digest,
                                      filename=item.name, account_id=None)
            except ParseError as exc:
                outcomes.append(FileOutcome(
                    item.name, digest, "unreadable", profile.id, None, str(exc), 0))
                continue
            account_id = resolve_account(
                probe.document.summary, _free_text(item.data, container), registry
            )

        if account_id is None:
            unassigned.append(item)
            outcomes.append(FileOutcome(
                item.name, digest, "unassigned", profile.id, None,
                "no registry account matches this statement; choose one on the Load page", 0,
            ))
            continue

        try:
            result = parse_tabular(item.data, profile, sha256=digest,
                                   filename=item.name, account_id=account_id)
        except ParseError as exc:
            outcomes.append(FileOutcome(
                item.name, digest, "unreadable", profile.id, account_id, str(exc), 0))
            continue

        by_account.setdefault(account_id, []).append(result)
        used_profiles[profile.id] = profile
        outcomes.append(FileOutcome(
            item.name, digest, "ok", profile.id, account_id,
            f"parsed {len(result.transactions)} transaction(s)", len(result.transactions),
        ))

    ledgers: dict[str, AccountLedger] = {}
    status: dict[str, str] = {}
    checks: list[Check] = []

    for account_id, results in by_account.items():
        account = registry.by_id(account_id)
        if account is None:      # pragma: no cover - resolve_account only returns known ids
            continue
        ledger = merge_account(
            results, account, tax_year,
            profiles=used_profiles,  # type: ignore[arg-type]
            anchor=(anchors or {}).get(account_id),
            prior_year_closing=(prior_year or {}).get(account_id),
        )
        ledgers[account_id] = ledger
        status[account_id] = ledger.status
        checks.extend(ledger.checks)

    return RunResult(
        outcomes=tuple(outcomes),
        ledgers=ledgers,
        account_status=status,
        all_checks=tuple(checks),
        unassigned=tuple(unassigned),
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/fbr/pipeline.py tests/test_pipeline.py
git commit -m "$(cat <<'EOF'
feat: add pipeline entry point

One call takes statement bytes to reconciled per-account ledgers. Each
file reports its own outcome so a single bad file never stops the run, and
identical files are deduplicated by hash.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: Bank profiles and the TY2026 tax-year config

**Files:**
- Create: `profiles/meezan.csv.v1.toml`, `profiles/mcb.csv.v1.toml`, `profiles/nayapay.csv.v1.toml`, `taxyears/TY2026.toml`
- Test: `tests/test_profiles_ship.py`

**Interfaces:**
- Consumes: Tasks 5, 6, 8, 9
- Produces: shipped config that `load_profiles()` and `load_tax_year("TY2026")` return

**Important:** these profiles are written against the *synthetic* layouts, because no masked dump exists yet. They are a starting point, not a finished parser. The first real `fbr-dump` output will change column labels, date formats and summary regexes. Every value that a real dump must confirm is marked `# VERIFY` in the file.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_profiles_ship.py
"""The shipped config must load, self-test, and detect the layouts it claims."""

from datetime import date
from pathlib import Path

import pytest

from fbr.config.loader import load_profiles, load_tax_year, run_selftest
from fbr.engines.tabular import parse_row, parse_tabular
from fbr.ingest import detect_layout
from fbr.reconcile import check_statement, statement_usable
from tests.fixtures.synth import build_statement, write_mcb_csv, write_meezan_csv, write_nayapay_csv

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def shipped():
    return load_profiles(ROOT / "profiles")


def test_shipped_profiles_load(shipped):
    assert {p.id for p in shipped.profiles} >= {
        "meezan.csv.v1", "mcb.csv.v1", "nayapay.csv.v1"
    }


def test_every_shipped_profile_passes_its_own_selftest(shipped):
    for profile in shipped.profiles:
        status = run_selftest(profile, parse_row)
        assert status.ok, f"{profile.id}: {status.message}"


@pytest.mark.parametrize(
    "writer,expected_id",
    [
        (write_meezan_csv, "meezan.csv.v1"),
        (write_mcb_csv, "mcb.csv.v1"),
        (write_nayapay_csv, "nayapay.csv.v1"),
    ],
)
def test_each_profile_detects_and_reconciles_its_own_layout(shipped, writer, expected_id):
    stmt = build_statement(seed=81, start=date(2025, 7, 1), end=date(2026, 6, 30))
    data = writer(stmt)
    profile = detect_layout(data, shipped, "csv")
    assert profile.id == expected_id
    result = parse_tabular(data, profile, sha256="a" * 64, filename="x.csv",
                           account_id="acct")
    assert len(result.transactions) == len(stmt.txns)
    assert statement_usable(check_statement(result, profile)), \
        [c for c in check_statement(result, profile) if c.status == "fail"]


def test_no_two_shipped_profiles_match_the_same_file(shipped):
    # Review Focus #3, at the level of the config that actually ships.
    stmt = build_statement(seed=82)
    for writer in (write_meezan_csv, write_mcb_csv, write_nayapay_csv):
        detect_layout(writer(stmt), shipped, "csv")   # raises if ambiguous


def test_ty2026_config_loads_with_the_verified_export_code():
    ty = load_tax_year("TY2026", ROOT / "taxyears")
    assert ty.name == "TY2026"
    assert ty.period_start == date(2025, 7, 1)
    assert ty.period_end == date(2026, 6, 30)
    # 64060285 is the 1% export line, verified against FBR's TY2024 form text.
    assert ty.codes["export_receipts"].code == "64060285"
    assert ty.codes["profit_final"].code == "64040052"
    assert ty.codes["salary_149"].code == "64020004"
    assert ty.codes["tax_236y"].code == "64151905"


def test_the_ty2026_wealth_bank_code_is_blank_and_flagged_unknown():
    # Unreadable in FBR's scanned SRO; the owner reads it off IRIS (open question A1).
    ty = load_tax_year("TY2026", ROOT / "taxyears")
    entry = ty.codes["wealth_bank_accounts"]
    assert entry.code == ""
    assert entry.verification == "unknown"


def test_thresholds_are_in_paisa():
    ty = load_tax_year("TY2026", ROOT / "taxyears")
    assert ty.thresholds.review_threshold == 1_000_000            # Rs 10,000
    assert ty.thresholds.profit_final_regime_max == 500_000_000   # Rs 5,000,000


def test_profiles_mark_values_that_a_real_dump_must_confirm():
    for name in ("meezan.csv.v1", "mcb.csv.v1", "nayapay.csv.v1"):
        text = (ROOT / "profiles" / f"{name}.toml").read_text()
        assert "VERIFY" in text, f"{name} must flag values awaiting a real dump"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_profiles_ship.py -v`
Expected: FAIL — `ConfigError: no profiles found`

- [ ] **Step 3: Write `profiles/meezan.csv.v1.toml`**

```toml
# Meezan Bank CSV export.
#
# STATUS: written against synthetic fixtures. Every line marked VERIFY must be
# confirmed against a real `fbr-dump` before this profile is trusted on a
# real statement.
#
# Known from research 03: the CSV export puts Debit BEFORE Credit, the reverse
# of the app PDF. Columns are mapped by name, so the order does not matter -
# but the LABELS below must match the real export exactly.

id          = "meezan.csv.v1"
institution = "Meezan Bank Limited"
container   = "csv"
valid_from  = 2025-07-01
notes       = "CSV/XLSX export from the Meezan app or internet banking."

[detect]
header_contains = ["Booking Date", "Value Date"]   # VERIFY against a real export

[columns]
date        = "Booking Date"                       # VERIFY
value_date  = "Value Date"                         # VERIFY
reference   = "Doc No"                             # VERIFY
description = "Description"                        # VERIFY
debit       = "Debit"                              # VERIFY
credit      = "Credit"                             # VERIFY
balance     = "Available Balance"                  # VERIFY

[formats]
dates = ["%d %b %Y", "%d/%m/%Y", "%d/%m/%y"]       # VERIFY which one the export uses
sign  = "columns"

[rows]
skip = ['(?i)^\s*(opening|closing)\s+balance']

[summary]
opening = '(?i)OPENING\s+BALANCE\D+(?P<value>[\d,]+\.\d{2})'    # VERIFY
closing = '(?i)CLOSING\s+BALANCE\D+(?P<value>[\d,]+\.\d{2})'    # VERIFY

[balance]
semantics = "running"
# VERIFY: does "Available Balance" behave as a ledger running balance, or does
# it differ when funds are on hold? (spec §12)
kind      = "available"

[[selftest.cases]]
row = { "Booking Date" = "01 Jul 2025", "Value Date" = "01 Jul 2025", "Doc No" = "D00001", "Description" = "Top-up", "Debit" = "", "Credit" = "1,000.00", "Available Balance" = "1,000.00" }
expect_date   = 2025-07-01
expect_amount = 100000

[[selftest.cases]]
row = { "Booking Date" = "15 Jan 2026", "Value Date" = "15 Jan 2026", "Doc No" = "D00002", "Description" = "ATM Cash Withdrawal", "Debit" = "2,500.00", "Credit" = "", "Available Balance" = "7,500.00" }
expect_date   = 2026-01-15
expect_amount = -250000
```

- [ ] **Step 4: Write `profiles/mcb.csv.v1.toml`**

```toml
# MCB Live CSV export.
#
# STATUS: written against synthetic fixtures. Lines marked VERIFY need a real
# `fbr-dump`. Research 03 confirms MCB Live offers "Download in CSV format",
# but its column layout is not published anywhere.
#
# The Dr/Cr suffix is glued to the amount (e.g. "1,234.00Dr"), so sign comes
# from the suffix rather than from separate columns.

id          = "mcb.csv.v1"
institution = "MCB Bank Limited"
container   = "csv"
valid_from  = 2025-07-01
notes       = "CSV export from MCB Live (Account Management -> Download Statement)."

[detect]
header_contains = ["Date", "Reference Number", "Amount"]   # VERIFY

[columns]
date        = "Date"                                       # VERIFY
description = "Description"                                # VERIFY
reference   = "Reference Number"                           # VERIFY
amount      = "Amount"                                     # VERIFY
balance     = "Balance"                                    # VERIFY

[formats]
dates         = ["%d %b %Y", "%d/%m/%y", "%d/%m/%Y"]       # VERIFY
sign          = "suffix"
debit_tokens  = ["Dr", "DR", "dr"]                         # VERIFY exact casing
credit_tokens = ["Cr", "CR", "cr"]                         # VERIFY

[rows]
skip = ['(?i)^\s*(opening|closing)\s+balance']

[summary]
opening = '(?i)Opening\s+Balance\D+(?P<value>[\d,]+\.\d{2})'   # VERIFY
closing = '(?i)Closing\s+Balance\D+(?P<value>[\d,]+\.\d{2})'   # VERIFY

[balance]
semantics = "running"
kind      = "ledger"

[[selftest.cases]]
row = { "Date" = "01 Jul 2025", "Description" = "INTERBANK FUNDS RECEIVING", "Reference Number" = "1000000001", "Amount" = "5,000.00Cr", "Balance" = "15,000.00" }
expect_date   = 2025-07-01
expect_amount = 500000

[[selftest.cases]]
row = { "Date" = "02 Jul 2025", "Description" = "Cash Withdrawal", "Reference Number" = "1000000002", "Amount" = "2,000.00Dr", "Balance" = "13,000.00" }
expect_date   = 2025-07-02
expect_amount = -200000
```

- [ ] **Step 5: Write `profiles/nayapay.csv.v1.toml`**

```toml
# NayaPay CSV export.
#
# STATUS: written against synthetic fixtures. Lines marked VERIFY need a real
# `fbr-dump`. Research 03 confirms the app exports "PDF or CSV", but the CSV
# columns are undocumented.
#
# Open question from the spec: public NayaPay samples DO print Opening and
# Closing Balance on the summary card, contradicting the original brief. The
# summary patterns below assume they are present; if a real export omits them,
# delete those two lines and the account will fall back to a manual anchor.

id          = "nayapay.csv.v1"
institution = "NayaPay"
container   = "csv"
valid_from  = 2025-07-01
notes       = "CSV export from the NayaPay app (More -> Statements)."

[detect]
header_contains = ["Date", "Type", "Amount", "Balance"]    # VERIFY

[columns]
date        = "Date"                                       # VERIFY
type        = "Type"                                       # VERIFY
description = "Description"                                # VERIFY
amount      = "Amount"                                     # VERIFY
balance     = "Balance"                                    # VERIFY

[formats]
dates = ["%d %b %Y", "%d-%b-%Y"]                           # VERIFY
sign  = "signed"

[rows]
skip = ['(?i)carried\s+forward', '(?i)^\s*page\s+\d+\s+of\s+\d+']

[summary]
opening      = '(?i)Opening\s+Balance\D+(?P<value>[\d,]+\.\d{2})'   # VERIFY it exists
closing      = '(?i)Closing\s+Balance\D+(?P<value>[\d,]+\.\d{2})'   # VERIFY it exists
total_credit = '(?i)Total\s+Income\D+(?P<value>[\d,]+\.\d{2})'      # VERIFY
total_debit  = '(?i)Total\s+Spent\D+(?P<value>[\d,]+\.\d{2})'       # VERIFY

[balance]
semantics = "running"
kind      = "ledger"

[[selftest.cases]]
row = { "Date" = "01 Jul 2025", "Time" = "10:15 AM", "Type" = "IBFT In", "Description" = "Incoming fund transfer", "Amount" = "+Rs. 5,000.00", "Balance" = "Rs. 15,000.00" }
expect_date   = 2025-07-01
expect_amount = 500000

[[selftest.cases]]
row = { "Date" = "02 Jul 2025", "Time" = "11:00 AM", "Type" = "IBFT Out", "Description" = "Outgoing fund transfer", "Amount" = "-Rs. 2,000.00", "Balance" = "Rs. 13,000.00" }
expect_date   = 2025-07-02
expect_amount = -200000
```

- [ ] **Step 6: Write `taxyears/TY2026.toml`**

```toml
# Tax Year 2026: 1 July 2025 - 30 June 2026.
#
# Codes, labels and sources come from docs/research/02-fbr-iris-codes.md.
# `verification` records HOW each code is known, so the UI can mark figures
# the owner still has to confirm against live IRIS:
#   iris_verified      - owner confirmed on the live IRIS screen
#   form_text          - read from an FBR form with a real text layer
#   form_scan          - read by OCR from a scanned FBR form
#   prior_year_assumed - carried over from TY2025
#   unknown            - not known; code left blank

name         = "TY2026"
period_start = 2025-07-01
period_end   = 2026-06-30
atl          = true          # the owner files every year; affects sanity rates only

# --- Income -----------------------------------------------------------------

[codes.export_receipts]
code         = "64060285"
label        = "Export of services u/s 154A @1%"
tab          = "Business / Final Tax"
columns      = { "1" = "Receipts", "2" = "Tax deducted", "3" = "Tax chargeable (IRIS computes)" }
source       = "SRO 1495(I)/2026 p.15; wording confirmed in TY2024 form text (SRO 950(I)/2024 row 110)"
verification = "form_scan"

[codes.export_receipts_pseb]
code         = "64060290"
label        = "Export of IT/ITeS Services u/s 154A @ 0.25%"
tab          = "Business / Final Tax"
columns      = { "1" = "Receipts", "2" = "Tax deducted" }
source       = "SRO 1495(I)/2026 p.15 (not used: the owner is not PSEB-certified)"
verification = "form_scan"

[codes.business_income_total]
code         = "3000"
label        = "Income / (Loss) from Business"
tab          = "Business"
columns      = { "1" = "Head total" }
source       = "SRO 1495(I)/2026 p.36"
verification = "form_scan"

[codes.profit_on_debt_income]
code         = "500312"
label        = "Profit on Debt"
tab          = "Other Sources / Receipts"
columns      = { "1" = "Total", "2" = "Subject to final tax", "3" = "Subject to normal tax" }
source       = "SRO 1562(I)/2025 p.55; TY2026 digits illegible in the scan"
verification = "prior_year_assumed"

[codes.profit_final]
code         = "64040052"
label        = "Profit on Debt u/s 151(1)(b) from Bank Accounts / Deposits"
tab          = "Other Sources / Final Tax"
columns      = { "1" = "Gross profit", "2" = "Tax deducted" }
source       = "SRO 1495(I)/2026 p.23"
verification = "form_scan"

[codes.profit_adjustable]
code         = "64040002"
label        = "Profit on Debt u/s 151(1)(b) from Bank Accounts / Deposits"
tab          = "Adjustable Tax"
columns      = { "1" = "Receipts", "2" = "Tax deducted" }
source       = "SRO 1495(I)/2026 p.29; used only when total profit exceeds Rs 5m"
verification = "form_scan"

# --- Withholding ------------------------------------------------------------

[codes.salary_149]
code         = "64020004"
label        = "Salary of Employees u/s 149"
tab          = "Adjustable Tax"
columns      = { "1" = "Receipts", "2" = "Tax deducted" }
source       = "SRO 1495(I)/2026 pp.4, 29"
verification = "form_scan"

[codes.tax_236y]
code         = "64151905"
label        = "Persons remitting amount abroad through credit / debit / prepaid cards u/s 236Y"
tab          = "Adjustable Tax"
columns      = { "1" = "Amount remitted", "2" = "Tax collected" }
source       = "SRO 1495(I)/2026 p.30"
verification = "form_scan"

[codes.tax_231ab]
code         = "64100101"
label        = "Advance tax on cash withdrawal u/s 231AB"
tab          = "Adjustable Tax"
columns      = { "1" = "Amount withdrawn", "2" = "Tax collected" }
source       = "SRO 1562(I)/2025 p.59; TY2026 not confirmed"
verification = "prior_year_assumed"

[codes.withholding_total]
code         = "9201"
label        = "Withholding Income Tax"
tab          = "Computations"
columns      = { "1" = "Total (IRIS computes)" }
source       = "SRO 1495(I)/2026 p.36"
verification = "form_scan"

# --- Allowances -------------------------------------------------------------

[codes.zakat]
code         = "9001"
label        = "Zakat u/s 60"
tab          = "Deductible Allowances"
columns      = { "1" = "Total", "2" = "Inadmissible", "3" = "Admissible" }
source       = "SRO 1562(I)/2025 p.56; TY2026 dialog shows the label but no code"
verification = "prior_year_assumed"

# --- Wealth statement -------------------------------------------------------

[codes.wealth_bank_accounts]
code         = ""
label        = "Bank Account(s)"
tab          = "Wealth Statement / Financial Assets & Investments (Non-Business)"
columns      = { }
source       = "SRO 1495(I)/2026 p.38: code cell illegible. TY2025 used 7006. Owner action A1: read it off IRIS."
verification = "unknown"

[codes.wealth_cash]
code         = ""
label        = "Cash in hand"
tab          = "Wealth Statement / Financial Assets & Investments (Non-Business)"
columns      = { }
source       = "SRO 1495(I)/2026 p.38: illegible. TY2025 used 7012."
verification = "unknown"

[codes.wealth_foreign_total]
code         = "701902"
label        = "Total Foreign Assets"
tab          = "116A - Foreign Assets / Liabilities"
columns      = { }
source       = "SRO 1495(I)/2026 p.37"
verification = "form_scan"

# --- Thresholds (paisa) and windows (days) ----------------------------------

[thresholds]
profit_final_regime_max  = 500000000   # Rs 5,000,000: above this, s.7B stops applying
s111_4_cap               = 500000000   # Rs 5,000,000: s.111(4) protection for remittances
review_threshold         = 1000000     # Rs 10,000: credits at or above this go to review
wht_ratio_tolerance_pp   = 1.0         # percentage points before a WHT rate is queried
profit_wht_window_days   = 1
tax154a_window_days      = 1
tax154a_amount_tolerance = 100         # Rs 1: banks may round tax to the rupee
transfer_window_days     = 3
transfer_fee_tolerance   = 10000       # Rs 100: IBFT fee netted out of a transfer
reversal_window_days     = 30

# --- Sanity-check rates -----------------------------------------------------
# Used ONLY to flag anomalies. The tool never computes an IRIS figure from a
# rate; it reports the tax actually deducted.

[rates]
s151_atl       = 0.20      # raised from 15% by the Finance Act 2025
s151_non_atl   = 0.40
s7b            = 0.20
s236y_atl      = 0.05
s236y_non_atl  = 0.10
s231ab_non_atl = 0.008
s154a          = 0.01      # the owner's rate (not PSEB-certified)
s154a_pseb     = 0.0025

# --- Display templates ------------------------------------------------------

[templates]
wealth_line = "{iban} - {title} - {institution_upper} - {ownership}"
profit_line = "Profit on Debt u/s 151(1)(b) from Bank Accounts/Deposits - Profit on Savings Account - Investment in {institution}"
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run pytest tests/test_profiles_ship.py -v`
Expected: PASS

- [ ] **Step 8: Run the whole suite**

Run: `uv run pytest`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add profiles taxyears tests/test_profiles_ship.py
git commit -m "$(cat <<'EOF'
feat: ship Meezan/MCB/NayaPay CSV profiles and TY2026 config

Profiles are written against synthetic layouts with every unconfirmed value
marked VERIFY, pending a real fbr-dump. TY2026 config carries IRIS codes
with their verification state; the wealth bank-account code stays blank
until read off live IRIS.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 15: Streamlit pages — Setup, Load, Checks

**Files:**
- Create: `app/main.py`, `app/state.py`, `app/pages/1_Setup.py`, `app/pages/2_Load.py`, `app/pages/3_Checks.py`
- Test: `tests/test_app_state.py`

**Interfaces:**
- Consumes: `fbr.pipeline` (Task 13), `fbr.config.loader` (Task 6), `fbr.paths` (Task 4)
- Produces:
  - `app.state.mask_identifier(value: str) -> str` — `"…3474"`
  - `app.state.STATUS_ICON: dict[str, str]`
  - `app.state.VERIFICATION_MARK: dict[str, str]`
  - `app.state.summarize_run(run) -> dict` — counts for the header strip

**Rules:** pages contain no business logic; they call `load_files` and render. State goes in `st.session_state` only — never `st.cache_data`, whose values outlive the tab. Account identifiers are masked on screen.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_app_state.py
"""The pure helpers behind the pages. Streamlit itself is not exercised here;
the privacy smoke test in Step 6 covers the running app."""

import pytest

from app.state import STATUS_ICON, VERIFICATION_MARK, mask_identifier, summarize_run


@pytest.mark.parametrize(
    "value,expected",
    [
        ("PK00TEST0000000000003474", "…3474"),
        ("03001234567", "…4567"),
        ("1234", "…1234"),
        ("12", "…12"),
        ("", ""),
    ],
)
def test_identifiers_are_masked_for_display(value, expected):
    assert mask_identifier(value) == expected


def test_masking_never_shows_a_full_iban():
    full = "PK00TEST0000000000003474"
    assert full not in mask_identifier(full)


def test_status_icons_cover_every_account_status():
    assert set(STATUS_ICON) == {"complete", "incomplete", "failed"}


def test_verification_marks_cover_every_state():
    assert set(VERIFICATION_MARK) == {
        "iris_verified", "form_text", "form_scan", "prior_year_assumed", "unknown"
    }
    assert VERIFICATION_MARK["iris_verified"] == "✓"
    assert VERIFICATION_MARK["unknown"] == "✗"


def test_summarize_counts_outcomes_and_checks():
    from fbr.model import Check
    from fbr.pipeline import FileOutcome, RunResult

    run = RunResult(
        outcomes=(
            FileOutcome("a.csv", "h1", "ok", "meezan.csv.v1", "meezan-main", "", 12),
            FileOutcome("b.csv", "h2", "unknown_layout", None, None, "no match", 0),
        ),
        ledgers={},
        account_status={"meezan-main": "complete"},
        all_checks=(
            Check("c1", "document", "running_balance", "pass", "", "", ""),
            Check("c2", "account", "gap", "warn", "", "", ""),
            Check("c3", "document", "unresolved_rows", "fail", "", "", ""),
        ),
    )
    s = summarize_run(run)
    assert s["files_ok"] == 1
    assert s["files_problem"] == 1
    assert s["transactions"] == 12
    assert s["checks_failed"] == 1
    assert s["checks_warned"] == 1


def test_summarize_handles_an_empty_run():
    from fbr.pipeline import RunResult

    s = summarize_run(RunResult(outcomes=()))
    assert s["files_ok"] == 0 and s["transactions"] == 0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_app_state.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.state'`

- [ ] **Step 3: Write `app/state.py`**

```python
# app/state.py
"""Display helpers shared by the pages.

Pure functions only: everything here is testable without Streamlit, which
keeps the pages free of logic that could otherwise drift away from the rules
the rest of the codebase enforces.
"""

from __future__ import annotations

from fbr.pipeline import RunResult

STATUS_ICON = {"complete": "✅", "incomplete": "⚠️", "failed": "❌"}

VERIFICATION_MARK = {
    "iris_verified": "✓",
    "form_text": "⚠",
    "form_scan": "⚠",
    "prior_year_assumed": "⚠",
    "unknown": "✗",
}

VERIFICATION_HELP = {
    "iris_verified": "confirmed on the live IRIS screen",
    "form_text": "read from an FBR form's text layer; confirm in IRIS",
    "form_scan": "read by OCR from a scanned FBR form; confirm in IRIS",
    "prior_year_assumed": "carried over from last year; confirm in IRIS",
    "unknown": "not known; read it off IRIS before filing",
}


def mask_identifier(value: str) -> str:
    """Show only the last four characters of an account identifier."""
    if not value:
        return ""
    return f"…{value[-4:]}"


def summarize_run(run: RunResult) -> dict[str, int]:
    """Counts for the header strip."""
    return {
        "files_ok": sum(1 for o in run.outcomes if o.status == "ok"),
        "files_problem": sum(1 for o in run.outcomes if o.status != "ok"),
        "transactions": sum(o.transactions_parsed for o in run.outcomes),
        "accounts": len(run.ledgers),
        "checks_failed": sum(1 for c in run.all_checks if c.status == "fail"),
        "checks_warned": sum(1 for c in run.all_checks if c.status == "warn"),
    }
```

- [ ] **Step 4: Write `app/main.py`**

```python
# app/main.py
"""Local UI entry point. Run it with ./run, never `streamlit run` directly,
so the privacy flags are always applied."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

st.set_page_config(page_title="FBR Tax Return Aggregator", page_icon="📄", layout="wide")

st.title("FBR Tax Return Aggregator")
st.caption(
    "Local only. Nothing leaves this machine. Figures are for you to enter into "
    "IRIS by hand."
)

st.markdown(
    """
**Order of work**

1. **Setup** — check the private folder, accounts and profiles.
2. **Load** — read this year's statements and see which layout and account each one matched.
3. **Checks** — confirm every statement reconciles before believing any figure.

Classification, review, the IRIS summary and the Excel export arrive in later phases.
"""
)

st.info("Phase 0–1: CSV/XLSX statements only. PDF support arrives in phase 2.")
```

- [ ] **Step 5: Write the three pages**

`app/pages/1_Setup.py`:

```python
# app/pages/1_Setup.py
"""Setup: is everything this tool needs in place?"""

from __future__ import annotations

import streamlit as st

from app.state import VERIFICATION_HELP, VERIFICATION_MARK, mask_identifier
from fbr import paths
from fbr.config.loader import ConfigError, load_profiles, load_registry, load_tax_year
from fbr.engines.tabular import parse_row
from fbr.ingest import usable_profiles

st.header("Setup")

tax_year = st.selectbox("Tax year", ["TY2026"], index=0)
st.session_state["tax_year"] = tax_year

st.subheader("Private folder")
st.caption(
    "Owner data lives outside this repository. Set FBR_PRIVATE_DIR to move it."
)
for path, exists in paths.describe_private_layout():
    st.write(("✅ " if exists else "⬜ ") + f"`{path}`")
if st.button("Create missing folders"):
    try:
        paths.ensure_private_layout()
        st.success("Folder layout created.")
    except paths.PrivatePathError as exc:
        st.error(str(exc))

st.subheader("Accounts")
try:
    registry = load_registry()
    st.session_state["registry"] = registry
    st.write(f"Owner: **{registry.owner.name}**")
    st.dataframe(
        [
            {
                "id": a.id,
                "institution": a.institution,
                "kind": a.kind,
                "identifier": mask_identifier(a.iban or a.account_number or a.wallet_number),
                "statement expected": "yes" if a.statement_expected else "no",
            }
            for a in registry.accounts
        ],
        hide_index=True,
    )
except ConfigError as exc:
    st.error(str(exc))

st.subheader("Layout profiles")
try:
    profiles = load_profiles()
    st.session_state["profiles"] = profiles
    rows = []
    for container in ("csv", "xlsx", "pdf"):
        _, report = usable_profiles(profiles, container)
        for status in report:
            rows.append({
                "profile": status.profile_id,
                "self-test": "✅ pass" if status.ok else "❌ fail",
                "detail": status.message,
            })
    if rows:
        st.dataframe(rows, hide_index=True)
    st.caption("A profile that fails its own self-test is excluded from layout detection.")
except ConfigError as exc:
    st.error(str(exc))

st.subheader("IRIS codes")
try:
    ty = load_tax_year(tax_year)
    st.session_state["tax_year_config"] = ty
    st.dataframe(
        [
            {
                "": VERIFICATION_MARK[e.verification],
                "code": e.code or "(blank)",
                "label": e.label,
                "tab": e.tab,
                "state": VERIFICATION_HELP[e.verification],
            }
            for e in ty.codes.values()
        ],
        hide_index=True,
    )
    unknown = [e.label for e in ty.codes.values() if e.verification == "unknown"]
    if unknown:
        st.warning(
            "Read these off live IRIS before filing: " + ", ".join(unknown)
        )
except ConfigError as exc:
    st.error(str(exc))
```

`app/pages/2_Load.py`:

```python
# app/pages/2_Load.py
"""Load: read this year's statements and report what matched."""

from __future__ import annotations

import streamlit as st

from app.state import summarize_run
from fbr import paths
from fbr.pipeline import InputFile, load_files, read_statement_dir

st.header("Load statements")

tax_year = st.session_state.get("tax_year", "TY2026")
registry = st.session_state.get("registry")
profiles = st.session_state.get("profiles")
ty_config = st.session_state.get("tax_year_config")

if not (registry and profiles and ty_config):
    st.warning("Open **Setup** first so the registry, profiles and codes are loaded.")
    st.stop()

folder = paths.statements_dir(tax_year)
st.caption(
    f"Reading from `{folder}`. Files are read straight from disk rather than "
    "uploaded, because Streamlit writes uploads over 1 MB to a temporary file."
)

files: list[InputFile] = []
source = st.radio("Source", ["Private folder", "Upload"], horizontal=True)

if source == "Private folder":
    files = read_statement_dir(tax_year)
    st.write(f"{len(files)} file(s) found.")
else:
    uploaded = st.file_uploader(
        "Statements", type=["csv", "xlsx"], accept_multiple_files=True
    )
    files = [InputFile(f.name, f.getvalue()) for f in (uploaded or [])]

if files and st.button("Parse", type="primary"):
    run = load_files(files, registry=registry, profiles=profiles, tax_year=ty_config)
    st.session_state["run"] = run

run = st.session_state.get("run")
if run:
    s = summarize_run(run)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Files parsed", s["files_ok"])
    c2.metric("Problems", s["files_problem"])
    c3.metric("Transactions", s["transactions"])
    c4.metric("Accounts", s["accounts"])

    st.subheader("Per file")
    st.dataframe(
        [
            {
                "file": o.name,
                "status": o.status,
                "layout": o.layout_id or "—",
                "account": o.account_id or "—",
                "rows": o.transactions_parsed,
                "detail": o.message,
            }
            for o in run.outcomes
        ],
        hide_index=True,
    )

    if run.unassigned:
        st.warning(
            f"{len(run.unassigned)} file(s) matched no account. Add the account's "
            "IBAN or number to accounts.toml, then parse again."
        )
```

`app/pages/3_Checks.py`:

```python
# app/pages/3_Checks.py
"""Checks: prove every statement reconciles before believing any figure."""

from __future__ import annotations

import streamlit as st

from app.state import STATUS_ICON
from fbr.money import format_paisa

st.header("Checks")

run = st.session_state.get("run")
registry = st.session_state.get("registry")
if not run:
    st.warning("Load statements first.")
    st.stop()

st.subheader("Accounts")
rows = []
for account_id, ledger in run.ledgers.items():
    account = registry.by_id(account_id) if registry else None
    rows.append({
        "": STATUS_ICON[ledger.status],
        "account": account.institution if account else account_id,
        "transactions": len(ledger.transactions),
        "opening 1 Jul": format_paisa(ledger.opening) if ledger.opening is not None else "unknown",
        "from": ledger.opening_source,
        "closing 30 Jun": format_paisa(ledger.closing) if ledger.closing is not None else "unknown",
        "from ": ledger.closing_source,
    })
st.dataframe(rows, hide_index=True)
st.caption(
    "A balance shown as **unknown** is never treated as zero. Enter the 1 July "
    "balance in manual inputs for accounts whose statements print no balance."
)

failed = [c for c in run.all_checks if c.status == "fail"]
warned = [c for c in run.all_checks if c.status == "warn"]

if failed:
    st.error(
        f"{len(failed)} check(s) failed. Those statements contribute nothing to "
        "any total until the cause is fixed."
    )
    st.dataframe(
        [
            {"check": c.kind, "expected": c.expected, "found": c.actual,
             "where": c.locator or c.scope, "detail": c.detail}
            for c in failed
        ],
        hide_index=True,
    )

if warned:
    st.warning(f"{len(warned)} warning(s).")
    st.dataframe(
        [
            {"check": c.kind, "expected": c.expected, "found": c.actual,
             "where": c.locator or c.scope, "detail": c.detail}
            for c in warned
        ],
        hide_index=True,
    )

with st.expander(f"All {len(run.all_checks)} checks"):
    st.dataframe(
        [
            {"status": c.status, "scope": c.scope, "check": c.kind,
             "expected": c.expected, "found": c.actual, "detail": c.detail}
            for c in run.all_checks
        ],
        hide_index=True,
    )
```

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/test_app_state.py -v`
Expected: PASS

- [ ] **Step 7: Launch the app and verify the privacy posture**

```bash
./run &
sleep 5
lsof -i -P | grep -i python | grep LISTEN     # expect ONLY 127.0.0.1:8501
lsof -i -P | grep -i python | grep ESTABLISHED # expect NOTHING outbound
kill %1
```

Expected: one loopback listener and no outbound connections. If anything reaches `data.streamlit.io` or `checkip.amazonaws.com`, stop and fix `.streamlit/config.toml` before going further — that is the guarantee the whole privacy posture rests on.

- [ ] **Step 8: Walk the three pages by hand**

```bash
./run
```

Open `http://127.0.0.1:8501`, then:
1. **Setup** — create the private folder, see the profile self-tests pass, and see the wealth bank-account code flagged `✗`.
2. Put a synthetic CSV in `~/fbr-private/statements/TY2026/` (generate one with `uv run python -c "from tests.fixtures.synth import *; open('/tmp/s.csv','wb').write(write_meezan_csv(build_statement(seed=1)))"`), and add a matching account to `accounts.toml`.
3. **Load** — parse it and confirm the layout and account resolve.
4. **Checks** — confirm the account shows ✅ and the boundary balances appear.

- [ ] **Step 9: Run the whole suite**

Run: `uv run pytest`
Expected: PASS — every test in Tasks 1–15

- [ ] **Step 10: Commit**

```bash
git add app tests/test_app_state.py
git commit -m "$(cat <<'EOF'
feat: add Setup, Load and Checks pages

Pages call the pipeline and render; all logic stays in the library. Account
identifiers are masked on screen, IRIS codes show their verification state,
and unknown balances are never displayed as zero.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Phase exit criteria

Before phase 2 begins, all of these must hold:

1. `uv run pytest` passes with no failures or errors.
2. `./run` serves only on `127.0.0.1`, with no outbound connections (Task 15, Step 7).
3. `uv run fbr-dump <a real statement>` writes a dump whose text contains no name, IBAN or amount from the source.
4. Every shipped profile passes its own self-test.
5. A statement with a dropped row, a flipped sign or a wrong printed total is reported as failed and contributes nothing to any total.
6. The pre-commit hook blocks an IBAN-shaped string (Task 1, Step 10).

**Then, before writing the phase 2 plan, the owner supplies:** real `fbr-dump` output for Meezan, MCB Live and NayaPay CSV/XLSX exports, plus a SadaPay PDF dump. Those dumps replace every `# VERIFY` value in the shipped profiles. Until that happens, the profiles parse synthetic fixtures only, and no figure from this tool should go anywhere near IRIS.
