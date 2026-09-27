# Original Brief — FBR Tax Return Data Aggregator

> **Source:** requirements written by the project owner, pasted on 2026-09-27. The wording below is the owner's, reformatted as Markdown. Only the two amendments listed here change it.
>
> **Amendments**
> 1. **The export-of-services rate is 1%, not 0.25%.** The owner confirmed this on 2026-09-27, which settles the "ask me which rate applies" item in Output §1. [research/02-fbr-iris-codes.md](research/02-fbr-iris-codes.md) records which IRIS code carries the 1% rate.
> 2. In this copy, the account digits of the example IBAN in §6 are masked. The line format is unchanged.
>
> The review of this brief, covering gaps, risks and proposed changes, is in [spec-review.md](spec-review.md). Open questions are in [open-questions.md](open-questions.md). The approved design is in [superpowers/specs/2026-09-27-fbr-aggregator-design.md](superpowers/specs/2026-09-27-fbr-aggregator-design.md).

---

# Project: FBR Tax Return Data Aggregator (Pakistan — Individual Return 114(1))

## Context

I'm a Pakistani resident individual taxpayer (IT/software exporter + salaried employee) who files FBR Return 114(1) annually. My income touches multiple bank/wallet accounts (currently: Meezan Bank, MCB, SadaPay, NayaPay — more may be added later, e.g. JazzCash, EasyPaisa). Every year I manually extract figures from PDF bank statements to fill in FBR's return and wealth statement forms. I want a tool that automates the extraction and aggregation, leaving only genuinely manual items (cash in hand, personal items, expense categorization) for me to confirm.

## Core requirement

Build a local app (web UI is fine, doesn't need to be hosted) where I:

1. Upload one or more bank/wallet PDF statements for a fiscal year (1 Jul–30 Jun)
2. The app parses each statement and extracts structured transaction data
3. The app classifies and aggregates transactions into FBR-relevant buckets
4. The app outputs a clean summary mapped to FBR field codes, ready to copy into the IRIS portal, plus a per-account breakdown so I can sanity-check every number

## Statement formats to support (varies significantly by institution — must be format-agnostic, not hardcoded to one layout)

- **Meezan Bank:** table format, columns [Booking Date, Description, Credit, Debit, Available Balance]. Opening/Closing balance printed once at top of statement.
- **MCB:** table format, columns [Date, Description, Reference Number, Amount (with Dr/Cr suffix), Balance]. Opening/Closing balance printed once at top.
- **SadaPay:** table format, columns [Date, Description, Debit/Credit (signed with +/-)]. Only prints Total Debit / Total Credit at top — NO opening/closing balance shown anywhere. (This is a known gap — the app should compute a running balance from transactions and let me manually anchor day-1 opening balance if I supply it.)
- **NayaPay:** similar to SadaPay — Total Income / Total Spent at top, transaction-level running balance in the ledger.
- All statements are PDF, sometimes password-protected (I'll unlock before upload).
- Use pdfplumber or `pdftotext -layout` as extraction base; the layout is not perfectly consistent column-to-column so use regex/heuristic parsing rather than fixed column indices.

## Classification logic (this is the important part)

### 1. Foreign remittance / export income detection

Flag any CREDIT transaction whose description contains any of:
`"Thunes"`, `"Payoneer"`, `"Remitly"`, `"Wise"`, `"Inward Foreign Remittance"`, `"PAYONEER payment"`, `"IBFT In...from Thunes"`

These represent export-of-services receipts (Sec 154A). Sum per account and grand total. Also capture: date, reference/STAN number, source label — I need an itemized list, not just a total, for audit trail purposes.

### 2. Profit on Debt detection

Flag any CREDIT transaction whose description contains:
`"Payment of Profit"` (Islamic bank profit) OR `"PROFIT-LOSS"` (conventional bank)

For each, find the paired same-date WHT debit:
`"Withholding Tax Debit"` OR `"WHT COLL: UNDER SEC 151"`

Output: gross profit, tax withheld, net — per bank account AND combined total, matching this exact structure (mirror how FBR itemizes it):

> "Profit on Debt u/s 151(1)(b) from Bank Accounts/Deposits - Profit on Savings Account - Investment in [Bank Name]"

### 3. International card transaction tax (Sec 236Y)

This typically comes from a SEPARATE tax certificate PDF, not the statement itself (e.g. NayaPay issues "Certificate of collection of tax... Rule 42"). Support uploading this as an optional separate document type and extract: "On the amount of Rs. X" and "Rs. Y" tax collected.

### 4. Internal transfer de-duplication (CRITICAL — do not skip this)

Many credits/debits are just money moving between MY OWN accounts (e.g. Meezan → MCB, SadaPay → NayaPay). These must NOT be double-counted as income.

Approach:

- Build a combined transaction list across all uploaded statements for the same fiscal year.
- Match candidate pairs: a debit on Account A and a credit on Account B where
  - (a) amounts are equal or very close (allow for bank IBFT fees, e.g. debit 200,000 exactly matching credit 200,000, or debit matching credit minus a small fee),
  - (b) dates are within 0-3 days of each other,
  - (c) descriptions reference the counterparty account (e.g. contains "MUHAMMAD FAIZAN HASNAAT" + partial IBAN/account number match, or contains the other bank's name).
- Flag matched pairs as "internal transfer — excluded from income" and show them in a separate reviewable list (don't just silently delete them — I need to see and confirm each match, since false positives are possible).
- Any credit that looks like income (foreign remittance / profit) but is ALSO matched as an internal transfer should raise a warning, not be auto-classified either way.

### 5. Unclassified / ambiguous entries

Any credit above a configurable threshold (default 10,000 PKR) that doesn't match remittance, profit, or a confirmed internal transfer should be flagged in a "needs manual review" list with full description text, rather than being silently excluded or silently counted as income.

### 6. Wealth Statement inputs

Per account, output:

- Closing balance as of 30 June (from statement's own stated closing balance where available; for SadaPay/NayaPay which don't print an opening/closing balance, compute from the last transaction's running balance column if present, or from opening balance I manually enter + net of Total Credit − Total Debit)
- Opening balance as of 1 July (same logic, for year-over-year comparison)

Map each account to its FBR wealth statement line using account nickname + IBAN, formatted exactly like:

> "PK96MEZN0003XXXXXXXX3474 - MUHAMMAD FAIZAN HASNAAT - MEEZAN BANK LIMITED - Self"

## Output format

A single results screen/export (PDF or Excel) with these sections, each showing the FBR field code alongside the computed value:

1. **INCOME FROM BUSINESS (Export of Services)**
   - Itemized remittance list (date, source, account, amount)
   - Total → maps to code 3000 / 64060285 or 64060290 (ask me which rate applies) → **Resolved: the 1% rate applies (see Amendment 1).**
2. **INCOME FROM OTHER SOURCES (Profit on Debt)**
   - Per-bank breakdown: gross profit, WHT deducted, net
   - Total → maps to code 500312 / 64040052
3. **ADJUSTABLE TAX / WITHHOLDING SUMMARY**
   - All WHT found (profit on debt tax, Sec 236Y if uploaded)
   - Total withholding income tax → maps to code 9201
4. **WEALTH STATEMENT — BANK ACCOUNTS**
   - Per account: opening balance, closing balance, net change
   - Maps to code 7006 entries
5. **FLAGGED FOR REVIEW**
   - Internal transfer matches (confirm/reject)
   - Unclassified large credits
   - Any statement where opening/closing balance couldn't be determined automatically (missing data warning)
6. **TOTAL DEBIT / TOTAL CREDIT per account** (sanity-check figure — should match the "Total debit" / "Total credit" printed on each statement's cover page if the statement has one, as a parsing-correctness check)

## Tech preferences

- Python backend (pdfplumber or pymupdf for PDF parsing, pandas for aggregation)
- Simple local web UI (Streamlit is fine — I don't need this deployed anywhere, just running on my machine each tax season)
- Store nothing remotely — all processing local, since this is financial/PII data
- Let me save named "bank profiles" (regex patterns per bank) so if a bank changes their statement format next year I can update the parser without touching the core logic
- Export the final summary as an Excel file with one tab per section above, plus a "raw transactions" tab with every parsed row and its classification, so I have a full audit trail to defend the numbers if FBR ever asks

## What NOT to build

- Don't try to auto-categorize personal expenses (rent, travel, utilities) — that requires judgment I'll enter manually. Just give me the total non-remittance, non-profit, non-internal-transfer debit sum per account as a starting reference number.
- Don't submit anything to FBR/IRIS automatically — output is for me to manually enter into the portal.
- Don't guess at cash-in-hand or personal items values — leave blank for manual entry.

## Build order (owner's)

Start by building the PDF parser for Meezan and MCB formats first (since those have clean opening/closing balances and Dr/Cr or Credit/Debit columns), then add SadaPay/NayaPay support, then the remittance/profit classification layer, then the internal-transfer matcher, then the export.
