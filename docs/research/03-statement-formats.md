# Research 03: Bank and wallet statement formats in Pakistan

## Scope & date researched

- **Date researched:** 2026-09-27.
- **Institutions:** Meezan Bank, MCB Bank (Pakistan, `mcb.com.pk`, not MCB Mauritius), SadaPay and NayaPay in depth. JazzCash and Easypaisa more briefly. Regulator material from the SBP and FBR, and open-source parsers on GitHub.
- **Questions:** (1) export options; (2) layouts, passwords, text vs scanned; (3) withholding-tax (WHT) and profit certificates; (4) how incoming foreign payments appear; (5) open-source parsers.
- **Method:** official websites, help centres, in-app user guides (PDF), schedules of charges, app-store listings, SBP circulars, FBR rules and notices, and the source code of GitHub repos (read through the unauthenticated GitHub API and raw files). Secondary sources are labelled as such.
- **Privacy:** all web and API queries were generic. No owner data from the brief was used anywhere. Third-party sample statements (Scribd uploads, repo fixtures) were read for structure only. No personal data from them is reproduced here; names are replaced by `<NAME>`.
- **Confidence tags:**
  - `[PRIMARY]`: the institution, regulator or repo itself says it.
  - `[SECONDARY]`: a blog, news report, user-uploaded sample, or a third-party repo used as evidence of someone else's layout.
  - `[UNVERIFIED]`: inference, a dead link, or not confirmed.
- **Limits:**
  - No banking app or portal was logged into.
  - Layouts of CSV exports are almost entirely undocumented by the institutions.
  - Scribd samples are of unknown provenance and date.
  - Some SBP pages refused a plain fetch and were retrieved with a scraper.
- **Separating findings from the brief:** where the brief (`docs/requirements.md`) already describes a layout, this document labels that text **"Brief says"**. Only material labelled **"Found"** is new evidence.

## Summary

| Institution | Export formats | Balances shown | Password | WHT certificate available | Confidence |
|---|---|---|---|---|---|
| **Meezan Bank** | PDF from app/internet banking; internet banking "download statements into different formats"; **CSV and XLSX exports** (≤1 year per CSV, per a repo); emailed PDF e-statements; WhatsApp statement download | Opening + closing at top (brief; CSV rows 2–3); running "Available Balance" per row | Not documented | **Yes.** Net banking, WhatsApp banking, branch. WHT certificates free. Sample shows s.151 "Tax Deduction Certificate" per account per FY | Formats: PRIMARY ("different formats") + SECONDARY (CSV/XLSX specifics). Certificates: PRIMARY |
| **MCB Bank** | **MCB Live: PDF or CSV**; custom date range; e-statements downloadable for last 3 years; monthly emailed PDF e-statement | Opening + closing (both PDF formats; app screen); running balance | **MCB Live PDF: last 4 digits of account number.** Credit-card statement and balance certificate: birth year | **Yes.** MCB Live → Certificates → Withholding Tax Certificate (pick account + financial year) | PRIMARY |
| **SadaPay** | PDF from app, any start/end date from 1 Jul 2023; older periods via in-app chat; **no CSV documented** | Total debit / Total credit only; **no opening/closing** (brief + 2024 sample) | Not documented | **On request.** "Tax Certificate" via in-app chat (≤5 working days); PRC via chat | Access: PRIMARY. Layout: SECONDARY. No CSV: UNVERIFIED |
| **NayaPay** | **App: PDF or CSV** ("Statements": account statement, WHT certificate, annual statements); custom statements by email | Brief: Total Income/Spent + running balance. **Public samples also show Opening and Closing Balance on the summary card** (conflicts with brief §6) | Not documented | **Yes.** WHT certificate in app ("Statements"). Brief: Rule 42 certificate for s.236Y | Formats: PRIMARY. Layout: SECONDARY |
| **JazzCash** | Emailed statement via app/online (free); e-statements "only … upon … specific written request"; mini statement | Running balance per row | Not documented | Not found for the wallet | PRIMARY (SOC/T&C); layout SECONDARY |
| **Easypaisa** | E-statement emailed / downloadable from app "Transaction History"; app history covers 30 days; older via helpline; some statements are scanned | Per-row opening/closing balance; "Balance B/F" | Not documented | In-app "Tax Certificate" (profit on debt; tax on foreign remittance), 3 years | FAQ: PRIMARY. Certificate/layout: SECONDARY |

**Headline:** a CSV (or Excel) export is officially documented for **MCB Live** and **NayaPay**. It is strongly indicated for **Meezan**: the bank documents "different formats", and two independent open-source tools parse Meezan CSV and XLSX exports. **SadaPay** documents no CSV. JazzCash and Easypaisa appear to provide PDF or emailed statements only.

---

## Detailed findings

### Q1. Statement export options

#### Meezan Bank

**Brief says:** PDF statements, sometimes password-protected.

**Found:**
- **Internet banking:** "View full details of your transactions. (Download statements into different formats)". The official page does not name the formats. `[PRIMARY]` ([S11](https://www.meezanbank.com/ways-to-bank/))
- **CSV export exists.**
  - A Meezan CSV parser's README says: open the Meezan mobile app → **Transactions → Download → select CSV → choose date range**. `[SECONDARY]` ([G1](https://github.com/ibrahimahtsham/meezan-statement-parser-and-expense-tracker))
  - The same repo's in-app help says: "Meezan only lets you download a CSV for a limit of **one year at a time**" when "exporting your statement from Meezan Internet Banking". `[SECONDARY]` ([G1](https://github.com/ibrahimahtsham/meezan-statement-parser-and-expense-tracker/blob/main/src/pages/MergeStatementsPage/components/InstructionsCollapse.jsx))
- **XLSX export exists.** A second, independent tool accepts `.csv,.xlsx` and is "Optimized for Meezan Bank CSV & Excel exports". It converts XLSX to CSV with SheetJS. `[SECONDARY]` ([G2](https://github.com/theajmalrazaq/mznviz))
- **WhatsApp Banking** (launched 2 Aug 2023) offers "downloading account statements, and obtaining tax certificates". `[PRIMARY]` ([S13](https://www.meezanbank.com/meezan-bank-introduces-meezan-whatsapp-banking/), [S11](https://www.meezanbank.com/ways-to-bank/))
- **Emailed e-statements.** Monthly "E-STATEMENT OF ACCOUNT" PDFs exist; a 2021 sample is a user upload. `[SECONDARY]` ([X5](https://www.scribd.com/document/525319881/5372389-010517-01-05-2021-31-05-2021-1-unlocked)) Frequency options are not published. `[UNVERIFIED]`
- **Branch:** "Duplicate Statement of Account: Rs. 25/- per item" (Schedule of Charges, Jul–Dec 2026). `[PRIMARY]` ([S12](https://www.meezanbank.com/wp-content/themes/mbl/downloads/home-downloads/SOC-ENG-Jul-Dec-2026.pdf))
- **Payoneer in the Meezan app:** real-time USD→PKR withdrawal. "When the customer withdraws money to their MBL … account they will also get PRC … in the email." (Published 28 Feb 2025.) `[PRIMARY]` ([S14](https://www.payoneer.com/resources/payoneer-and-meezan-bank-transform-international-payment-withdrawals-in-pakistan-with-new-partnership/))

#### MCB Bank

**Brief says:** PDF statements, sometimes password-protected.

**Found:**
- **MCB Live (app/web), Menu → Account Management:** "Download statements in **PDF or CSV** format. (PDF statements are password-protected for security.)". `[PRIMARY]` ([S15](https://mcblive.com/public/user_guide.pdf), p. 61)
  - The "Download Statement" dialog in the guide's screenshot has two buttons: "Download in CSV format" and "Download in PDF format". `[PRIMARY]` ([S15](https://mcblive.com/public/user_guide.pdf), p. 62; guide PDF last modified 23 Jan 2026)
- **Full Account Statement** in MCB Live has the "option to view the last 30-days or 90-days transaction history. You can also specify the date range of your choice". "E-statements can be downloaded for a maximum of last three years." `[PRIMARY]` ([S16](https://mcblive.com/public/faqs.pdf), "MCB Live FAQs 23 June 2025"; also [S18](https://www.mcb.com.pk/faqs/mcb-live-faqs))
- **Emailed e-Statement:** "Receive in PDF format on your given e-mail address". Delivered "on monthly basis and detailed transaction history on semi & bi-annual basis as well". "No charges at all." `[PRIMARY]` ([S17](https://www.mcb.com.pk/self-service-channels/personal-services-estatement))
  - Subscription is set in MCB Live with a frequency selector; screenshots show "Weekly" and "Quarterly". `[PRIMARY]` ([S15](https://mcblive.com/public/user_guide.pdf), p. 63)
- **Certificates in MCB Live:**
  - Account Maintenance Certificate.
  - Balance Confirmation Certificate: "date range (up to the last 3 years)".
  - Withholding Tax Certificate.

  `[PRIMARY]` ([S15](https://mcblive.com/public/user_guide.pdf), pp. 76–77)

#### SadaPay

**Brief says:** PDF with Date / Description / signed amount; Total Debit and Total Credit only.

**Found:**
- **App path:** More → Documents → "Account Statement" → "Set the Start and End dates" → Download. `[PRIMARY]` ([S4](https://help.sadapay.pk/en/articles/7907996-account-statement), 12 Jul 2024)
  - Statements are available "for 1st July 2023 and onward dates". "Ongoing day's transactions will not be included". Unsettled transactions from the past 30 days are excluded.
  - Periods before 1 Jul 2023 are obtained via in-app chat. The English article says "within 24 hours"; the Urdu version says 2 business days. `[PRIMARY]` ([S4](https://help.sadapay.pk/en/articles/7907996-account-statement), [S4b](https://help.sadapay.pk/en/articles/8123235-account-statement))
- **File format:** SadaPay's help centre does not state it.
  - A public 2024 sample is a PDF titled "Account Statement", with file name pattern `sadapay_account_statement_<start>_<end>`. `[SECONDARY]` ([X7](https://www.scribd.com/document/775065859/sadapay-account-statement-2023-07-01-2024-09-05))
  - No CSV or Excel option is documented anywhere searched. `[UNVERIFIED that none exists]`
- **Address:** statements "don't display the address". An Account Maintenance Certificate is available via chat within 2 working days. `[PRIMARY]` ([S4](https://help.sadapay.pk/en/articles/7907996-account-statement), [S7](https://help.sadapay.pk/en/articles/7908001-account-maintenance-certificate))
- **Certificates via chat:**
  - Tax Certificate within 5 working days. `[PRIMARY]` ([S5](https://help.sadapay.pk/en/articles/7908002-tax-certificate))
  - Remittance Certificate / PRC within 3 working days. `[PRIMARY]` ([S6](https://help.sadapay.pk/en/articles/7908004-remittance-certificate-prc))

#### NayaPay

**Brief says:** PDF, sometimes password-protected; a separate "Certificate of collection of tax … Rule 42".

**Found:**
- **App path:** Home → More → Statements.
  - Available documents: "Account Statement" and "Withholding Tax Certificate".
  - "These statements can easily be downloaded as a **PDF or CSV** file with just a single tap!"
  - Personalised statements: email support.

  `[PRIMARY]` ([S1](https://help.nayapay.com/article/251-how-can-i-view-my-documents-on-nayapay), updated 24 Jun 2025)
- **Annual statements.** NayaPay's own post: "Get your **annual** Account Statements and Withholding Tax Certificate instantly on NayaPay!". `[PRIMARY]` ([S3](https://www.facebook.com/nayapaypk/posts/long-lines-never-heard-of-em-get-your-annual-account-statements-and-withholding-/845175051056440/))
  - A third-party guide says the app offers "current statement, along with the last four months' statements and annual" statements. `[SECONDARY]` ([X2](https://taxationpk.com/how-to-get-your-nayapay-tax-certificate/), [X3](https://www.linkedin.com/pulse/access-your-nayapay-bank-statements-tax-certificate-filing-mefyf))
  - A parser strips annual-period lines such as "01 Jul 2022 - 30 Jun 2023", so annual statements appear to follow the July–June fiscal year. `[SECONDARY]` ([G5](https://github.com/AnasSaleem547/nayapay-account-statement-to-csv-parser))
- **CSV column layout:** not documented publicly. `[UNVERIFIED]`

#### JazzCash (brief)

- **Schedule of Charges (Q3 2026, dated 30 Jun 2026):**
  - "Email Statement via Mobile App/Online: Free".
  - "Mini Statement Mobile App/Online: Free".

  `[PRIMARY]` ([S22](https://www.jazzcash.com.pk/assets/documents/SOC-Q3-2026-Final.pdf))
- **Terms & Conditions:** the bank is "not liable for sending semiannual statement of account". "Electronic statements will only be issued to the Customer upon his/her specific written request." `[PRIMARY]` ([S23](https://www.jazzcash.com.pk/tc))
- **No CSV export found.**

#### Easypaisa (brief)

- **FAQ:**
  - "Your e-statement will be sent to your registered e-mail address."
  - App → profile → "Transaction History" to "download e-statement of account".
  - The app shows only "the last 30 days". For older history, call the helpline "to request for their bank statement".

  `[PRIMARY]` ([S21](https://easypaisa.com.pk/faqs/))
- **No CSV export found.**

### Q2. Layout details (columns, dates, balances, passwords, text vs scanned)

#### Meezan Bank

**Brief says:** columns [Booking Date, Description, Credit, Debit, Available Balance]; opening and closing balance printed at the top.

**Found:** three distinct layouts.

1. **App / internet-banking PDF (2026-era).** A Meezan PDF parser treats:
   - a row containing "Booking Date", "Description", "Credit"/"Debit" and "Available Balance" as the header;
   - "Meezan Bank … Account Statement" as the page header;
   - dates in the form **"DD Mon YYYY"** (for example `21 Jan 2026`).

   Amounts sit in **separate Credit and Debit columns with signs and currency**: `+ PKR1,234.56` for credits (the repo's AI prompt says these are green) and `- PKR1,234.56` for debits (red). The values here are illustrative; the format is the parser's.

   Descriptions continue onto extra lines (STAN, party details). The footer looks like `<page no> DD Mon YYYY, HH:MM`.

   The PDF has **digital text**: the parser uses pdf.js text coordinates and only falls back to AI OCR for scans. `[SECONDARY]` ([G3](https://github.com/AteebNoOne/meezan-statement-calculator/blob/main/src/utils/pdfParser.ts)) This corroborates the brief's column order.
2. **CSV export** (from G1's parser and G2's CSV/XLSX reader):
   - row 1: account number and title;
   - row 2: opening balance (for example `PKR      <amount>`);
   - row 3: closing balance;
   - row 4: currency;
   - then a header row starting "Booking Date, Value Date".

   Transaction columns, in order: Booking Date, Value Date, Doc No, Description, **Debit, Credit**, Available Balance. The Debit/Credit order is the **reverse of the PDF**. G2 finds the balance rows by the text "OPENING BALANCE" and "CLOSING BALANCE". `[SECONDARY]` ([G1 parser](https://github.com/ibrahimahtsham/meezan-statement-parser-and-expense-tracker/blob/main/src/pages/UploadCSVPage/utils/parseMeezanStatement.js), [G2](https://github.com/theajmalrazaq/mznviz))

   The column names above are the parser's field names, not confirmed header text.
3. **Older monthly e-statement (2021 sample).**
   - Title: "E-STATEMENT OF ACCOUNT".
   - Header fields: From Date, To Date.
   - Opening Balance and Closing Balance are shown.
   - Columns: Date, Value Date, Doc. No, Particulars, Debit, Credit, Balance.
   - Dates: **DD/MM/YY**.

   `[SECONDARY]` ([X5](https://www.scribd.com/document/525319881/5372389-010517-01-05-2021-31-05-2021-1-unlocked))

- **Description strings observed in repos** (keyword lists and fixtures):
  - Profit and tax: "Payment of Profit", "Withholding Tax", "FED AMOUNT", "FBRTax", "Charges Taxes Plus FED".
  - Raast and transfers: "Raast P2P Fund transfer - from `<NAME>` RAAST … `<ref>`", "Raast P2P Fund transfer to …", "Money Received from `<NAME>` `<masked acct>` STAN (n)", "Money Transferred To", "Batch Transfer - Credit FUND TRF".
  - Home remittance: "Remittance From `<remitter or money-transfer operator>` … STAN(n)".
  - Card and cash: "`<merchant>` POS Transaction STAN (n)", "ATM Cash Withdrawal … STAN (n)", "1-Link ATM Cash Withdrawa[l]".
  - Charges and bills: "BANK CHARGES …", "1BILL - INVOICES", "KUICKPAY".

  `[SECONDARY]` ([G1 categories](https://github.com/ibrahimahtsham/meezan-statement-parser-and-expense-tracker/blob/main/src/pages/ShowStatsPage/utils/categorizeTransaction.js), [G3 fixtures](https://github.com/AteebNoOne/meezan-statement-calculator/blob/main/src/data/sampleStatement.test.ts))
- **Password:** not documented. `[UNVERIFIED]` The 2021 sample's file name ends in "-unlocked", which suggests the original was protected. `[UNVERIFIED]`

#### MCB Bank

**Brief says:** [Date, Description, Reference Number, Amount (with Dr/Cr suffix), Balance]; opening and closing balance at the top.

**Found:** two PDF layouts plus a CSV.

1. **MCB Live account statement PDF.**
   - Each row starts with a date **"DD Mon YYYY"** (for example `11 Jun 2026`).
   - The row ends with a **10-digit reference**, an **amount with `Dr`/`Cr` glued on** (for example `1,234.00Dr`), and the balance.

   `[SECONDARY]` ([G7 parsers.py](https://github.com/adsoftpk/four-bank-statement/blob/main/parsers.py))
   - Another parser reads pdfplumber tables with the header "Date | Description | Reference Number | Amount | Balance", "Opening Balance"/"Closing Balance" lines, and a period line such as "DD Mon YYYY to DD Mon YYYY". `[SECONDARY]` ([G9](https://github.com/Muhammad-Uzair-Kayani/FinParse))
   - The MCB Live "My Statement" screen shows Opening Balance and Closing Balance tiles above the transaction list. `[PRIMARY]` ([S15](https://mcblive.com/public/user_guide.pdf), p. 62 screenshots)
2. **Emailed MCB eStatement.**
   - Dates are **"DD/MM/YY"**, with a transaction date and a value date.
   - Debit, credit and balance are in separate columns; "Opening Balance" and "Closing Balance" are printed.
   - Extracted text loses the column position, so G7 **infers debit vs credit from the running balance**.

   `[SECONDARY]` ([G7 README](https://github.com/adsoftpk/four-bank-statement))
3. **CSV (MCB Live):** exists `[PRIMARY]` ([S15](https://mcblive.com/public/user_guide.pdf)), but its columns are not documented. `[UNVERIFIED]`

- **Description strings:** IBFT credits appear as "INTERBANK FUNDS RECEIVING"; G7 uses the phrase to detect MCB statements. `[SECONDARY]` ([G7](https://github.com/adsoftpk/four-bank-statement/blob/main/parsers.py)) The brief's "PROFIT-LOSS" and "WHT COLL: UNDER SEC 151" were not found in any public source.
- **Password:**
  - MCB Live PDF: "The statement in PDF format is password protected. Use the **last 4 digits of your account number** as a password". `[PRIMARY]` ([S15](https://mcblive.com/public/user_guide.pdf), p. 62 dialog)
  - Credit-card statement PDF: "4-digit year of birth". Balance Confirmation Certificate: "your birth year". `[PRIMARY]` ([S15](https://mcblive.com/public/user_guide.pdf), pp. 32, 77)
  - Emailed e-statement: not documented. `[UNVERIFIED]`
- **Text vs scanned:** both PDF layouts are parsed from embedded text. `[SECONDARY]` ([G7](https://github.com/adsoftpk/four-bank-statement), [G9](https://github.com/Muhammad-Uzair-Kayani/FinParse))

#### SadaPay

**Brief says:** [Date, Description, signed amount]; Total Debit and Total Credit at the top; no opening or closing balance anywhere.

**Found:**
- **2024 in-app statement sample.** Matches the brief. `[SECONDARY]` ([X7](https://www.scribd.com/document/775065859/sadapay-account-statement-2023-07-01-2024-09-05))
  - Title "Account Statement"; header field "Account Currency"; summary "Total debit" and "Total credit".
  - Columns: **Date | Description | Debit/Credit**. Dates in the form **"DD Mon, YYYY"** (for example `16 Mar, 2024`). Amounts are signed `-`/`+` in PKR.
  - Description prefixes: `TRANSF CR/ICT/`, `TRANSF DR/OGT/`, `PUR/`, `REC TXN/`, `REFUND/`, `MISC CDT/`.
  - Footer: "This is a system generated statement … Generated on: `<date>` [`<time>` (PKT)] Page X of N".
- **Older, support-generated statements (2023 sample) use a different layout.** `[SECONDARY]` ([X8](https://www.scribd.com/document/633148332/SadaPay-Account-Statement-Virtual-Card)) Statements requested via chat for pre-July-2023 periods may arrive in this format. `[UNVERIFIED]`
  - Title "ISDCST - Detailed Customer Statement".
  - Summary: Total Debits, Total Cash Withdrawals, Total Purchases, Total Fees, Total Credits, "Available Balance (As on)".
  - Columns: Device Number, Transaction Date, Transaction Amount, Billing Amount, CR/DR, Transaction Ref. Number, Merchant Name, Transaction Type, Transaction Description, Merchant Country. Dates **DD/MM/YYYY**.
- **Password:** not documented. `[UNVERIFIED]`
- **Text vs scanned:** both samples yield text. `[SECONDARY]`

#### NayaPay

**Brief says:** Total Income and Total Spent at the top; a running balance per transaction. §6 of the brief assumes no opening or closing balance.

**Found:**
- **The summary card shows Opening Balance, Closing Balance, Total Spent and Total Income.** `[SECONDARY]` ([X9](https://www.scribd.com/document/788028529/NAYAPAY-STATEMENT))
  - An independent parser, built against a Sep 2026 statement, says: "the summary-card numbers (opening/closing balance, total income/spent) extract in an order that varies by renderer". It notes that the opening balance is "reliably glued onto the IBAN line". `[SECONDARY]` ([G6](https://github.com/codewithwaheed/ledger-ai/blob/master/Packages/LedgerParsing/Sources/LedgerParsing/Statements/NayaPayStatementParser.swift))
  - **This conflicts with the brief; check against the owner's own files.**
- **Table header:** "TIME TYPE DESCRIPTION AMOUNT BALANCE". `[SECONDARY]` ([G5](https://github.com/AnasSaleem547/nayapay-account-statement-to-csv-parser/blob/main/pdf_to_csv.py), [G6](https://github.com/codewithwaheed/ledger-ai), [X9](https://www.scribd.com/document/788028529/NAYAPAY-STATEMENT))
- **Transaction blocks.** `[SECONDARY]` ([G6](https://github.com/codewithwaheed/ledger-ai/blob/master/Packages/LedgerParsing/Sources/LedgerParsing/Statements/NayaPayStatementParser.swift), [G5](https://github.com/AnasSaleem547/nayapay-account-statement-to-csv-parser/blob/main/pdf_to_csv.py))
  - Description lines such as "Incoming fund transfer from `<NAME>`", "Outgoing fund transfer to `<NAME>`", "`<bank>`-`<last4>`" and "Transaction ID `<24-char id>`".
  - A "Service Charges Rs. N" line.
  - Date **"DD Mon YYYY"**, then time **"HH:MM AM/PM"**.
  - An amount line of the form `<Type> -Rs. <amount> Rs. <balance>`: a signed amount followed by the running balance.
- **Type labels:** "Raast In", "Raast Out", "IBFT In", "IBFT Out", "Peer to Peer" and "Bill Payment". A "(1LINK)" continuation can follow a type. Samples also show "Online", "Debit Card charges", "Fees and Government Taxes" and "Reversed". `[SECONDARY]` ([G6](https://github.com/codewithwaheed/ledger-ai), [X9](https://www.scribd.com/document/788028529/NAYAPAY-STATEMENT))
- **Page furniture:** "CARRIED FORWARD" lines between pages. The footer says the statement is auto-generated and discrepancies must be reported within 15 days (NayaPay helpline and support email). `[SECONDARY]` ([G5](https://github.com/AnasSaleem547/nayapay-account-statement-to-csv-parser/blob/main/pdf_to_csv.py), [X9](https://www.scribd.com/document/788028529/NAYAPAY-STATEMENT))
- **Text vs scanned:** text-based (PyMuPDF, PDFKit and pypdf all work). The **reading order differs between PDF libraries**. `[SECONDARY]` ([G5](https://github.com/AnasSaleem547/nayapay-account-statement-to-csv-parser), [G6](https://github.com/codewithwaheed/ledger-ai))
- **Password:** not documented. `[UNVERIFIED]`

#### JazzCash and Easypaisa (brief)

- **JazzCash PDFs:**
  - Dates **"DD-Mon-YYYY"** with "HH:MM AM/PM" times.
  - G7 infers direction from wording ("Fee", "Top-up", "Merchant") because the column position is unreliable.

  `[SECONDARY]` ([G7](https://github.com/adsoftpk/four-bank-statement/blob/main/parsers.py))
- **Easypaisa:** two variants.
  - Scanned statements need OCR; embedded-text eStatements do not.
  - Dates are "Mon D, YYYY" or "D Mon YYYY".
  - Every row carries opening balance, incoming, outgoing and closing balance, plus a "Transaction ID" of 10–12 digits and tax, fee, discount and transaction-total fields. A "Balance B/F" row appears.

  `[SECONDARY]` ([G7 README](https://github.com/adsoftpk/four-bank-statement))

### Q3. Withholding-tax and profit certificates

**Legal basis.** Under s.164 of the Income Tax Ordinance 2001 and Rule 42 of the Income Tax Rules 2002, anyone collecting or deducting tax other than on salary "shall issue a certificate to the person from whom tax has been collected or deducted, in the form as set out in Part VII of the Second Schedule … within fifteen days after the end of the financial year".
- If requested before year-end, the certificate must be issued "within seven days of the request made".
- Duplicates must be issued on request.

`[PRIMARY]` ([S40](https://download1.fbr.gov.pk/Docs/201622142101721New-updatedIncomeTaxRules2002-withamendments-FBR-Abid10122015dox(3).pdf), FBR consolidation to 2015; later amendments not checked)

**The Part VII form** ("Certificate of Collection or Deduction of Tax (See rule 42)") has these fixed labels:
- "Certified that a sum of Rupees … (Amount of tax collected/deducted in figures)";
- name, NTN and CNIC;
- "on … (Date of collection/deduction) Or during the period From … To …";
- "under section … (Specify section of the Income Tax Ordinance, 2001)";
- "on account of … (Specify nature)";
- "vide … (Particulars…)";
- "on the value/amount of Rupees … (Gross amount on which tax collected/deducted)";
- a deposit table: Date of deposit, SBP/NBP/Treasury, Branch/City, Amount, Challan/Treasury No.

`[PRIMARY]` ([S40](https://download1.fbr.gov.pk/Docs/201622142101721New-updatedIncomeTaxRules2002-withamendments-FBR-Abid10122015dox(3).pdf), p. 223)

The brief's NayaPay "Rule 42" certificate ("On the amount of Rs. X", "Rs. Y") fits this form.

| Institution | Certificate(s) found | How to get it | Evidence |
|---|---|---|---|
| **Meezan** | Tax certificates (WHT); "Profit Payment" and balance-confirmation certificates | **WhatsApp Banking** ("Request Tax Certificates"); **any branch** ("Tax Certificate Issuance"); **Net Banking** side menu "Tax Certificate" → choose type and financial year (secondary). **No charge** for Zakat/WHT certificates | `[PRIMARY]` [S11](https://www.meezanbank.com/ways-to-bank/), [S13](https://www.meezanbank.com/meezan-bank-introduces-meezan-whatsapp-banking/), [S12](https://www.meezanbank.com/wp-content/themes/mbl/downloads/home-downloads/SOC-ENG-Jul-Dec-2026.pdf); net-banking path `[SECONDARY]` [X1](https://taxationpk.com/how-to-get-your-meezan-bank-tax-certificate/) |
| **Meezan** (format) | Sample "Tax Deduction Certificate" is a bank letter, **not** the Part VII layout. Per account: "Profit of an amount of Rs. … has been paid for the period of … to …"; "Withholding Tax of Rs. … has been deducted under **section 151**". Covers 1 Jul–30 Jun; dates DD-MON-YYYY | n/a | `[SECONDARY]` [X6](https://www.scribd.com/document/885269522/Meezan-Saving-Tax-2) |
| **Meezan** (236Y) | Charges schedule: "Advance Tax on international transactions will be applied as follows: Filer: 5% & Non-Filer: 10%" (cards). Which certificate reports this is not documented | n/a | `[PRIMARY]` [S12](https://www.meezanbank.com/wp-content/themes/mbl/downloads/home-downloads/SOC-ENG-Jul-Dec-2026.pdf); certificate `[UNVERIFIED]` |
| **MCB** | Withholding Tax Certificate | **MCB Live → Menu → Certificates → Withholding Tax Certificate**; "Select the account and financial year" → Download. Content and sections not published | `[PRIMARY]` [S15](https://mcblive.com/public/user_guide.pdf) p. 77, [S16](https://mcblive.com/public/faqs.pdf), [S20](https://apps.apple.com/us/app/mcb-live/id1584933248) |
| **SadaPay** | "Tax Certificate" | In-app chat; "within 5 working days". Sections covered not stated | `[PRIMARY]` [S5](https://help.sadapay.pk/en/articles/7908002-tax-certificate) |
| **NayaPay** | "Withholding Tax Certificate" | App → Statements; fiscal-year certificates. Brief: Rule 42 certificate for s.236Y | `[PRIMARY]` [S1](https://help.nayapay.com/article/251-how-can-i-view-my-documents-on-nayapay), [S3](https://www.facebook.com/nayapaypk/posts/long-lines-never-heard-of-em-get-your-annual-account-statements-and-withholding-/845175051056440/) |
| **Easypaisa** | "Profit on Debt" and "Tax on Foreign Remittance" certificates, past 3 years, PDF or image | App → Account → Tax Certificate | `[SECONDARY]` [X4](https://taxationpk.com/easypaisa-tax-certificate/) |
| **JazzCash** | None found for the wallet. Search results about "Jazz tax certificate" concern the telecom operator | n/a | `[UNVERIFIED]` |

**FBR-side withholding data (an alternative to extracting WHT from statements):**
- FBR's Maloomat displays tabs for "withholding data, Vehicles, Properties, Frequent travelling, Debit transactions, Credit transactions and Educational expenses". Third-party data about existing taxpayers "has been displayed under a menu in their IRIS login". `[PRIMARY]` ([S41](https://fbr.gov.pk/malomaat-web-portal-for-the-third-party-and-fbr-data-about-the-existing-and-unregistered-potential-t/173824))
- FBR tells taxpayers the tax-deduction information "is already made available in the IRIS tax returns portal". `[PRIMARY]` ([S42](https://www.fbr.gov.pk/all-taxpayers-are-requested-that-instead-of-visiting-the-maloomat-portal-for-verification-of-their-t/174135))
- An open-source tool processes an IRIS/Maloomat **"Payments & Withholding.xls"** (legacy `.xls`) export. `[SECONDARY]` ([G12](https://github.com/fbr-returns-helper/xls-withholding-analyzer))
  - Columns: Sr., Transaction Date (for example `03-Jul-2025`), Tax Year, Section, Payment Type, Value / Taxable Amount, Tax Amount.
  - Example Payment Type: "64060286-Export of Computer software /IT services / IT Enabled services u/s 154A @ 0.25%".
  - Which IRIS code applies to the owner is covered in research 02.

### Q4. How incoming foreign payments appear

**Home remittance vs export proceeds is decided by the ITRS purpose code, not by the statement description.**
- SBP's ITRS code guide:
  - 9181–9185 computer services, including **9184 "Export of Computer Software"**;
  - **9186 "Freelance of computer and information services: Remittances received by resident individuals/households from reputed overseas IT firms and online platforms"**;
  - **9471 "Workers' remittances-other sectors"** (family maintenance).

  `[PRIMARY]` ([S37](https://www.sbp.org.pk/assets/documents/laws_regulations/codeguide-1.pdf))
- Codes **9186** and **9249** ("Other free lance services") were added in Dec 2018 for business-to-customer receipts. These are routed through banks' **home-remittance agency arrangements**, which FE Circular 11 of 2018 opened to such receipts. `[PRIMARY]` ([S35](https://www.sbp.org.pk/circulars/dsitsdgen2018-026966), [S36](https://www.sbp.org.pk/epd/2018/FEC11.htm))
- In HBL's 2021 inward-remittance guideline, software and IT receipts need an invoice or agreement, "Form R" and an undertaking. For services exported by individuals it says "Branch Confirmation to Deduct WHT". `[PRIMARY, dated Dec 2021]` ([S29](https://www.hbl.com/assets/downloads/Guidelines_Inward_Remittances.pdf)) Rates belong to research 02.
- Statement descriptions seen publicly do not carry the purpose code. The **PRC does**. `[PRIMARY]` ([S33](https://www.sbp.org.pk/assets/documents/circulars/EPD-2025-CL2-Appendix-V-148.pdf))

**PRC, e-PRC and S-PRC (the most useful certificate for export income):**
- SBP required banks that are authorised foreign-exchange dealers (ADs) to issue **electronic PRCs and a Statement of PRCs (S-PRC)** by 29 Aug 2022. `[PRIMARY]` ([S30](https://www.sbp.org.pk/epd/2022/FEC5.htm), [S31](https://www.sbp.org.pk/assets/documents/circulars/FE-2022-C5-Annex-A.pdf))
  - **Same-bank model:** the bank emails the e-PRC and S-PRC or puts them on a portal.
  - **Different-bank model:** the intermediary bank passes complete MT-102/MT-103 information, and "the beneficiary bank will issue e-PRC and S-PRC".
  - "**At the end of each financial year, ADs shall send S-PRCs, through digital means, to all their customers who have been issued ePRC(s) during the year.**"
- **New formats from 1 Oct 2025.** `[PRIMARY]` ([S32](https://www.sbp.org.pk/epd/2025/FECL2.htm), [S33](https://www.sbp.org.pk/assets/documents/circulars/EPD-2025-CL2-Appendix-V-148.pdf), [S34](https://www.sbp.org.pk/assets/documents/circulars/EPD-2025-CL2-Appendix-V-149.pdf))
  - **e-PRC fields:** e-PRC No. (unique ID) and date; remitter name, ID and account; "Name of Remitting (originating) Financial Institution"; country and ITRS country code; beneficiary name, CNIC/NTN, IBAN and bank; "Date of Realization of Proceeds" (DD-MM-YYYY); total proceeds in foreign currency (FCY); FCY retained in an exporters' special foreign-currency account (ESFCA); amount in FCY; rate of conversion; amount in PKR; purpose of remittance; **Purpose Code (as per ITRS)**; transaction reference number. It notes "e-PRC would be issued only once for each incoming remittance".
  - **S-PRC** ("For the Financial Year …"): one row per remittance with the same fields plus e-PRC number and date.
- **MCB (Dec 2021 guide):** issues e-PRC and S-PRC for foreign-currency home remittances. "**Currently MCB Bank is not issuing e-PRC / S-PRC for Local Currency Home Remittance and IBFT Incoming Remittance transactions.**" `[PRIMARY, dated]` ([S19](https://www.mcb.com.pk/assets/documents/Guide_for_ePRC__SPRC_Verification_via_MCB_Website.pdf))
- **Meezan:** PRC issuance is "Within one year - FREE; Over the period one year – Rs.500/-; Duplicate PRC – Rs.700/- (Free for Home Remittance Customers)". `[PRIMARY]` ([S12](https://www.meezanbank.com/wp-content/themes/mbl/downloads/home-downloads/SOC-ENG-Jul-Dec-2026.pdf))
- **SadaPay:** PRC on request via chat. You supply the beneficiary name, account number and bank; the amount credited in PKR and in foreign currency; the date of credit; the transfer number; and the **purpose code**. PKR 464 is charged for transactions over a year old, "aligns with the recent policy adjustment made by our **partner bank**". `[PRIMARY]` ([S6](https://help.sadapay.pk/en/articles/7908004-remittance-certificate-prc))

**By channel:**

| Channel | What is documented | Tag |
|---|---|---|
| **Payoneer** | Meezan app integration (real-time USD→PKR; PRC emailed) ([S14](https://www.payoneer.com/resources/payoneer-and-meezan-bank-transform-international-payment-withdrawals-in-pakistan-with-new-partnership/)). HBL app integration, 30 Apr 2026 ([S25](https://www.payoneer.com/resources/business/payoneer-partners-with-hbl-bank-to-enable-real-time-withdrawals-for-pakistani-customers/)). **NayaPay:** withdraw from Payoneer to the NayaPay IBAN; "Bank name > NayaPay", "Bank account currency > PKR", 19 Aug 2023 ([S2](https://help.nayapay.com/article/241-how-can-i-transfer-money-from-payoneer-to-my-nayapay-account)). **SadaPay** lists Payoneer as a source ([S8](https://help.sadapay.pk/en/articles/7120961-how-can-i-receive-remittances-with-sadapay-account)). The routing rail and description text are not documented | `[PRIMARY]`; rail `[UNVERIFIED]` |
| **Payoneer (older)** | 2020 report: Payoneer to JazzCash freelancer mobile accounts ([X11](https://profit.pakistantoday.com.pk/2020/01/23/intl-payment-platform-payoneer-expands-services-in-pakistan)). A Payoneer community thread said withdrawals went via a microfinance bank as IBFT; the page now returns 404 | `[SECONDARY]` / `[UNVERIFIED]` |
| **Wise** | Pays PKR by IBAN to personal accounts only ("You can't send to a business account"; "recipient … must be a private individual"). It warns that accounts which "do not allow any IBFT credit … or … inward local transfers" will reject payments, which implies **Wise payouts arrive as domestic inward transfers via a local partner** ([S26](https://wise.com/help/articles/2932334/guide-to-pkr-transfers)). SadaPay lists "Transferwise" ([S8](https://help.sadapay.pk/en/articles/7120961-how-can-i-receive-remittances-with-sadapay-account)) | `[PRIMARY]`; inference `[UNVERIFIED]` |
| **Remitly** | SadaPay lists Remitly (US, Canada, UK) ([S8](https://help.sadapay.pk/en/articles/7120961-how-can-i-receive-remittances-with-sadapay-account)). Description text not documented | `[PRIMARY]` / `[UNVERIFIED]` |
| **Thunes** | Thunes's payout coverage for Pakistan: bank deposit (real-time); cash pickup at Bank Alfalah and Bank of Punjab; wallets Easypaisa, JazzCash, **SadaPay**, Finja and **NayaPay** (consumer-to-consumer) and Easypaisa, JazzCash, **SadaPay** and Finja (business-to-consumer). Dated 2022 ([S27](https://www.temenos.com/wp-content/uploads/2022/10/Thunes-Payouts-Network-Coverage-Detailed-Summary-2.pdf)). Thunes and Bank Alfalah (25 Aug 2021) give access to all Pakistani bank accounts ([S28](https://www.thunes.com/news/thunes-enables-real-time-consumer-payments-to-pakistan-with-bank-alfalah/)). **No public document ties Thunes to Payoneer or Wise payouts in Pakistan.** The brief's "IBFT In … from Thunes" fits a Thunes payout arriving over IBFT, but the upstream sender cannot be identified from public sources | `[PRIMARY, dated]`; link `[UNVERIFIED]` |
| **Raast** | SBP's instant payment system ([S18](https://www.mcb.com.pk/faqs/mcb-live-faqs)). From 15 Jan 2026, exchange companies may, with approval, "disburse home remittances in beneficiary's accounts/wallets … digitally through Raast" ([S39](https://www.sbp.org.pk/circulars/epd-circular-letter-no-02-of-2026)). Foreign-origin money can therefore look like a Raast P2P credit | `[PRIMARY]` |
| **IBFT** | NayaPay "IBFT In"/"IBFT Out" types; MCB "INTERBANK FUNDS RECEIVING" ([G6](https://github.com/codewithwaheed/ledger-ai), [G7](https://github.com/adsoftpk/four-bank-statement)) | `[SECONDARY]` |
| **Meezan home remittance** | Credits described "Remittance From `<remitter or money-transfer operator>` … STAN(n)" ([G3](https://github.com/AteebNoOne/meezan-statement-calculator/blob/main/src/data/sampleStatement.test.ts)) | `[SECONDARY]` |
| **SadaBiz (SadaPay)** | Invoicing platform of SadaPay UK Ltd. Clients pay by card via payment link; funds reach the SadaBiz account in PKR "within 6 business days"; "We provide you with a Proceeds Realisation Certificate (PRC) for all your incoming payments"; 2% service fee ([S10](https://sadabiz.co.uk/), [X12](https://www.linkedin.com/posts/sadapay_freelancers-this-is-for-you-activity-7094987982792720385-Excx)) | `[PRIMARY]` |
| **JazzCash / Easypaisa** | JazzCash Freelance Digital Account: "Receive international payments from global platforms"; "MDR on receiving International Payments through 'pay via link' (Freelance segment) 5%"; "Receive International Remittance: Free" ([S24](https://www.jazzcash.com.pk/mobile-account/freelance-payments/), [S22](https://www.jazzcash.com.pk/assets/documents/SOC-Q3-2026-Final.pdf)). Easypaisa "provides the ability to receive remittances … from other countries" ([S21](https://easypaisa.com.pk/faqs/)) | `[PRIMARY]` |

SadaPay's remittance FAQ also says: "you cannot link your account to any of the remittance platforms". Amounts are "converted to PKR when received". There is no fee, and arrival is "usually instant … up to 1-2 working days". `[PRIMARY]` ([S8](https://help.sadapay.pk/en/articles/7120961-how-can-i-receive-remittances-with-sadapay-account), 14 Aug 2025)

### Q5. Open-source parsers on GitHub

The searches used: sadapay, nayapay, meezan, mcb, easypaisa, jazzcash, "pakistan bank statement", fbr/iris, and in-README variants. Dates are the last push. "No licence" means GitHub detects no licence file.

| Repo | Institution(s) | What it does and how | Licence | Last push |
|---|---|---|---|---|
| [ibrahimahtsham/meezan-statement-parser-and-expense-tracker](https://github.com/ibrahimahtsham/meezan-statement-parser-and-expense-tracker) (G1) | Meezan **CSV** | React app. Hand-rolled CSV parser: account and balances from rows 1–4, header located by "booking date" + "value date", 7 fixed columns. Merges yearly CSVs (1-year export limit). Keyword categoriser lists real Meezan description strings | No licence file (README says MIT) | 2025-06-28 |
| [theajmalrazaq/mznviz](https://github.com/theajmalrazaq/mznviz) (G2) | Meezan **CSV/XLSX** | React PWA, local only. SheetJS converts XLSX to CSV. Finds "OPENING BALANCE"/"CLOSING BALANCE" lines; takes date, description, debit, credit and balance from columns 0, 3, 4, 5 and 6 | No licence file (README says MIT) | 2026-02-14 |
| [AteebNoOne/meezan-statement-calculator](https://github.com/AteebNoOne/meezan-statement-calculator) (G3) | Meezan **PDF** (2026 layout) | pdf.js text items grouped by y-coordinate (±6 px). Regexes for "DD Mon YYYY" dates and `+`/`-` PKR amounts; multi-line descriptions; footer filtering. Gemini "AI OCR" fallback for scans (sends the file to a server) | No licence | 2026-09-19 |
| [ibrahimshkeel1/atlas](https://github.com/ibrahimshkeel1/atlas) (G4) | Meezan, HBL, UBL PDF | Regex line parser (`DD Mon YYYY … ±Rs. amt Rs. bal`) plus AI extraction. **Fixtures are synthetic**, so weak layout evidence | No licence | 2026-09-13 |
| [AnasSaleem547/nayapay-account-statement-to-csv-parser](https://github.com/AnasSaleem547/nayapay-account-statement-to-csv-parser) (G5) | NayaPay **PDF** (annual) | PyMuPDF `get_text()`. Uses each `Rs. x.xx` balance line as a record anchor and walks back to amount, type, time and date. Handles the "(1LINK)" wrap; drops "Carried Forward" and footer lines | No licence | 2025-10-14 |
| [codewithwaheed/ledger-ai](https://github.com/codewithwaheed/ledger-ai) (G6) | NayaPay **PDF** | Swift/iOS (PDFKit). Block parser keyed on the amount line `<Type> ±Rs. amt Rs. bal`. Known type labels; counterparty regexes. Documents renderer-dependent text order; tests with Sep 2026 fixtures | No licence | 2026-09-22 |
| [adsoftpk/four-bank-statement](https://github.com/adsoftpk/four-bank-statement) (G7) | **MCB (MCB Live + eStatement)**, HBL, JazzCash, Easypaisa | **Local Streamlit app** (Python). PyMuPDF text when a page has ≥80 alphanumeric characters, otherwise Tesseract OCR via pdfium/poppler. Bank-specific regex parsers; running-balance reconciliation to infer MCB eStatement direction; confidence and "Needs Review" flags; "Unparsed Lines" sheet; fuzzy cross-statement matching; Excel/CSV export | No licence | 2026-09-17 |
| [peer231/bank-statement-pdf](https://github.com/peer231/bank-statement-pdf) (G8) | Same as G7 | Near-identical README; one appears to be a copy of the other | No licence | 2026-09-07 |
| [Muhammad-Uzair-Kayani/FinParse](https://github.com/Muhammad-Uzair-Kayani/FinParse) (G9) | **MCB** PDF | pdfplumber `extract_tables()`. Maps columns from the header row (Date, Description, Reference Number, Amount, Balance); `Dr`/`Cr` suffix parser; 10 date formats. Rejects password-protected PDFs; no OCR | No licence | 2026-08-05 |
| [abdullah2993/alfalah-statement-parser](https://github.com/abdullah2993/alfalah-statement-parser) (G10) | Bank Alfalah PDF | Rust (`pdf-extract`, `regex`). Amounts held in paisa. **Fails loudly if opening + running totals ≠ closing balance** | No licence | 2026-08-09 |
| [sania-builds/-bank-statement-converter](https://github.com/sania-builds/-bank-statement-converter) (G11) | HBL PDF | pdfplumber tables → Excel with categories | No licence | 2026-06-05 |
| [fbr-returns-helper/xls-withholding-analyzer](https://github.com/fbr-returns-helper/xls-withholding-analyzer) (G12) | FBR IRIS "Payments & Withholding.xls" | xlrd; groups withholding by tax year, section and payment type; lets bank-confirmed rows supplement FBR data | No licence | 2026-07-11 |
| [engrahsaninam/file-pakistan-fbr-return](https://github.com/engrahsaninam/file-pakistan-fbr-return) (G13) | Guidance, not a parser | Evidence-first FBR filing "skill" with normalized-transaction and evidence-register templates; stresses PRC/e-PRC and purpose codes for export positions | **MIT** | 2026-07-31 |
| [abdu1hanan/Velops](https://github.com/abdu1hanan/Velops) (G14), [Anas923/nayapay-expense-tracker](https://github.com/Anas923/nayapay-expense-tracker) (G15) | NayaPay | Parse **notifications** (G14) and **transaction emails** (G15), not statements | No licence file (G15 README says MIT) | 2026-03-01 / 2026-01-28 |
| [Techylem/hbl-bank-statement-txt-csv](https://github.com/Techylem/hbl-bank-statement-txt-csv) (G16) | HBL text statements | Not inspected in depth | Not checked | 2021-08-10 |

- **No SadaPay statement parser was found.**
- **Not counted:**
  - [waki44/fbr-wala](https://github.com/waki44/fbr-wala) (G17): a manual-entry tax calculator with no statement parsing.
  - Several AI or SMS-based finance apps.
  - One repo with the same name as this project.

**What the repos show, taken together:**
- Institutions ship **several layouts**: Meezan has three and MCB has two.
- Robust parsers **anchor on amount or balance lines and validate with running balances** rather than trusting column positions.
- Every Meezan, MCB, NayaPay and SadaPay sample was **text-based**. OCR only appears for Easypaisa and HBL.
- Nobody handles passwords; all the parsers expect PDFs that are already unlocked.

---

## Implications for the tool

1. **Make CSV/XLSX the first-choice input where it exists.** That means MCB Live (CSV), NayaPay (CSV) and Meezan (CSV/XLSX). Keep PDF parsing for SadaPay (PDF only), emailed e-statements and history. The CSV layouts are **not publicly documented** except Meezan's (reverse-engineered by G1 and G2), so the owner needs to export one real file from each institution before profiles are written.
2. **One profile per layout, not per institution.** Detect the variant from its header signature, for example:
   - Meezan: "Booking Date … Credit … Debit" PDF, the "Booking Date, Value Date, Doc No" CSV, or the "E-STATEMENT OF ACCOUNT" PDF.
   - MCB: the "DD Mon YYYY … Dr/Cr" MCB Live PDF or the "DD/MM/YY" eStatement.
   - SadaPay: the in-app "Account Statement" or the support-generated "ISDCST".

   **Map columns by header name.** Meezan's CSV has Debit before Credit, while the PDF has Credit before Debit.
3. **Check every parse with the balance equation.** Use opening + credits − debits = closing for the statement and the running balance per row (as G7 and G10 do). Use the same arithmetic to **infer direction** when column positions are lost (MCB eStatement). Compare the result with the "Total debit/credit" or "Total Income/Spent" figures the brief already plans to check.
4. **NayaPay may not need a computed balance.** Public samples show Opening and Closing Balance on the summary card, contrary to brief §6. Verify against the owner's files. **SadaPay does need one:** the in-app statement accepts any start and end date from 1 Jul 2023, so request exactly 1 Jul–30 Jun and anchor as the brief proposes.
5. **Add certificate document types beside the 236Y certificate:**
   - a **generic Rule 42 parser** keyed on the Part VII labels ("Certified that a sum of Rupees", "under section", "on the value/amount of", "From … To");
   - the **Meezan "Tax Deduction Certificate"** layout (s.151, gross profit, WHT, period);
   - the **MCB Live WHT certificate** (layout unknown; needs a sample).

   These can replace or verify the "Payment of Profit" / "Withholding Tax" pairing logic.
6. **Treat the S-PRC as the authoritative itemised export-income list.** SBP requires banks to send it digitally at financial-year end, with a new format from 1 Oct 2025. Import S-PRC and e-PRC as a document type, since they carry the FCY amount, PKR amount, rate, remitting institution and **ITRS purpose code**. Use 9186 or 9184/9185 for export or freelance income and 9471 for home remittance. Reconcile each PRC to a statement credit; one e-PRC is issued per remittance, which helps de-duplication. Expect **gaps for IBFT-routed receipts** (MCB 2021 note) and for wallets, where PRCs come from partner banks only on request.
7. **Keyword matching alone will miss foreign receipts.** Foreign money can arrive as IBFT from a partner bank (Wise, Thunes via Bank Alfalah), as a Raast P2P credit (exchange companies from 2026), as "Remittance From …" (Meezan), as "IBFT In" (NayaPay) or under opaque prefixes such as `TRANSF CR/ICT/` or `MISC CDT/` (SadaPay).
   - Keep the counterparty list configurable per profile.
   - Match short words like "Wise" with word boundaries.
   - Route unmatched large credits to review, as the brief already plans.
8. **Offer the FBR cross-check.** The IRIS/Maloomat "Payments & Withholding" `.xls` lists every withholding record by section and value. It can reconcile both WHT totals and s.154A export entries against the parsed statements.
9. **Passwords.** The only documented schemes are MCB Live PDF (last 4 digits of the account number) and MCB certificates (birth year). Keep "unlock before upload", or add optional local decryption with a password typed each run and never stored.
10. **Extraction engine.** All four target institutions produce text PDFs, so pdfplumber or PyMuPDF with **coordinate-aware word extraction** is enough for v1. G6 shows that reading order varies by library, so avoid depending on raw text order. OCR (Tesseract) is only needed if Easypaisa or HBL are added.
11. **Date and amount formats vary widely.** Seen so far: `DD Mon YYYY`, `DD Mon, YYYY`, `DD/MM/YY`, `DD/MM/YYYY`, `DD-Mon-YYYY` and `Mon D, YYYY`. Amounts appear as `+ PKR1,234.56`, `-Rs. 1,234`, `1,234.56Dr` and `PKR      1234.56` (illustrative values). Put date and amount grammars in the bank profiles, as the brief already plans for regexes.

## Could not verify / open questions

- **CSV/XLSX column layouts** for MCB Live CSV, NayaPay CSV and Meezan XLSX. Also where exactly Meezan's CSV export lives (app, internet banking or both) and whether the 1-year limit still applies. *Owner: export one sample of each.*
- **Whether SadaPay offers any CSV export.** None is documented.
- **PDF password schemes** for Meezan, SadaPay, NayaPay and MCB's emailed e-statement.
- **NayaPay opening/closing balance.** Public evidence says it is printed; the brief says it is not. Possibly a layout change or a monthly vs annual difference.
- **Contents of certificates:**
  - SadaPay's "Tax Certificate" (which sections?);
  - MCB's WHT certificate (format and sections);
  - NayaPay's WHT certificate beyond 236Y;
  - whether Meezan reports 236Y card tax on a certificate.
- **Exact statement descriptions** for Payoneer, Wise and Remitly credits at each institution, and which upstream sender(s) the "IBFT In … from Thunes" credits come from.
- **Whether PRCs or S-PRCs are issued for IBFT-routed foreign receipts** today. MCB said no in 2021. Also whether the partner banks of SadaPay and NayaPay send S-PRCs automatically.
- **The IRIS/Maloomat "Payments & Withholding" export:** its location in IRIS, its availability to every taxpayer and its exact columns. The only evidence is one repo.
- **Rule 42 text** was read from FBR's 2015 consolidation; later amendments were not checked.
- **Thunes coverage** comes from a 2022 document; current Pakistani partners may differ.
- **Raast references** in Meezan samples start with bank-like prefixes. Whether these identify the originating institution (useful for matching internal transfers) is `[UNVERIFIED]`.
- **Easypaisa's "Tax on Foreign Remittance" certificate** (secondary source only), and whether JazzCash issues any wallet WHT certificate.

## Sources

**Primary: institutions**
- **S1** `[PRIMARY]` NayaPay Help, "How can I view my documents on NayaPay?" (updated 24 Jun 2025): https://help.nayapay.com/article/251-how-can-i-view-my-documents-on-nayapay
- **S2** `[PRIMARY]` NayaPay Help, "How can I transfer money from Payoneer to my NayaPay account?" (19 Aug 2023): https://help.nayapay.com/article/241-how-can-i-transfer-money-from-payoneer-to-my-nayapay-account
- **S3** `[PRIMARY]` NayaPay official Facebook post on annual statements and WHT certificate (undated): https://www.facebook.com/nayapaypk/posts/long-lines-never-heard-of-em-get-your-annual-account-statements-and-withholding-/845175051056440/
- **S4** `[PRIMARY]` SadaPay Help, "Account Statement" (12 Jul 2024): https://help.sadapay.pk/en/articles/7907996-account-statement
- **S4b** `[PRIMARY]` SadaPay Help, "Account Statement" (Urdu) (12 Jul 2024): https://help.sadapay.pk/en/articles/8123235-account-statement
- **S5** `[PRIMARY]` SadaPay Help, "Tax Certificate" (31 May 2024): https://help.sadapay.pk/en/articles/7908002-tax-certificate
- **S6** `[PRIMARY]` SadaPay Help, "Remittance Certificate/PRC" (31 May 2024): https://help.sadapay.pk/en/articles/7908004-remittance-certificate-prc
- **S7** `[PRIMARY]` SadaPay Help, "Account Maintenance Certificate" (31 May 2024): https://help.sadapay.pk/en/articles/7908001-account-maintenance-certificate
- **S8** `[PRIMARY]` SadaPay Help, "How can I receive remittances with Sadapay Account?" (14 Aug 2025): https://help.sadapay.pk/en/articles/7120961-how-can-i-receive-remittances-with-sadapay-account
- **S9** `[PRIMARY]` SadaPay Help, "How can I deposit money into my SadaPay wallet?" (31 May 2024): https://help.sadapay.pk/en/articles/4947095-how-can-i-deposit-money-into-my-sadapay-wallet
- **S10** `[PRIMARY]` SadaBiz (SadaPay UK Ltd): https://sadabiz.co.uk/
- **S11** `[PRIMARY]` Meezan Bank, "Ways to Bank": https://www.meezanbank.com/ways-to-bank/
- **S12** `[PRIMARY]` Meezan Bank Schedule of Charges, Jul–Dec 2026: https://www.meezanbank.com/wp-content/themes/mbl/downloads/home-downloads/SOC-ENG-Jul-Dec-2026.pdf
- **S13** `[PRIMARY]` Meezan Bank, WhatsApp Banking launch (2 Aug 2023): https://www.meezanbank.com/meezan-bank-introduces-meezan-whatsapp-banking/
- **S14** `[PRIMARY]` Payoneer, "Payoneer and Meezan Bank Transform International Payment Withdrawals…" (28 Feb 2025): https://www.payoneer.com/resources/payoneer-and-meezan-bank-transform-international-payment-withdrawals-in-pakistan-with-new-partnership/
- **S15** `[PRIMARY]` MCB Live User Guide, PDF modified 23 Jan 2026 (pp. 32, 61–63, 76–77): https://mcblive.com/public/user_guide.pdf
- **S16** `[PRIMARY]` "MCB Live FAQs 23 June 2025" (PDF): https://mcblive.com/public/faqs.pdf
- **S17** `[PRIMARY]` MCB e-Statement page: https://www.mcb.com.pk/self-service-channels/personal-services-estatement
- **S18** `[PRIMARY]` MCB Live FAQs (web): https://www.mcb.com.pk/faqs/mcb-live-faqs
- **S19** `[PRIMARY]` MCB, "Guide for e-PRC & S-PRC Verification Process via MCB Website" (29 Dec 2021): https://www.mcb.com.pk/assets/documents/Guide_for_ePRC__SPRC_Verification_via_MCB_Website.pdf
- **S20** `[PRIMARY]` MCB Live, Apple App Store listing: https://apps.apple.com/us/app/mcb-live/id1584933248
- **S21** `[PRIMARY]` Easypaisa FAQs: https://easypaisa.com.pk/faqs/
- **S22** `[PRIMARY]` JazzCash (Mobilink Microfinance Bank) Branchless Banking Schedule of Charges Q3 2026: https://www.jazzcash.com.pk/assets/documents/SOC-Q3-2026-Final.pdf
- **S23** `[PRIMARY]` JazzCash / MMBL Terms and Conditions for Mobile Account: https://www.jazzcash.com.pk/tc
- **S24** `[PRIMARY]` JazzCash, Freelance Payments: https://www.jazzcash.com.pk/mobile-account/freelance-payments/
- **S25** `[PRIMARY]` Payoneer, "Payoneer partners with HBL Bank…" (30 Apr 2026): https://www.payoneer.com/resources/business/payoneer-partners-with-hbl-bank-to-enable-real-time-withdrawals-for-pakistani-customers/
- **S26** `[PRIMARY]` Wise Help Centre, "Guide to PKR transfers": https://wise.com/help/articles/2932334/guide-to-pkr-transfers
- **S27** `[PRIMARY, dated 2022]` Thunes, "Payouts Network Coverage – Detailed Summary" (hosted by Temenos): https://www.temenos.com/wp-content/uploads/2022/10/Thunes-Payouts-Network-Coverage-Detailed-Summary-2.pdf
- **S28** `[PRIMARY]` Thunes, "Thunes enables real-time consumer payments to Pakistan with Bank Alfalah" (25 Aug 2021): https://www.thunes.com/news/thunes-enables-real-time-consumer-payments-to-pakistan-with-bank-alfalah/
- **S29** `[PRIMARY, dated Dec 2021]` HBL, Guidelines for Inward Remittances: https://www.hbl.com/assets/downloads/Guidelines_Inward_Remittances.pdf

**Primary: regulators**
- **S30** `[PRIMARY]` SBP FE Circular No. 05 of 2022, "Automated Issuance and Verification of ePRC" (5 Aug 2022): https://www.sbp.org.pk/epd/2022/FEC5.htm
- **S31** `[PRIMARY]` SBP FE Circular 05/2022, Annexure A (guidelines): https://www.sbp.org.pk/assets/documents/circulars/FE-2022-C5-Annex-A.pdf
- **S32** `[PRIMARY]` SBP EPD Circular Letter No. 02 of 2025, "Revised Format of ePRC" (12 Jun 2025): https://www.sbp.org.pk/epd/2025/FECL2.htm
- **S33** `[PRIMARY]` SBP Appendix V-148 (e-PRC format, 2025): https://www.sbp.org.pk/assets/documents/circulars/EPD-2025-CL2-Appendix-V-148.pdf
- **S34** `[PRIMARY]` SBP Appendix V-149 (S-PRC format, 2025): https://www.sbp.org.pk/assets/documents/circulars/EPD-2025-CL2-Appendix-V-149.pdf
- **S35** `[PRIMARY]` SBP DS.ITSD/GEN/2018-026966, "Monthly FX Returns (ITRS) – Addition of purpose codes" (6 Dec 2018): https://www.sbp.org.pk/circulars/dsitsdgen2018-026966
- **S36** `[PRIMARY]` SBP FE Circular No. 11 of 2018, "Extension in Home Remittance Services" (22 Oct 2018): https://www.sbp.org.pk/epd/2018/FEC11.htm
- **S37** `[PRIMARY]` SBP ITRS code guide (codes 9181–9186, 9471): https://www.sbp.org.pk/assets/documents/laws_regulations/codeguide-1.pdf
- **S38** `[PRIMARY]` SBP EPD Circular Letter No. 02 of 2023, "Exports of Software, IT and ITeS" (13 Jan 2023; background on exporters' special FCY accounts): https://www.sbp.org.pk/epd/2023/FECL2.htm
- **S39** `[PRIMARY]` SBP EPD Circular Letter No. 02 of 2026, exchange companies may disburse home remittances via Raast (15 Jan 2026): https://www.sbp.org.pk/circulars/epd-circular-letter-no-02-of-2026
- **S40** `[PRIMARY]` FBR, Income Tax Rules 2002 (consolidated with amendments to 2015), Rule 42 and Second Schedule Part VII: https://download1.fbr.gov.pk/Docs/201622142101721New-updatedIncomeTaxRules2002-withamendments-FBR-Abid10122015dox(3).pdf
- **S41** `[PRIMARY]` FBR, Maloomat web portal notice: https://fbr.gov.pk/malomaat-web-portal-for-the-third-party-and-fbr-data-about-the-existing-and-unregistered-potential-t/173824
- **S42** `[PRIMARY]` FBR, notice that tax-deduction data is available in IRIS: https://www.fbr.gov.pk/all-taxpayers-are-requested-that-instead-of-visiting-the-maloomat-portal-for-verification-of-their-t/174135

**GitHub repositories** (`[PRIMARY]` for what each repo does; `[SECONDARY]` as evidence of an institution's layout)
- **G1** https://github.com/ibrahimahtsham/meezan-statement-parser-and-expense-tracker
- **G2** https://github.com/theajmalrazaq/mznviz
- **G3** https://github.com/AteebNoOne/meezan-statement-calculator
- **G4** https://github.com/ibrahimshkeel1/atlas
- **G5** https://github.com/AnasSaleem547/nayapay-account-statement-to-csv-parser
- **G6** https://github.com/codewithwaheed/ledger-ai
- **G7** https://github.com/adsoftpk/four-bank-statement
- **G8** https://github.com/peer231/bank-statement-pdf
- **G9** https://github.com/Muhammad-Uzair-Kayani/FinParse
- **G10** https://github.com/abdullah2993/alfalah-statement-parser
- **G11** https://github.com/sania-builds/-bank-statement-converter
- **G12** https://github.com/fbr-returns-helper/xls-withholding-analyzer
- **G13** https://github.com/engrahsaninam/file-pakistan-fbr-return
- **G14** https://github.com/abdu1hanan/Velops
- **G15** https://github.com/Anas923/nayapay-expense-tracker
- **G16** https://github.com/Techylem/hbl-bank-statement-txt-csv
- **G17** https://github.com/waki44/fbr-wala

**Secondary**
- **X1** `[SECONDARY]` TaxationPk, "How to Get Your Meezan Bank Tax Certificate?" (29 Apr 2024): https://taxationpk.com/how-to-get-your-meezan-bank-tax-certificate/
- **X2** `[SECONDARY]` TaxationPk, "How to Get Your NayaPay Tax Certificate?" (15 May 2024): https://taxationpk.com/how-to-get-your-nayapay-tax-certificate/
- **X3** `[SECONDARY]` TaxationPk on LinkedIn, NayaPay statements and tax certificate (16 May 2024): https://www.linkedin.com/pulse/access-your-nayapay-bank-statements-tax-certificate-filing-mefyf
- **X4** `[SECONDARY]` TaxationPk, Easypaisa tax certificate (30 Apr 2024): https://taxationpk.com/easypaisa-tax-certificate/
- **X5** `[SECONDARY]` Scribd user upload, Meezan "E-STATEMENT OF ACCOUNT" (May 2021), structure only: https://www.scribd.com/document/525319881/5372389-010517-01-05-2021-31-05-2021-1-unlocked
- **X6** `[SECONDARY]` Scribd user upload, Meezan "Tax Deduction Certificate" (tax year 2023), structure only: https://www.scribd.com/document/885269522/Meezan-Saving-Tax-2
- **X7** `[SECONDARY]` Scribd user upload, SadaPay in-app "Account Statement" (generated Sep 2024), structure only: https://www.scribd.com/document/775065859/sadapay-account-statement-2023-07-01-2024-09-05
- **X8** `[SECONDARY]` Scribd user upload, SadaPay "ISDCST - Detailed Customer Statement" (Mar 2023), structure only: https://www.scribd.com/document/633148332/SadaPay-Account-Statement-Virtual-Card
- **X9** `[SECONDARY]` Scribd user upload, NayaPay account statement (undated), structure only: https://www.scribd.com/document/788028529/NAYAPAY-STATEMENT
- **X10** `[SECONDARY]` Business Recorder, "IT exporters, freelancers: SBP eases reporting formats" (18 Jun 2025): https://www.brecorder.com/news/40368328/it-exporters-freelancers-sbp-eases-reporting-formats
- **X11** `[SECONDARY]` Profit / Pakistan Today, "Int'l payment platform Payoneer expands services in Pakistan" (23 Jan 2020): https://profit.pakistantoday.com.pk/2020/01/23/intl-payment-platform-payoneer-expands-services-in-pakistan
- **X12** `[PRIMARY]` SadaPay official LinkedIn post announcing SadaBiz (~2023): https://www.linkedin.com/posts/sadapay_freelancers-this-is-for-you-activity-7094987982792720385-Excx
