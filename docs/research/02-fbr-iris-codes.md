# FBR IRIS field codes: individual return (s.114(1)) and wealth statement (s.116 / s.116A), TY2025 and TY2026

## Scope & date researched

- **Researched:** 27 September 2026.
- **Tax years covered:** TY2025 (1 Jul 2024 – 30 Jun 2025, the year the owner's codes were probably copied from) and TY2026 (1 Jul 2025 – 30 Jun 2026, the return being filed now). I also checked TY2024 and TY2019 forms to see whether the codes stay the same from year to year.
- **Questions:** what the brief's codes (3000, 64060285, 64060290, 500312, 64040052, 9201, 7006) mean; the withholding codes for s.236Y, s.151, s.149 and s.154A; the wealth-statement codes and fields for bank accounts, cash and foreign assets; the Zakat code; and whether codes change between years.
- **Method:** I read FBR's own notifications (the SROs that add each year's return forms to the Second Schedule of the Income Tax Rules, 2002) from `download1.fbr.gov.pk`, plus FBR's IRIS manual and FAQ from `e.fbr.gov.pk`. The TY2024 and TY2019 forms have a text layer. The TY2025 and TY2026 forms are screenshots of the IRIS screens embedded as images, so I read them with OCR (tesseract 5.5), in memory. The TY2026 final SRO is a low-quality photocopy scan. Where a TY2026 digit was hard to read, the finding says so, along with how I cross-checked it.
- **Not done:** I had no access to the live IRIS portal, so nothing here comes from logging in. FBR says the form inside IRIS can change after the SRO is issued (see Q5), so what the owner's IRIS screen shows overrides this document.
- **Privacy:** I searched only public code numbers and generic terms. No owner data went into any search, URL or tool.
- **Confidence tags:** **[PRIMARY]** means read directly in an FBR document (SRO, FBR manual, FAQ or statute page). **[PRIMARY, scan]** means an FBR document read by OCR from a poor scan, with the digits cross-checked as noted. **[SECONDARY]** means a tax-consultant blog or news source. **[UNVERIFIED]** means I could not confirm it; treat it as unknown.

## Summary

**Answer to the key question:** **64060285 is the 1% line ("Export of services u/s 154A @1%"). 64060290 is the 0.25% line ("Export of IT/ITeS Services u/s 154A @ 0.25%").** The mapping is the same in TY2024, TY2025 and TY2026. The owner has confirmed the 1% rate, so the code to use is **64060285**.

| Code | Meaning (IRIS label, verbatim where read) | Section of return | Tax year(s) seen | Confidence | Source |
|---|---|---|---|---|---|
| **64060285** | Export of services u/s 154A @1% | Tax Chargeable / Payments → Fixed / Final Tax (also listed on the "Option out of PTR" tab) | TY2024 (paper), TY2025, TY2026 | [PRIMARY] (TY2026: [PRIMARY, scan]) | [SRO 950/2024][S950] p.6; [SRO 1562/2025][S1562] p.62, p.70; [SRO 1495/2026][S1495] p.15, 31, 69, 100 |
| **64060290** | Export of IT/ITeS Services u/s 154A @ 0.25% (TY2024 paper label: "Export of services u/s 154A @ 0.25%") | Same as above | TY2024 (paper), TY2025, TY2026 | [PRIMARY] (TY2026: [PRIMARY, scan]) | Same as above |
| **3000** | Income / (Loss) from Business (the head-of-income total, not a receipts line) | Data → Business (top line) and Computations | TY2024 (paper), TY2025, TY2026 | [PRIMARY] (TY2026: [PRIMARY, scan]) | [S950] p.3; [S1562] p.49, p.65; [S1495] p.36 |
| **500312** | Profit on Debt (Other Sources → Receipts). The TY2022 and TY2024 paper forms label it "Profit on Debt (if amount u/s 7B exceeds Rs. 36 million)" | Data → Other Sources → Receipts / Deductions | TY2022 and TY2024 (paper), TY2025; TY2026 not legible in the individual return | [PRIMARY] for TY2025; [UNVERIFIED] for the TY2026 individual return | [S1562] p.55; [S950] p.3; [S2022]; [S835] p.131 |
| **64040052** | Profit on Debt u/s 151(1)(b) from Bank Accounts / Deposits @15% (amount not exceeding 5 million) | Fixed / Final Tax | TY2025, TY2026 | [PRIMARY] (TY2026: [PRIMARY, scan]) | [S1562] p.61; [S1495] p.23 |
| 64040002 | Profit on Debt u/s 151(1)(b) from Bank Accounts / Deposits @15% | Adjustable Tax | TY2025, TY2026 | [PRIMARY] (TY2026: [PRIMARY, scan]) | [S1562] p.59; [S1495] p.29 |
| **9201** | Withholding Income Tax (IRIS calculates this total; it is not typed in) | Tax Chargeable / Payments → Computations | TY2025, TY2026 (and the 2023 IRIS manual) | [PRIMARY] | [S1562] p.65; [S1495] p.36; [IRIS manual][MAN] p.8 |
| 64151905 | Persons remitting amount abroad through credit / debit / prepaid cards u/s 236Y | Adjustable Tax | TY2019 (paper), TY2025, TY2026 | [PRIMARY] (TY2026: [PRIMARY, scan]) | [S1160] p.10; [S1562] p.60; [S1495] p.30 |
| 64020004 | Salary of Employees u/s 149 | Adjustable Tax | TY2025, TY2026 | [PRIMARY] | [S1562] p.59; [S1495] p.4, p.29; [MAN] p.7; [FAQ] |
| 64100101 | Advance tax on cash withdrawal u/s 231AB | Adjustable Tax | TY2024 (paper), TY2025 | [PRIMARY]; [UNVERIFIED] for TY2026 | [S950] p.8; [S1562] p.59 |
| 9001 | Zakat u/s 60 (inside 9009 Deductible Allowances) | Tax Chargeable / Payments → Deductible Allowances | TY2019 and TY2024 (paper), TY2025; TY2026 shows the description only | [PRIMARY]; [UNVERIFIED] for the TY2026 code | [S1562] p.56; [S950] p.2–3 |
| **7006** | Investment (Non-Business) (Account / Annuity / Bond / Certificate / Debenture / Deposit / Fund / Instrument / Policy / Share / Stock / Unit, etc.). A bank account is entered as Form "Account". | Wealth Statement → Personal Assets / Liabilities | TY2019 to TY2025. In TY2026 this section was regrouped and the code could not be read. | [PRIMARY] up to TY2025; [UNVERIFIED] for TY2026 | [S950] p.22; [S1562] p.66; [S1160] p.21–22; [S1495] p.38 |
| 7012 | Cash (Non-Business) ("Notes & Coins") | Wealth Statement | Up to TY2025 | [PRIMARY]; [UNVERIFIED] for TY2026 | [S950] p.24; [S1562] p.66 |
| 7016 | Assets held outside Pakistan | Wealth Statement (s.116) and the s.116A declaration | TY2024, TY2025 | [PRIMARY]; [UNVERIFIED] for TY2026 | [S950] p.25; [S1562] p.66, p.78 |
| 701902 / 702901 | Total Foreign Assets / Total Foreign Liabilities | 116A – Foreign Assets / Liabilities tab | TY2026 | [PRIMARY, scan] | [S1495] p.37 |
| 7033 | Income Attributable to Receipts, etc. Declared as per Return for the year subject to Final / Fixed Tax | Reconciliation of Net Assets → Inflows | TY2019, TY2024, TY2025 | [PRIMARY]; [UNVERIFIED] for TY2026 | [S1562] p.67; [S950] p.26 |
| 7035 | Foreign Remittance | Reconciliation of Net Assets → Inflows | TY2019, TY2024, TY2025 | [PRIMARY]; [UNVERIFIED] for TY2026 | [S1562] p.67; [S950] p.26 |
| 640000 / 64000101 / 920100 | Schedule totals: Adjustable Tax / Fixed / Final Tax / "Final / Fixed / Minimum / Average / Relevant / Reduced Income Tax" (Computations) | Tax Chargeable / Payments | TY2025, TY2026 | [PRIMARY] (TY2026: [PRIMARY, scan]) | [S1562] p.59, 61, 65; [S1495] p.31, 36 |

Page numbers ("p.") are PDF page indexes. Each source reference links to the PDF.

## Detailed findings

### Q1. What the brief's codes mean in TY2025 and TY2026

#### 1a. 64060285 and 64060290: which is the 1% line

- **TY2025 e-return for individuals (SRO 1562(I)/2025, Part-II-ZC):** on the Fixed / Final Tax schedule the lines read "Export of IT/ITeS Services u/s 154A @ 0.25% — 64060290" and "Export of services u/s 154A @1% — 64060285". The "Option out of PTR" tab repeats "Export of services u/s 154A @1% 64060285" and "Export of Services u/s 154A @ 0.25% 64060290". [PRIMARY] ([S1562] p.62, p.70)
- **TY2024 paper return (SRO 950(I)/2024, IT-2 page 2/2):** row 109 is "Export of services u/s 154A @ 0.25% — 64060290" and row 110 is "Export of services u/s 154A @ 1% — 64060285". [PRIMARY] ([S950] p.6)
- **TY2026 e-return for individuals (SRO 1495(I)/2026, Part-II-ZE):** the same two labels appear on two screens of the individual return. On p.31 they sit under a "Final Tax 64000101" heading. On p.15 the screen appears to be a Business-side "Tax Deductions" list with Final Tax and Minimum Tax headings (p.14). The 0.25% code reads "64060290" at 600 dpi. The last digit of the 1% code is hard to read on the individual-return pages ("6406028?", "640692 85"). The AOP and company returns in the same SRO list the same two lines clearly as 64060285 (1%) and 64060290 (0.25%). [PRIMARY, scan] ([S1495] p.15, p.31; cross-check p.69, p.100)
- **Secondary agreement:** a Pakistani tax blog (Sep 2025) says the "code for 1% tax is 64060285 and for 0.25% code is 64060290". [SECONDARY] ([accountingblogger][AB])
- **Label change worth noting:** from TY2025 the 0.25% line names **IT/ITeS** services specifically. The owner, an IT/software exporter, has confirmed 1%, so this changes nothing. Whether a taxpayer qualifies for 0.25% is a legal question outside this document; one secondary source ties it to PSEB registration. [SECONDARY]

#### 1b. What the "3000 / 640xxxxx" pairing means

The pair is not "receipts code / tax code". It is **income-head code / tax-schedule line**.

- **3000** is "Income / (Loss) from Business", the total for the head of income. On the Business tab it sits above "Net Revenue … 3029" and "Gross Revenue … 3009". The columns there are *Total Amount | Amount Exempt from Tax / Subject to Fixed / Final Tax | Amount Subject to Normal Tax*. It appears again in Computations. [PRIMARY] ([S1562] p.49, p.65; [S950] p.3)
- **64060285** is a line in the **Fixed / Final Tax** schedule. One line carries three columns: *Receipts / Value | Tax Collected / Deducted | Tax Chargeable*. [PRIMARY] ([S1562] p.61–62)
- FBR's IRIS FAQ gives the entry rule for a final-tax line: enter the amount "in first Column and the amount of Tax deducted against the same code in second Column". IRIS then calculates Tax Chargeable. [PRIMARY] ([FAQ], "Final / Fixed / Minimum / Average / Relevant / Reduced Tax Regimes" answers)
- So export receipts appear twice: as business revenue in the final-tax column, which rolls up to 3000, and as Receipts / Value on 64060285, where the tax is worked out. [PRIMARY for the layout]. I did not verify whether IRIS checks that the two figures match. [UNVERIFIED]
- **TY2026 changes:** the Computations columns are now *Total Income | Subject to Final Tax | Subject to Exemption | Subject to Normal Tax*, and the tax-deduction tables use *Taxable Amount | Tax Deducted | Tax Chargeable*. The codes stay in a separate column. [PRIMARY, scan] ([S1495] p.13, p.20, p.36)
- **Code structure (my reading, not an FBR rule):** the 8-digit 64xxxxxx codes are lines in the tax schedules. 6402xxxx is s.149 salary. 6404xxxx is s.151 profit on debt, with 640400x1–x4 for adjustable and 640400(5)1–(5)4 for final. 6406xxxx covers s.153 and s.154A. 64151xxx is the s.236 family. Four-digit codes (1000–6000) are heads of income, and 70xx codes are the wealth statement. [UNVERIFIED as a rule; each individual code above is PRIMARY]

#### 1c. 500312 and 64040052 (profit on debt)

- **TY2025:** Other Sources → Receipts has the line "Profit on Debt — 500312", with the same three columns as the Business tab (Total / Exempt-or-Final / Normal). [PRIMARY] ([S1562] p.55) The Fixed / Final Tax schedule has "Profit on Debt u/s 151(1)(b) from Bank Accounts / Deposits @15%(amount not exceeding 5 million) — 64040052". Its siblings are 64040051 (151(1)(a), NSC / PO deposits), 64040053 (151(1)(c), Government securities) and 64040054 (151(1)(d), others). [PRIMARY] ([S1562] p.61)
- **TY2026:** "Profit on Debt u/s 151(1)(b) from Bank Accounts / Deposits — 64040052" appears on p.23 (digits read 64040052 twice at 600–800 dpi). The page heading is illegible, but every neighbouring line is a final-regime item (prize bonds, sukuk, dividends, 64040051/53/54). The adjustable version, 64040002, is on a separate list (p.29). [PRIMARY, scan] ([S1495] p.23, p.29) In the individual return's Other Sources screen, the profit-on-debt code is illegible ("5503?"). The TY2026 draft shows "Profit on Debt 500312" in another return type. So 500312 probably carries over, but I have not confirmed it for the TY2026 individual return. [UNVERIFIED] ([S1495] p.21; [S835] p.131)
- **The pairing** is the same idea as 1b: 500312 is the income line under Other Sources, and 64040052 is the final-tax line carrying gross profit, the s.151 tax withheld and the tax chargeable. [PRIMARY for the layout]
- **Which line applies depends on the amount of profit.** In TY2025 the final-tax line is labelled "(amount not exceeding 5 million)". Above that, profit is taxed at normal rates and the withholding moves to the adjustable line 64040002. The older paper forms (TY2022 and TY2024) label 500312 "if amount u/s 7B exceeds Rs. 36 million". The legal threshold is outside this document; the tool should not hardcode it. [PRIMARY for the labels] ([S1562] p.59, 61; [S950] p.3; [S2022]) A Q&A site says the Rs 5 million limit covers all s.7B profit on debt combined, i.e. s.151(1)(a)–(d), but not prizes under s.156. [SECONDARY] ([taxationpk][TPK])
- **The brief's line text** ("Profit on Debt u/s 151(1)(b) from Bank Accounts/Deposits - Profit on Savings Account - Investment in [Bank Name]") is not in the SRO images. FBR's FAQ does confirm that IRIS itemises profit on debt per account through a dialog with "Type", "Form", "Account / Instrument No." and "Institution". The brief's string looks like IRIS showing such an itemised entry, but I could not confirm the exact format. [PRIMARY for the dialog fields ([FAQ]); UNVERIFIED for the string]

#### 1d. 9201

- "Withholding Income Tax — 9201" is in Computations, between "Refund Adjustment … 92101" and "Advance Income Tax 9202". [PRIMARY] ([S1562] p.65; [S1495] p.36, all four OCR reads gave 9201)
- **IRIS calculates it.** FBR's manual shows salary tax entered at 64020004 on the Adjustable Tax tab; after "Calculate", "the amount will be shifted from Admitted Income Tax to Withholding Income Tax" (9201). [PRIMARY] ([MAN] p.7–8)
- **What goes into it:** the TY2025 simplified return defines "Total Withholding Taxes (A + B + C)" as Adjustable (salary, cash withdrawal, credit/debit card, phone/internet), plus Minimum (payment for services), plus Final (profit on bank account, dividends, electricity bill). [PRIMARY] ([S1561] p.10) I infer that 9201 in the full return is the same total, including final-tax deductions such as 64040052's column 2, but I found no FBR text that says so for code 9201 directly. [UNVERIFIED]
- The paper returns use "Tax Paid" (64220057 on IT-1B) instead of 9201, so codes differ between the paper and electronic forms. [PRIMARY] ([S950] p.2; [S1160]; [S2022])

#### 1e. 7006

- **TY2024 paper form:** "6 Investment (Non-Business) [Sum of 6 i to 6 xiii] — 7006". Sub-row "i Account" has types Current, Fixed Deposit, Profit / Loss Sharing and Saving; the other sub-rows are Annuity, Bond, Certificate, Debenture, Deposit (Term Deposit), Fund, Instrument, Insurance Policy, Security, Stock / Share, Unit and Others. The columns are *Form | Account / Instrument No. | Institution Name / Individual CNIC | Share % | Code | Value at Cost*. [PRIMARY] ([S950] p.22) The TY2019 form is identical. [PRIMARY] ([S1160] p.21–22)
- **TY2025 e-return:** "Investment (Non-Business) (Account / Annuity / Bond / Certificate / Debenture / Deposit / Fund / Instrument / Policy / Share / Stock / Unit, etc.) — 7006 [+]". [PRIMARY] ([S1562] p.66) **The brief's 7006 is therefore correct for TY2025.** A blog also says "FBR wealth statement code for closing balances of banks: 7006". [SECONDARY] ([AB])
- **TY2026:** the wealth statement was regrouped. See Q3. [PRIMARY for the structure; UNVERIFIED for the code]

### Q2. Codes for tax collected or deducted

| Section | Code and label | Where | TY | Confidence / source |
|---|---|---|---|---|
| **s.236Y** (card payments abroad) | **64151905**: "Persons remitting amount abroad through credit / debits / prepaid cards u/s 236Y" (the TY2019 label was "Advance tax on remittance through credit, debit, prepaid cards u/s 236Y") | Adjustable Tax, column *Tax Collected / Deducted* (the amount goes in *Receipts / Value*) | TY2019, TY2025, TY2026 | [PRIMARY] [S1562] p.60; [S1160] p.10; TY2026 [PRIMARY, scan] [S1495] p.30 |
| **s.151** profit on debt, bank deposits, final regime | **64040052**: tax withheld goes in column 2 of the same final-tax line | Fixed / Final Tax | TY2025, TY2026 | [PRIMARY] [S1562] p.61; [S1495] p.23; column rule [FAQ] |
| **s.151** profit on debt, bank deposits, adjustable (normal regime) | **64040002**: "Profit on Debt u/s 151(1)(b) from Bank Accounts / Deposits @15%". Siblings: 64040001 (NSC / PO), 64040003 (Government securities), 64040004 (others) | Adjustable Tax | TY2025, TY2026 | [PRIMARY] [S1562] p.59; [S1495] p.29 |
| **s.149** salary | **64020004**: "Salary of Employees u/s 149" | Adjustable Tax | TY2025, TY2026 | [PRIMARY] [S1562] p.59; [S1495] p.4, 29; [MAN] p.7. FBR's 2023 FAQ also lists 64020001 (Federal Govt), 64020002 (Provincial Govt) and 64020003 (Corporate sector) employees. The TY2025 and TY2026 lists I read show only 64020004. [PRIMARY] [FAQ] |
| **s.154A** export of services | **No separate withholding code found.** Any tax deducted or paid u/s 154A goes in the *Tax Collected / Deducted* column of 64060285 (or 64060290). | Fixed / Final Tax | TY2024–TY2026 | [PRIMARY] for the column layout ([S950] p.6; [S1562] p.61–62). The finding that no code exists rests on 154A being absent from the adjustable-tax lists I read ([S950] p.8; [S1562] p.59–60). |
| s.231AB (useful for bank statements) | **64100101**: "Advance tax on cash withdrawal u/s 231AB" | Adjustable Tax | TY2024 (paper), TY2025 | [PRIMARY] [S1562] p.59; [S950] p.8; TY2026 [UNVERIFIED] |

In the TY2024 paper form, profit on debt used different codes: "Profit on debt u/s 151 @ 15% — 64040005" (Annex-A, adjustable) and "Profit on Debt u/s 7B — 64310056" (final). [PRIMARY] ([S950] p.6, p.8)

### Q3. Wealth statement: bank balances, cash, foreign assets, and the fields for a bank entry

**TY2025 and earlier (the owner's copied codes):**

- **Bank balances:** 7006, Investment (Non-Business), as Form "Account". [PRIMARY] ([S1562] p.66; [S950] p.22)
- **Cash:** 7012, "Cash (Non-Business)" (paper sub-row "Notes & Coins"). [PRIMARY] ([S1562] p.66; [S950] p.24)
- **Foreign assets:** 7016, "Assets held outside Pakistan", on the s.116 wealth statement. TY2025 also lists "Capital or voting rights in foreign company 7018", "Total Assets held outside Pakistan 7020" and "Foreign liabilities 7022". [PRIMARY] ([S1562] p.66)
- **The separate s.116A declaration (TY2025)**, "Electronic Foreign Income and Assets Declaration for Resident Individual", reuses the same codes for foreign assets: 7006 (Investment, including accounts), 7012 (Cash), 7016 (total), 7017 (share or interest in a foreign trust, company or entity) and 7022 (foreign liabilities), plus 703005 / 703006 (foreign assets transferred, and the consideration received). [PRIMARY] ([S1562] p.78)
- **When s.116A applies:** a resident individual must file a foreign income and assets statement if foreign income is at least US$10,000 or foreign assets are at least US$100,000. [PRIMARY] ([FBR s.116A][S116A])
- **Fields for a bank entry:**
  - The paper form's columns are *Form | Account / Instrument No. | Institution Name / Individual CNIC | Share % | Code | Value at Cost*, with the account type chosen from Current / Fixed Deposit / Profit-Loss Sharing / Saving. [PRIMARY] ([S950] p.22)
  - IRIS uses a dialog. For institutions other than Pakistani banks or National Savings Centres, FBR says to "Select relevant option against 'Type'. Select 'Unspecified' against 'Form'. Enter Number against 'Account / Instrument No.' Search 'Unspecified' … against 'Institution'." [PRIMARY] ([FAQ])
  - "Institution" is picked from IRIS's list of bank branches. FBR tells users to enter branch names in the bank's own order (e.g. "National Bank of Pakistan Mall Road Lahore"). [PRIMARY] ([FAQ])
  - TY2025 adds an optional "Estimated Current Market Value" column, which FBR says is "for academic and policy research purposes only". [PRIMARY] ([S1562] p.66)
- **TY2025 simplified return (SRO 1561):** bank accounts are keyed by "the 24-digit IBAN" with the "closing balance as of 30 June 2025". FBR also pre-adds accounts it knows about: "According to our records, the following bank account(s) belong to you and will be added to your personal assets." [PRIMARY] ([S1561] p.12–13) This simplified form has no export-of-services path. Its income sources are salary, pension, rent, payment for services, profit on bank account and dividends, so an exporter files the full e-return. [PRIMARY] ([S1561] p.4–10)

**TY2026 (the redesigned form, SRO 835 draft and SRO 1495 final):**

- **Personal Assets / Liabilities is regrouped:**
  - Immovable Properties (Non-Business).
  - **Financial Assets & Investments (Non-Business)**, containing **Bank Account(s)**, **Cash in hand**, Investments / Stocks / Bonds / etc., Advances / Prepayments / Receivables, and Assets held on others' name (including non-filer spouse / dependents).
  - Moveable Assets (Non-Business): motor vehicles, equipment, animals, precious possession, household effects, personal items, any other asset.
  - Business Capital, Assets held outside Pakistan, Total Assets, Payables, Foreign liabilities, Total Liabilities, Net Assets Current Year.
  - [PRIMARY] ([S835] p.52–58; [S1495] p.38)
- **Codes read in the TY2026 final:** Business Capital 7003; Business Capital in AOPs / Companies 700302; Assets held on others' name 7014; Total Assets 7019; Payables 7021; Total Liabilities 7029; Net Assets Current Year 703001. [PRIMARY, scan] ([S1495] p.38)
- **The code for "Financial Assets & Investments (Non-Business)" and its "Bank Account(s)" rows could not be read.** Every OCR attempt on that cell came back blank or noise. **Do not assume 7006 carried over.** [UNVERIFIED]
- **Bank account entry in TY2026:** the list shows each account as **"Sample IBAN, Title, Bank Name"**. The add dialog asks "Enter IBAN" and "Account Title" (seen in the business balance-sheet version of the dialog). [PRIMARY, draft] ([S835] p.26–27, p.58)
- **Foreign assets in TY2026** have their own "116A – Foreign Assets / Liabilities" tab. It covers Foreign Immovable Property; Foreign Movable Assets (Cash in hand, Investment / Advances, Motor Vehicle(s), Any Other Assets, **Bank Account**, with a dialog for "Enter IBAN / Account Number", "Account Title", "Bank Name" and "Country"); Foreign Business Capital; Capital or voting rights in foreign company (7018); **Total Foreign Assets 701902**; Payables 7022; **Total Foreign Liabilities 702901**. [PRIMARY] ([S835] p.50–51) Codes: [PRIMARY, scan] ([S1495] p.37). The codes for the individual foreign items could not be read. [UNVERIFIED]
- **Payoneer / Wise:** these are not Pakistani bank accounts. In TY2025 they would go under assets held outside Pakistan (7016) and, if a 116A statement is required, under 7006 in that declaration. In TY2026 they would go under 116A Foreign Movable Assets, as a "Bank Account" or "Investment / Advances". Which fits an e-money wallet is a judgment call for the owner. [PRIMARY for the slots; UNVERIFIED for the classification]
- **The description format "<IBAN> - <ACCOUNT TITLE> - <BANK> - Self":** partly consistent with TY2026's "IBAN, Title, Bank Name" display. I found no primary source for the " - " separators or the trailing "Self", which is probably ownership (sole holder versus joint or someone else's name). [UNVERIFIED] Treat it as the owner's observed format, not an FBR specification.

### Q4. Zakat

- **9001 "Zakat u/s 60"**, inside **9009 "Deductible Allowances"** (columns *Total | Inadmissible | Admissible*), next to 9002 (Workers Welfare Fund u/s 60A) and 9008 (Educational Expenses u/s 60D). [PRIMARY] ([S1562] p.56; [S950] p.2–3; [S1160] p.3–4)
- **TY2026:** "Zakat u/s 60" is offered in the "Add Deductible Allowances" dialog, and 9009 is present, but the dialog shows no code. [PRIMARY, scan] ([S1495] p.26, p.36) 9001 for TY2026 is [UNVERIFIED], though probably unchanged.
- **Wealth reconciliation:** Zakat paid also belongs in personal expenses, "Donation, Zakat, Annuity, Profit on Debt, Life Insurance Premium, etc." (7076). [PRIMARY] ([S1562] p.66)

### Q5. Do codes change between tax years, and where does FBR publish the forms?

**Where FBR publishes them.** Each year's return forms are notified by an SRO under s.237 of the Income Tax Ordinance, 2001. The SRO adds a new "Part" to the Second Schedule of the Income Tax Rules, 2002. A draft is published first for comments, and the final version follows. The PDFs are on `download1.fbr.gov.pk/SROs/` and listed on FBR's Income Tax SRO page ([index][SROIDX], from search results, not opened). FBR's IRIS manual and FAQ ([MAN], 2023; [FAQ], Jan 2023) are not tied to a tax year.

| Tax year | Draft | Final | Rules Part | What it contains | Source |
|---|---|---|---|---|---|
| 2024 | SRO 896(I)/2024, 21 Jun 2024 | SRO 950(I)/2024, 4 Jul 2024 | Part-II-ZA | Individual paper return (IT-1B, IT-2, annexes, wealth statement) | [S950] p.1 [PRIMARY]; [S896] |
| 2025 | SRO 1212(I)/2025, 7 Jul 2025 | **SRO 1562(I)/2025, 18 Aug 2025** | Part-II-ZC | E-returns for companies, AOPs, **individuals**, non-residents, the **s.116A foreign income & assets declaration**, manufacturers, traders and SMEs | [S1562] p.1 [PRIMARY]; [S1212] |
| 2025 | SRO 1213(I)/2025, 7 Jul 2025 | SRO 1561(I)/2025, 18 Aug 2025 | Part-II-ZD | Simplified e-return for individuals | [S1561] p.1 [PRIMARY]; [S1213] |
| 2026 | SRO 835(I)/2026, 7 May 2026 | **SRO 1495(I)/2026, 2 Sep 2026** | Parts II-ZE, II-ZF, II-ZG, II-ZH | E-returns for individuals, SMEs, AOPs / firms and companies | [S1495] p.1, 111 [PRIMARY]; [S835] p.1 [PRIMARY] |

**What changed and what did not:**

- **Stable from TY2025 to TY2026:** 64060285, 64060290, 64040052, 64040002, 64151905, 64020004, 3000, 9009, 9201. 64151905 goes back to TY2019. 7006, 7012 and 7016 are the same from TY2019 to TY2025. [PRIMARY]
- **Labels changed:** 64060290 became "IT/ITeS" from TY2025. 500312 went from "(if amount u/s 7B exceeds Rs. 36 million)" on the paper forms to "Profit on Debt" in the TY2025 e-return. 64040052 carries "(amount not exceeding 5 million)" in TY2025. [PRIMARY]
- **Paper and electronic forms differ:** the TY2024 paper form uses 64310056 and 64040005 for profit on debt, and "Tax Paid" 64220057 where the e-return has 9201. [PRIMARY] ([S950] p.2, 6, 8)
- **TY2026 is a structural redesign:**
  - A new "Summary of Economic Transactions" screen.
  - "Tax Deductions" sub-tabs under each head of income, with renamed columns.
  - A regrouped wealth statement with new codes (700302, 701902, 702901).
  - s.116A folded into the return as its own tab.
  - [PRIMARY] ([S835]; [S1495])
  - The press called it a structural redesign. [SECONDARY]
- **Late change:** the final TY2026 SRO is dated 2 Sep 2026, four weeks before the 30 Sep 2026 deadline, and practitioners criticised the timing. [SECONDARY] ([ProPakistani][PP])
- **IRIS can change mid-season:** both TY2025 final SROs say "Any changes in the return available in IRIS shall be deemed to have always been present, however, this will not cause any prejudice to the taxpayers having filed the return prior to the change." [PRIMARY] ([S1562] p.97; [S1561] p.24) I did not see this clause on the last page of SRO 1495/2026 (p.111). [PRIMARY, scan]

## Implications for the tool

1. **Keep codes in per-tax-year configuration, keyed by form variant.** Examples: TY2025 "Electronic Return for Individual", TY2025 "Simplified", TY2026 "Electronic Return for Individuals", and paper returns. For each code, store:
   - the code as a **string** (lengths vary from 4 to 8+ digits, e.g. 3000, 500312, 9231822, 64060285);
   - the verbatim IRIS label;
   - the tab or section;
   - what each column means;
   - the source URL and page;
   - a verification status.

   The evidence behind this: codes and labels differ between years and between paper and e-returns, and FBR says the live IRIS form wins.
2. **Model outputs as (code, column) cells, not one number per code.**
   - **Export:** 64060285 gets col 1 = total export receipts and col 2 = s.154A tax deducted or paid (usually zero unless found). IRIS calculates col 3; the tool can show the expected 1% only as a cross-check. The same receipts also belong in Business revenue (3009 → 3029 → 3000) in the final-tax column.
   - **Profit on debt:** list it per account, since IRIS itemises by Type / Form / Account No. / Institution. 500312 (Other Sources) plus 64040052 get gross profit in col 1 and s.151 tax in col 2. Keep 64040002 as the alternative line when profit on debt falls under the normal regime; the threshold should be a config or legal decision, not code.
3. **Treat 9201 as a check total, not something to enter.** Show its components by code: 64020004 (salary, from the employer's certificate; the brief's withholding list leaves this out), 64040052 col 2 or 64040002 (bank profit), 64151905 (s.236Y certificate), 64100101 (s.231AB, if it appears in statements), and 64060285 col 2 (s.154A). Label the section "Withholding taxes (adjustable + final)" rather than "Adjustable tax". In IRIS, final-regime bank-profit tax is not on the Adjustable Tax tab.
4. **Store wealth-statement account records in a way that fits both years.** Fields: IBAN (24 characters for Pakistan), account number, account title, bank legal name, branch (the TY2025 IRIS institution picker works at branch level), account type (Current / Saving / PLS / Fixed Deposit), ownership share % (the "Self" tag), currency and country (for foreign accounts), and the closing balance at 30 June in PKR.
   - TY2025 maps these to 7006 (Form "Account").
   - TY2026 maps them to "Financial Assets & Investments (Non-Business) → Bank Account(s)". **Leave that code blank and flag it "verify in IRIS"** until the owner reads it off the live form.
5. **Make the description line a template the owner can edit**, defaulting to the owner's "<IBAN> - <TITLE> - <BANK> - Self". Only the "IBAN, Title, Bank Name" parts appear in FBR's TY2026 screens.
6. **Cash and foreign assets:** cash is manual (7012 in TY2025; "Cash in hand" under Financial Assets in TY2026). Put foreign wallets (Payoneer / Wise) in a separate foreign-assets section (7016 / 116A in TY2025; the 116A tab in TY2026). Warn when foreign income or assets may cross the s.116A thresholds (US$10,000 income / US$100,000 assets). The PKR conversion method is out of scope here.
7. **Offer reconciliation hints:** in TY2025, final-tax income (export receipts and bank profit ≤ threshold) feeds 7033, and foreign remittances may be 7035. Their TY2026 codes are unverified.
8. **Show a per-code "confidence / verified in IRIS" flag.** Each season, let the owner confirm or override a code against the IRIS screen before exporting.

## Could not verify / open questions

1. **The TY2026 bank-account code**, "Financial Assets & Investments (Non-Business)" → "Bank Account(s)". The code cell is blank or unreadable in SRO 1495/2026 p.38, and the TY2026 draft screens show no codes for it. Whether 7006 survives is unknown. **The owner should read it off IRIS.**
2. **TY2026 codes for Cash in hand, foreign bank accounts, and 7016 / 7033 / 7035.** Only the totals 701902 and 702901, and 7014, 7003, 700302, 7019, 7021, 7029 and 703001–703003, were legible.
3. **The TY2026 500312** (Other Sources → Profit on Debt) in the individual return is illegible. It appears as 500312 in another return type in the TY2026 draft.
4. **The TY2026 64060285 digits** on the individual-return pages are partly illegible. The AOP and company schedules in the same SRO read 64060285 cleanly, and TY2024 and TY2025 agree, so confidence is high but not absolute.
5. **Whether 9201 includes final-tax withholding.** This is supported by the TY2025 simplified return's definition "Total Withholding Taxes (A+B+C)", but I found no FBR text naming 9201.
6. **The exact IRIS display strings** "<IBAN> - <TITLE> - <BANK> - Self" and "Profit on Debt u/s 151(1)(b) … - Profit on Savings Account - Investment in [Bank Name]". Neither appears in any FBR document I could reach.
7. **Whether IRIS checks** that Business revenue (3009 / 3029, final-tax column) equals the Receipts / Value on 64060285. Not checked.
8. **The profit-on-debt threshold** (Rs 5 million in the TY2025 label vs Rs 36 million in the paper-form label for 500312). This is a tax-law question for another research note.
9. **Eligibility for the 0.25% IT/ITeS line.** The owner has confirmed 1%. Conditions such as PSEB registration come from secondary sources only.
10. **The live TY2026 IRIS form** (open since before 2 Sep 2026) may differ from SRO 1495/2026. The owner's screen is authoritative.

## Sources

**Primary: FBR notifications (return forms)**

- [S1562] SRO 1562(I)/2025, 18 Aug 2025: TY2025 e-returns, Part-II-ZC. The individual return is PDF pp.47–71; the s.116A declaration is pp.77–79. Image-only; read by OCR.
- [S1561] SRO 1561(I)/2025, 18 Aug 2025: TY2025 simplified e-return for individuals, Part-II-ZD. Image-only; read by OCR.
- [S1495] SRO 1495(I)/2026, 2 Sep 2026: TY2026 e-returns, Parts II-ZE to II-ZH. Individuals pp.2–44, SMEs pp.45–52, AOPs about pp.53–77, companies pp.78–110. Scanned; read by OCR.
- [S835] SRO 835(I)/2026, 7 May 2026: draft of the TY2026 forms. Scanned; read by OCR.
- [S950] SRO 950(I)/2024, 4 Jul 2024: TY2024 individual paper return, Part-II-ZA. Text layer.
- [S1160] SRO 1160(I)/2019: TY2019 paper return and "Instructions for Filling in Return Form & Wealth Statement", Part-II-OA. Text layer.
- [S2022] TY2022 individual paper return. Text layer.
- Drafts cited from the finals' preambles; I have not opened these PDFs, and the URLs come from search results: [S896] SRO 896(I)/2024; [S1212] SRO 1212(I)/2025; [S1213] SRO 1213(I)/2025.

**Primary: FBR guidance and statute**

- [MAN] FBR, "File Your Tax Returns – User Guide" (IRIS Return Manual, PDF created 19 Jul 2023). Image-only; pp.7–8 read by OCR.
- [FAQ] FBR, "Iris – FAQs" (PDF created 20 Jan 2023). Text layer.
- [S116A] FBR, Income Tax Ordinance s.116A, "Foreign income and assets statement".
- [SROIDX] FBR Income Tax SROs index (from search results; not opened).

**Secondary**

- [AB] accountingblogger.com, "FBR Pakistan Tax Return Questions & Answers" (dated 2 Sep 2025): 64060285 = 1%, 64060290 = 0.25%, 7006 for bank balances, 64040052 for profit on debt ≤ Rs 5 million.
- [TPK] ask.taxationpk.com Q&A on 64040051 vs 64040052 (Oct 2025).
- [PP] ProPakistani, "FBR Again Changes 2026 Tax Return Form" (3 Sep 2026): SRO 1495(I)/2026 and the timing criticism.

[S1562]: https://download1.fbr.gov.pk/SROs/2025818198324521SRO1562.pdf
[S1561]: https://download1.fbr.gov.pk/SROs/2025818198039714SRO1561.pdf
[S1495]: https://download1.fbr.gov.pk/SROs/2026921792446743SRO1495.pdf
[S835]: https://download1.fbr.gov.pk/SROs/2026571753641255SRO835.pdf
[S950]: <https://download1.fbr.gov.pk/SROs/20247413755816SRONo.950(ManualReturn)2024.pdf>
[S896]: <https://download1.fbr.gov.pk/SROs/20246242361216879SRO-896(I)2024-Manual.pdf>
[S1212]: https://download1.fbr.gov.pk/SROs/2025781471118495SRO1212-2025.pdf
[S1213]: https://download1.fbr.gov.pk/SROs/202578147134572SRO1213-2025.pdf
[S1160]: https://download1.fbr.gov.pk/SROs/2019101151017301SRO1160.pdf
[S2022]: https://download1.fbr.gov.pk/SROs/20229131692519454ManualReturn.pdf
[MAN]: https://e.fbr.gov.pk/SOP/IRIS/IRIS_Return_Manual.pdf
[FAQ]: https://e.fbr.gov.pk/SOP/IRIS/Iris_FAQs.pdf
[S116A]: https://www.fbr.gov.pk/section-116A/152720
[SROIDX]: https://www.fbr.gov.pk/ShowSROs?Department=Income+Tax
[AB]: https://accountingblogger.com/fbr-pakistan-tax-return/
[TPK]: https://ask.taxationpk.com/565/difference-fbr-iris-codes-64040051-clause-64040052-clause
[PP]: https://propakistani.pk/2026/09/03/fbr-again-changes-2026-tax-return-form/
