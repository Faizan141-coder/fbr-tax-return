# SDD ledger — plan: docs/superpowers/plans/2026-09-27-phase-0-1-foundation-tabular.md

Spec: docs/superpowers/specs/2026-09-27-fbr-aggregator-design.md (read; binding authority)
Branch: main (owner gave explicit consent to work directly on main, 2026-09-27)
Start commit: 1eb9712

## Pre-flight scan

### A. Cross-task rows (tasks sharing a file or an interface)

| Producer → Consumer | Shared file / interface | Finding |
|---|---|---|
| 1 → all | `pyproject.toml` (`packages = ["src/fbr","tools"]`), `tests/__init__.py` | OK. `tools/__init__.py` created in T1 step 3, so `tools.dump_layout:main` resolves once T12 lands. |
| 1 → 12 | `[project.scripts] fbr-dump = "tools.dump_layout:main"` | OK. Hatchling does not import entry points at install time, so `uv sync` in T1 succeeds before T12 exists. `fbr-dump` is only runnable from T12 on. |
| 1 → 15 | `.streamlit/config.toml` | OK. T1 writes it; T15 step 7 verifies the running app binds loopback only. |
| 1 → controller | `.gitignore` | **CONFLICT** → Ruling R1. |
| 1 → 15 | `app/` package | **CONFLICT** → Ruling R2. |
| 2 → 8, 10, 11, 15 | `parse_paisa`, `format_paisa`, `AmountError` | OK. Signatures match every call site. |
| 3 → 5 | `Account`, `Owner`, `Registry` (built by `RegistryFile.to_model`) | OK. Field names and order match. |
| 3 → 8 | `Transaction`, `Provenance`, `make_txn_id`, `assign_occurrences`, `tax_year_for` | OK. |
| 3 → 10, 11 | `Check`, `Transaction`, `Account` | OK. `Check` takes 7 positional + optional `locator`; all call sites conform. |
| 4 → 6 | `paths.registry_path()` | OK. |
| 4 → 12 | `dumps_dir`, `dump_candidates_dir`, `dump_allowlist_path`, `ensure_private_layout` | OK. |
| 4 → 13 | `statements_dir(tax_year)` | OK. |
| 4 → 15 | `describe_private_layout`, `ensure_private_layout`, `PrivatePathError` | OK. |
| 5 → 6 | `Profile`, `RegistryFile`, `TaxYear` | OK. |
| 5 → 8 | `Profile.columns/formats/rows/summary/balance` | OK. `SummaryPatterns.compiled()` is the only regex accessor the engine uses. |
| 6 → 9 | `ProfileSet`, `ProfileStatus`, `run_selftest(profile, parse_row)` | OK. `run_selftest` takes the engine callable, so the loader never imports the engine (no cycle). |
| 7 → 8, 10, 11, 13, 14 | `build_statement`, `write_*_csv`, `write_xlsx`, `corrupt`, `SynthTxn` | OK. |
| 8 → 9 | `parse_row`, `read_rows`, `ParseError` | OK. |
| 8 → 12 | `read_rows` (local import inside `_read_rows`) | OK; local import avoids a cycle. |
| 8 → 13 | `parse_tabular`, `ParseResult`, `ParseError` | OK. |
| 9 → 12 | `sha256_of`, `sniff_container` | OK. |
| 9 → 13 | `detect_layout`, `resolve_account`, `LayoutUnknown`, `LayoutAmbiguous` | OK. |
| 10 → 11 | `src/fbr/reconcile.py` — T11 **appends** to T10's module; uses `_check`, `check_statement`, `statement_usable` | OK. `Profile` is already imported at T10's module top, so T11's appended block needs no new import for it. |
| 11 → 13 | `merge_account(..., profiles=...)`, `AccountLedger` | OK after the plan's self-review made `profiles` required. |
| 13 → 15 | `InputFile`, `RunResult`, `FileOutcome`, `load_files`, `read_statement_dir` | OK. `RunResult(outcomes=())` is constructible; the other fields default. |
| 14 → 6, 9 | `profiles/*.toml`, `taxyears/TY2026.toml` loaded by `load_profiles` / `load_tax_year` | OK. |
| cross-test | T9/T11/T13 import `MEEZAN`/`MCB` from `tests.test_tabular`; T11/T13 import `TAXYEAR_TOML` from `tests.test_loader` | OK — `tests/__init__.py` exists from T1, so `tests` is an importable package. |

### B. Per-task self-consistency rows

| Task | Do its tests match the code it specifies? | Finding |
|---|---|---|
| 1 | Guardrail tests read the files the task writes | OK. Hook regex in the test matches the hook body. |
| 2 | Amount grammar vs its parametrized cases | OK. Rejects `1,234.56Dr` (direction is the profile's job) and >2 decimals. |
| 3 | `txn_id` / `assign_occurrences` vs tests | OK. `None` vs `0` balance hash differently, as tested. |
| 4 | Path helpers vs tests | OK. Repo-inside and cloud-synced guards both tested. |
| 5 | Validators vs tests | OK. Each `ValidationError` test targets a validator that exists. |
| 6 | Loader vs tests | OK. Duplicate-id and malformed-TOML paths both raise `ConfigError` naming the file. |
| 7 | Generators vs tests | OK. Balances computed, `PK00TEST` prefix, six corruption modes. |
| 8 | Engine vs tests | OK. Name-mapped columns, three sign modes, printed order preserved, unresolved rows never zero. |
| 9 | Ingest vs tests | OK. Ambiguity raises; self-test failures excluded from detection. |
| 10 | Five checks vs tests | OK. Each check has a passing and a failing case. |
| 11 | Merge vs tests | OK after the `profiles` fix; the missing-profile guard has its own test. |
| 12 | Masking vs tests | OK. `FENCE` built from `chr(96)` so the block cannot break its own fence. |
| 13 | Pipeline vs tests | OK. Per-file outcomes; hash dedupe. |
| 14 | Shipped config vs tests | OK. Every profile self-tests and round-trips its own synthetic layout. |
| 15 | Pure helpers vs tests | OK. Streamlit itself is exercised only by the manual steps 7–8. |

### C. Rulings made before execution

- **R1 — `.gitignore` content.** T1 step 4 writes a `.gitignore` that omits `.superpowers/`, which the controller added in 1eb9712; transcribing T1 verbatim would un-ignore the scratch workspace and risk committing it. **Ruling:** T1 must append its block to the existing `.gitignore` rather than overwrite it, keeping the `.superpowers/` line. *Cost if wrong:* the scratch workspace becomes committable; caught by `git status` at the next commit.
- **R2 — `app/__init__.py` missing.** T15's `tests/test_app_state.py` does `from app.state import …`, but neither T1 nor T15 creates `app/__init__.py`. It would work only as an implicit namespace package, which depends on pytest's rootdir insertion. **Ruling:** T1 also creates `app/__init__.py` and `app/pages/__init__.py`. *Cost if wrong:* nothing — an extra empty file that makes the import explicit.
- **R3 — batch tasks 2, 3, 4.** They are three independent leaf modules (`money.py`, `model.py`, `paths.py`) whose complete code is in the plan, with no interdependencies. **Ruling:** one implementer and one review for all three. *Cost if wrong:* a muddier fix loop if the review finds problems in more than one module; findings stay localized because the modules do not touch each other.
- **R4 — T15's privacy smoke test.** Steps 7–8 need a backgrounded server plus `lsof`, which a sandboxed subagent may not be able to run. **Ruling:** the implementer must attempt it and, if the environment prevents it, report `DONE_WITH_CONCERNS` naming the step as unverified rather than claiming it passed. The controller then runs it. *Cost if wrong:* the privacy posture goes unverified until the controller's own run.
- **R5 — pushes.** The owner consented to committing on `main`; pushing to a shared branch is a side effect to confirm. **Ruling:** commit per task locally, push once at the end. *Cost if wrong:* the remote lags the local branch until the final push.

## Progress

Task 1: implementer DONE (commit d228ede). Review: spec ✅, quality Approved, 0 Critical, 2 Important, 2 Minor.
Task 1: Ruling: both Important findings are plan-mandated (my Step 8 test code), and both weaken the guardrail that stops statement data reaching git — the one failure this project must not have. Fixing rather than dismissing: (a) the hook test must execute the real hook against a real staged file, not re-declare its own copy of the regex; (b) the config test must assert all 7 mandated values, not 5. Cost if wrong: ~30 lines of extra test code in a file nothing depends on.
Task 1: minor (deferred): the hook's line-based `grep -v PK00TEST` would suppress a real IBAN sharing a line with a PK00TEST string.
Task 1: minor (deferred): `fbr-dump` entry point is a forward reference to tools/dump_layout.py (Task 12) — harmless, does not break `uv sync`.
Task 1: fix round 1/5 (2 addressed, 0 open; commits d228ede..e215f8d) — hook now exercised end-to-end in a throwaway repo; config test asserts all 7 values.
Task 1: complete (commits 1eb9712..e215f8d, review clean). 6 tests passing.
Tasks 2-4: complete (commits e215f8d..f8c215c, review clean). 74 tests passing.
Tasks 2-4: Ruling: accepted the implementer's deviation from the Task 2 brief. My `_normalize` stripped all whitespace, so the brief's own reject-case "1 234 56" would have parsed as 1,234.56 — a wrong amount on a tax return. The fix strips only U+00A0 and lets the regex's `\s*` tokens absorb ordinary whitespace; the reviewer confirmed it by executing the regex against every valid and invalid case, plus thin/narrow spaces. Cost if wrong: an exotic separator is rejected rather than parsed, which surfaces as an unresolved row, never as a silent figure.
Task 5: complete (commit cde3fb2, review clean). 92 tests passing.
Task 5: Ruling: accepted the pydantic fix (`self.model_fields` -> `type(self).model_fields`). Instance access is deprecated in 2.13 and removed in v3, and pyproject pins `pydantic>=2.13` with no upper bound, so a future `uv sync` would have broken it. Reviewer reproduced the deprecation and byte-diffed the rest against the brief. Cost if wrong: none; behaviourally identical for a class that is never subclassed.
Task 5: Ruling: commit cde3fb2's trailer says "Claude Sonnet 5" where earlier commits say "Claude Opus 5". The subagent followed its own session's attribution policy over my dispatch instruction, and it is the more truthful line — Sonnet wrote that code. Leaving it rather than rewriting history over one word. Future dispatches will tell subagents to follow their own attribution reminder. Cost if wrong: a mixed set of co-author trailers in the log, cosmetic only.
Task 5: minor (deferred): two `sign` cross-field validator branches and two tax-year period branches have no test, though all were manually confirmed to raise correctly. Gap is in my brief's test list, not the implementation.
Task 6: complete (commit fa3dd1d, review clean). 103 tests passing. Brief's code worked verbatim; reviewer independently confirmed the duplicate-id path names both files, every error names its file, and loader.py never imports the engine.
Task 6: minor (deferred): three tests use generic `match=` phrases that would still pass if the file name were dropped from the message; the implementation does interpolate it correctly.
Task 7: implementer DONE (commit 5cfc90c). Review: spec ✅, quality Needs work — 1 Important, 1 Minor.
Task 7: Ruling: fixing the Important finding rather than deferring it. `corrupt(nayapay, "flip_sign")` returns the file unchanged, and five later tasks use `corrupt` to prove their reconciliation checks fire — a silent no-op there is indistinguishable from a passing test. Fix adds signed-amount support and makes `corrupt` raise when it cannot damage the input. Cost if wrong: a later task gets a loud ValueError for an inapplicable mode instead of a silent clean file, which is the failure direction I want.
Task 7: fix round 1/5 (2 addressed, 0 open; commits 5cfc90c..d20002e) — flip_sign handles signed layouts; corrupt() raises rather than returning unchanged bytes; all 18 writer x mode combinations verified by execution.
Task 7: complete (commits fa3dd1d..d20002e, review clean). 115 tests passing.
Task 8: implementer DONE (commit 156ea39), 3 real brief bugs found and fixed. Review (opus): spec ✅, quality Approved, 0 Critical, 1 Important (forward-looking), 4 Minor.
Task 8: Ruling: accepted all three of the implementer's deviations. (a) `_map_columns` never required the balance role, so a renamed balance column silently left every balance_after None — reviewer confirmed the old code returned 8 transactions with no error. (b) greedy `\D+` in the summary regexes swallowed a leading minus: reviewer measured 18 of 80 opening/closing values wrong across 40 seeds, sign-inverted, e.g. -3,019.90 read as +3,019.90. On a wealth statement that is a wrong number in the worst direction. The lazy `\D+?` with `-?` fixes it with no regression across 8 adversarial preambles. (c) a test's byte replacement matched a date string the generator never emits, so the test could never pass. Cost if wrong: (b) is the one that matters, and it was verified by execution against 40 seeds both ways.
Task 8: Ruling: fixing the Important finding now rather than deferring. `parse_row` shares `_map_columns` but has no use for a balance, so a running-balance profile whose selftest row omits the balance column fails run_selftest, and loader.py catches every exception and excludes the profile from layout detection. A good profile would silently stop matching real statements. No profiles ship yet, but Task 14 ships three. Cost if wrong: a profile could be wrongly excluded, surfacing as "unknown layout" rather than a wrong figure.
Task 8: minor (deferred): parenthesised negatives like (4,500.00) stay positive under the summary patterns — matters when Task 14 writes real profiles.
Task 8: minor (deferred): test_xlsx_parses_identically_to_csv asserts only amounts; test_identical_rows_get_distinct_ids distinguishes by balance, so it never exercises the occurrence tie-break.
Task 8: fix round 1/5 (1 addressed, 0 open; commits 156ea39..da6a3e8) — require_balance keyword-only, parse_row opts out, parse_tabular unchanged. Re-reviewer loaded the pre-fix module via importlib and confirmed the new test fails without the fix.
Task 8: complete (commits d20002e..da6a3e8, review clean). 133 tests passing.
Task 9: implementer DONE (commit 67e70fa), brief's code worked verbatim — first task with no bug in the brief. Review: spec ✅, quality Approved, 0 Critical, 1 Important, 2 Minor.
Task 9: Ruling: fixing the Important finding now. A corrupt or truncated xlsx propagates a raw zipfile.BadZipFile out of detect_layout, confirmed by execution. Task 13 loads the owner's files one after another and reports a per-file outcome so one bad file never stops the run; an uncaught traceback breaks exactly that. Fix also distinguishes "could not read the bytes" from "no profile matches", because the existing message tells the owner to send a masked dump, which is the wrong advice for a part-downloaded file. Cost if wrong: a broad except could mask a genuine bug in read_rows, so the fix must name the exception types it catches.
Task 9: minor (deferred): sniff_container's filename="" default differs from the brief's interface line; harmless.
Task 9: minor (deferred): test_resolves_an_account_by_iban does not uniquely prove IBAN matching — the fixture's account_number is a substring of its iban, so a resolver ignoring the iban field would still pass.
Task 9: fix round 1/5 (1 addressed, 0 open; commits 67e70fa..95f7f71) — unreadable bytes now raise LayoutUnknown with a distinct "could not be read" message; re-reviewer probed empty bytes, a non-workbook zip and undecodable CSV, none escape uncaught.
Task 9: Ruling: accepted `except Exception` scoped to the single read_rows call rather than an enumerated tuple. Two corruption patterns already produced two different third-party exception types (BadZipFile, KeyError), so an enumerated list would leave gaps exactly where the fix must hold; it mirrors the reviewed precedent in loader.run_selftest. Cost if wrong: a genuine bug inside read_rows would be reported as "corrupt file" rather than crashing — accepted, and the same cost the precedent already carries.
Task 9: complete (commits da6a3e8..95f7f71, review clean). 150 tests passing.
Task 10: implementer DONE (commit f170c47), found a real fixture bug — write_meezan_csv never printed a statement period, so date_range returned warn unconditionally and even the baseline clean-statement test failed. Review (opus): spec ✅, quality Approved with issues, 0 Critical, 3 Important, 2 Minor.
Task 10: Ruling: accepted the shared-fixture change. It touches write_meezan_csv and the MEEZAN profile, which Tasks 8, 11, 13 and 14 consume, so I had the reviewer compare parent vs HEAD: parsed amounts, balances, txn_ids and summary values are byte-identical across 4 seeds; only row locators shift by one and Document.period_start/end now carry the printed period, neither of which any test asserts. Cost if wrong: a later task's expectations shift silently — mitigated by that comparison.
Task 10: Ruling: fixing all three Important findings now rather than deferring. (1) printed_totals is exercised by no test, and it is the only check available for a statement printing no balances, which is the SadaPay case Task 11+ must handle. (2) the new period regexes' `\D+?` crosses newlines and can fabricate a statement period from unrelated preamble rows — same family as the greedy bug that inverted negative balances, and Task 14 ships real profiles that must not copy it. (3) build_statement defaults period_end to the last printed row rather than the latest date, so any later task building deliberately unsorted rows gets spurious date_range failures. Cost if wrong: (3) changes a default four tasks rely on, so the explicit `end=` path must keep behaving exactly as before.
Task 10: minor (deferred): a printed total of exactly 0 falls back to the parsed value in the Check's `expected` field.
Task 10: minor (deferred): date_range's warn detail says "does not print its period" even when it does but has no transactions.
Task 10: fix round 1/5 (3 addressed, 0 open; commits f170c47..ed8f166). 165 tests.
Task 10: CARRY FORWARD TO TASK 14: the fix audited MEEZAN's summary patterns and found `opening`/`closing` shared the same newline-crossing flaw as the period patterns (all fixed). MCB and NAYAPAY profiles in tests/test_tabular.py still carry it — left untouched as out of scope. Task 14 ships real MCB and NayaPay profile TOMLs and must use `[^\d\n]+?`, never `\D+?`, in every summary pattern.
Task 10: Ruling: dispatching Tasks 11 and 12 concurrently. Their file sets are provably disjoint (src/fbr/reconcile.py + tests/test_reconcile_account.py vs tools/ + tests/test_dump_layout.py), and the owner asked for this finished sooner. Each agent is instructed to commit only its own files by explicit path and never to rebase, reset or amend. Cost if wrong: an interleaved commit or a dirty tree; recoverable from git log, and the per-task reviews still gate both.
Task 12: implementer DONE (commit e6c0c84), found a real brief bug — _TOKEN's unconditional comma glued CSV fields into one blob and mangled allowlisted words. Review: spec ✅, quality Needs work — 1 Important, 2 Minor.
Task 12: Ruling: fixing the Important finding. PEER and STAN are shipped allowlist entries that are also real name fragments; the reviewer reproduced "Received from PEER MUHAMMAD BAKHSH" leaving PEER readable in a dump. This is the privacy gate, and a leak here is silent and permanent because the dump has already been sent. Removing both. Keeping ACE/HOME/UNION, which are remittance-channel vocabulary and far less likely inside a Pakistani personal name. Cost if wrong: dumps show XXXX where STAN appeared, losing a little layout signal — the right direction to err.
Task 11: implementer DONE (commit 69df7d0), found a real brief bug — has_balance was always False for a dormant account. Review (opus): spec ✅, quality Needs work — 1 CRITICAL, 2 Important, 3 Minor.
Task 11: Ruling: fixing all three. The Critical produces a silently wrong wealth-statement figure: when a tax year has no in-year transactions but the statement has out-of-year ones, the printed balances are copied and hard-labelled "printed", reporting 300000/310000 where the truth is 310000/310000, status complete, no warning. The Importants double-count income across partially overlapping statements, and hide a missing 30 June balance behind status=complete. All three are the same shape: a number that looks right, reconciles against itself, and is wrong. Cost if wrong: these are the figures the owner types into IRIS.
Task 13: implementer DONE (commit d301ae4), found a real brief bug — an InputFile.account_id naming an unknown account reported "ok" then silently vanished from the ledgers.
Task 12: fix round 1/5 (1 addressed, 0 open; commit f5546b3) — STAN and PEER removed from the allowlist; new test asserts neither is present and that a realistic name line leaves nothing readable, so re-adding either fails the suite. 219 tests.
Task 12: complete (commits ed8f166..f5546b3, review clean). Privacy leak closed and pinned.
Task 13: review clean — spec ✅, Approved, 1 Important (fix had no regression test), 2 Minor. Fix round 1 dispatched.
Task 14: implementer DONE (commit 5ccefea). Confirmed the carried-forward regex fix was load-bearing, not hygiene: the brief's own test seeds (81, 82) drive every account into overdraft, so without `-?` the shipped profiles would have inverted those signs.
Task 14: CONTROLLER FINDING (to fix): the implementer set nayapay.csv.v1 `[balance] semantics = "none"`, which disables running-balance checking for a real bank, because the fixture writes negative balances as "Rs. -500.00" which the amount grammar rejects. That fixes the wrong layer. tests/fixtures/synth.py:176 already writes the AMOUNT correctly as "{sign}Rs. {abs}" (sign before the prefix, matching both the grammar and research 03's documented "<Type> -Rs. <amount> Rs. <balance>"), while line 177 writes the BALANCE as "Rs. {format_paisa(...)}", putting the minus inside. The fixture is inconsistent with itself. Fix line 177, then restore semantics="running" so NayaPay keeps its balance-chain verification.
Task 14: review (opus) — spec ✅, Approved, 0 Critical, 1 Important, 2 Minor. Verified by mutation: swapping Meezan's debit/credit labels excludes the profile, the VERIFY test fails when stripped, all three profiles detect only their own layout. IRIS codes confirmed: 64060285 = @1%, 64060290 = @0.25% (not swapped); both wealth codes genuinely blank with verification="unknown", no fabricated digits; zero entries falsely marked iris_verified; thresholds in paisa.
Task 14: Ruling: fixing the NayaPay semantics="none" workaround rather than accepting it — reviewer and I reached this independently. It permanently costs one of four accounts its per-row balance-chain check to work around a bug in a shared test fixture, where synth.py:177 renders a negative balance as "Rs. -X" while line 176 already renders amounts correctly as "-Rs. X". Nothing is unsafe today (opening_closing and printed_totals still fail closed), but weakening real verification to accommodate a fixture is the wrong direction. Also adding the unused total_credit/total_debit patterns for Meezan and MCB — free verification already being printed and ignored. Cost if wrong: synth.py is shared by five tasks, so the fix must report any test whose behaviour moves.
Task 15: implementer DONE (commit 601f752). All 15 tasks now implemented; 244 tests passing.
CONTROLLER-RUN PRIVACY CHECK (the brief's manual step 7, run by me rather than a subagent):
  ./run -> Uvicorn bound 127.0.0.1:8501 only; `lsof -nP -i -a -p <app pid>` showed NO ESTABLISHED or SYN_SENT connections.
  Outbound traffic visible in a naive `lsof | grep python` belonged to an unrelated Python 3.12 process (pid 78482); our app is Python 3.14. Verified by pid, not by name.
  Also confirmed by grep: no st.cache_data / st.cache_resource / page_icon=":material/..." / map elements anywhere in app/.
  Conclusion: the local-only guarantee holds. Server stopped afterwards.
Task 13: fix round 1/5 (1 addressed; commit 11b8fe4) — regression test for the invalid-override guard, verified red against a guard-less copy loaded into sys.modules; cross-account anchor/prior_year test added; unused import removed. 241 tests.
Task 15: DONE_WITH_CONCERNS is the correct status — the implementer could not run a browser for the brief's manual step 8 and said so rather than claiming a pass, substituting Streamlit's official headless AppTest harness to drive the real page scripts end to end. It also verified step 7 independently and, like me, had to trace PIDs to rule out an unrelated pre-existing python process that a plain `grep -i python` catches. Two independent runs, same conclusion.
Task 13: complete (commits 69df7d0..11b8fe4, review clean). 241 tests.
Task 15: complete (commit 601f752, review clean — spec ✅, Approved, 0 Critical, 0 Important, 2 Minor). Reviewer confirmed the pages hold no business logic, masking has exactly one reachable site with no raw identifier elsewhere in app/, unknown balances render the literal "unknown" and never 0, both TY2026 unknown codes surface with a mark plus a named warning, and a repo-wide grep finds zero cache_data/cache_resource.
Task 15: minor (deferred to final review): dead `parse_row` import at app/pages/1_Setup.py:11.
Task 15: minor (deferred to final review): summarize_run's test fixtures are symmetric (1 ok/1 problem, 1 fail/1 warn), so swapping those branch conditions would not be caught. Inherited from my brief.
Task 14: fix round 1 landed (commit 42cc8ea). Verified by me before re-review: nayapay semantics back to "running"; meezan and mcb now carry total_credit/total_debit patterns using [^\d\n]+? with -?; synth.py's balance rendering fixed at the right layer with an explanatory comment. Suite green.
Task 14: Ruling: keeping the MCB Total Credit/Debit patterns, with the speculation documented. My instruction to add them rested on the reviewer's claim that both writers already printed those rows; that was half wrong — MCB's writer printed none, and research 03 documents only Opening/Closing Balance for MCB's three layouts. The implementer disclosed this rather than quietly satisfying the instruction, and extended write_mcb_csv so the pattern has text to exercise. Keeping it because: it is marked # VERIFY, the profile comment states outright that MCB may not print such a line, and an absent label simply means no match, so printed_totals is skipped and nothing is ever wrong. Cost if wrong: the owner looks for a Total Credit row in a real MCB export, does not find one, and deletes two lines. SURFACE THIS TO THE OWNER.
Task 14: fix round 1/5 (2 addressed, 0 open; commits 5ccefea..42cc8ea). Re-reviewer executed rather than inspected: NayaPay seed 81 (all 8 rows overdrawn) now parses 8/8 with running_balance passing; printed_totals fails closed on a corrupted total for all three profiles; the decoy preamble harvests nothing where the old pattern did; writer output byte-identical across 300 positive seeds and 41 overdraft seeds except the intended NayaPay negative-balance cells.
Task 14: complete (commits f5546b3..42cc8ea, review clean). 244 tests.
STATUS: 14 of 15 tasks complete. Only Task 11's fix outstanding (agent running 31m; uncommitted reconcile.py mid-refactor currently breaks test_pipeline/test_reconcile_account with "boundary_balances() missing 'tax_year'" — expected mid-flight, not a landed regression).
Task 11: RECOVERY — the original implementer's session ended with ~119 lines uncommitted in reconcile.py and no report. I backed the tree up (reconcile.py.orphaned-wip, task-11-orphaned.patch), probed it to confirm all three fixes were present, and dispatched a fresh opus implementer to verify, test and commit rather than restart.
Task 11: fix round 1/5 (3 addressed, 0 open; commit f8ddf59). Re-review (opus) measured every case itself and checked parent-failure independently via `git archive` into a scratch tree: 6 failed / 15 passed against the parent, including both Critical tests.
  Critical: 300000/310000 "printed" -> 310000/310000 "computed"; second case -> 300000/300000 "computed"; dormant control unchanged at 250000/250000 "printed".
  Overlap: 4 txns -> 3 with an overlap check; a disagreeing intersection fails the account; genuine identical same-day twins survive in every arrangement tested, and a later statement printing only one twin FAILS rather than dropping one.
  Mixed profiles: early half None + false "no anchor" warning -> 500000 honouring the anchor; late half closing None + silent "complete" -> 530000, and a truly undeterminable account warns and reports incomplete.
Task 11: complete (commits e6c0c84..f8ddf59, review clean). 250 tests.
ALL 15 TASKS COMPLETE.
FINAL REVIEW (opus, whole branch): 2 Critical, 5 Important, 7 Minor. The Criticals were cross-task failures no per-task review could see: (1) resolve_account could attribute a whole bank's ledger, and its 30 June balance, to a different account while the real account vanished without a warning; (2) the masking gate's tokenizer was ASCII-only, so Urdu text passed through a dump unchanged. Important 3 was fixture/profile drift: the shipped profiles omit period patterns, so date_range could never fail and every account was falsely incomplete — invisible in CI because test_pipeline.py used test-local profiles that did carry them.
FINAL FIX WAVE: 10 commits c85e02e..05286c4, 250 -> 313 tests.
PUSH ANOMALY — CORRECTION: I earlier told the owner that subagents pushed against instruction. That was wrong and I retracted it. Evidence: 609d2ea was committed 18:22:41 and reached origin 18:22:47, six seconds later, by an agent that explicitly reports it did not push; meanwhile the most recent 7 commits are NOT pushed. There is no post-commit hook in .githooks (only pre-commit), none in .git/hooks, no global core.hooksPath, and no push-related git config. Something external to git pushes intermittently and I could not identify it. SURFACE THIS TO THE OWNER as an unexplained behaviour on their machine.
FINAL FIX WAVE RE-REVIEW (opus): all 7 findings ADDRESSED, new breakage none, 313 tests. Verified by execution against pre-fix copies, not read off the report.
THREE RESIDUALS TO SURFACE (none introduced by this wave, all need the owner's judgement or a real dump):
  R-a: no shipped profile defines [summary] account_id, so attribution runs on body text only; real statements will more often arrive "unassigned" and need a manual pick. Safe direction, but manual. Writing those patterns from the first real dump is the highest-value next task.
  R-b: period patterns and the MCB/NayaPay "Statement Period" rows are # VERIFY and are exercised only against fixtures the same generator writes. A real export labelling the period differently reverts to the old permanent gap warn — loud and harmless, but the loop stays closed until a real dump opens it.
  R-c: an account can display complete while carrying warnings — only `gap` and `anchor_missing` demote status, so a continuity seam, an unanchored chain and a skipped opening/closing check can all sit under a green tick. Measured: 3 warnings, status complete. Demoting on ANY warn is the obvious fix, but it risks recreating the "warning fires always" problem that Important 3 just removed, so it is the owner's call, not mine.
