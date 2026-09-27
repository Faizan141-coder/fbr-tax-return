# Spec Review — FBR Tax Return Data Aggregator

> **Status:** draft for owner review, 27 Sep 2026
> **Reviews:** [requirements.md](requirements.md) (the owner's brief)
> **Evidence:**
> - [01 tax rules](research/01-fbr-tax-rules.md)
> - [02 IRIS codes](research/02-fbr-iris-codes.md)
> - [03 statement formats](research/03-statement-formats.md)
> - [04 tech stack](research/04-tech-stack.md)
>
> **Pending decisions:** [open-questions.md](open-questions.md)
>
> **Superseded where different** by the design spec, [superpowers/specs/2026-09-27-fbr-aggregator-design.md](superpowers/specs/2026-09-27-fbr-aggregator-design.md), including the build order in §6.
>
> This review supports the design. It is not tax advice. Legal questions the tool can't settle are listed for a tax advisor in [open-questions.md §D](open-questions.md#d-for-a-tax-advisor).

## 1. Verdict

The brief is sound and buildable, and its instincts are right: an itemised audit trail, nothing silently excluded, every internal-transfer match reviewed, all processing local, and no guessing at manual items. All of that stays.

Research changes four things:

1. **A statement label can't prove export income.**
   - Credits labelled "Payoneer", "Wise", "Remitly" or "Thunes" can be client payments, family money or your own funds.
   - SadaPay and NayaPay receive them through SBP's home-remittance channel.
   - The banking record that tells them apart is the SBP purpose code: 9186 for freelance IT and 9471 for family maintenance. That code is on PRCs (the bank's proceeds realization certificates), not on statements.
   - So classification can only propose; the owner confirms. ([01 §Q1c, §Q5](research/01-fbr-tax-rules.md); [03 §Q4](research/03-statement-formats.md))
2. **Withholding is not one "adjustable tax → 9201" bucket.**
   - Bank-profit tax (when total profit is ≤ Rs 5m) and s.154A export tax are **final** taxes. Each sits on its own final-tax line.
   - Only salary, s.236Y and s.231AB tax are adjustable.
   - IRIS calculates 9201 itself.
   - ([01, implication 6](research/01-fbr-tax-rules.md#implications-for-the-tool); [02 §1d](research/02-fbr-iris-codes.md))
3. **Better inputs than PDF exist.**
   - MCB Live and NayaPay export CSV, and Meezan very likely exports CSV/XLSX.
   - Banks issue annual withholding-tax (WHT) certificates in the standard Rule 42 form.
   - SBP requires banks to send an annual statement of PRCs (S-PRC). It lists every foreign receipt with its purpose code.
   - ([03 Summary, §Q3, §Q4](research/03-statement-formats.md))
4. **The TY2026 return form changed** (SRO 1495(I)/2026, 2 Sep 2026).
   - The wealth statement was regrouped, and the bank-account code can't be read in FBR's scan.
   - Codes must therefore live in per-tax-year config that the owner confirms against IRIS.
   - ([02 §Q3, §Q5](research/02-fbr-iris-codes.md))

**Timing:** TY2026 returns and wealth statements are due **30 September 2026**. No extension had been announced as of 26–27 Sep 2026 ([01 §Q8](research/01-fbr-tax-rules.md)).

**Owner's decisions** ([open-questions.md §A](open-questions.md#a-decisions-that-shape-the-design-answered-27-sep-2026)):
- Build for next season. The owner files TY2026 manually, and those filed numbers become the acceptance test.
- Claude sees statement layouts only as masked dumps.
- Inputs are CSV/XLSX first.
- All foreign-channel credits are work income.

## 2. What research confirmed and corrected

### 2.1 Codes and rates

| Brief | Finding | Confidence | Evidence |
|---|---|---|---|
| Export of services, "64060285 or 64060290" | **64060285 is "Export of services u/s 154A @1%"**. 64060290 is "@ 0.25%", which applies only to IT/ITeS exporters registered with and certified by PSEB. The same in TY2024–TY2026. *Checked in the TY2024 form text during this review.* | Primary | 02 §1a; 01 §1a |
| 3000 | "Income/(Loss) from Business": the total for that head of income, not a receipts line. Export receipts reach it through the business final-tax column. | Primary | 02 §1b |
| How 64060285 is filled | One line with three columns: receipts (col 1) and tax deducted (col 2). IRIS computes tax chargeable (col 3). | Primary | 02 §1b |
| 500312 / 64040052 | **500312** is Profit on Debt under Other Sources. **64040052** is the final-tax line for bank profit when total profit is ≤ Rs 5m: gross profit in col 1, s.151 tax in col 2. Above Rs 5m, profit moves to the normal regime and its tax to the adjustable line **64040002**. | Primary (500312 unreadable in the TY2026 scan) | 02 §1c; 01 §Q2 |
| Profit-on-debt tax rate | **TY2026: 20%** (40% if not on the Active Taxpayers' List, ATL). TY2025: 15% (35%). *Checked in FBR Circular 01 of 2025-26, para 26, during this review.* | Primary | 01 §Q2 |
| 9201 | "Withholding Income Tax", **calculated by IRIS**, not entered. Use it as a check total. | Primary | 02 §1d |
| Withholding lines the brief leaves out | **Salary (s.149):** 64020004. **Card payments abroad (s.236Y):** 64151905 (adjustable; 5% ATL / 10% non-ATL in TY2026). **Cash withdrawal (s.231AB):** 64100101 (non-ATL only; TY2026 code unverified). **s.154A:** no line of its own; the tax goes in col 2 of 64060285. | Primary | 02 §Q2; 01 §Q3, §Q6 |
| 7006 | Correct for TY2025: Investment (Non-Business), Form "Account". **TY2026 regrouped** bank accounts under "Financial Assets & Investments (Non-Business) → Bank Account(s)", entered by IBAN, title and bank name. That code is unreadable in FBR's scan. | Primary to TY2025; unverified for TY2026 | 02 §1e, §Q3 |
| Line texts: "Profit on Debt u/s 151(1)(b) … Investment in [Bank]" and "\<IBAN\> - \<TITLE\> - \<BANK\> - Self" | Not found in any FBR document. They look like how IRIS displays an entry; treat them as editable templates. | Unverified | 02 §1c, §Q3 |
| Zakat (not in brief) | Deductible allowance **9001** "Zakat u/s 60", not a tax. It reduces normal-regime income (mainly salary) and never reduces final-tax income. | Primary (TY2026 code unverified) | 01 §Q4; 02 §Q4 |

### 2.2 Statements

| Brief | Finding | Evidence |
|---|---|---|
| All statements are PDF | **MCB Live:** PDF **or CSV**. **NayaPay:** PDF **or CSV**. **Meezan:** internet banking offers "different formats", and two open-source tools parse its CSV/XLSX exports. **SadaPay:** only PDF is documented. | 03 Summary |
| Meezan: [Booking Date, Description, Credit, Debit, Available Balance] | Matches the 2026 app PDF. Meezan has **three** layouts: app PDF, CSV (with Debit *before* Credit) and the older e-statement. MCB has two layouts, as does SadaPay. | 03 §Q2 |
| NayaPay: no opening/closing balance | Public samples show **Opening and Closing Balance** on the summary card. Check the owner's file. | 03 §Q2 |
| SadaPay: no balances | Confirmed. The app generates a statement for any date range from 1 Jul 2023, so request exactly 1 Jul – 30 Jun. | 03 §Q1 |
| "I'll unlock before upload" | Not needed. pdfplumber opens RC4, AES-128 and AES-256 PDFs in memory with the password, so no unlocked copy is written to disk. The MCB Live PDF password is the last 4 digits of the account number. | 04 §Q2; 03 §Q2 |

## 3. Gaps the tool will hit

None of these are in the brief. §5 has a proposed fix for each.

| # | Gap | Why it matters |
|---|---|---|
| G1 | **Several statements per account** (monthly files, overlapping periods, missing months) | Overlaps double-count and gaps drop transactions. Row-level de-duplication is also wrong: two identical Rs 1,000 top-ups on one day are both real. Overlaps must be resolved per statement period. |
| G2 | **Statement period ≠ tax year** | When a statement straddles the year boundary, the 1 Jul and 30 Jun balances must come from the running balance at the boundary, not from the printed opening or closing. |
| G3 | **No list of the owner's own accounts** | Wealth-statement lines and internal-transfer detection both need the owner's IBANs, account numbers, wallet numbers and titles. That includes own accounts with no uploaded statement (Payoneer, Wise, JazzCash). This is PII and must stay separate from the shareable bank profiles. |
| G4 | **Salary credits** | Monthly net-pay credits would flood the manual-review list. Gross salary and s.149 tax come from the employer's certificate, never from statements. |
| G5 | **Reversals and refunds** | "REFUND/", "Reversed" and failed-transfer reversals are credits, but not income. |
| G6 | **Family money vs export proceeds** | Family money booked as export income overstates income and the 1% tax. Export income booked as family money understates income and can breach the Rs 5m limit in s.111(4). |
| G7 | **s.154A tax actually deducted** | The bank may deduct 1% on realization, as a separate debit or netted into the credit. For credits routed through an e-money wallet (SadaPay, NayaPay) it may deduct nothing. The tool must report the tax deducted, the 1% expected and the shortfall. |
| G8 | **Zakat, FED and sales tax on bank charges** | These must be detected and kept **out** of withholding totals. Zakat is a deductible allowance, and FED and sales tax aren't income tax. |
| G9 | **Foreign balances** (Payoneer/Wise at 30 June) | The wealth statement must include foreign assets, and TY2026 has a separate 116A tab for them. They are entered by hand. |
| G10 | **Review decisions lost on re-run** | Confirming hundreds of matches is real work. Decisions must persist locally, keyed by a stable transaction ID. |
| G11 | **No home for manual inputs** | Cash in hand, salary-certificate figures, wallet opening anchors and foreign balances need explicit fields. Left blank, they appear blank in the export, never guessed. |
| G12 | **Scanned or broken-font PDFs** | Detect them and stop with a clear message, rather than guess. |
| G13 | **Codes change every year** | TY2025 → TY2026 regrouped the wealth statement, and the live IRIS form overrides the published form. |
| G14 | **Wealth reconciliation** | s.116(2) requires one. The tool can supply the inflows (final-tax receipts, remittances) and flag the s.111(4A) "imputable income" limit. |

## 4. Risks

| # | Risk | Mitigation |
|---|---|---|
| R1 | A parsing error silently changes a total | Reconcile every statement: the running balance on each row, opening + credits − debits = closing, and the printed totals. Any failure blocks that statement's numbers and is listed on a Checks sheet. |
| R2 | Columns are misassigned, flipping credits and debits (Meezan's amounts are unsigned) | Column bands anchored on the header row are the main signal. The change in balance validates every row. Ambiguous tokens are flagged, never guessed. |
| R3 | Misclassification over- or under-states income | Every classification records a rule ID and a reason. Income categories stay proposals until the owner confirms them. Anything unknown goes to review. |
| R4 | False internal-transfer matches | Match one to one and score by amount, date and description. Nothing is excluded until the owner confirms it. |
| R5 | Keyword collisions ("otherwise" contains "wise") | Word-boundary regexes (`\bWise\b`) on credits only, run through Python `re`. |
| R6 | A bank changes its layout | One profile per layout rather than per bank, each with `valid_from`, a header signature and sample lines it must parse. Prefer CSV where available. |
| R7 | Financial data leaks | Lock Streamlit down: no usage stats, loopback only, no external-IP lookup. Never put passwords on a command line. Build the Excel file in memory. Git-ignore statements and the account registry. Use synthetic test fixtures only. A pre-commit check blocks IBAN and CNIC patterns. |
| R8 | FBR changes a form or a rate | Per-tax-year config, with a citation and a "verified in IRIS" flag for each code. Rates only drive sanity checks; they never produce a figure for IRIS. |

## 5. Proposed changes

For each change, reply accept, change or reject. The phases are in §6.

| # | Change | Replaces / extends | Phase |
|---|---|---|---|
| P1 | **Accept CSV/XLSX as well as PDF.** One profile per *layout*, detected by its header signature, with columns mapped by header name. | "All statements are PDF" | 1 |
| P2 | **Enter PDF passwords in the app.** Decrypt in memory and drop the "unlock before upload" step. | Workflow step | 1 |
| P3 | **Account registry** (local, git-ignored), kept separate from the bank profiles. Fields: nickname, institution, IBAN, account number, wallet number, title, type, ownership, currency, and whether a statement is expected. | New | 0 |
| P4 | **Reconciliation layer** (covers R1, G1, G2): per-row running balance, statement totals, printed totals, period coverage (gaps and overlaps), and clipping to the tax year with boundary balances. A **Checks** sheet lists every check as pass or fail. | Output §6 sanity check | 0–1 |
| P5 | **Wider classification.** Categories:<br>• export proceeds (proposed, confirmed per counterparty)<br>• personal remittance (tracked against Rs 5m)<br>• profit plus its paired WHT (sanity check: ~20% in TY2026)<br>• s.154A tax deducted<br>• salary (by employer pattern)<br>• reversal/refund<br>• Zakat<br>• FED, sales tax and bank charges<br>• internal transfer<br>• transfer to an own account with no statement<br>• unclassified | Classification §1–5 | 3 |
| P6 | **Split the withholding summary into three groups.**<br>• **Final:** 64060285 col 2 and 64040052 col 2.<br>• **Adjustable:** 64020004, 64151905 and 64100101, plus 64040002 if profit > Rs 5m.<br>• **Not income tax:** Zakat, FED and bank charges.<br>9201 appears as a computed check total. | Output §3 | 5 |
| P7 | **Show export income as IRIS cells**: 64060285 col 1 = receipts, col 2 = tax deducted, with evidence. Show the 1% expected and any shortfall, labelled "confirm with advisor". | Output §1 | 5 |
| P8 | **Per-tax-year code config** (`TY2025`, `TY2026`, …). For each code: the code as a string, its verbatim label, section, column meanings, source and verification status. The TY2026 bank-account code stays blank until the owner reads it off IRIS. | Hard-coded codes | 0 |
| P9 | **Optional evidence documents:** Rule 42 WHT certificates (one generic parser), Meezan's tax-deduction certificate, the NayaPay 236Y certificate, S-PRC/e-PRC, and IRIS's own withholding export if available. They cross-check the numbers taken from statements, and the PRC purpose code settles export versus family money. | Classification §3 (236Y only) | 4 |
| P10 | **Manual inputs page:** salary certificate (gross salary, s.149 tax), wallet opening anchors, cash in hand, foreign balances (Payoneer/Wise) and last year's closing balances. A blank stays blank. | "Leave blank for manual entry" | 5 |
| P11 | **Persist review decisions** in a local, git-ignored file keyed by a stable transaction ID. | New | 3 |
| P12 | **Excel export only; drop PDF.** Add sheets for Checks, Sources (file name, SHA-256, period, pages), Manual inputs and Warnings. | Output "PDF or Excel" | 5 |
| P13 | **Store money as integer paisa.** Use `Decimal` only while parsing text. | Implicit | 0 |
| P14 | **Privacy hardening**, as in R7. | "Store nothing remotely" | 0 |
| P15 | **Wealth-reconciliation helper** (optional): compare the change in net assets with inflows (final-tax receipts, remittances) and outflows, and flag the s.111(4A) limit. | New | 6 |

## 6. Revised build order

The brief's order stays. A foundation phase comes first, and outputs are defined per IRIS cell.

0. **Foundation:** normalized transaction model (integer paisa, with provenance), account registry, tax-year config, reconciliation engine, a generator of synthetic statements for tests, and the privacy defaults.
1. **Meezan + MCB:** CSV first if the owner can export it, then the PDF layouts. Every statement must reconcile.
2. **SadaPay + NayaPay:** SadaPay PDF with an anchored opening balance; NayaPay CSV or PDF.
3. **Classification + review:** the rules in P5, with decisions persisted (P11).
4. **Internal-transfer matcher:** one to one, scored, confirm or reject. The optional evidence documents (P9) fit here or after phase 5.
5. **Outputs + Excel:** the IRIS-cell summary (P6–P8), manual inputs (P10), and the Checks and Sources sheets (P12).
6. **Streamlit polish + reconciliation helper** (P15).

The UI grows phase by phase instead of arriving last. Each phase adds its screen: upload → accounts → checks → review → summary.

## 7. Kept exactly as briefed

- No expense categorisation; only a per-account "other debits" reference total.
- No submission to FBR or IRIS; the output is for manual entry.
- No guessing cash in hand or personal items.
- Streamlit UI, pandas, and Excel with one tab per section plus raw transactions.
- User-editable bank profiles, now one per layout, in TOML.
- Manual-review threshold of Rs 10,000, configurable.
