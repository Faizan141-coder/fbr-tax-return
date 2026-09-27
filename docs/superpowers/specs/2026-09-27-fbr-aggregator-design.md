# Design Spec — FBR Tax Return Data Aggregator

> **Status:** approved section by section on 27 Sep 2026. Awaiting the owner's review of this written spec.
>
> **Inputs:**
> - [requirements.md](../../requirements.md): the owner's brief
> - [spec-review.md](../../spec-review.md): review and proposals P1–P15
> - [open-questions.md](../../open-questions.md): the owner's decisions
> - research [01](../../research/01-fbr-tax-rules.md), [02](../../research/02-fbr-iris-codes.md), [03](../../research/03-statement-formats.md), [04](../../research/04-tech-stack.md)
>
> **Precedence:** where this spec differs from the brief or the spec review, this spec wins. This includes the build order in spec-review §6, which §11 replaces. It is not tax advice.

## 1. Goal and success criteria

**Goal.** A local-only tool that reads the owner's bank and wallet statements for one tax year and turns them into figures ready to copy into IRIS, with a complete audit trail. It covers the income tax return (s.114(1)) and the wealth statement (s.116). Genuinely manual items are left to the owner.

**Success criteria**

1. **Acceptance test.** Run on the owner's TY2026 statements, the tool reproduces every figure the owner filed for TY2026, or it lists and explains each difference.
2. **Exactness.** Every figure traces to source rows: file hash, page or row, and raw text.
3. **Fail closed.** A statement that doesn't reconcile adds nothing to any total, and the summary is marked **INCOMPLETE** while any check fails or any review item is still open.
4. **Privacy.**
   - No network traffic other than the loopback listener.
   - No statement data is written to disk, except the owner's private folder and the Excel file the owner chooses to download.
   - Claude reads only masked layout dumps.
5. **Maintainability.** A bank changing its statement format next year needs a new TOML layout profile, not a code change.

**Owner decisions this spec builds on** ([open-questions §A](../../open-questions.md)):

| # | Decision |
|---|---|
| Q1 | Build for next season. TY2026 is filed manually and becomes the acceptance test. |
| Q2 | Claude sees statements only as masked layout dumps. |
| Q3 | CSV/XLSX first; PDF where needed (SadaPay) and as a later fallback. |
| Q4 | All foreign-channel credits (Payoneer, Wise, Remitly, Thunes, …) are work income. They default to export proceeds at 1% (IRIS 64060285) and stay reviewable. |
| — | Layouts are described by declarative TOML profiles read by generic engines (approach A; see §13). |

## 2. Scope

**In scope**
- Statements from Meezan Bank, MCB Bank, SadaPay and NayaPay, as CSV/XLSX and PDF.
- Further institutions can be added by profile only.
- Classification, reconciliation, internal-transfer matching and a review workflow.
- An IRIS-cell summary, an Excel export and a manual-inputs page.

**Out of scope**
- Categorising personal expenses. Only a per-account reference total is given.
- Submitting anything to FBR or IRIS.
- Guessing cash in hand or personal items.
- OCR of scanned statements.
- Calculating tax liability. Rates are used only for sanity checks.
- Foreign-currency (ESFCA) accounts, until the owner adds one.
- Hosting, multiple users, and any LLM or cloud extraction.

**In scope, arriving in phase 5:** a generic Rule 42 certificate parser, starting with NayaPay's s.236Y certificate as the brief requires. It extracts the "on the amount of Rs. X" and "Rs. Y" figures. Manual entry is the fallback (§4.4).

**Later / optional** (§11, phase 6):
- Other evidence documents: S-PRC and e-PRC, bank WHT certificates used as cross-checks, and IRIS's withholding export.
- PDF fallback profiles for Meezan, MCB and NayaPay.
- A wealth-reconciliation helper.
- A comparison with IRIS's pre-filled "Summary of Economic Transactions".

## 3. Architecture

```
upload / load (+ password) → detect layout → parse (tabular | pdf engine) → normalize
  → reconcile (per statement, per account, clip to tax year)
  → classify (rules + pairing) → match internal transfers → apply saved decisions
  → review → aggregate into IRIS cells → Excel (in memory) → download
```

Every stage is a pure function over typed, immutable objects, and can be tested on its own.

### 3.1 Repository layout (shareable; never contains real data)

```
pyproject.toml, uv.lock, .python-version
run                               # launcher: streamlit with privacy flags
.streamlit/config.toml            # privacy lockdown (§9.1)
.githooks/pre-commit              # blocks IBAN/CNIC patterns (§9.2)
src/fbr/                          # core library — no Streamlit imports
  model.py                        # types (§4)
  money.py                        # text → integer paisa, formatting
  config/                         # loaders + pydantic schemas: profiles, rules,
                                  #   tax years, registry, manual inputs
  ingest.py                       # bytes + password → Document, layout detection
  engines/tabular.py              # CSV/XLSX engine (§5.2)
  engines/pdf.py                  # positioned-words engine (§5.3)
  reconcile.py                    # checks, merge, boundary balances (§6)
  classify.py                     # rules + pairing (§7.1–7.2)
  transfers.py                    # internal-transfer matcher (§7.3)
  review.py                       # decision store (§7.4)
  summary.py                      # IRIS cells (§8.2)
  export.py                       # Excel workbook (§8.3)
app/                              # Streamlit pages (§8.1)
tools/dump_layout.py              # masking tool, entry point `fbr-dump` (§5.5)
tools/dump_allowlist.txt          # shipped non-personal vocabulary
profiles/*.toml                   # one per layout (§5.4)
rules/classification.toml         # shareable rules (§7.1)
taxyears/TY2026.toml              # IRIS codes, mappings, rates, thresholds (§4.3)
tests/                            # unit, round-trip, fault-injection (§10)
tests/fixtures/                   # synthetic generators only
docs/
```

### 3.2 Private folder (owner-only; outside the repo)

Default `~/fbr-private/`, overridden by `FBR_PRIVATE_DIR`. It is deliberately outside `~/Documents` and `~/Desktop`, which macOS can sync to iCloud.

```
~/fbr-private/
  accounts.toml                   # account registry (§4.2)
  rules.local.toml                # personal rules, e.g. employer name (§7.1)
  dump-allowlist.txt              # owner-approved extra vocabulary (§5.5)
  statements/TY2026/              # the owner's statement files
  decisions/TY2026.json           # saved review decisions (§7.4)
  manual/TY2026.toml              # manual inputs (§4.4)
  dumps/                          # masked layout dumps — the ONLY place Claude reads
  dump-candidates/                # frequent masked words — owner-only, Claude never reads
  private-tests/                  # optional real-file regression expectations (§10)
```

## 4. Data model

Money is **integer paisa** everywhere; `Decimal` is used only while parsing text. Dates are `datetime.date`. All types are frozen.

### 4.1 Core types

| Type | Fields |
|---|---|
| `Document` | `sha256`, `filename`, `kind` (`statement` \| `wht_certificate` \| `prc_statement`), `container` (`csv` \| `xlsx` \| `pdf`), `layout_id`, `account_id`, `period_start`, `period_end`, `pages`, `encrypted`, and `summary` (printed opening, closing, total credit, total debit, account identifier; each optional) |
| `Transaction` | `txn_id`, `account_id`, `date` (booking date), `value_date` (optional), `amount` (signed: + credit, − debit), `balance_after` (optional), `description` (complete, wrapped lines joined), `reference` (optional; STAN, reference or transaction ID), `tax_year`, and `provenance` (`sha256`, page or row, y-position, raw text, `sign_source` of `column` \| `suffix` \| `signed` \| `balance`) |
| `Check` | `check_id`, `scope` (`document` \| `account` \| `tax_year`), `kind` (`running_balance` \| `opening_closing` \| `printed_totals` \| `unresolved_rows` \| `date_range` \| `continuity` \| `gap` \| `overlap` \| `anchor_missing` \| `prior_year_mismatch`), `status` (`pass` \| `warn` \| `fail`), `expected`, `actual`, `detail`, `provenance` |
| `Classification` | `txn_id`, `category` (§4.5), `rule_id`, `reason`, `linked_txn_ids`, `status` (`proposed` \| `confirmed` \| `rejected` \| `overridden`) |
| `TransferMatch` | `match_id`, `debit_txn_id`, `credit_txn_id`, `tier` (`strong` \| `possible`), `signals`, `days_apart`, `fee` (paisa), `status` |
| `Decision` | `target_id` (a `txn_id` or `match_id`), `action` (`confirm` \| `reject` \| `reclassify`), `category` (only for reclassify), `note`, `at` (ISO timestamp), `tool_version` |
| `IrisCell` | `code` (a string), `column`, `label`, `value` (paisa or blank), `source_txn_ids`, `verification` (§4.3) |

**Stable IDs**

- `txn_id` = the first 16 hex digits of SHA-256 over:
  - `account_id`, `date`, `amount` and `balance_after` (empty if absent);
  - the normalized description (NFKC, upper case, whitespace collapsed, trimmed);
  - `occurrence`.
- `occurrence` numbers identical tuples 1, 2, … in printed order within the account's merged ledger (after §6.2). Re-loading the same file therefore gives the same IDs, and two identical same-day transactions get different IDs.
- `match_id` = the first 16 hex digits of SHA-256 over `debit_txn_id` + `credit_txn_id`.
- If a bank re-issues a statement with changed description text, those rows get new IDs and return to review.
- A saved decision whose target no longer exists is reported as **orphaned**.

### 4.2 Account registry (`~/fbr-private/accounts.toml`)

```toml
[owner]
name = "OWNER NAME"                # used as a transfer signal (§7.3)

[[account]]
id                 = "meezan-main"
institution        = "Meezan Bank Limited"
kind               = "bank"         # bank | wallet | foreign
iban               = "PK00TEST0000000000000000"   # examples always use the PK00TEST prefix (§9.2)
account_number     = "0000000000"   # optional
wallet_number      = ""             # optional (mobile wallets)
title              = "ACCOUNT TITLE"
type               = "Saving"       # Current | Saving | PLS | Fixed Deposit
ownership          = "Self"         # "Self" or a share, e.g. "50%"
currency           = "PKR"
statement_expected = true
match_hints        = ["MEEZAN", "0000"]
opened_on          = 2020-01-01     # optional; used when an account opens mid-year (§6.2)
closed_on          = 2099-12-31     # optional; used when an account closes mid-year
```

- A statement is linked to an account by matching its printed account identifier against `iban`, `account_number` or `wallet_number`. If nothing matches, the owner picks the account on the Load page.
- Accounts with `statement_expected = false` (Payoneer, Wise, JazzCash, …) still exist so that money moving to or from them is recognised (§7.2–7.3).

### 4.3 Tax-year config (`taxyears/TY2026.toml`, in the repo)

It holds:

- **Period:** `start = 2025-07-01`, `end = 2026-06-30`, `name = "TY2026"`. A tax year is named after the June in which it ends.
- **IRIS code entries.** Each has:
  - `code` (a string);
  - `label` (FBR's wording verbatim);
  - `tab`;
  - `columns` (the meaning of each column);
  - `source` (document and page);
  - `verification`, one of:
    - `iris_verified`: the owner confirmed it in live IRIS; shown as ✓;
    - `form_text`: read from an FBR form's text layer; shown as ⚠;
    - `form_scan`: read by OCR from a scanned form; shown as ⚠;
    - `prior_year_assumed`: carried over from the previous year; shown as ⚠;
    - `unknown`: code blank; shown as ✗.
- **Category → cell mappings**, shown in the table below.
- **Sanity rates** (TY2026):

  | Section | Rate |
  |---|---|
  | s.151(1)(b) | 20% ATL / 40% non-ATL |
  | s.7B | 20% |
  | s.236Y | 5% / 10% |
  | s.231AB | 0.8%, non-ATL only |
  | s.154A | 1% (owner) |

- **Thresholds and windows:**

  | Name | Value |
  |---|---|
  | `profit_final_regime_max` | Rs 5,000,000 |
  | `s111_4_cap` | Rs 5,000,000 |
  | `review_threshold` | Rs 10,000 (inclusive) |
  | `wht_ratio_tolerance` | 1 percentage point |
  | `profit_wht_window_days` | 1 |
  | `tax154a_window_days` | 1 |
  | `tax154a_amount_tolerance` | Rs 1 (covers banks that round to the rupee) |
  | `transfer_window_days` | 3 |
  | `transfer_fee_tolerance` | Rs 100 |
  | `reversal_window_days` | 30 |

- **Templates:**
  - `wealth_line = "{iban} - {title} - {institution_upper} - {ownership}"`
  - `profit_line = "Profit on Debt u/s 151(1)(b) from Bank Accounts/Deposits - Profit on Savings Account - Investment in {institution}"`
- **ATL assumption:** `atl = true`. The owner files every year; this only affects sanity rates.

TY2026 code entries at the start. Codes, labels and verification sources are from [research 02](../../research/02-fbr-iris-codes.md).

| Category / figure | Code, column | Verification at start |
|---|---|---|
| Export receipts | 64060285 col 1 ("Export of services u/s 154A @1%") | `form_scan` (clean in TY2024 text and TY2026 AOP/company pages) |
| s.154A tax deducted | 64060285 col 2 | `form_scan` |
| Profit on debt (income line) | 500312 | `prior_year_assumed` (TY2025 text; illegible in the TY2026 scan) |
| Profit on debt, final tax (total ≤ Rs 5m) | 64040052 col 1 = gross, col 2 = WHT | `form_scan` |
| Profit on debt WHT (total > Rs 5m) | 64040002 | `form_scan` |
| Salary tax (s.149), from manual input | 64020004 | `form_scan` |
| s.236Y | 64151905 | `form_scan` |
| s.231AB | 64100101 | `prior_year_assumed` |
| Zakat u/s 60 | 9001 | `prior_year_assumed` |
| Withholding Income Tax, check total | 9201 | `form_scan` |
| Business income, head total (context only) | 3000 | `form_scan` |
| Wealth: bank accounts | *blank* | `unknown`: owner action A1 ([open-questions §C](../../open-questions.md)) |
| Wealth: cash in hand; foreign assets (116A tab) | *blank* | `unknown` |

When the owner confirms a code in IRIS, its entry becomes `iris_verified`.

### 4.4 Manual inputs (`~/fbr-private/manual/TY2026.toml`)

- **`salary`:** employer, gross salary, s.149 tax deducted (from the employer's certificate).
- **`opening_anchor.<account_id>`:** balance at 1 July. Required for accounts without a balance column.
- **`prior_year_closing.<account_id>`:** closing balance declared in the TY2025 wealth statement.
- **`cash_in_hand`.**
- **`foreign_assets[]`:** description, institution, currency, amount, PKR value, conversion note.
- **`certificate_236Y[]`:** issuer, amount remitted, tax collected. This is the fallback when a Rule 42 certificate can't be parsed (§8.2).

Every field is optional. A blank is exported as blank, never as zero.

### 4.5 Categories

| Group | Category | Direction |
|---|---|---|
| Income | `export_proceeds_154A` | credit |
| Income | `profit_on_debt` | credit |
| Tax deducted or paid | `tax_154A_deducted`, `wht_151`, `wht_236Y`, `wht_231AB` | debit |
| Not income | `personal_remittance`: never a default; reached only by owner reclassification | credit |
| Not income | `salary_net` | credit |
| Not income | `reversal_refund` | either |
| Not income | `internal_transfer` | either |
| Not income | `own_transfer_unmatched` | either |
| Not income tax | `zakat`, `indirect_tax_charges` | debit |
| Everything else | `other_debit` | debit |
| Everything else | `other_credit`: below the review threshold | credit |
| Everything else | `unclassified_credit`: at or above the review threshold; goes to review | credit |

## 5. Parsing

### 5.1 Opening a file and detecting its layout (`ingest.py`)

1. **Container.** The type comes from magic bytes: `%PDF`, the ZIP signature for XLSX, otherwise CSV text. For CSV, try encoding `utf-8-sig`, then `cp1252`. Record which one decoded.
2. **Encrypted PDFs.** Open in memory with `pdfplumber.open(BytesIO, password=…)`. If the password is wrong, prompt again. Passwords are never logged, stored or placed on a command line.
3. **Unusable PDFs are refused.** This applies when a page has no characters or its text contains `(cid:`. The message reads: "scanned or unreadable fonts — not supported".
4. **Layout detection.** Every profile for that container type tests its `[detect]` signature.
   - Exactly one match: that profile is used.
   - No match: the file is an "unknown layout", and the `fbr-dump` command is shown.
   - More than one match: the owner chooses, and the signatures should then be tightened.
5. **Account.** The account is resolved as described in §4.2.

### 5.2 Tabular engine (CSV/XLSX), built first

- XLSX is read with openpyxl (read-only, from `BytesIO`, cached values); CSV with Python's `csv` module.
- The header row is the first row, within the first 30, that contains every `[detect].header_contains` string. The rows above it are the **preamble**; the `[summary]` regexes run over it.
- Columns are mapped by **header name**: role → label, with alternatives allowed. Extra columns are recorded and ignored.
- Each data row:
  - is skipped and counted if it matches `[rows].skip`;
  - is captured as a summary value if it matches `[rows].summary`;
  - otherwise the date is parsed with `[formats].dates` (in order; the first match wins) and the amount according to `[formats].sign`:
    - `columns`: separate Debit and Credit columns, each unsigned;
    - `suffix`: one amount with Dr/Cr tokens from the profile;
    - `signed`: `+` or `−`, including U+2212.
- If an amount token fails to fully match the profile's amount grammar, the row is marked `unresolved`.

### 5.3 PDF engine (positioned words), built second

1. For each page: `dedupe_chars()`, then drop non-upright characters, then take `extract_words` with NFKC normalisation.
2. Find the header on each page with `page.search()`: every `[columns]` label must sit on one visual line (same `top` within a tolerance). A continuation page with no header reuses the previous page's bands.
3. **Bands.**
   - Text columns are split at the midpoints between neighbouring header boxes.
   - A numeric column takes a token whose right edge is nearest that column's header right edge. The profile can set `align` to `right`, `left` or `center` per column.
   - A token outside every band, or equally close to two bands, is marked `ambiguous`.
4. The body is cropped between the header's bottom edge and the first `[rows].footer` match.
5. **Rows are rebuilt in printed order** (by `doctop`).
   - `row_anchor = "date"` is the default: a date in the date band starts a row.
   - `row_anchor = "amount"` makes an amount/balance line start a row instead (for block layouts such as NayaPay's PDF).
   - Lines without an anchor are continuation lines: `continuation = "below"` appends them to the open row, and `"nearest"` appends them to the nearest anchor line.
6. Summary rows (opening balance, B/F, carried forward, totals) become summary values, never transactions. The `[summary]` regexes run over the page text.
7. **v1 target:** SadaPay, `sign = "signed"`. Column-band sign logic for Meezan (`columns`), MCB (`suffix`) and NayaPay (`row_anchor = "amount"`) comes with the phase 6 fallbacks.

### 5.4 Layout profile (`profiles/<id>.toml`)

| Section | Contents |
|---|---|
| identity | `id` (e.g. `meezan.csv.v1`), `institution`, `container`, `valid_from`, optional `valid_to`, `notes` |
| `[detect]` | `header_contains` (list), optional `title_regex` |
| `[columns]` | role → header label or list of labels. Roles: `date`, `value_date`, `description`, `reference`, `debit`, `credit`, `amount`, `balance`, `type`. For PDF only: `[columns.align]` |
| `[formats]` | `dates` (strptime list), `sign` (`columns` \| `suffix` \| `signed`), `debit_tokens`, `credit_tokens`, `currency_prefixes`, `decimals = 2` |
| `[rows]` | `skip`, `summary`, `footer` (regex lists), `continuation`, `row_anchor` |
| `[summary]` | Regexes with named groups: `opening`, `closing`, `total_credit`, `total_debit`, `period_from`, `period_to`, `account_id`. Each is optional. |
| `[balance]` | `semantics` (`running` \| `none`), `kind` (`ledger` \| `available`) |
| `[selftest]` | Sample rows with their expected date, amount and sign |

- Profiles are validated with pydantic `extra="forbid"`. Regexes compile with Python `re` and are checked for the named groups they need.
- **A profile whose self-test fails refuses to load.** The Setup page shows why.
- Regexes are always applied with Python `re`, never through pandas `.str` methods, which may use a different regex engine.
- When a bank changes its format, copy the profile to a new `id` with a new `valid_from`. Old profiles stay, so earlier years can be re-run.

### 5.5 Masking tool (`fbr-dump`)

- **Usage:** `uv run fbr-dump <path> [--password] [--rows N] [--pages P] [--hide-magnitude]`.
  - `--password` prompts with `getpass`. An encrypted file is therefore dumped by the owner in their own terminal.
  - Defaults: `N = 15` rows from the start and end of the table; `P` = the first two pages and the last page.
- **Output:** `~/fbr-private/dumps/<sha256[:12]>.dump.md`. The original filename is never used, because it may contain an account number.
- **Stdout:** only `wrote <path>: <rows> rows / <pages> pages, <k> tokens masked`. No content.
- **Dump contents:**
  - file facts: container, encoding, pages, encryption yes/no, text layer present, count of `(cid:`;
  - for tabular files: the preamble and header as shapes, sample rows as shapes, and a histogram of shapes per column (e.g. `9,999.99` ×120, blank ×40);
  - for PDFs: for each sampled page, lines grouped by `top`, each word as `shape@x0–x1`, rounded to 1 pt.
- **How a shape is made:**
  - A token found in the shipped allowlist or the owner's allowlist is kept verbatim. The match ignores case and surrounding punctuation.
  - The shipped allowlist is non-personal banking vocabulary: header words, month names, IBFT, Raast, Transfer, Payment, Profit, Withholding, Tax, Zakat, FED, Charges, Reversal, Payoneer, Thunes, Wise, Remitly, bank names, section numbers, and so on.
  - Every other token becomes a shape: `A–Z` → `X`, `a–z` → `x`, digits → `9`, and punctuation is kept. For example, `PK96…` becomes `XX99…`.
  - `--hide-magnitude` also rewrites the integer part of every number to a fixed `9,999` / `9999` shape. Separator style, decimals, sign and Dr/Cr are kept.
- **Candidates:** masked tokens, ranked by frequency, go to `~/fbr-private/dump-candidates/<sha12>.txt` for the owner to review. The owner copies safe words into `~/fbr-private/dump-allowlist.txt`. **Claude never reads `dump-candidates/`.**
- **Residual risk (accepted):** an allowlisted word that is also part of a name appears verbatim.

## 6. Reconciliation (`reconcile.py`)

All comparisons are exact integer arithmetic with no tolerance.

### 6.1 Per statement

| Check | Rule | On failure |
|---|---|---|
| `running_balance` | When there is a balance column: `prev + amount == balance_after` on every row in printed order. `prev` starts at the printed opening balance; if none is printed, the first row cannot be checked (warn). | fail at that row |
| `opening_closing` | `opening + Σcredits − Σdebits == closing`, when both are printed | fail |
| `printed_totals` | Σcredits and Σdebits equal the printed totals (SadaPay "Total credit/debit"; NayaPay "Total Income/Spent") | fail |
| `unresolved_rows` | No row is `unresolved` or `ambiguous`. Exception: an ambiguous sign where `abs(Δbalance) == amount` takes its sign from the balance change, gets `sign_source = "balance"`, and is listed as a warning. | fail |
| `date_range` | Every transaction date falls within the printed period | fail |

**A failed statement contributes nothing to any total.**

### 6.2 Per account (several statements)

- Statements are ordered by period start.
- **Continuity:** each statement's closing balance must equal the next statement's opening balance (when both exist), and the periods must meet with no missing day.
- **Gap:** a warning ("missing X–Y"). The account's tax-year figures are marked incomplete.
  - The span from 1 July (or `opened_on`, if later) to the first statement counts as a gap. So does the span from the last statement to 30 June (or `closed_on`, if earlier).
  - An account whose `opened_on` falls inside the tax year opens at 0 on that date.
- **Overlap:**
  - The overlapping window must have the same `(date, amount, balance_after)` sequence in both statements.
  - If it matches, one copy is kept. Preference goes to CSV/XLSX over PDF; within the same container, to the statement with the longer period.
  - If it doesn't match, the check fails with "statements disagree" and that window adds nothing.
  - Uploading CSV and PDF for the same period therefore acts as a cross-check.
- **No row-level de-duplication across the year.**

### 6.3 Tax-year boundary

- `tax_year` comes from the **booking date**. Out-of-year rows stay in Raw transactions but are excluded from totals.
- **Opening at 1 July:** the running balance just before the first transaction dated on or after 1 July. If the statement starts exactly on 1 July, this is the printed opening balance; the `running_balance` check has already tied it to the first row.
- **Closing at 30 June:** the running balance after the last transaction dated on or before 30 June. If the statement ends exactly on 30 June, this equals the printed closing balance, as the `opening_closing` check has already confirmed.
- **No balance column:**
  - opening = `opening_anchor`;
  - closing = anchor + Σcredits − Σdebits for the year;
  - with no anchor, both balances are **unknown** (never zero), and `anchor_missing` appears in the review list.
- **`prior_year_mismatch`:** the computed opening at 1 July differs from `prior_year_closing`. This is a warning.

### 6.4 Status

Each account gets ✅ complete, ⚠️ warnings, or ❌ failed. The IRIS summary is **INCOMPLETE** while any account in the tax year is ❌ or has a `gap`, or while review items are open.

## 7. Classification, pairing and transfers

### 7.1 Rules

- **Shareable rules:** `rules/classification.toml`. Each rule has:
  - `id`, `category`, `direction` (`credit` \| `debit` \| `any`);
  - `pattern`: Python `re`, compiled case-insensitive, word-bounded by the rule author;
  - optionally `institutions`, `min_amount`, `max_amount`, `note`.
- **Personal rules:** `~/fbr-private/rules.local.toml`, for example the employer's name for `salary_net`. They are merged at load time and may add rules or disable a shared rule by `id`.
- **Evaluation:** every rule runs on every transaction.
  - Exactly one category matches: a `proposed` classification.
  - Two or more categories match: a **conflict**, sent to review.
  - No match: debit → `other_debit`; credit below `review_threshold` → `other_credit`; otherwise `unclassified_credit`, sent to review.
- **Initial shared rules** (to be refined from the owner's masked dumps):

  | Category | Direction | Patterns |
  |---|---|---|
  | `export_proceeds_154A` | credit | `\bPayoneer\b`, `\bThunes\b`, `\bWise\b`, `\bTransferwise\b`, `\bRemitly\b`, `Inward Foreign Remittance`, `^Remittance From\b` |
  | `profit_on_debt` | credit | `Payment of Profit`, `PROFIT-LOSS` |
  | `wht_151` | debit | `Withholding Tax`, `WHT COLL.*151` |
  | `wht_236Y` | debit | `\b236Y\b` |
  | `wht_231AB` | debit | `\b231AB\b` |
  | `zakat` | debit | `\bZakat\b` |
  | `indirect_tax_charges` | debit | `\bFED\b`, `Excise`, `Sales Tax`, `\b(PST\|SST\|PRA)\b`, `\bCharges?\b`, `\bFee\b` |
  | `reversal_refund` | any | `\bREFUND\b`, `\bRevers(al\|ed)\b` |

  `tax_154A_deducted` has no pattern-only rule. It comes only from pairing (§7.2).

### 7.2 Pairing (within one account)

- **Profit ↔ WHT (s.151)**
  - The WHT debit is within `profit_wht_window_days` of the profit credit. When several are possible, the WHT closest to `rate × gross` wins.
  - If the WHT differs from the expected rate (20% for TY2026, ATL) by more than `wht_ratio_tolerance`, a warning is raised. A reduced Zakat base, a change in ATL status or rounding are common causes.
  - Unpaired profit or unpaired WHT: a warning.
  - Σ gross profit across all accounts > `profit_final_regime_max`: a warning, and the IRIS mapping switches to 64040002 for WHT with 500312 on the normal regime.
- **Export ↔ s.154A tax**
  - A debit on the same account within `tax154a_window_days`, whose amount is within `tax154a_amount_tolerance` of 1% of the credit, or of 0.25% for information, becomes `tax_154A_deducted`, linked to the credit.
  - If none is found, deducted = 0 and the shortfall (1% × receipts − deducted) is shown as "confirm with advisor".
  - Tax netted out of the credit itself is not detectable from statements. It becomes detectable once PRCs are loaded in phase 6.
- **Reversal ↔ original**
  - A reversal credit pairs with an earlier debit of the same amount on the same account within `reversal_window_days`; both are marked `reversal_refund`.
  - An unpaired reversal credit at or above `review_threshold` goes to review.
- **Own accounts without statements**
  - If a transaction's description matches `match_hints` of an account with `statement_expected = false`:
    - a **domestic** account (`kind` `bank` or `wallet`) gives `own_transfer_unmatched`;
    - a **foreign** account (`kind = "foreign"`, e.g. Payoneer or Wise) gives:
      - for credits, the export rule. Money arriving from abroad is the moment the export proceeds are realized, so it is not a transfer;
      - for debits, `own_transfer_unmatched`.

### 7.3 Internal-transfer matcher (`transfers.py`)

- **Candidates:** a debit on account A and a credit on account B, where:
  - A ≠ B, and both are registry accounts with loaded statements;
  - neither is categorised as `wht_*`, `tax_154A_deducted`, `zakat` or `indirect_tax_charges`;
  - `abs(date difference) <= transfer_window_days`;
  - the credit equals the debit, **or** `0 < debit − credit <= transfer_fee_tolerance`.
- **Evidence signals:**
  - E1: either description contains a `match_hints` entry of the *other* account;
  - E2: either description contains `owner.name`;
  - E3: either description names the other account's institution.
- **Tiers:**
  - **strong:** exact amount, and `days_apart <= 1`, and at least one of E1–E3. These are pre-ticked in review.
  - **possible:** every other candidate. These start unticked.
- **One to one:** candidates are sorted by:
  1. tier (strong first);
  2. exact before fee;
  3. fewer `days_apart`;
  4. more signals;
  5. printed order.

  They are then assigned greedily, so each transaction is in at most one match.
  - When candidates tie on the whole sort key and are interchangeable (same account pair, amount and date), they are assigned in printed order.
  - When they tie but lead to **different** counterpart accounts, none is assigned and all are flagged `ambiguous_pair`.
- **Income conflict:**
  - A matched credit that was proposed as `export_proceeds_154A` or `profit_on_debt` becomes a **conflict**, shown with both explanations and never auto-resolved.
  - The same applies to a match involving `salary_net`.
  - Otherwise the pair's transactions become `internal_transfer` (proposed).

### 7.4 Review and decisions (`review.py`)

- **Queue order:**
  1. conflicts;
  2. transfer matches (strong, then possible);
  3. income proposals (itemised exports, which can be confirmed in bulk; profit/WHT pairs with their rate check);
  4. `unclassified_credit`;
  5. unpaired items;
  6. missing data (`anchor_missing`, failed checks, gaps).
- **Decisions** are saved to `decisions/TY2026.json` as soon as they are made. The write is atomic: a temp file in the same folder, then a rename.
- On every run, decisions are applied after proposals are made; a decision overrides its proposal. Orphaned decisions are listed on the Review page.

## 8. Outputs

### 8.1 Streamlit pages (`app/`)

| # | Page | Content |
|---|---|---|
| 1 | Setup | Tax year; private-folder status; registry accounts (IBAN shown as `…3474`); profiles, rules and tax-year config loaded, each with its self-test status |
| 2 | Load | By default, files are read from `~/fbr-private/statements/<TY>/`. This avoids Streamlit spooling uploads over 1 MB to a temp file. Upload is the alternative. Asks for passwords, and shows each file's detected layout and resolved account. |
| 3 | Checks | Account status ✅/⚠️/❌; per-statement checks; gaps and overlaps; boundary balances with their source (printed / computed / anchor) |
| 4 | Review | The §7.4 queue as `st.data_editor` tables (confirm / reject / reclassify), saved instantly |
| 5 | Manual inputs | The §4.4 fields |
| 6 | Summary & export | The IRIS summary (§8.2); an **INCOMPLETE** banner when it applies; Download Excel |

### 8.2 IRIS summary (from the tax-year config)

- **Business → Final tax:**
  - 64060285: col 1 = Σ `export_proceeds_154A`; col 2 = Σ `tax_154A_deducted`.
  - For information: the 1% expected and the shortfall.
  - Note: the same receipts also feed Business revenue in the final-tax column, which rolls up to 3000.
- **Other Sources → Final tax:**
  - One itemised line per bank using `profit_line`: col 1 = gross profit, col 2 = WHT. The codes are 500312 and 64040052 (or 64040002 above the threshold).
- **Adjustable tax:**
  - 64020004 = manual s.149 tax.
  - 64151905 takes the first available source:
    1. parsed Rule 42 certificates (phase 5);
    2. `certificate_236Y` manual inputs;
    3. Σ `wht_236Y` from statements.

    When both the certificate total and the statement total exist and differ, the difference is flagged.
  - 64100101 = Σ `wht_231AB`.
- **Deductible allowance:** Zakat u/s 60 = Σ `zakat`.
- **9201 check total:** the sum of all income tax deducted (final + adjustable). It is shown with its components and labelled "IRIS computes this — compare".
- **Not income tax (for information):** Σ `indirect_tax_charges`. Zakat is shown only as the allowance above.
- **Wealth — bank accounts:** per account, `wealth_line`, opening at 1 July, closing at 30 June, change, and the source of each balance.
- **Wealth — manual:** cash in hand; foreign assets (116A).
- **Expense reference per account:** Σ `other_debit` + Σ `indirect_tax_charges`. Totals for taxes, Zakat and own transfers are shown separately beside it.
- Every cell shows its verification mark (§4.3).

### 8.3 Excel workbook (`export.py`)

- **Writer:** XlsxWriter through `pd.ExcelWriter` with `in_memory=True`, `strings_to_formulas=False` and `strings_to_urls=False`.
- **Formatting:** amounts are written as numbers in `#,##0.00`; the header row is frozen; autofilter is on.
- **Filename:** `FBR_<TY>_<YYYYMMDD-HHMM>.xlsx`. It is delivered only through `st.download_button`, and the tool never saves it itself.

| Sheet | Contents |
|---|---|
| Summary | IRIS cells: code, label, column, value, verification, transaction count |
| 1 Export income | Date, account, source label, reference/STAN, amount, tax deducted, rule, decision |
| 2 Profit on debt | Per bank: gross, WHT, net, ratio check; itemised rows |
| 3 Withholding | Final / adjustable / not income tax; the 9201 check |
| 4 Wealth – bank accounts | Line text, opening, closing, change, balance sources |
| 5 Review | Every flag and its status |
| 6 Account totals | Per account and statement: parsed vs printed debits and credits |
| Checks | Every §6 check |
| Sources | File name, SHA-256, layout, container, period, pages, account |
| Manual inputs | What was entered (blanks stay blank) |
| Raw transactions | Every row: `txn_id`, account, dates, amount, balance, description, reference, category, rule, decision, provenance |

## 9. Privacy

### 9.1 Runtime

**`.streamlit/config.toml`:**

| Setting | Value |
|---|---|
| `browser.gatherUsageStats` | `false` |
| `browser.serverAddress` | `127.0.0.1` |
| `server.address` | `127.0.0.1` (also stops Streamlit's external-IP lookup) |
| `server.headless` | `true` |
| `server.showEmailPrompt` | `false` |
| `server.allowedHosts` | `["127.0.0.1", "localhost"]` |
| `server.maxUploadSize` | `25` |
| `client.toolbarMode` | `viewer` |

- `./run` passes the same flags on the command line.
- State lives only in `st.session_state`, never `st.cache_data` or `st.cache_resource`.
- Passwords are held only in memory and never go on any command line.
- The Excel file is built in memory.
- The app never uses `page_icon=":material/…"` or map elements, since both fetch from CDNs.

### 9.2 Repository

- **`.gitignore`:**
  - `*.pdf`, `*.csv` and `*.xlsx` everywhere, except `tests/fixtures/**`, which only ever holds synthetic generator output;
  - `.venv/`, the Streamlit cache, and `tests/private/`.
- **`.githooks/pre-commit`** (activated with `git config core.hooksPath .githooks`) rejects staged content matching:
  - an IBAN: `PK\d{2}[A-Z]{4}\d{16}`, except the literal test prefix `PK00TEST`;
  - a CNIC: `\d{5}-\d{7}-\d`.

### 9.3 Claude's working rule

- Claude reads only `~/fbr-private/dumps/`.
- Claude never reads statements, `dump-candidates/`, the registry, decisions or manual inputs.
- Claude never prints raw extraction output.
- If diagnosing a bug needs real values, the owner runs the check locally and reports the result.

## 10. Testing

| Layer | What |
|---|---|
| Unit | Amount grammars (commas, lakh grouping, Dr/Cr, ±, U+2212, parentheses), date formats, the paisa round trip, rule matching and conflicts, each pairing rule, matcher tiers, one-to-one assignment and tie cases, boundary balances, gap and overlap logic, stable `txn_id` and `occurrence`, decision application and orphans |
| Round trip | Generators render a synthetic statement model for each profile: CSV/XLSX writers, reportlab PDFs, and pypdf-encrypted variants (RC4, AES-128, AES-256). Parsing must return exactly the model. Fixtures are generated at test time; fake IBANs use the `PK00TEST…` prefix. |
| Fault injection | A dropped row, a flipped sign, merged rows, a wrong printed total, a disagreeing overlap, a missing anchor, and an ambiguous token must each trigger the expected check |
| Property (optional) | Hypothesis tests for the amount and date parsers and the round trip |
| Golden | The Excel sheet names and headers for a synthetic year |
| Private regression | `tests/private/` (git-ignored) runs only when `FBR_PRIVATE_TESTS=1`, against the owner's files in `~/fbr-private/`. It reports pass/fail counts only. |
| Acceptance | The TY2026 run matches the owner's filed TY2026 return cell by cell, or each difference is explained (success criterion 1) |
| Privacy smoke | While the app runs, `lsof -i -P` shows only the `127.0.0.1` listener; `git grep` finds no IBAN or CNIC patterns |

## 11. Build order

The owner's order is kept, adjusted for CSV-first. **Each phase gets its own implementation plan.** The first plan covers phases 0–1.

| Phase | Delivers | Owner provides |
|---|---|---|
| 0 Foundation | uv project; privacy config, launcher and git guardrails; `model` and `money`; config loaders and schemas; reconciliation engine (tested on synthetic ledgers); `fbr-dump` with the shipped allowlist; synthetic CSV generator | The private folder and `accounts.toml` |
| 1 Tabular | Tabular engine; CSV/XLSX profiles for Meezan, MCB Live and NayaPay (built from masked dumps); account merge and boundary balances; Setup, Load and Checks pages | TY2026 CSV/XLSX exports from the three institutions, and their `fbr-dump` output |
| 2 PDF | PDF engine (signed mode); SadaPay profile; encrypted-PDF handling; reportlab fixtures; anchor handling | SadaPay PDF for exactly 1 Jul 2025 – 30 Jun 2026, its dump, and the opening anchor |
| 3 Classify | Rules and loader, pairing, the Review page, the decision store | `rules.local.toml` (employer name) |
| 4 Transfers | Matcher, review integration, conflicts | — |
| 5 Outputs | IRIS summary, Manual inputs page, Excel export, generic Rule 42 certificate parser (NayaPay s.236Y first) | Manual inputs; the TY2026 bank-account code read off IRIS (A1); the s.236Y certificate and its dump |
| 6 Acceptance + later | Acceptance run against the filed TY2026 return. Then, as needed: PDF fallback profiles (Meezan, MCB, NayaPay); other evidence documents (S-PRC/e-PRC, bank WHT certificates, IRIS withholding export); wealth-reconciliation helper; comparison with IRIS's pre-filled summary | The filed TY2026 return figures |

## 12. Open items carried from research

- **Owner look-ups:** A1–A5 in [open-questions §C](../../open-questions.md). A1, the TY2026 bank-account code, blocks only that one summary cell.
- **Tax advisor:** T1–T5 in [open-questions §D](../../open-questions.md). The tool reports the relevant figures and does not decide them.
- **To confirm from real files** (via dumps and local checks):
  - whether NayaPay prints opening/closing balances;
  - whether Meezan's "Available Balance" behaves as a running balance;
  - which PDF encryption each bank uses;
  - the exact description wording for foreign credits, s.154A deductions and s.236Y at each institution.
- **To confirm in phase 1:** that openpyxl's read-only XLSX reader, given a `BytesIO`, writes no temp files. Research 04 only confirmed that openpyxl *writes* temp files when saving. If the reader does too, XLSX input converts in memory some other way.

## 13. Alternatives considered

| Option | Why not chosen |
|---|---|
| One Python parser module per layout | Quicker first parser, but every format change becomes a code change, which contradicts the brief's "update without touching core logic". Parsers also drift apart in behaviour. It survives only as a possible future escape-hatch hook, added if the engines ever can't express a layout. |
| Line regexes over `pdftotext -layout` | Closest to the brief's wording, but it can't reliably place Meezan's unsigned Credit/Debit amounts, because proportional fonts lose column position. Wrapped descriptions also break line regexes. |
| PyMuPDF instead of pdfplumber | Faster, but AGPL-licensed. pdfplumber (MIT) is fast enough for a once-a-year run, and its speed will be measured in phase 2. |
| PDF-only input (as briefed) | The owner chose CSV/XLSX first (Q3), which removes most of the parsing risk for three of the four institutions. |
| Emergency MVP for TY2026 | The owner chose to build for next season (Q1). |

## 14. Glossary

| Term | Meaning |
|---|---|
| ATL | Active Taxpayers' List. Non-ATL persons pay higher withholding rates. |
| Anchor | A balance the owner enters, used where a statement has no balance column. |
| EMI | Electronic Money Institution (SadaPay, NayaPay). They receive foreign money through a partner bank's home-remittance channel. |
| e-PRC / S-PRC | A bank's electronic Proceeds Realization Certificate, and the annual Statement of PRCs. They carry the SBP purpose code (9186 freelance IT; 9471 family). |
| IBFT / Raast | Interbank fund transfer / SBP's instant payment system. |
| IRIS | FBR's online return-filing portal. |
| Layout profile | A TOML description of one statement layout. |
| Paisa | 1/100 rupee. All money is stored as integer paisa. |
| PSEB | Pakistan Software Export Board. Registration and certification qualify an exporter for 0.25% instead of 1%. |
| SRO | Statutory Regulatory Order: how FBR publishes each year's return forms. |
| STAN | System Trace Audit Number: a bank transaction reference. |
| WHT | Withholding tax. |
