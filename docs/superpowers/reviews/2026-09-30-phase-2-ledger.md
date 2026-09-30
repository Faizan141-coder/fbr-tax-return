# SDD ledger — plan: docs/superpowers/plans/2026-09-30-phase-2-pdf-engine.md

Spec: docs/superpowers/specs/2026-09-27-fbr-aggregator-design.md (binding authority)
Branch: main (owner consented to committing directly on main, 2026-09-27)
Start commit: 971dc9c — phases 0–1 complete, 313 tests passing
Execution: subagent-driven (owner's standing choice from the phase 0–1 run)

## Pre-flight scan

### A. Cross-task rows

| Producer → Consumer | Shared file / interface | Finding |
|---|---|---|
| 1 → 3 | `write_sadapay_pdf`, `write_meezan_pdf`, `write_wrapped_description_pdf`, `encrypt_pdf` | OK |
| 1 → 4 | `write_sadapay_pdf`, `encrypt_pdf` | OK |
| 2 → 3 | `Word`, `Band`, `build_bands`, `assign`, `group_lines`, `BandError` | **CONFLICT** → Ruling R1 (fixed before dispatch) |
| 3 → 4 | `parse_pdf`, `pdf_row_samples`, `PdfPasswordError`, `PdfNotTextual` | OK |
| 3 → existing | reuses `ParseResult`, `UnresolvedRow`, `ParseError` from `engines/tabular.py` rather than redefining them, so `reconcile.check_statement` is untouched | OK — verified those three names exist and are importable |
| 4 → existing | `loader.run_selftest` gains a keyword-only `summary_text=None`; `schema_profile.SelfTest` gains `summary_sample: str = ""`; `pipeline.InputFile` gains `password: str \| None = None`. All three are additive with defaults, so every existing caller keeps working. | OK |
| 4 → existing | `ingest.usable_profiles` starts passing `summary_text`. A profile with summary patterns but no sample passes `None`, so the summary pass is skipped and nothing breaks before step 8 adds the samples. | OK — the `or None` is load-bearing |
| 4 → existing | `_head_text`'s CSV error wording is preserved verbatim, because `tests/test_ingest.py` asserts on "could not be read as a csv file" | OK |
| 4 → existing | `pipeline` drops the `unsupported` short-circuit for PDFs. `tests/test_pipeline.py` has no test asserting that status, so nothing regresses. | OK — grepped |

### B. Per-task self-consistency

| Task | Finding |
|---|---|
| 1 | OK. Asserts Credit is printed left of Debit and that both amounts are unsigned — the property the engine must not paper over. |
| 2 | **Was broken** → R1. Now verified: I executed the corrected implementation against all 12 assertions the task's tests make, and all 12 hold. |
| 3 | OK. Test profiles validate against the real `Profile` schema (`columns.align` accepts a partial dict; `ColumnAlign` defaults the rest). |
| 4 | OK. `test_every_shipped_profile_declares_a_summary_sample` fails until step 8 adds samples to the five existing profiles — expected, and the plan runs tests at step 11. |

### C. Rulings made before execution

- **R1 — `assign()` would have orphaned every word of a multi-word description.** As written, Task 2 matched *every* column by edge proximity within a 6pt tolerance. A description is many words wide, so only its first word would have assigned; every later word would return `None`, be flagged ambiguous, and turn every row into an unresolved row — failing every statement and leaving the PDF engine entirely non-functional. I proved it by executing the plan's own logic against a realistic row: `TRANSF` assigned, then `CR/ICT/`, `Top-up`, `from`, `ALI` all `None`.
  **Ruling:** rewrote `build_bands`/`assign` as two stages. A numeric (right- or centre-aligned) column claims a word by edge proximity — the test that separates Meezan's unsigned Credit from its Debit — and only if none claims it does a left-aligned text column claim it by containment, its span running to where the next column begins. Numeric is tried first because a money column's band sits *inside* the description column's span; reversed, every amount would read as description text. Verified: 12/12 of the task's assertions hold, including that an amount midway between Credit and Debit still returns `None`.
  *Cost if wrong:* a description word ending within 6pt of a money column's right edge is claimed as an amount, fails to parse, and becomes an unresolved row — it fails closed rather than producing a figure.

- **R2 — plan scoped to phase 2 alone, not phases 2–5.** The owner asked for the complete application. Phases 2–5 are four separate subsystems and one plan for all of them ran past 2,000 lines at a quarter written; the phase 0–1 plan at 6,500 lines contained fourteen bugs that only surfaced on execution. **Ruling:** one plan per phase, executed in turn, each shipping working software. *Cost if wrong:* three more plan-then-execute cycles instead of one, and the owner waits longer for a complete tool.

- **R3 — `sniff_container` signature.** The plan told an implementer to replace `sniff_container(item.data, item.name)`, but the final phase-1 cleanup removed that unused parameter. An exact-text match would have failed. **Ruling:** corrected to `sniff_container(item.data)` at both call sites and in Task 4's test. *Cost if wrong:* none; verified against the live source.

## Progress

Task 1: complete (commit 915c387, review clean — spec ✅, Approved, 0 Critical, 0 Important, 7 Minor). Reviewer measured amount alignment with pdfplumber: Credit x1=400.0 with 0.0 offset, Debit x1=470.0 with 0.0 offset, Credit printed left of Debit, both amounts unsigned. All three encryption algorithms verified.
Task 1: found a real bug in my brief — `test_fake_ibans_use_the_reserved_prefix` used `PK\w+`, which also matches `PKR`, the currency code the SadaPay header prints. Corrected to `PK\d{2}\w*`; reviewer confirmed it still fails when the fixture stops using the PK00TEST prefix.
Task 1: minor (deferred): the wrapped-description test asserts only >=2 pages and that CONTINUATION appears somewhere, so the page-break claim itself is unchecked; Meezan's repeated header has no test; the encryption test uses a bare `pytest.raises(Exception)` and never tries a wrong password (Task 3 does); the IBAN test would pass vacuously if the fixture printed no IBAN at all.
Task 2: implementer DONE (commit 8063c40), 16 tests. Brief's code needed no fixes — the two-stage design from ruling R1 worked as written.
Task 2: Ruling: the "flaky" failure the Task 2 agent reported was not flakiness and not a product bug. The Task 1 reviewer temporarily rewrote TEST_IBAN in tests/fixtures/synth.py to PK36SCBL... to prove the test bites, then restored it — while the Task 2 agent was running the full suite. That is a race I caused by running a mutating reviewer concurrently with an implementer. Verified after the fact: tree clean, TEST_IBAN restored, both IBAN tests pass 5/5. Cost if I had missed it: a reviewer crashing mid-mutation would leave a real IBAN-shaped string in a tracked fixture, which is exactly what the pre-commit hook exists to stop.
Task 2: Ruling: from here every review prompt forbids mutating a tracked file even temporarily — non-vacuity must be proved against a copy outside the repo, or by loading a modified module via importlib. Cost if wrong: reviewers do slightly more work to prove a test bites.
Task 2: complete (commit 8063c40, review clean — spec ✅, Approved, 0 Critical, 0 Important, 6 Minor). Reviewer called the module with its own coordinates: six description words from x=130 to 375 all assign; an amount with x1 in 430–441 returns None (a 58pt dead zone either side of the 435 midpoint); with the stages reversed an amount at x0=372 would read as description text, confirming the ordering is load-bearing.
Task 2: minor (deferred): a role missing from `aligns` silently defaults to "right", which would turn date/description into narrow numeric bands and orphan every such word — Task 3's `_roles_and_aligns` sets text roles explicitly so it is safe today; duplicate header labels silently take the first match; nothing rejects two numeric windows closer than 12pt; two tests duplicate assertions made elsewhere.
Task 3: implementer DONE (commits 267abc8, db98bdc), 17 tests, suite 357. Found two real bugs in my brief.
Task 3: review (opus) — spec ✅, quality Needs work: 1 CRITICAL, 2 Important, 3 Minor. Both declared deviations were real and correctly fixed. Reviewer confirmed the engine's geometry is sound: a sign inversion that still reconciles is constructible only via a mis-authored profile on a layout with no balance column AND no printed totals AND net zero; with a real profile it fails both running_balance and opening_closing.
Task 3: CRITICAL — a dateless row carrying an amount is silently swallowed (pdf.py:238-245). The continuation branch keeps only `description` and discards `amount`, `balance` and the computed `ambiguous` list, emitting no UnresolvedRow. Reviewer built a bank that omits a repeated date on a same-day second row: Rs 700.00 and its balance vanished, running_balance still PASSED because the balance vanished with it, unresolved was empty, statement_usable was True. Money disappearing from a tax return with everything green.
Task 4: review (opus) — spec ✅, quality Needs work: 0 Critical, 2 Important, several Minor. Step 13 reproduced independently: stdout only paths and counts, dump named by sha256 prefix not the source filename (which contained PK00TEST), 14 coordinate lines, no fixture name or amount readable. All six profiles pass a self-test that exercises their summary patterns.
Task 4: Ruling: fixing both Importants and two of the Minors in one wave alongside Task 3's findings, because they are small and they undercut features shipped in this very phase — app/main.py still tells the owner "PDF support arrives in phase 2", the # VERIFY test loop omits the one profile most dependent on those markers, and the dump masks `Debit/Credit`, which is simultaneously sadapay's detect signature and its amount column, i.e. exactly what the dump exists to reveal.
Task 4: Ruling: also closing a gap in the mechanism I built this phase. `run_selftest` checks `pattern.search()` truthiness but never the captured value, so a summary pattern that matches the WRONG number passes for all six profiles. It catches "pattern never matches" (the shipped backslash bug) but not "pattern captures the wrong figure" — and the latter is the one that puts a wrong number on a return. Cost if wrong: profiles need a small `summary_expect` map, and authors must state what their sample should yield.
PHASE 2 FIX WAVE: 5 commits de48ea4..999f7a6, 372 -> 405 tests.
FIX-WAVE RE-REVIEW (opus): all 7 ADDRESSED, new breakage none. Every case re-measured rather than read off the report. The Rs 700.00 dateless row now surfaces as an UnresolvedRow naming both 700.00 and 2,200.00, with statement_usable False; a description-only continuation still joins on pages 2 and 3, with and without repeated headers; the wrong-profile PDF raises ParseError naming the labels; swapping each profile's two consequential summary patterns now fails for ALL SIX (a one-paisa error fails too); Debit/Credit survives the dump while Payoneer/AHMED, AHMED-KHAN and IBFT/0300123/ALI all mask. Mutation-checked: the strengthened continuation test fails when open_row is reset per page.
Task 3: complete (commits 8063c40..db98bdc + fix wave, review clean).
Task 4: complete (commit 68bd5b8 + fix wave, review clean).
ALL 4 PHASE-2 TASKS COMPLETE. 405 tests.
TWO BEHAVIOUR NOTES FOR THE OWNER (not defects):
  (1) A description-only continuation whose word starts right of the description band is now an UnresolvedRow that fails the statement, where before it was silently truncated. Fail-closed and better, but expect it as a possible false failure on a real statement with wide descriptions.
  (2) A dateless money line that also matches a footer/skip/summary regex is still swallowed, because those tests run before the dateless branch. Pre-existing, unchanged by this wave; SadaPay's footers make it unlikely.
RESIDUAL: every summary_expect figure and every # VERIFY setting in sadapay.pdf.v1 is still invented, so the self-test proves internal consistency only. summary_sample and summary_expect must be updated together from a real masked dump before any figure from a real SadaPay statement goes near IRIS. Expect the first real run to surface unresolved rows rather than wrong numbers.
