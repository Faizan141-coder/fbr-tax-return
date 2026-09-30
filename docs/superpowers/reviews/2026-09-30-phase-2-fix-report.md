# Phase 2 — fix report for the two reviews

Repo `/Users/faizanhasnaat/Documents/Github/fbr-tax-return`, branch `main`,
starting at `68bd5b8` (372 tests passing). Python: CPython 3.14 via `uv run`
throughout; the system Python 3.9.6 was never used.

Every finding was reproduced by execution before the fix and re-verified after,
with the real numbers below. Final state: **405 tests passing**, 5 commits, not
pushed, no PR.

| Finding | Commit |
| --- | --- |
| CRITICAL 1, IMPORTANT 2, IMPORTANT 3 | `de48ea4` |
| IMPORTANT 4 | `fb29986` |
| IMPORTANT 5 | `7e99816` |
| IMPORTANT 6 | `2d1b031` |
| MINOR 7 | `999f7a6` |

---

## CRITICAL 1 — a dateless row carrying an amount was silently swallowed

`src/fbr/engines/pdf.py`, the continuation branch.

### Reproduction before

A two-row Meezan-style page: a full row, then a same-day second row whose date
the bank did not reprint, carrying credit `700.00` and balance `2,200.00`.
No `CLOSING BALANCE` printed, so the opening/closing check cannot run.

```
transactions: [('2025-07-02', 50000, 150000, 'Money Received Second Same Day Credit')]
unresolved:   ()
  running_balance:  pass - chain verified from the printed opening balance
  opening_closing:  warn - statement does not print both balances; check skipped
  unresolved_rows:  pass - every row parsed
  date_range:       warn - statement does not print its period; dates not bounded
statement_usable: True
```

Rs 700.00 (70 000 paisa) and its balance Rs 2,200.00 (220 000 paisa) are gone.
`running_balance` **passed** — the balance vanished along with the row, so the
chain still verified over the single row that survived. `unresolved` empty.
`statement_usable() == True`. The row's description was absorbed into the row
above (`'Money Received Second Same Day Credit'`), which is the only visible
trace. Money gone from a tax return with every check green.

### Fix

On the continuation path, before absorbing anything, the line's cells are
inspected. If any of `debit`, `credit`, `amount` or `balance` is non-empty (by
the engine's own `_EMPTY` set), or the `ambiguous` list the loop just computed
is non-empty, an `UnresolvedRow` is emitted naming the reason and the figures,
and `open_row` is cleared. A genuine continuation — description text only —
joins its row exactly as before, including across a page break.

### Verification after

Same PDF, same profile:

```
transactions: [('2025-07-02', 50000, 150000, 'Money Received')]
unresolved:   (UnresolvedRow(locator='page:1,y:126',
   raw='Second Same Day Credit 700.00 2,200.00',
   reason="row has no date in the 'Booking Date' column but carries
           credit '700.00', balance '2,200.00'; it cannot be a description
           continuation, and its figures must not be silently dropped"),)
  running_balance:  pass
  opening_closing:  warn
  unresolved_rows:  fail - 1 row(s) could not be parsed; first: row has no date...
  date_range:       warn
statement_usable: False
```

The refused money is named in the reason, so the owner can find the row on the
statement. The statement is unusable, which is the correct outcome.

### Tests added (`tests/test_pdf_engine.py`)

A `_meezan_page()` helper draws a page from explicit line specs at the same
x-positions the fixtures use (Credit right edge 400, Debit 470, Balance 555),
so a dateless line is expressed by simply omitting the date.

* `test_a_dateless_line_carrying_an_amount_is_unresolved_not_swallowed` —
  asserts one transaction of 50 000 paisa, exactly one unresolved row, that the
  reason names `700.00` and `2,200.00`, and that `statement_usable()` is False
  with `unresolved_rows` failing.
* `test_a_dateless_line_of_description_text_still_joins_its_row` — asserts
  `unresolved == ()`, one transaction, description exactly
  `'IBFT In from THUNES STAN 123456 REF ABCDEF'`, amount 50 000, balance
  150 000.
* `test_a_dateless_line_with_an_ambiguous_token_is_unresolved` — a token drawn
  at x = 435, midway between Credit (400) and Debit (470): the reason names both
  "no date" and "outside every column band", and the statement is unusable.

---

## IMPORTANT 2 — the shipped test did not protect the continuation fix

`tests/test_pdf_engine.py::test_a_wrapped_description_is_joined_onto_its_row`.

### Reproduction before

A copy of `src/fbr/engines/pdf.py` was written to the scratchpad with
`open_row = None` re-inserted at the top of the page loop (the original bug),
loaded via `importlib.util.spec_from_file_location`, and rebound into the test
module. **The repo's own module was never edited.**

Under the mutant the four descriptions came out as:

```
'Withholding Tax Debit CONTINUATION STAN 100000'
'POS Transaction STAN 222333 CONTINUATION STAN 100001'
'IBFT In from THUNES STAN 123456 CONTINUATION STAN 100002'
'ATM Cash Withdrawal STAN 654321'          <-- truncated, continuation lost
```

The shipped assertions (`any("CONTINUATION" in …)` plus the "must not be its own
transaction" count) **all passed**. The last row's continuation lands on page 2,
and `any(...)` was satisfied by the first three rows. That is how the original
bug hid.

### Fix

The test now asserts the exact description of every row as a list, so the row
whose continuation crosses the page break is pinned:

```
"ATM Cash Withdrawal STAN 654321 CONTINUATION STAN 100003"
```

plus `len(res.transactions) == len(stmt.txns)` and that no description starts
with `CONTINUATION`.

### Verification after

The same importlib harness, now calling the **real test function** against both
engines:

```
repo engine   (must pass): PASSED
mutant engine (must fail): FAILED -> AssertionError at the exact-description assert
VERDICT: the strengthened test bites = True
(repo module unchanged: True)
```

---

## IMPORTANT 3 — a header that is never found gave a silent empty parse

`src/fbr/engines/pdf.py`.

### Reproduction before

A synthetic SadaPay PDF parsed with the Meezan profile:

```
PDF engine, wrong profile:
  transactions: 0
  unresolved:   0
  statement_usable: True        (no exception raised)
```

The tabular engine in the same situation:

```
tabular ParseError: header row not found for profile 'meezan.pdf.v1';
                    expected all of ['Booking Date', 'Credit', 'Debit']
```

Two engines, opposite behaviour; the PDF one failed open.

### Fix

`_rows_from_pdf` counts pages seen and, after the page loop, raises `ParseError`
when `bands is None` **and** at least one page had text. Guarding on
`pages_seen > empty_pages` preserves the more specific `PdfNotTextual` for a PDF
with no text on any page, which is checked by `parse_pdf` afterwards. A cover
page before the first header, and continuation pages that repeat no header, are
untouched: the raise fires only when not one page matched.

### Verification after

```
ParseError: header row not found for profile 'meezan.pdf.v1' on any of the
            1 page(s); expected all of ['Booking Date', 'Credit', 'Debit']
```

### Tests added

* `test_a_pdf_whose_header_is_never_found_is_refused` — asserts `ParseError`,
  that the message says "header row not found", that it names **every** label in
  `detect.header_contains`, and that it is not a `PdfNotTextual` or
  `PdfPasswordError`.
* `test_a_cover_page_before_the_first_header_is_still_parsed` — a header-less
  first page followed by a page with a header and one row parses cleanly
  (`unresolved == ()`, amount 50 000), proving the allowance survived.

---

## IMPORTANT 4 — the home page contradicted the shipped feature

`app/main.py:35`.

### Reproduction before

```python
st.info("Phase 0–1: CSV/XLSX statements only. PDF support arrives in phase 2.")
```

### Fix

Replaced with text describing what works. The claims were checked against the
code before writing them: `app/pages/2_Load.py:53-68` accepts
`type=["csv", "xlsx", "pdf"]` and prompts for a PDF password, and
`fbr.ingest.sniff_container` returns `pdf` on the `%PDF` magic. The password
wording matches the promise the Load page itself makes.

```python
st.info(
    "Statements can be CSV, XLSX or PDF. A password-protected PDF — as an "
    "emailed bank statement usually is — asks for its password on the **Load** "
    "page; that password is held in memory for the run only, never written to "
    "disk, logged, or placed on a command line. A scanned PDF has no text layer "
    "and cannot be read."
)
```

### Verification after

`grep` across `app`, `src`, `tests`, `tools` and `README.md` finds no remaining
"CSV/XLSX only" or "arrives in phase 2" claim. The only surviving mention of
phase 2 is an explanatory comment in `tests/test_dump_layout.py:264`, which is
accurate.

---

## IMPORTANT 5 — the `# VERIFY` test omitted the profile that most needs it

`tests/test_profiles_ship.py`.

### Reproduction before

The loop covered `("meezan.csv.v1", "mcb.csv.v1", "nayapay.csv.v1")` only.
Marker counts per shipped profile:

```
mcb.csv.v1.toml              16
mcb.xlsx.v1.toml              0
meezan.csv.v1.toml           17
meezan.xlsx.v1.toml           0
nayapay.csv.v1.toml          14
sadapay.pdf.v1.toml          11      <-- none asserted
```

`sadapay.pdf.v1` is the profile written entirely against
`tests/fixtures/synth_pdf.py`, so its markers are the only record of what still
needs checking against a real export.

### Fix

Three changes:

1. `sadapay.pdf.v1` added to the loop (`SYNTHETIC_PROFILES`).
2. `test_a_synthetic_profile_marks_every_decisive_setting` — "VERIFY appears
   somewhere in the file" is too weak; a marker on a comment line satisfies it
   while the amount column goes unflagged. Each setting that decides a figure
   (`header_contains`, every column role, `dates`, `debit_tokens`,
   `credit_tokens`, every summary pattern) must be marked on its own line, and
   on **every** line where the key appears.
3. `test_a_profile_with_no_verify_markers_cites_the_real_dump_it_came_from` —
   the two XLSX profiles carry no markers because both say they were written
   from a real `fbr-dump` (`5493f541ca92`, `e80f3960d62c`). That exemption is
   now pinned to the citation, so a future unflagged profile cannot inherit it
   by silence. **The two XLSX profiles were therefore not added to the loop:
   they carry no markers, and the reason is now itself a test.**

Two subtleties found while verifying the new test actually bites:

* A first attempt matched keys by prefix, so `debit_tokens` satisfied `debit`.
  Fixed to exact key names.
* A first attempt OR-ed the marker across repeated keys, and `amount` appears
  twice in `sadapay.pdf.v1` — once as the column, once under `[columns.align]`.
  The align marker rescued an unmarked amount column. Switched to requiring
  every occurrence to be marked.

### Verification after

Baseline: 18 tests in the file pass. Bite checks, each restored afterwards:

* Stripping `# VERIFY` from sadapay's `amount = "Debit/Credit"` line:
  `AssertionError: sadapay.pdf.v1 sets ['amount'] without a # VERIFY marker`.
* Removing `mcb.xlsx.v1`'s `fbr-dump` citation:
  `test_a_profile_with_no_verify_markers_cites_the_real_dump_it_came_from`
  fails on `assert 'fbr-dump' in …`.

---

## IMPORTANT 6 — `run_selftest` never checked what a summary pattern captures

`src/fbr/config/loader.py`, `src/fbr/config/schema_profile.py`, `profiles/*.toml`.

### Reproduction before

Baseline — all six profiles pass, exercising 30 summary patterns between them.
Then each profile's `opening`/`closing` patterns (or SadaPay's
`total_debit`/`total_credit`) were **swapped**, so each captures the other's
figure. Both still match, so the dead-pattern check is satisfied:

```
mcb.csv.v1      swapped opening<->closing: ok=True  opening captures '25,935.59', correct is '5,000.00'
mcb.xlsx.v1     swapped opening<->closing: ok=True  opening captures '25,935.59', correct is '5,000.00'
meezan.csv.v1   swapped opening<->closing: ok=True  opening captures '25,935.59', correct is '5,000.00'
meezan.xlsx.v1  swapped opening<->closing: ok=True  opening captures '25,935.59', correct is '5,000.00'
nayapay.csv.v1  swapped opening<->closing: ok=True  opening captures '25,935.59', correct is '5,000.00'
sadapay.pdf.v1  swapped total_debit<->total_credit: ok=True  total_debit captures '1,000.00', correct is '2,500.00'
```

An opening balance of Rs 25,935.59 where Rs 5,000.00 was meant — a
Rs 20,935.59 error — passed for every shipped profile. The mechanism caught
"pattern never matches" (the doubled-backslash bug it was built for) but not
"pattern captures the wrong figure", and the latter is what puts a wrong number
on a return.

### Fix

`SelfTest` gains an optional `summary_expect: dict[str, int | str | date]`:
role name → the value its pattern must capture out of the profile's own
`summary_sample`, as integer paisa for a money role and an ISO date string for a
period role. `run_selftest` parses each capture the way the engine does and
compares exactly. Absent, nothing changes, so a profile without it still loads.

Guards, each with a test:

* The field is validated `mode="before"`. Validated after coercion, pydantic had
  already turned the float `5000.0` into the int `5000` — an accepted
  expectation of Rs 50.00 where Rs 5,000.00 was meant — and no `isinstance`
  check could still see it had been a float. Money must be integer paisa; a
  float, a string (`"5,000.00"` or `"500000"`) or a date is refused at load.
* A period expectation must be an ISO date string; a bare TOML date
  (`period_from = 2025-07-01`, which `tomllib` gives as a `datetime.date`) is
  accepted and normalised rather than failing on a spelling that reads well.
* A `Profile`-level validator refuses an expectation naming a pattern the
  profile does not declare, or a role that is not a summary pattern at all: it
  would silently never run. It also refuses `summary_expect` without a
  `summary_sample`.
* `run_selftest` cannot import the engine (the engine is injected as
  `parse_row`), so `_capture_as_the_engine_does` re-implements the two
  conversions. `test_the_loader_parses_a_capture_exactly_as_the_engine_does`
  pins it against `fbr.engines.tabular._read_summary` across all 30 shipped
  patterns, so the two cannot drift.

### Values populated, checked against each profile's own sample

All six were populated from `summary_sample` after printing what each pattern
actually captures, and each value was checked against the sample line it should
read:

```
mcb.csv.v1      opening 500000  closing 2593559  total_credit 4351393
                total_debit 2257834  period_from 2025-07-01  period_to 2025-08-23
meezan.csv.v1   (identical figures; same sample values)
nayapay.csv.v1  (identical; total_credit is "Total Income", total_debit "Total Spent")
mcb.xlsx.v1     opening 500000  closing 2593559  period_from 2025-07-01  period_to 2026-06-30
meezan.xlsx.v1  opening 500000  closing 2593559  period_from 2025-07-01  period_to 2026-06-30
sadapay.pdf.v1  total_credit 100000  total_debit 250000
                period_from 2025-07-01  period_to 2026-06-30
```

i.e. Rs 5,000.00 → 500 000 paisa, Rs 25,935.59 → 2 593 559, Rs 43,513.93 →
4 351 393, Rs 22,578.34 → 2 257 834, Rs 1,000.00 → 100 000, Rs 2,500.00 →
250 000. All 30 declared patterns are pinned.

### Verification after

The same swap, re-run:

```
mcb.csv.v1      ok=False    meezan.csv.v1   ok=False    nayapay.csv.v1  ok=False
mcb.xlsx.v1     ok=False    meezan.xlsx.v1  ok=False    sadapay.pdf.v1  ok=False
```

The failure message names the role, what it wrongly read, and what it must read:

> `summary pattern opening captured '25,935.59' -> 2593559 from the profile's own
> summary_sample, but summary_expect says 500000; the pattern matches, so nothing
> else would have noticed - it is reading the wrong figure`

And unswapped, every profile reports e.g.
`2 selftest case(s) and 6 summary pattern(s) and 6 expected capture(s) pass`.
`src/fbr/ingest.py:64` already passes `summary_text`, so the app's Setup page
gets this for free.

### One consequential side effect

`summary_expect`'s keys (`opening`, `closing`, …) collided with IMPORTANT 5's
new per-setting marker scan, failing four tests. The scan is now section-aware
and skips `[selftest]` and its sub-tables: they are the profile's own sample
data, self-consistent by construction, and a real dump has nothing to confirm
about them. Only settings that describe the **bank** need a marker. The marker
test was re-verified to still bite after that change.

---

## MINOR 7 — the dump masked a column label it exists to reveal

`tools/dump_layout.py`.

### Reproduction before

```
'Debit/Credit'   -> 'Xxxxx/Xxxxxx'
'Date/Time'      -> 'Xxxx/Xxxx'
DEBITCREDIT in allowlist: False | DEBIT: True | CREDIT: True
```

`Debit/Credit` is both `sadapay.pdf.v1`'s `detect.header_contains` entry and its
amount column. `/` is excluded from `_BREAKERS`, so it does not end a token, and
`_STRIP` folds the whole thing to `DEBITCREDIT`, which is not on the allowlist
though `DEBIT` and `CREDIT` each are. The dump hid the one label a profile
author must read off it.

### Fix

The more general of the two options: a new `_is_allowlisted()` keeps a token
verbatim when the whole token is allowlisted **or every `/`- or `-`-separated
part is**. `shape()` calls it in place of the one-line lookup. The allowlist
file was not touched.

Fail-closed in both edge cases: an empty part proves nothing about what follows,
and a numeric part is never allowlisted.

### Verification after, with the shipped allowlist

```
'Debit/Credit'      -> 'Debit/Credit'        KEPT
'Date/Time'         -> 'Date/Time'           KEPT
'TOTAL-CREDIT'      -> 'TOTAL-CREDIT'        KEPT
'Payoneer/AHMED'    -> 'Xxxxxxxx/XXXXX'      masked
'AHMED/Payoneer'    -> 'XXXXX/Xxxxxxxx'      masked
'ABDUL-REHMAN'      -> 'XXXXX-XXXXXX'        masked
'1234-5678-9012'    -> '9999-9999-9999'      masked
'PK00TEST-0000'     -> 'XX99XXXX-9999'       masked
```

Through `mask_text`, a header line survives intact:
`Date  Description  Debit/Credit` → unchanged; while
`Payoneer/AHMED RAZA  1,234.00` → `Xxxxxxxx/XXXXX XXXX  9,999.99`.

### Tests added (`tests/test_dump_layout.py`)

Both directions, as asked. `test_a_compound_label_of_allowlisted_parts_survives`
(5 cases), `test_the_sadapay_detect_label_survives_a_dump`,
`test_a_name_glued_to_an_allowlisted_word_still_masks` (4 cases, each asserting
the name does not appear and the separator does),
`test_a_compound_of_digits_is_still_shaped`, and
`test_one_unlisted_part_is_enough_to_mask_the_whole_token` (every part, not any).

Bite check: reverting `shape()` to the pre-fix one-line lookup fails 6 of the
new tests; the name-masking tests pass in both states, since masking was never
the broken half.

### Noted, not changed

`Dr/Cr` travels this path but still masks, because neither `DR` nor `CR` is on
the shipped allowlist — so the review's claim that the fix "covers `Dr/Cr`" is
true of the mechanism but not of the current allowlist contents. Adding them is
a decision about the privacy allowlist rather than a mechanism fix, so it was
left to the owner; the glued form a real statement prints already reaches the
dump as `9,999.99Xx`, which shows the suffix's shape and casing.

---

## Recorded as out of scope, unchanged

Per the brief, deliberately untouched:

* `Document.encrypted = bool(password)` marking an unencrypted file as encrypted.
* `rows.continuation` and `row_anchor: "amount"` accepted by the schema but
  never read — a later phase needs them.
* The password surviving in `st.session_state["run"].unassigned[*].password`;
  memory only, never disk or log.
* `dump-candidates/*.txt` carrying raw tokens; pre-existing and owner-only.
* `test_a_pdf_with_no_text_layer_is_refused` left loose. **Which exception
  actually fires:** `fbr.engines.tabular.ParseError`, message
  `cannot open this PDF: PdfminerException`, raised from `pdf._open`. Not
  `PdfNotTextual`. The minimal byte string in that test is malformed enough that
  pdfminer refuses to open it at all, so `_rows_from_pdf` is never reached and
  the `PdfNotTextual` path the test names is never exercised — it passes only on
  the `Exception` fallback in its `pytest.raises((PdfNotTextual, Exception))`.
  A genuine no-text-layer PDF (one that opens, with pages carrying no words)
  would reach `parse_pdf`'s `empty_pages == pages` check and raise
  `PdfNotTextual`; nothing currently covers that. The IMPORTANT 3 change does
  not affect this test — the failure happens before the header logic — and its
  `pages_seen > empty_pages` guard is what preserves `PdfNotTextual` for the
  real case.

## Decisions worth flagging to the owner

* **`Dr/Cr` in the masked dump** (above): add `DR` and `CR` to
  `tools/dump_allowlist.txt` if you want that label released verbatim.
* **`summary_expect` is populated from synthetic samples.** For the four
  synthetic profiles the expected figures come from invented `summary_sample`
  text, so they pin *internal consistency*, not correctness against a real
  export. When a real `fbr-dump` arrives, `summary_sample` and `summary_expect`
  must be updated together — the selftest will fail loudly if only one is.
  `test_every_shipped_profile_pins_every_summary_pattern_it_declares` enforces
  that a newly added pattern cannot ship unpinned.
* **No real statement data, no real IBANs.** Every fixture value is invented;
  fake IBANs use the `PK00TEST` prefix only. No password reached a message, a
  log or a command line.

## Test summary

```
before:  372 passed
after:   405 passed  (+33)
```

New test cases by file (counting parametrised cases, not `def`s):

| File | `def`s | cases |
| --- | --- | --- |
| `tests/test_pdf_engine.py` | 17 → 22 | +5 |
| `tests/test_profiles_ship.py` | 9 → 11 | +5 (one `def` parametrised over 4 profiles) |
| `tests/test_loader.py` | 11 → 22 | +11 |
| `tests/test_dump_layout.py` | 25 → 30 | +12 (two `def`s parametrised, 5 and 4 cases) |

5 + 5 + 11 + 12 = 33, and 372 + 33 = 405.
