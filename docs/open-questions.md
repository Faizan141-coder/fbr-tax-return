# Open Questions — FBR Tax Return Data Aggregator

> **Status:** 27 Sep 2026.
> - §A was answered on 27 Sep 2026.
> - §B lists the defaults that will be used unless the owner objects.
> - §C is information only the owner can look up.
> - §D is for a tax advisor.
>
> **Context:** [spec-review.md](spec-review.md), [requirements.md](requirements.md)

## A. Decisions that shape the design (answered 27 Sep 2026)

| # | Question | Why it matters | Options | Recommended | Answer |
|---|---|---|---|---|---|
| Q1 | TY2026 returns are due 30 Sep 2026, with no extension announced. Is this build for this filing or the next one? | Decides whether we build a quick minimum version or the full tool. | (a) Next season, using the TY2026 statements as the test set<br>(b) This filing: a thin minimum version in about 2 days | (a). A rushed tax tool is how wrong numbers get filed. | **(a) Next season** |
| Q2 | How should Claude see the real statement layouts during development? | Parsers have to be built against real layouts. Anything Claude reads is sent to Anthropic as part of the conversation. | (a) Masked layout dumps: a local script replaces names, digits and amounts, and Claude reads only its output<br>(b) Claude reads the real files<br>(c) Synthetic statements only; the owner tests locally and reports mismatches | (a) | **(a) Masked layout dumps** |
| Q3 | Which inputs should v1 accept? | CSV removes most parsing risk for 3 of the 4 institutions. | (a) CSV/XLSX first, PDF where needed<br>(b) PDF only, as briefed<br>(c) Both, cross-checked | (a) | **(a) CSV/XLSX first** |
| Q4 | Are all the Payoneer, Wise, Remitly and Thunes credits work income, or is some of it family or personal money? | Sets the default category for foreign credits. | (a) All work income<br>(b) Some personal<br>(c) Not sure | No recommendation: this is a question of fact. | **(a) All work income** |

**What the answers mean for the design**

- **Q1 → no rush.**
  - The owner files TY2026 the usual way, and those already-filed numbers become the tool's acceptance test: the tool must reproduce them or explain every difference.
  - TY2026 is the first tax-year config.
  - The TY2027 config is added when FBR notifies next year's form, around mid-2027.
- **Q2 → a masking tool is needed before any parser.**
  - It is a small local dev tool, built in Phase 0. It reads a statement and writes a *layout dump*: word positions, column headers and value *formats* (e.g. `9,999.99Dr`, `DD Mon YYYY`), with names, digits and amounts replaced.
  - Claude reads only those dumps, never the original files.
  - Real statements live outside the repo.
- **Q3 → the tabular engine comes first.**
  - It reads CSV/XLSX for MCB Live, NayaPay and Meezan.
  - The PDF engine starts with SadaPay, whose amounts are signed (the easy PDF case). PDF layouts for the other banks are fallbacks, added later.
- **Q4 → foreign-channel credits default to `export_proceeds_154A` at 1%.**
  - They still appear, itemised, in the review list.
  - The personal-remittance category stays available for manual reclassification, but nothing defaults to it.

## B. Defaults unless the owner objects

| # | Topic | Default | Why |
|---|---|---|---|
| Q5 | Statement files | Support both monthly and yearly files per account, and detect gaps and overlaps. | Either may turn up. |
| Q6 | Salary | Credits that match the employer's name are labelled "net salary". Gross salary and s.149 tax are entered from the employer's certificate. | Keeps the review list short. The gross figures exist only on the certificate. |
| Q7 | Evidence documents (WHT certificates, S-PRC) | Phase 4, optional, used only for cross-checks. | The core pipeline comes first. |
| Q8 | Review decisions | Saved locally in a git-ignored file. | A re-run keeps earlier review work. |
| Q9 | Export format | Excel only. | The brief allows PDF or Excel; Excel is the audit format. |
| Q10 | Python environment | Homebrew Python 3.14 in a project venv managed by uv (`brew install uv`). Fallback: plain `venv` + `pip`. | System Python 3.9.6 can't run current Streamlit or pandas. |
| Q11 | Transfer matching | Match exact amounts first. A configurable fee tolerance (starting at Rs 100) catches netted fees; those matches are marked lower-confidence. Dates within 0–3 days, strictly one to one. | Follows the brief. The Rs 100 starting value is an assumption to tune on real data. |
| Q12 | Review threshold | Rs 10,000, configurable. | As briefed. |
| Q13 | ATL status | Assume the owner is on the Active Taxpayers' List. Expected bank-profit WHT is then 20% for TY2026. | The owner files every year. The rate is used only for sanity checks. |
| Q14 | Foreign-currency (ESFCA) accounts | Out of scope unless the owner has one. | Freelancers may keep up to 50% of proceeds, or USD 5,000 a month, in an exporter's foreign-currency account (ESFCA). If the owner has one, its statements matter. |
| Q15 | Payoneer / Wise balances | Entered by hand in a foreign-assets section. | They don't appear on Pakistani statements. |
| Q16 | Git | Nothing has been committed. Commit only when the owner says so. | The owner's call. |

## C. Things only the owner can look up

| # | What | Where | Used for |
|---|---|---|---|
| A1 | The TY2026 wealth-statement code for bank accounts | IRIS → Wealth Statement → Financial Assets & Investments (Non-Business) → Bank Account(s) | P8 code config |
| A2 | Whether the NayaPay statement shows opening and closing balances | The summary card of the owner's own statement | The NayaPay profile and opening anchors |
| A3 | The TY2025 closing balance of each account | Last year's filed wealth statement | Opening anchors for TY2026, especially SadaPay |
| A4 | Whether 1% was deducted from any foreign credit | Look for a tax debit next to the credit, or a credit smaller than the PRC amount | Tax deducted vs expected (G7) |
| A5 | (Optional) WHT certificates and S-PRCs | Meezan: WhatsApp or Net Banking. MCB Live: Certificates. NayaPay app: Statements. SadaPay: in-app chat, up to 5 working days | P9 cross-checks |

## D. For a tax advisor

The tool reports these; it won't decide them.

| # | Question | Research |
|---|---|---|
| T1 | s.154A tax is final only if sales-tax returns have been filed "if required". Does that condition apply to the owner as a non-PSEB individual exporting services? If it applies and isn't met, the 1% is no longer a final tax. | [01 §1b](research/01-fbr-tax-rules.md) |
| T2 | How to pay any s.154A shortfall through IRIS, e.g. 1% not deducted on wallet-routed credits. | [01 §1c](research/01-fbr-tax-rules.md) |
| T3 | How to treat export earnings still held in Payoneer or Wise at 30 June. | [01, open question 7](research/01-fbr-tax-rules.md) |
| T4 | Are s.154A "proceeds" the rupees realized, or the gross invoice before platform fees? | [01, open question 8](research/01-fbr-tax-rules.md) |
| T5 | How FBR applies the s.111(4A) imputable-income limit to a freelancer's wealth reconciliation. | [01 §Q5](research/01-fbr-tax-rules.md) |
