# Whole-branch fix report — phase 2 (PDF engine + SadaPay)

Branch `main`. Findings reproduced at `344af41` (405 tests passing) and fixed in
seven commits, `4a158b1`..`81ae418` (423 tests passing). Every figure below came out
of an execution, not a reading.

Reproduction scripts lived in the session scratchpad and are not committed; the
behaviours they measured are now pinned by tests named under each finding.

**Headline answers to the two questions asked:**

- A SadaPay statement whose `[summary]` patterns are dead **is now refused.**
  `nothing_verified` fails, `statement_usable()` is `False`, the account ledger
  is `status="failed"` with `transactions=()` and `closing=None`.
- A SadaPay statement whose patterns **do** match **still passes.**
  `printed_totals` passes, `nothing_verified` is absent, the ledger is
  `status="complete"` with 8 transactions and a 30 June closing of
  Rs -44,698.23 — exactly `anchor 5,000.00 + net`.

---

## CRITICAL 1 — a statement reported "complete" when no arithmetic check ran

Commits `4a158b1`, `81ae418` (the latter only adapts the detail's opening clause
for the case where one of the three ran and failed rather than being absent).

### Before

`sadapay.pdf.v1` is the first profile with `balance.semantics = "none"` and no
`opening`/`closing` patterns. All three amount-verifying checks then report
*absence*, and nothing distinguished that from *verified*:

- `_check_running_balance` → `None` (no balance column, `reconcile.py:47`)
- `_check_opening_closing` → **warn** (neither balance printed, `reconcile.py:85`)
- `_check_printed_totals` → `None` (neither printed total matched, `reconcile.py:96-98`)

Measured on a SadaPay-shaped PDF whose four `# VERIFY` summary patterns did not
match the printed wording (`Debits in period` / `Credits in period` /
`Period covered … through …` instead of `Total debit` / `Total credit` /
`Statement Period … to …`):

```
statement checks : [('opening_closing','warn'), ('unresolved_rows','pass'), ('date_range','warn')]
statement_usable : True
summary          : DocumentSummary(opening=None, closing=None, total_credit=None,
                                   total_debit=None, period_start=None, period_end=None)
ledger closing   : Rs -44,698.23  (source "computed")
```

The closing figure was numerically right *by luck* — it is `anchor + net`, and no
row happened to be dropped in this variant. Nothing had checked it. Compounded
with finding 3 (a `Page 2 of 2` banner at the top of a continuation page) the
same green run lost money outright: **1 of 2 transactions parsed, net Rs 300.00
where the truth was Rs 100.00, 0 unresolved rows, every check pass or warn,
`usable == True`.**

### Fix

A new `nothing_verified` check in `reconcile.check_statement`. `check_statement`
now holds the three amount-verifying checks in a dict and passes it to
`_check_nothing_verified`, which **fails** when none of them reached `pass`.
`unresolved_rows` and `date_range` are deliberately not in that set: an empty
unresolved list and an in-range date prove nothing about the money.

The detail names each one's actual state, so the owner knows which pattern to
fix. Its opening clause adapts: "no arithmetic check could be run" when all three
are absent-or-warn, "not one arithmetic check confirmed this statement's amounts"
when one of them ran and failed — because in that case a check *did* run.

It returns `None`, not a passing check, once any of the three passes. Each of
them already reports its own pass; a second row saying the same thing is noise,
and returning `None` is why `test_all_five_checks_are_reported` (which pins the
exact set of kinds for a clean Meezan CSV) still holds unchanged.

### After

```
==== SadaPay, DEAD summary patterns
ledger status : failed | transactions: 0 | closing: None (unknown)
checks        : [('opening_closing','warn'), ('nothing_verified','fail'),
                 ('unresolved_rows','pass'), ('date_range','warn'), ('gap','warn')]
detail        : no arithmetic check could be run against this statement, so nothing
                confirms the figures parsed out of it (running_balance absent,
                opening_closing warn, printed_totals absent). A layout that prints
                no running balance can only be proved by its own printed totals or
                opening/closing balances: check that this profile's [summary]
                patterns match the statement's exact wording (run `fbr-dump` on it),
                or use a statement that prints them.

==== SadaPay, WORKING summary patterns
ledger status : complete | transactions: 8
closing       : Rs -44,698.23 (computed) | expected: Rs -44,698.23
checks        : [('opening_closing','warn'), ('printed_totals','pass'),
                 ('unresolved_rows','pass'), ('date_range','pass'), ('gap','pass')]

==== Meezan CSV with a running balance (unaffected)
outcome       : ok | ledger: complete
checks        : [('running_balance','pass'), ('opening_closing','pass'),
                 ('printed_totals','pass'), ('unresolved_rows','pass'),
                 ('date_range','pass'), ('gap','pass')]
closing       : Rs -44,698.23 (printed)
```

Consequence accepted, as instructed: SadaPay is unusable until its patterns match
a real statement. The same file becomes usable the moment `printed_totals`
passes — demonstrated by the two runs above, which differ only in the printed
wording of the totals.

### Tests

`tests/test_pdf_engine.py`
- `test_sadapay_with_working_totals_patterns_still_passes`
- `test_sadapay_with_dead_summary_patterns_is_refused` (asserts the fail is the
  *only* fail, and that the detail names all three states)
- `test_a_running_balance_statement_is_unaffected`

`tests/test_pdf_wiring.py` (account level, where the "complete" claim was made)
- `test_a_sadapay_statement_whose_totals_do_not_match_yields_no_figures`
- `test_a_sadapay_statement_whose_totals_do_match_still_produces_figures`

`tests/fixtures/synth_pdf.py` gained `write_sadapay_pdf(..., summary_wording=)`,
`"profile"` or `"unmatched"`, so the dead-pattern case is a fixture rather than a
one-off script.

---

## IMPORTANT 2 — PDF account resolution was dead, and the error named a control that does not exist

Commits `c596618`, `4b6ce21`.

### Before

`pipeline._free_text` pushed PDF bytes through `tabular.read_rows` — the CSV
decoder — so `resolve_account` searched the file's own binary preamble:

```
free_text length: 581 | contains PK00TEST: False
free_text sample: '%PDF-1.3\n%""... ReportLab Generated PDF document (opensource)\n1 0 obj\n...'
```

No profile declares an `account_id` summary pattern, so
`summary.account_identifier` is always `None` and resolution had nothing else to
work with. Measured, same statement bytes, no explicit `account_id`, registry
account holding exactly the printed IBAN:

```
PDF outcome: unassigned | no registry account matches this statement; choose one on the Load page
CSV outcome: ok        | parsed 8 transaction(s)
```

As shipped, SadaPay could not produce a figure without a manual override. Every
PDF wiring test passed `account_id="sadapay"` explicitly, which is exactly why
nothing caught it — and the fixture registry carried `iban=""`, so there was
nothing to resolve against even in principle.

### Fix, half one

`engines.pdf.extract_text(data, *, password=None, pages=2)` extracts real text
through `pdfplumber`, reusing `_open` so the password reaches the decoder and
nothing else — never a log, a message or a command line. `_free_text` routes
`container == "pdf"` there and takes the password `InputFile` already carries;
the CSV/XLSX path is untouched. Two pages, matching `ingest._head_text`: the
printed identifier sits in the statement header, and reading further would only
widen the window for a transaction description to name some other account.

The test-fixture registry now holds the IBAN the synthetic statements print, so
resolution has something real to work against.

### Fix, half two

The `unassigned` messages said "choose one on the Load page", and
`app/pages/2_Load.py` has no account picker.

**Resolved by building the picker — see the Picker section at the end of this
report.** The route taken here, in order:

1. First pass: changed the messages to point at `accounts.toml` only, and
   justified the picker's absence in the UI copy as a deliberate design choice.
   That was wrong — spec §4.2 requires the picker, so its absence was a gap.
2. `4b6ce21`: removed that invented rationale and said plainly that the picker
   is spec and unbuilt, rather than quietly reframing a gap as a decision.
3. On the coordinator's ruling: built it. The messages now name both routes, both
   of which exist.

With half one in place, the `accounts.toml` route is also genuinely actionable for
a PDF for the first time — the printed identifier is now actually searched.

### After

```
free_text has PK00TEST: True | chars: 604
outcome : ok | account: sadapay | parsed 8 transaction(s)

unassigned | no registry account matches this statement; add the IBAN, account
             number or wallet number it prints to that account in accounts.toml,
             then parse again
unassigned | 'nope' is not a known registry account id; it must match an
             account's `id` in accounts.toml
```

### Tests

`tests/test_pdf_wiring.py`
- `test_a_pdf_resolves_its_account_from_the_printed_iban` — **no** `account_id`
  override
- `test_an_encrypted_pdf_resolves_its_account_too` — the password reaches the
  extractor and never the message
- `test_an_unassignable_pdf_is_told_what_it_can_actually_do`
- `test_an_unknown_explicit_account_id_is_told_what_it_can_actually_do`

---

## IMPORTANT 3 — a `rows.footer` match dropped the rest of the page silently

Commit `658fc93`.

### Before

`pdf.py:220` `break`s out of the page on any `rows.footer` match. The shipped
`sadapay.pdf.v1` footer list holds `'(?i)^\s*page\s+\d+'`, which matches a
`Page 2 of 2` banner printed at the **top** of a continuation page. Measured on a
two-page statement (page 1: header + `+300.00`; page 2: the banner, then
`-200.00`):

```
transactions parsed: 1 of 2
unresolved         : 0
net parsed         : Rs 300.00  | truth: Rs 100.00
```

`tabular.py` never reads `profile.rows.footer` at all, so the same profile key
meant two different things depending on the container.

### Fix

**Chosen: emit an `UnresolvedRow` when a footer matches with body rows still
following on that page.** A footer still ends the page — but only when nothing
that could be a transaction follows it.

Why not "terminate only the final page": that still drops rows silently whenever
the pattern matches early on the last page, which is the same failure with a
smaller blast radius. Failing closed is the rule this engine already follows for
every other ambiguity.

To keep the ordinary case quiet, lines the profile itself classes as furniture
(`skip`, `summary`, or another `footer` match) do not count as "following", so a
real footer followed by a page number or a listed disclaimer behaves exactly as
before. Anything else following becomes an unresolved row naming the footer line
and telling the author to tighten the pattern — a loud, fixable false positive
rather than silent loss.

**Making the engines agree:** `rows.footer` is PDF-only, because it ends a *page*
and the tabular engine has no pages. `Rows` now carries a docstring saying which
keys each engine reads, what `footer` means, and the specific trap (a pattern
loose enough to match a banner printed above real rows). `Profile` gained
`_footer_is_a_pdf_only_rule`, which **refuses** `rows.footer` on a csv/xlsx
profile at load time and points the author at `rows.skip`/`rows.summary` — the
same fail-loudly-at-load-time principle as this file's `extra="forbid"`. No
shipped non-PDF profile declares it, so nothing broke.

### After

```
-- totals matching the profile: parsed 1/2, net Rs 300.00 (truth Rs 100.00), unresolved 1
   checks: [('opening_closing','warn'), ('printed_totals','fail'),
            ('nothing_verified','fail'), ('unresolved_rows','fail'),
            ('date_range','pass')]  | usable: False
-- totals worded differently:  parsed 1/2, net Rs 300.00 (truth Rs 100.00), unresolved 1
   checks: [('opening_closing','warn'), ('nothing_verified','fail'),
            ('unresolved_rows','fail'), ('date_range','warn')]  | usable: False
   reason: a rows.footer pattern matched this line, but 1 line(s) follow it on
           page 2; ending the page here would discard them without a trace, so
           the statement is refused instead - tighten the footer pattern so it
           matches only the real end of a page
```

The second line is the compound case from the brief. Both halves of it now
refuse: the footer loss is announced, and even with the totals dead the statement
cannot report usable.

### Tests

`tests/test_pdf_engine.py`
- `test_a_page_banner_above_real_rows_does_not_lose_them_silently`
- `test_a_real_footer_with_nothing_after_it_still_just_ends_the_page`

`tests/test_schemas.py`
- `test_rows_footer_is_refused_on_a_non_pdf_profile`

`tests/fixtures/synth_pdf.py` gained `write_sadapay_paged_pdf`, whose page 2
opens with the banner and repeats no header.

---

## MINOR — `value_date` built a band and threw the words away

Commit `00b46ce`.

**Before.** `pdf.py:318` hardcoded `"value_date": None` while `_roles_and_aligns`
still builds a `value_date` band for any profile naming the column — so the word
was assigned to that band, consumed into `cells`, and discarded with no field and
no unresolved row. Measured on a PDF printing `01 Jul 2025 | 02 Jul 2025 |
Top-up | +1,000.00`:

```
transactions: 1 unresolved: 0
  date: 2025-07-01 | value_date: None | desc: 'Top-up' | amount: 1,000.00
```

**Fix.** Parse it, which is what the tabular engine does. A blank or unreadable
value date stays `None` exactly as it does there: the value date moves no money,
and every check and every tax-year slice uses the booking date.

**After.** `value_date: 2025-07-02`.

**Tests.** `test_a_value_date_column_is_parsed_not_swallowed`,
`test_a_blank_or_unreadable_value_date_leaves_the_row_alone`.

---

## MINOR — the dump hid the glued `Dr` it claimed to preserve

Commit `68026f5`. **Chosen: make the claim true.**

**Before.** `shape()`'s docstring and the comment beside its ASCII branch both
said a glued `Dr` survives a dump. It did not — a letter following a digit does
not break a token, so the whole thing folded to `123400DR`, which is on no
allowlist:

```
'1,234.00Dr' -> '9,999.99Xx'
'1,234.00Cr' -> '9,999.99Xx'
```

Indistinguishable. `formats.sign = "suffix"` and
`debit_tokens`/`credit_tokens` are written from exactly that signal, and
`mcb.csv.v1` uses it. This is the same class of loss the last wave fixed for the
`Debit/Credit` header label, so it gets the same rule: split the token, shape the
part that could identify anything, release only the part the allowlist holds.

`_GLUED_SUFFIX` matches a number with a 1–3 letter suffix glued to its end; the
suffix is released **only** when it is itself allowlisted, and the number is
still shaped. `DR` and `CR` join the shipped allowlist, with a comment saying
why.

**After.**

```
'1,234.00Dr'               -> '9,999.99Dr'
'1,234.00Cr'               -> '9,999.99Cr'
'500Dr'                    -> '999Dr'
'1,234.00 Dr'              -> '9,999.99 Dr'
'1,234,567.89Dr' (hidden)  -> '9,999.99Dr'      # --hide-magnitude still hides it
'1,234.00AHM'              -> '9,999.99XXX'     # not vocabulary: masks whole
'1,234.00Xyz'              -> '9,999.99Xxx'
'0300123456Dr'             -> '9999999999Dr'    # every digit still masked
'PK00TEST0000000000000000' -> 'XX99XXXX9999999999999999'
```

**Tests.** `test_a_glued_direction_token_survives_a_dump`,
`test_only_an_allowlisted_suffix_is_released_and_never_the_number`.

---

## MINOR — `--rows` was ignored for PDFs

Commit `68026f5`. `dump_pdf` was called with `pages=2`, hardcoded, so `--rows`
was accepted and silently dropped for a PDF. **Chosen: add a `--pages` option
that actually reaches `dump_pdf`, and make each option's help text name the
container it governs** (`--rows` → "CSV/XLSX only", `--pages` → "PDF only: pages
to show from the start; the last page is always added").

**Test.** `test_cli_honours_pages_for_a_pdf` — a 5-page fixture, `--pages 1`
gives `pages shown: [1, 5]`, `--pages 3` gives `[1, 2, 3, 5]`, and the page-block
count differs.

---

## MINOR — five helpers duplicated across both engines

Commit `00b46ce`. **Chosen: share them**, which the brief preferred.

`_labels`, `_parse_date`, `_strip_suffix`, `_read_summary` and the
`_EMPTY`/`_EMPTY_MARKERS` set were verbatim duplicates. The drift hazard had a
specific shape: `tests/test_loader.py:354` pins
`loader._capture_as_the_engine_does` against `tabular._read_summary` for all six
shipped profiles (30 patterns), so the CSV copy could not drift — and the PDF
copy could drift freely, silently reading a different figure out of the same
`[summary]` pattern on a PDF than on a CSV.

New module `src/fbr/engines/_shared.py` holds `EMPTY_MARKERS`, `is_empty`,
`labels`, `parse_date`, `strip_suffix`, `read_summary`. Both engines import them,
so that existing loader pin now covers both containers. `is_empty` is shared too,
which removed the PDF engine's five inline `.strip().lower() not in _EMPTY`
membership tests. Where the two copies differed, the better text won:
`strip_suffix` keeps the tabular engine's error, which names the profile's actual
`debit_tokens + credit_tokens` rather than saying "no Dr/Cr token".
`tabular._read_summary` stays as an alias, because that is the name the loader
test imports.

**Test.** `test_both_engines_share_one_copy_of_every_duplicated_helper` asserts
**identity** (`is`), not equality — two equal-but-separate copies is the state
this replaced.

---

## Not changed (recorded, out of scope as instructed)

- `rows.continuation` schema-validated and read by neither engine;
  `pdf_row_samples` with no production caller.
- `_bands.assign` returning `None` only on exact ties, so two numeric columns
  closer than 12pt could pick the wrong side. Still carried forward: it must be
  fixed before any two-money-column PDF profile ships.
- `_find_label` taking the first of duplicate header labels (fails closed).
- `sadapay.pdf.v1`'s `# VERIFY` markers and invented `summary_expect` figures.
- `write_sadapay_pdf`'s unused `pages_hint` parameter (pre-existing, unlisted).

## Follow-up raised by this pass

- **Spec §4.2's Load page account picker — CLOSED.** Built on the coordinator's
  ruling; see the Picker section at the end of this report.

## Verification

```
uv run pytest        ->  423 passed
```

405 before, 423 after: 18 new tests. CPython 3.14 via `uv run` throughout; money
compared as integer paisa with no tolerance anywhere; fake identifiers use the
`PK00TEST` prefix only; no password reaches a message, a log or a command line.

---

## Picker — spec §4.2's Load page account picker, built

Commit: see below. Ruling received: do not ship the gap. Built as UI plus one
testable seam; `_bands.assign` left untouched, history left unamended.

### What was built

**`pipeline.load_files_with_assignments(files, assignments, *, registry,
profiles, tax_year, anchors=None, prior_year=None)`** — the whole rule, in
`src/fbr/pipeline.py`, so the page holds no business logic. It applies the
owner's chosen `account_id` to each file by name and re-runs `load_files` over
the **whole** set.

Re-running rather than merging the new ledger onto the previous `RunResult` is
not a shortcut, it is the only correct option: `merge_account` has to see every
one of an account's statements at once to check them for overlapping periods, a
balance discontinuity where two statements meet, and days of the tax year none of
them covers. Stitching one late ledger on afterwards would skip all three for
the very file the owner just assigned. Re-running is also what makes the
coordinator's second requirement hold structurally — every already-assigned file
parses identically, so its ledger comes back unchanged and a bad assignment
cannot cost the owner a good parse.

Two edges, both documented at the seam and tested:
- an assignment naming a file no longer loaded is inert (the owner removed the
  file after choosing; a stale key must not break the next parse);
- an assignment naming no registry account is not re-validated here, because
  `load_files` already routes an unknown id straight back to `unassigned` with
  the message the owner needs — the same fail-closed path.

**`app/pages/2_Load.py`** — one selectbox per unassigned file, options
`[— leave unassigned —, <id> — <institution>, …]`, defaulting to leaving it
alone so nothing is assigned by accident. "Parse again with these accounts" is
disabled until something is picked. Choices go in
`st.session_state["account_assignments"]`, never `st.cache_data`, and every
parse — including the plain **Parse** button — goes through one `parse_now`
helper, so a choice does not have to be made twice. A password is attached per
run inside the `InputFile` and is never written to session state.

**Messages, third and final revision.** Both now name two routes that exist:
"no registry account matches this statement; choose its account on the Load page,
or add the IBAN, account number or wallet number it prints to that account in
accounts.toml". `resolve_account`'s docstring points at the picker by name. The
"not built yet" wording from `4b6ce21` is gone.

### Verified by execution

The page itself was driven through `streamlit.testing.v1.AppTest`, in-process, no
browser. Two statements in the private folder: `meezan.csv` printing an IBAN a
registry account holds, and `sada.pdf` printing `PK00TEST9999999999999999`, which
no account holds — the case the picker exists for.

```
--- after Parse ---
warning:      1 file(s) matched no account: `sada.pdf`. Each statement is normally …
selectboxes:  ('Account for `sada.pdf`',
               ['— leave unassigned —', 'meezan-main — Meezan Bank Limited',
                'sadapay — SadaPay'])
buttons:      [('Parse', False), ('Parse again with these accounts', True)]   # disabled
ledgers:      ['meezan-main']
unassigned:   ['sada.pdf']

--- after picking "sadapay" ---
buttons:      [('Parse', False), ('Parse again with these accounts', False)]  # enabled

--- after re-parse ---
exception:    ElementList()                      # none
assignments:  {'sada.pdf': 'sadapay'}
ledgers:      ['meezan-main', 'sadapay']
unassigned:   []
  meezan-main: status=complete   txns=2  closing=130000
  sadapay:     status=incomplete txns=2  closing=None
session keys: ['account_assignments', 'profiles', 'registry', 'run',
               'tax_year', 'tax_year_config']
```

`meezan-main` came back byte-identical to the pre-assignment run — 2
transactions, closing 130000 paisa (Rs 1,300.00) — which is the "must not lose a
good parse" requirement, measured.

`sadapay: status=incomplete, closing=None` is correct, not a picker defect: the
page passes no `anchor`, and a layout with no balance column has no boundary
balance without one, so `anchor_missing` warns rather than a figure being
invented. Assignment worked; the missing anchor is reported.

At the seam, integer paisa, exact: with `anchors={"sadapay": 500000}` the
assigned ledger closes at **510000 paisa** — anchor Rs 5,000.00 + Rs 300.00 −
Rs 200.00 = Rs 5,100.00 — with `opening_source == "anchor"`.

### Tests

`tests/test_pipeline.py` (the seam, no Streamlit)
- `test_an_owner_assignment_produces_a_ledger_and_keeps_the_existing_ones` — the
  test the ruling asked for: the chosen account gets a ledger, and
  `meezan-main`'s ledger, transactions and status are unchanged
- `test_an_assignment_for_a_file_no_longer_loaded_does_not_break_the_parse`
- `test_an_assignment_naming_no_registry_account_fails_closed`
- `test_no_assignments_is_exactly_load_files`

`tests/test_load_page.py` (new; the page, via `AppTest`, `importorskip`-guarded)
- `test_the_picker_offers_every_account_and_defaults_to_leaving_it_alone`
- `test_choosing_an_account_assigns_the_file_and_keeps_the_good_ledger`
- `test_a_remembered_choice_still_applies_on_a_plain_re_parse`
- `test_the_page_stores_only_the_run_and_the_assignments`

`tests/test_pdf_wiring.py` — the two message tests were rewritten, since the
messages should now name the Load page:
`test_an_unassignable_pdf_names_both_routes_the_owner_actually_has`,
`test_an_unknown_explicit_account_id_names_both_routes`.

Exact output:

```
tests/test_load_page.py::test_the_picker_offers_every_account_and_defaults_to_leaving_it_alone PASSED
tests/test_load_page.py::test_choosing_an_account_assigns_the_file_and_keeps_the_good_ledger PASSED
tests/test_load_page.py::test_a_remembered_choice_still_applies_on_a_plain_re_parse PASSED
tests/test_load_page.py::test_the_page_stores_only_the_run_and_the_assignments PASSED
tests/test_pipeline.py::test_an_owner_assignment_produces_a_ledger_and_keeps_the_existing_ones PASSED
tests/test_pipeline.py::test_an_assignment_for_a_file_no_longer_loaded_does_not_break_the_parse PASSED
tests/test_pipeline.py::test_an_assignment_naming_no_registry_account_fails_closed PASSED
tests/test_pipeline.py::test_no_assignments_is_exactly_load_files PASSED

$ uv run pytest
431 passed in 6.67s
```

405 at `344af41` → 431 now: 26 new tests. The §4.2 follow-up recorded earlier in
this report is closed.
