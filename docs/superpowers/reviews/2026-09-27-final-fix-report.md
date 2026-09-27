# Final fix round — whole-branch review

Branch `main`, from `f8ddf59` (250 tests) to `05286c4` (313 tests, all passing).
Python: CPython 3.14.6 via `uv run`. Ten commits, one per finding or coherent group.

Every finding below was reproduced by execution before the fix and re-verified after.
Figures are real output, not paraphrase.

---

## CRITICAL 1 — wrong account attribution (`src/fbr/ingest.py`, `resolve_account`)

Commit `c85e02e`.

### Before

`resolve_account` squashed `summary.account_identifier` and 30 rows of body text into
one haystack and returned the **first** registry account whose IBAN, account number or
wallet number appeared anywhere in it.

Reproduction: a registry declaring the wallet `03001234567` first, then
`meezan-main` (`PK00TEST0000000000000000`); a Meezan CSV printing the Meezan IBAN in
its preamble and carrying the description
`Raast P2P Fund transfer to 0300 1234567`:

```
printed account_identifier: None
body contains wallet-ish text: True
resolve_account -> nayapay              # EXPECTED meezan-main
```

Every Meezan transaction would then be booked to the wallet, the wallet's 30 June
balance would become Meezan's, and `meezan-main` would vanish from the Checks page
with nothing said.

Second reproduction — two registry accounts sharing an IBAN:

```
two matching accounts -> a              # EXPECTED None
```

Deferred finding, also reproduced: `test_resolves_an_account_by_iban` could not prove
what it claimed, because its fixture's `account_number` was a substring of its `iban`:

```
'0000000000' in 'PK00TEST0000000000000000': True
```

### Fix

Spec §4.2: a statement is linked "by matching its **printed account identifier**".

- `summary.account_identifier` is now matched alone, first. A unique hit returns.
- More than one hit on the printed identifier returns `None` without reading on — the
  authority is ambiguous, and body text could only contradict it.
- Body text is consulted only when the printed identifier names no registry account.
  A unique hit returns; anything else returns `None`.
- `None` is the deliberate outcome for ambiguity: an unassigned file is reported to the
  owner and recoverable on the Load page; a wrongly attributed one is not.

The fixture's `account_number` became `1122334455`, and both the IBAN and the
account-number test now assert the other branch cannot be what matched.

### After

```
printed IBAN + wallet named in body  -> meezan-main      (was nayapay)
no printed id, two accounts in body  -> None             (was nayapay)
two accounts sharing an IBAN         -> None             (was "a")
```

New tests in `tests/test_ingest.py`: unique printed-identifier match; body text naming
another account never overriding the printed one (the exact reproduction); two accounts
matching → `None`; two accounts named only in body text → `None`; body text used only
when the printed identifier matches nothing. `tests/test_ingest.py`: 14 → 22 tests.

---

## CRITICAL 2 — the masking gate leaked non-ASCII names (`tools/dump_layout.py`)

Commit `a7cad98`.

### Before

`_TOKEN` was `[A-Za-z0-9](?:[A-Za-z0-9._/-]|,(?=[0-9]))*`. Text it never captured was
never shaped:

```
'محمد فیضان حسنات' -> 'محمد فیضان حسنات'     (unchanged, fully readable)
'José Müller'      -> 'Xxxé Xüxxxx'
'Ünal Öztürk'      -> 'Üxxx Öxxüxx'
'Владимир Петров'  -> 'Владимир Петров'      (unchanged)
```

`shape()` was also wrong for caseless scripts: `'م'.isupper()` and `'م'.islower()` are
both `False`, so `shape('محمد')` returned `'محمد'` verbatim.

This is the only gate between the owner's real statements and what Claude reads
(spec §5.5, §9.3). A foreign remitter's name or any Urdu narration reached a dump
readable.

### Fix

- `_TOKEN` is now "a run that starts with a letter or digit in **any** script and ends
  at ASCII whitespace or ASCII punctuation", built as
  `rf"[^\W_](?:[^\s{re.escape(_BREAKERS)}]|,(?=\d))*"` where `_BREAKERS` is
  `string.punctuation` minus `._/-`. Non-ASCII combining marks (Arabic harakat,
  Devanagari matras, a decomposed accent) therefore stay **inside** the word rather
  than splitting it into one-character fragments that are allowlist-checked separately.
- `shape()` gained a branch: ASCII punctuation survives (it is the layout signal a
  profile author reads the dump for), and **everything else** non-ASCII is masked to
  the lowercase placeholder. Caseless scripts have no upper form, so lowercase is the
  case-appropriate choice.
- `_STRIP` became `[\W_]` (Unicode). This was necessary, not cosmetic: once the
  tokenizer captured `José` whole, an ASCII-only fold would reduce it to `JOS`, and an
  allowlist entry `JOS` would release the entire token — name and accent — verbatim.
  Confirmed against the old code: `old_shape("José", allowlist={"JOS"})` → `'José'`.

### After

```
'محمد فیضان حسنات' -> 'xxxx xxxxx xxxxx'
'مُحَمَّد اقبال'       -> 'xxxxxxxx xxxxx'
'José Müller'      -> 'Xxxx Xxxxxx'
'Ünal Öztürk'      -> 'Xxxx Xxxxxx'
'Владимир Петров'  -> 'Xxxxxxxx Xxxxxx'
'Received from 张伟' -> 'Received from xx'
shape("José", allowlist={"JOS"})   -> 'Xxxx'
```

Layout signal intact:

```
'1,234.56'                       -> '9,999.99'
'1,234.00Dr'                     -> '9,999.99Xx'
'Booking Date,Description,Credit'-> unchanged (allowlisted)
'٣٤٥'                            -> '999'      (Arabic-Indic digits are digits)
```

New tests in `tests/test_dump_layout.py`: Urdu (plain and with harakat), accented
Latin, Turkish, Cyrillic, CJK and NFD-decomposed text, each asserting no readable
fragment survives; a mixed-script line where only allowlisted banking vocabulary
remains; per-token shape assertions; the ASCII-skeleton allowlist bypass; separator
preservation; and an end-to-end CLI dump of a statement carrying an Urdu narration.
`tests/test_dump_layout.py`: 26 → 47 tests.

**Accepted tradeoff (documented in the source):** a non-ASCII character glued *between*
two letters (an em dash in `A—B`) now joins the token and is shaped — `'A—B'` → `'XxX'`.
Standing alone, as every separator in a real statement does, it is not a token start and
survives verbatim (`'—'` → `'—'`), so separator style is unaffected. Masking is the
fail-closed direction.

---

## IMPORTANT 3 — `date_range` inert, every account falsely `incomplete`

Commit `609d2ea`.

### Before

All three shipped profiles omitted `period_from`/`period_to`:

```
mcb.csv.v1:     period_from=None period_to=None
meezan.csv.v1:  period_from=None period_to=None
nayapay.csv.v1: period_from=None period_to=None
```

So `summary.period_start/end` were always `None`, `date_range` was a permanent warn, and
`Document.period_start/end` fell back to the first and last **printed** transaction.
End-to-end with the shipped config, a clean 1 Jul 2025 – 30 Jun 2026 Meezan statement
(transactions on 1 Aug and 1 May):

```
account_status: {'meezan-main': 'incomplete'}
  warn date_range  a printed period / not printed
  warn gap         2025-07-01..2026-06-30 /
                   2025-07-01..2025-07-31; 2026-05-02..2026-06-30
```

— naming as missing the very days the statement covers. The gap warning is the signal
for genuinely missing data, and firing it always trains the owner to ignore it.

CI could not see this: `tests/test_pipeline.py` built its `ProfileSet` from
`test_tabular.py`'s hand-written `MEEZAN`/`MCB`, which *do* carry period patterns.

### Fix

- `period_from`/`period_to` added to all three shipped profiles, using `[^\d\n]+?` as
  the label separator and marked `# VERIFY` like their neighbours. `period_to`
  re-matches the first date and takes the second on the same line, because both ends
  are printed together.
- `write_mcb_csv` and `write_nayapay_csv` print no period line, so one was added in the
  same additive style already used there for Total Credit / Total Debit, with the
  reasoning recorded in each docstring. `write_meezan_csv` already printed one.
- `tests/test_pipeline.py` now loads the real `profiles/` directory via
  `load_profiles()`. The hand-built profiles stay in `test_tabular.py` for the unit
  tests that vary one setting at a time; the no-balance variant used by
  `test_anchor_and_prior_year_do_not_cross_accounts` is now derived from the shipped
  meezan profile.

### After

Same statement, shipped config:

```
account_status: {'meezan-main': 'complete', 'mcb-main': 'missing'}
  pass running_balance  1,300.00 / 1,300.00
  pass opening_closing  1,300.00 / 1,300.00
  pass printed_totals   credits 500.00 / debits 200.00
  pass unresolved_rows  0 / 0
  pass date_range       2025-07-01..2026-06-30 / 2025-07-01..2026-06-30
  pass gap              2025-07-01..2026-06-30 / covered
```

(`mcb-main: missing` is Finding 5's new, correct report.)

All three layouts parse their period:

```
meezan.csv.v1  summary period=2025-07-01..2026-06-30  date_range=pass
mcb.csv.v1     summary period=2025-07-01..2026-06-30  date_range=pass
nayapay.csv.v1 summary period=2025-07-01..2026-06-30  date_range=pass
```

The signal still fires when data really is missing — a Jul–Dec statement:

```
account_status: incomplete
warn gap  actual = "2026-01-01..2026-06-30"
```

New tests: clean full-year statement is `complete` with `date_range` pass, `gap` pass
and no warning on that account; a genuinely missing period still warns with the exact
window; every shipped profile defines both period patterns.

---

## IMPORTANT 4 — spec §6.2 continuity chain not implemented

Commit `9479821`.

### Before

Only date gaps were checked. Statement A (1 Jul – 31 Dec, closing **1,500.00**) followed
by B (1 Jan – 30 Jun, opening **9,000.00**) — contiguous dates, each individually
reconciling:

```
status: complete   opening: 1,000.00   closing: 9,100.00
check kinds: date_range, gap, opening_closing, printed_totals,
             running_balance, unresolved_rows
fails: []
```

A 7,500.00 discontinuity, nothing firing, and a 30 June closing balance the owner would
type straight onto the wealth statement.

### Fix

`_check_balance_continuity` (kind `continuity`, scope `account`), run from
`merge_account`:

- Statements ordered by `(period_start, period_end)`, never by file order.
- The check applies only to a pair whose periods **meet with no missing day**
  (`later.period_start == earlier.period_end + 1 day`). Where a gap separates them the
  balance legitimately moved in between and the `gap` warning is the right report;
  where they overlap, the `overlap` check is.
- A mismatch is a `fail`, consistent with the module's fail-closed stance.
- A contiguous pair where one statement prints no balance at the seam `warn`s that the
  chain was not verified.

### After

```
status: failed   closing: None          (was complete / 910000 paisa)
fail continuity: 1,500.00 -> 9,000.00
  jul-dec.csv -> jan-jun.csv at 2026-01-01: one statement closes at
  1,500.00 and the next opens at 9,000.00, a difference of 7,500.00;
  a statement is missing, truncated or belongs to another account
```

The account contributes nothing until the cause is fixed.

New tests in `tests/test_reconcile_account.py`: the break fails with the exact figures
and the account contributes nothing; an unbroken chain passes; the verdict is unchanged
when the same two statements are handed over newest-first (proving period ordering — it
would produce no check at all under file ordering); a gap does **not** also fail
continuity (it would turn every incomplete account into a failed one); overlapping
statements do not either. `tests/test_reconcile_account.py`: 21 → 26 tests.

---

## IMPORTANT 5 — expected accounts vanished silently

Commit `ac1aa42`.

### Before

`ledgers` is built only from accounts that produced a parse. With `meezan-main` and
`mcb-main` both `statement_expected = true` and only the Meezan statement loaded:

```
ledgers: ['meezan-main']
account_status: {'meezan-main': 'complete'}
any check mentioning mcb: False
```

`mcb-main` was simply absent — no row, no status, no check — which understates declared
wealth in exactly the way nobody notices.

### Fix

- `RunResult.missing_accounts: tuple[str, ...]`.
- Each such account gets `account_status = "missing"` and a `warn`
  `statement_missing` check naming the account id and institution, with the remedy.
- Not reported: `statement_expected = false` accounts (spec §4.2 — Payoneer, Wise,
  JazzCash exist only so transfers to them are recognised); an account whose
  `closed_on` predates the tax year; one whose `opened_on` follows it.
- `app/state.py` `STATUS_ICON` gained `"missing": "⬜"` (matching the Setup page's
  existing ⬜ for a missing folder). `"missing"` is deliberately **not** a
  `reconcile.AccountStatus`: there is no ledger to reconcile.
- `app/pages/3_Checks.py` renders a row per missing account and an explicit warning
  listing them.

### After

```
missing_accounts: ('mcb-main',)
account_status: {'meezan-main': 'complete', 'mcb-main': 'missing'}
warn statement_missing: mcb-main (MCB Bank Limited) is marked
  statement_expected in accounts.toml but no statement was loaded for it.
  Its balances and transactions are missing from this run entirely - add
  the file, or set statement_expected = false if none is due.
```

New tests: the expected account is reported; an unassigned file still leaves its
accounts named; `statement_expected = false` is not reported; an account closed before
or opened after the tax year is not reported; and `test_app_state.py` pins that every
status the pipeline can produce has an icon (the Checks page indexes `STATUS_ICON`
directly, so a gap there is a `KeyError` in the owner's face).

**Two existing expectations updated, deliberately:**
`test_an_invalid_account_override_is_reported_not_silently_dropped` asserted
`account_status == {}`; both accounts are now correctly reported `missing`.
`test_a_clean_full_year_statement_is_complete_with_no_false_gap` narrowed its "no
warnings" assertion to that account's own checks.

---

## IMPORTANT 6 — `formats.decimals` corrupted amounts

Commit `007991c`.

### Before

`decimals` padded the fraction while `PAISA_PER_RUPEE` stayed 100 and the grammar capped
the fraction at two digits, so it never rescaled — it corrupted:

```
parse_paisa("1.50", decimals=3) -> 600   = Rs 6.00   (should be Rs 1.50)
parse_paisa("1.5",  decimals=1) -> 105   = Rs 1.05   (should be Rs 1.50)
Formats(decimals=3) accepted?: 3
Formats(decimals=0) accepted?: 0
```

A profile author using the knob documented in spec §5.4 got a silently wrong figure on
every row.

### Fix

- `Formats.decimals` validator refuses any value but 2, at load time, with a message
  naming the concrete corruption.
- `parse_paisa` raises `UnsupportedDecimals` before touching the text.
- `UnsupportedDecimals` derives from `Exception`, **not** `ValueError` and not
  `AmountError`: `engines/tabular.py` turns both of those into an unresolved row, which
  would blame the statement for what is a configuration or programming bug.

### After

```
parse_paisa('1.50', decimals=0) -> UnsupportedDecimals
parse_paisa('1.50', decimals=1) -> UnsupportedDecimals
parse_paisa('1.50', decimals=2) -> 150   = Rs 1.50
parse_paisa('1.50', decimals=3) -> UnsupportedDecimals
parse_paisa('1.50', decimals=4) -> UnsupportedDecimals
Profile.model_validate(... decimals=3) -> ValidationError ("...paisa...")
```

New tests in `tests/test_money.py` (rejection for 0/1/3/4, the exception is not an
`AmountError` or `ValueError`, 2 still the working default) and `tests/test_schemas.py`
(the profile is refused at load time; 2 and the omitted default are accepted).

---

## IMPORTANT 7 — the pre-commit hook missed the printed forms

Commit `a87b922`.

### Before

Against a throwaway repo with `core.hooksPath` pointed at the real `.githooks`:

```
COMMITTED CLEANLY: spaced_iban.txt   (IBAN grouped in fours)     <-- LEAK
COMMITTED CLEANLY: spaced_cnic.txt   (CNIC with spaces)          <-- LEAK
COMMITTED CLEANLY: sameline.txt      (real IBAN beside PK00TEST) <-- LEAK
```

Grouped-in-fours is how statements actually print an IBAN —
`resolve_account`'s own docstring says so — and how a copy-paste carries it. The
line-based `grep -v PK00TEST` dropped whole lines, so a real IBAN sharing a line with a
fixture one went through untouched.

### Fix

- Blanks and hyphens are removed (`tr -d '[:blank:]-'`) before the IBAN match, so any
  grouping is caught.
- The CNIC pattern accepts either separator: `[0-9]{5}[- ][0-9]{7}[- ][0-9]`. The
  hyphen is **first** inside each bracket so it is a literal, not a range — `[ -]`
  would have been the range `!"#$%&'()*+,-`.
- The exemption is applied per **match** (`grep -oE … | grep -v '^PK00TEST'` captured
  into a variable), not per line.
- Matches are **counted, never echoed**. The old hook printed the matching line, putting
  the very value it was blocking on the terminal — contrary to spec §5.5's stdout rule.
- `grep -a` so a binary blob is scanned as text rather than skipped.
- Pipelines are captured into variables rather than ending in `grep -q`: under
  `set -o pipefail`, `grep -q` exiting early SIGPIPEs the upstream `grep -o` (exit 141),
  which would have made the pipeline look like "no match" in exactly the case where
  there *is* one.
- No real-shaped literal appears in the hook (its first draft failed its own scan) — the
  comments use fbr-dump shape notation instead.

### After

```
BLOCKED : IBAN grouped in fours          (IBAN-shaped, 1 occurrence)
BLOCKED : IBAN hyphen-separated          (IBAN-shaped, 1 occurrence)
BLOCKED : plain IBAN                     (IBAN-shaped, 1 occurrence)
BLOCKED : CNIC with spaces               (CNIC-shaped, 1 occurrence)
BLOCKED : CNIC with hyphens              (CNIC-shaped, 1 occurrence)
BLOCKED : real IBAN sharing a PK00TEST line
ALLOWED : PK00TEST0000000000000000
ALLOWED : PK00 TEST 0000 0000 0000 0000
ALLOWED : ordinary text with amounts and dates
```

A scan of every tracked file found no false positive.

New tests in `tests/test_guardrails.py`, all end to end through the real hook: the three
printed grouped forms; a real IBAN sharing a line with a test one; the PK00TEST prefix
still allowed in its printed grouping; the blocked value never echoed; ordinary content
(amounts, dates, reference numbers, `s.151(1)(b)`) still commits cleanly.
`tests/test_guardrails.py`: 6 → 19 tests.

---

## Minors

### Upload vs disk (commit `05286c4`)

`app/pages/2_Load.py` offered Upload while `pipeline.read_statement_dir`'s docstring said
files are read from disk "rather than an upload". Spec §8.1 explicitly keeps upload as
the alternative, so **it stays** and the disagreement was resolved the other way: the
page now states the cost where the owner chooses it (Streamlit writes any upload over
1 MB to a temporary file in the OS temp directory, outside the private folder), with a
`help=` on the radio and a per-branch caption; the docstring says "the Load page's
default" and records that upload remains available with a stated cost.

### `.gitignore` (commit `6081284`)

`!tests/fixtures/**` re-included `tests/fixtures/__pycache__` — confirmed with
`git check-ignore -v .gitignore:14:!tests/fixtures/** …/synth.cpython-314.pyc`, and
visible as an untracked directory in `git status` — and would have re-included a real
`.csv` dropped there. Nothing writes to that directory (`synth.py` builds statements in
memory), so the negation was removed rather than narrowed, with a note to restore a
narrow one if a generator ever does write a file. Pinned with `git check-ignore` so the
rule is tested as git applies it, including that `tests/fixtures/synth.py` stays tracked.

After: `tests/fixtures/sample.csv` → ignored by `.gitignore:10:*.csv`;
`tests/fixtures/__pycache__/*.pyc` → ignored by `.gitignore:2:__pycache__/`;
`git status` clean.

### Dead code (commit `05286c4`)

- **`reconcile.worst_status` removed.** No production caller, and **no test needs it**:
  the only tests touching it were `test_worst_status_prefers_fail_over_warn` (which
  tested nothing but the helper itself) and one convenience assertion in
  `test_a_clean_statement_passes_every_check`. The former is replaced by
  `test_a_broken_statement_is_not_usable`, asserting `statement_usable` — the function
  the pipeline actually gates on — plus the `running_balance` fail; the latter now
  asserts the check statuses directly.
- **`sniff_container`'s `filename` parameter removed.** It was accepted and ignored,
  inviting the belief that the extension had a say. Callers in `pipeline.py` and
  `tools/dump_layout.py` updated. `test_sniffing_ignores_a_misleading_extension` became
  `test_sniffing_cannot_be_influenced_by_a_filename`, asserting the signature is
  `["data"]` — the guarantee moves out of a comment.
- **`app/pages/1_Setup.py`'s unused `parse_row` import removed** (`usable_profiles`
  passes it to `run_selftest` internally).

### `assign_occurrences` tie-break test (commit `f4dd0e3`)

`test_identical_rows_get_distinct_ids` looks like it covers this but does not: its
fixture has a running balance, so the two rows differ in `balance_after` and are
separated by that — the tie-break never runs. Its own comment said the no-balance case
still needed covering; it never was.

Two new tests use a wallet-shaped layout with no balance column, where two identical
same-day rows tie on account, date, amount, balance (`None`) and description, so only
`occurrence` can separate them. They assert the ids are exactly the ones occurrence 1
and 2 produce, and that re-loading the same file reproduces them (spec §4.1: a saved
review decision must still attach to its row next week).

Confirmed load-bearing — with `assign_occurrences` stubbed to a constant:

```
with tie-break   : ['5c56bae3a5ee7bcb', 'c1ee6ae185107a2f'] -> 2 distinct
without tie-break: ['5c56bae3a5ee7bcb']                     -> 1 distinct
```

Two real transactions collapse into one id: income understated, and one review decision
attached to both rows.

---

## Not changed, and why

**Out of scope by instruction** (untouched, confirmed by reading the code at HEAD):
`assign_occurrences` running per file rather than per merged ledger (spec §4.1);
parenthesised negatives such as `(4,500.00)` in the summary patterns; `reconcile.py`
choosing printed opening/closing by file order rather than period order;
`ingest._matches` using substring matching while `tabular._find_header` uses exact cell
equality.

The new occurrence tests are single-file, so they assert nothing that a later
per-merged-ledger fix would have to undo.

**Chosen, and worth the owner knowing:**

1. **No `[summary] account_id` pattern was added to the shipped profiles.** None of the
   three defines one, so `summary.account_identifier` is `None` in production today and
   the new printed-identifier branch is, for these layouts, not yet reached — resolution
   falls through to body text. In the Finding 1 reproduction the result is now `None`
   (unassigned, reported, recoverable on the Load page) rather than the wrong account.
   Writing such a pattern means guessing a label no `fbr-dump` has confirmed, which is
   exactly what the `# VERIFY` discipline exists to prevent. **Worth doing in the
   real-statement pass**, alongside the parenthesised-negatives work: once a real dump
   shows how each bank labels the account number, adding `account_id` makes the printed
   identifier authoritative and turns those `None`s back into correct attributions.

2. **All `period_from`/`period_to` patterns are `# VERIFY`.** They match what the
   synthetic writers print. The MCB and NayaPay writers had no period line at all, so
   one was invented in the same additive style already used for their equally
   unconfirmed Total Credit / Total Debit rows. A real export may label or format the
   period differently, in which case `date_range` reverts to its (now meaningful) "not
   printed" warn rather than misreading anything.

3. **`"missing"` is not a `reconcile.AccountStatus`.** It lives only in
   `RunResult.account_status` and `STATUS_ICON`, because there is no ledger to
   reconcile. A test pins that every status the pipeline emits has an icon.

4. **Tokenizer tradeoff** (Finding 2): a non-ASCII character glued between two letters
   is now shaped rather than preserved. Documented in the source; masking is the
   fail-closed direction and standalone separators are unaffected.

---

## Verification

```
$ uv run python -V
Python 3.14.6
$ uv run pytest
313 passed in 2.22s
$ git status --short
(clean)
```

Baseline at `f8ddf59` was 250 passed. Per-file counts at HEAD:

| file | tests |
|---|---|
| test_app_state | 11 |
| test_dump_layout | 47 |
| test_guardrails | 19 |
| test_ingest | 22 |
| test_loader | 11 |
| test_model | 24 |
| test_money | 42 |
| test_paths | 8 |
| test_pipeline | 20 |
| test_profiles_ship | 13 |
| test_reconcile_account | 26 |
| test_reconcile_statement | 15 |
| test_schemas | 23 |
| test_synth | 12 |
| test_tabular | 20 |

Commits (oldest first), all made with the repo's own pre-commit hook active
(`core.hooksPath = .githooks`). Nothing was pushed; nothing was rebased, reset, amended
or stashed.

| SHA | Finding |
|---|---|
| `c85e02e` | CRITICAL 1 — printed account identifier |
| `a7cad98` | CRITICAL 2 — Unicode masking |
| `609d2ea` | IMPORTANT 3 — `date_range` / shipped profiles in tests |
| `9479821` | IMPORTANT 4 — §6.2 continuity chain |
| `ac1aa42` | IMPORTANT 5 — missing expected accounts |
| `007991c` | IMPORTANT 6 — `formats.decimals` |
| `a87b922` | IMPORTANT 7 — pre-commit printed forms |
| `6081284` | MINOR — `.gitignore` |
| `f4dd0e3` | MINOR — occurrence tie-break test |
| `05286c4` | MINOR — upload tradeoff + dead code |
