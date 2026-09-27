# 01 — FBR income-tax rules for the statement aggregator (Tax Years 2025 and 2026)

## Scope & date researched

- **Researched on:** 27 September 2026. The return being filed is **Tax Year 2026 (TY2026)**. That tax year runs from 1 July 2025 to 30 June 2026 and takes its name from the calendar year in which it ends (s.74) [PRIMARY, S1 p.160].
- **Law read:**
  - **TY2026:** the Income Tax Ordinance 2001 ("ITO") as amended by the Finance Act 2025. The base text is FBR's consolidation "amended up to 31.07.2025" [S1]. Every provision cited here was re-checked against the "amended up to 20.02.2026" consolidation [S2]. That version includes the mid-year Income Tax (Amendment) Acts 2025/2026, and none of the provisions below changed.
  - **TY2025:** the ITO "amended up to 30.06.2024", which includes the Finance Act 2024 [S4].
  - **TY2027 onward:** the ITO "amended up to 30.06.2026" [S3] and the Finance Act 2026 [S7] (in force from 1 July 2026). These are noted only where they change what the tool must do in future years.
  - **Also read:** the Income Tax Rules 2002 as amended to 15.09.2026 [S10], FBR's withholding rate card for 2025-26 [S5], FBR explanatory circulars [S6, S8, S9], the TY2026 return-form notification SRO 1495(I)/2026 [S11], and SBP's FE Manual, purpose-code list and EMI Regulations [S13–S16].
- **Method:**
  - FBR and SBP PDFs were downloaded and searched as text.
  - The TY2026 return form [S11] is a scan of IRIS screenshots. It was read by OCR, and the key rows were confirmed by eye on cropped images. Anything taken from it is marked "(scan)".
  - Page references such as "S1 p.349" are **PDF page numbers of the copy downloaded on 27 Sep 2026**. FBR re-issues these files, so page numbers can drift; the section numbers are the stable reference.
- **Privacy:** search queries were generic. No names, account numbers or figures from the brief were used anywhere.
- **Out of scope:**
  - The full IRIS code mapping is in `02-fbr-iris-codes.md`. The few codes quoted here only show *where* an item sits in the return.
  - Tax computation.
  - Advice. This is research to support a design and is not tax advice; filing positions should be confirmed with a tax practitioner.
- **Confidence tags:**
  - **[PRIMARY]** — read in the statute, rules, an FBR or SBP document, or the institution's own page.
  - **[SECONDARY]** — a tax firm, news outlet or vendor.
  - **[UNVERIFIED]** — an inference, or not confirmed in any source.
  - Source keys ("S#") resolve to URLs in the **Sources** section.

## Summary

| Fact | Value | Tax year | Confidence | Source |
|---|---|---|---|---|
| s.154A rate: IT/ITeS exporter **registered with and duly certified by PSEB** | 0.25% of proceeds | TY2024–TY2026; extended to TY2029 by FA 2026 | PRIMARY | S1 p.349 (s.154A(1)(a)), p.548 (Div IVA); S3 p.566; S7 p.58 |
| s.154A rate: **any other case** (IT exporter not on PSEB, non-IT services, etc.) | **1% of proceeds** | TY2025, TY2026 (unchanged TY2027) | PRIMARY | S1 p.548; S4 p.538 |
| s.154A rate if **not on the Active Taxpayers' List (ATL)** | Same rate: the Tenth Schedule does not apply to s.154A (rule 10(ca)). FBR's own rate card wrongly shows 0.5% / 2% | TY2025, TY2026 | PRIMARY (the conflict is between two primary documents) | S1 p.785; S8 p.9; S5 p.7 |
| Nature of s.154A tax | **Final tax** if four conditions hold: return filed; withholding statements filed if required; sales-tax returns filed if required (this one is waived only for PSEB IT exporters); no foreign tax credit claimed. The taxpayer can opt out each year when filing | TY2025, TY2026 | PRIMARY | S1 p.349–350, p.369–370 |
| Did FA 2024 / FA 2025 change s.154A? | **No.** FA 2024 changed s.154 (goods exports) from final to minimum tax and added s.147(6C); s.154A was left alone. FA 2025 made no change | TY2025, TY2026 | PRIMARY | S1 p.348 fn, p.321, p.369 fn; S6 p.1 |
| Who collects s.154A tax | The authorized dealer in foreign exchange, at realization of the proceeds. No Board/SBP procedure rules under s.154A(5) were found | TY2025, TY2026 | PRIMARY | S1 p.349–350; S10 (text search found no rule citing s.154A) |
| Where s.154A sits in the TY2026 return | Business → Tax Deduction → **Final Tax** → "Export of services u/s 154A @1%" **64060285** (the 0.25% line is 64060290). Each line has an "offer under Normal Tax regime" toggle | TY2026 | PRIMARY (scan) | S11 p.15 |
| s.151(1)(b) withholding on bank profit | **20% ATL / 40% non-ATL** | TY2026 | PRIMARY | S1 p.540, p.781 fn; S5 p.3; S6 p.10 |
| s.151(1)(b) withholding on bank profit | 15% ATL / 35% non-ATL | TY2025 | PRIMARY | S4 p.531, p.763 |
| s.7B separate tax on bank profit (non-company) | **20% of gross** (FA 2025 raised it from 15%) | TY2026 | PRIMARY | S1 p.519; S6 p.10 |
| s.7B separate tax on bank profit (non-company) | 15% of gross | TY2025 | PRIMARY | S4 p.511 |
| s.7B threshold | s.7B does not apply to profit on debt that **exceeds Rs 5 million**; that profit goes to the normal regime and the s.151 withholding becomes a minimum tax | TY2025, TY2026 | PRIMARY (the "aggregate for the year" reading is SECONDARY) | S1 p.59, p.330; S21 p.36 |
| s.151 withholding base | Gross profit "as reduced by the amount of Zakat, if any, paid … at the time the profit is paid" | both | PRIMARY | S1 p.329–330 |
| Where bank profit sits in the TY2026 return | Other Sources → Final Tax: "Profit on Debt u/s 151(1)(b) from Bank Accounts / Deposits" **64040052**. An adjustable-tax twin of the same line exists (64040002) | TY2026 | PRIMARY (scan) | S11 p.23, p.29 |
| s.236Y (card payments to persons abroad) | **5% ATL / 10% non-ATL** of the gross amount; **adjustable** | TY2024–TY2026 | PRIMARY | S1 p.496–497, p.573; S4 p.563; S5 p.14 |
| s.236Y from 1 July 2026 | 0.5% (ATL); 1% non-ATL per KPMG | TY2027+ | PRIMARY (rate) / SECONDARY (non-ATL figure) | S7 p.58; S3 p.590; S21 |
| Rule 42 certificate | Anyone collecting tax under Chapter XII (which includes s.236Y), or deducting under Division III of Part V (which includes s.151 and s.154A), must issue a certificate in the form at Part VII of the Second Schedule, within 15 days after the financial year ends or 7 days after a request | all | PRIMARY | S10 p.196; S1 p.358 (s.164) |
| s.231AB cash-withdrawal tax (non-ATL only) | 0.8% of daily cash withdrawals above Rs 50,000; adjustable | TY2026 (0.6% in TY2025) | PRIMARY | S1 p.475; S6 p.3; S4 p.469 |
| Zakat deducted by a bank | **Deductible allowance** under s.60. It reduces normal-regime taxable income only; it is not a tax credit, does not reduce final-tax income, and any unused part is lost. In IRIS it sits under Deductible Allowances → "Zakat u/s 60" | both | PRIMARY | S1 p.136, p.63, p.370; S11 p.26 (scan) |
| How banks deduct Zakat | 2.5% of a savings/PLS account balance on the first day of Ramadan, if the balance is above the Nisab | both | PRIMARY | S17 (First Schedule, S.No.1) |
| Nisab for Ramadan 1447 AH (Feb 2026) | Rs 503,529; deduction date about 19–20 Feb 2026 | TY2026 | SECONDARY | S28 |
| Foreign remittance that is not export income | s.111(1) ("unexplained income") does not apply to up to **Rs 5 million per tax year** of foreign exchange received through normal banking channels, converted into rupees by a scheduled bank, with that bank's certificate. Remittances through money transfer operators (MTOs) and exchange companies count as normal banking channels | TY2025, TY2026 | PRIMARY | S1 p.233; S4 |
| Final-tax income used to explain wealth | The credit is limited to "imputable income" unless audited accounts are furnished (s.111(4A)) | both | PRIMARY (how FBR applies it in practice: UNVERIFIED) | S1 p.33, p.233–234 |
| Federal excise duty (FED) or sales tax on bank charges | **Not income tax.** FED is 16% of the charges for banking services, and is not levied where a province charges its own sales tax on services | both | PRIMARY (FED) / SECONDARY (provincial) | S12 p.86–87 |
| Salary tax (s.149) | The employer deducts at the employee's average rate. It is **adjustable**, and the figures come from the employer's certificate or IRIS, not from bank statements | both | PRIMARY | S1 p.327, p.366, p.785; S10 p.150 |
| Due date for the return and wealth statement | **30 September 2026** | TY2026 | PRIMARY | S2 p.256 (s.118(3)–(4)); S19 |
| Extension of the due date | **None announced** as of 26–27 Sep 2026; requests are pending | TY2026 | PRIMARY (FBR press-release list, negative check) + SECONDARY | S18; S22; S23 |
| TY2026 return forms | Notified by SRO 1495(I)/2026 dated 2 Sep 2026 | TY2026 | PRIMARY | S11 p.1 |
| Wealth statement | Every resident individual who files a return must file a wealth statement **and a wealth reconciliation**. Both must include foreign assets | both | PRIMARY | S1 p.254–255 |
| Foreign income & assets statement (s.116A) | Required if foreign income is at least USD 10,000 or foreign assets are at least USD 100,000 | both | PRIMARY | S1 p.256 |

## Detailed findings

### Q1. Section 154A — export of services

#### 1a. Rate schedule, and who pays 1% versus 0.25%

- **Where the rates live.** s.154A(1) says the authorized dealer deducts tax "at the rates specified in Division IVA of Part III of the First Schedule" [PRIMARY, S1 p.349].
- **The Division IVA table, as it applies to TY2025 and TY2026** [PRIMARY, S1 p.548; identical in S2 p.548 and S4 p.538]:
  - **S.No.1** — "Export proceeds of Computer software or IT services or IT Enabled services by persons registered with Pakistan Software Export Board": **0.25% of proceeds "for tax years 2024 up to tax year 2026"**. The finance act of 2023 added that time limit.
  - **S.No.2** — "Any other case": **1% of proceeds**.
- **TY2027 onward.** The Finance Act 2026 changes "2026" to "2029" in S.No.1, so the 0.25% rate now runs to TY2029. The 1% rate is unchanged [PRIMARY, S7 p.58; S3 p.566].
- **Who falls in which clause.** Since the Finance Act 2022, s.154A(1)(a) covers IT/ITeS exports only "where the exporter is registered with and duly certified by the Pakistan Software Export Board (PSEB)". The other clauses are [PRIMARY, S1 p.349]:
  - (b) services or technical services rendered outside Pakistan or exported from Pakistan;
  - (c) royalty, commission or fees earned by a resident company;
  - (d) construction contracts executed abroad;
  - (da) foreign indenting commission;
  - (e) other services the Board notifies.

  The definitions of "IT services" and "IT enabled services" are in s.2(30AD) and s.2(30AE); software development is expressly an IT service [PRIMARY, S1 p.35].

| Exporter | Clause of s.154A(1) | Division IVA row | Rate, TY2025–TY2026 |
|---|---|---|---|
| IT/ITeS exporter registered with and certified by PSEB (company or individual) | (a) | S.No.1 | 0.25% |
| IT/ITeS exporter **not** PSEB-registered/certified, including freelancers | (b) *(interpretation)* | S.No.2 "any other case" | **1%** |
| Any other services exported or rendered abroad | (b) | S.No.2 | 1% |
| Company royalty/fees, construction abroad, indenting commission, notified services | (c), (d), (da), (e) | S.No.2 | 1% |

- **Freelancers.** The ITO has no "freelancer" category. Reading a non-PSEB IT freelancer into clause (b) and the 1% row is an interpretation [UNVERIFIED], but three sources support it:
  - KPMG's table puts clause (a) at 0.25% and clauses (b)–(e) at 1% [SECONDARY, S21 p.44].
  - The TY2026 return has two separate lines, "Export of IT/ITeS Services u/s 154A @ 0.25%" and "Export of services u/s 154A @1%" [PRIMARY (scan), S11 p.15].
  - PSEB's own page says: "Registered companies pay only 0.25% tax on export proceeds of IT & IT-enabled Services as opposed to non-registered companies that pay 1% tax" [PRIMARY for PSEB's statement, S20].
- **PSEB registration for individuals.** Individual freelancers can register with PSEB and give the certificate to their bank to get 0.25% withheld [SECONDARY, freelancer guides; not verified on PSEB's site].
- **What puts someone at 1%:** exporting IT/ITeS without being "registered with and duly certified by PSEB", or exporting services that are not IT/ITeS. **ATL status plays no part:**
  - Rule 10(ca) of the Tenth Schedule, inserted by FA 2022, says the Tenth Schedule "shall not apply" to tax collected or deducted under s.154A [PRIMARY, S1 p.785]. FBR Circular 15 of 2022-23 says the same: "provisions of Tenth Schedule will not apply on tax collectible under section 154A" [PRIMARY, S8 p.9].
  - **Contradiction:** FBR's rate card for FY2025-26 lists 154A non-ATL rates of 0.5% and 2% "read with R.1 of Tenth Schedule" [PRIMARY, S5 p.7]. The card's own disclaimer says the statute prevails. KPMG's TY2027 table shows one rate for 154A, with no ATL split [SECONDARY, S21].
- **Owner's amendment (1%).** The 1% rate is legally consistent if the owner is not PSEB-registered and certified, or exports non-IT services. If the owner were PSEB-certified and the bank held the certificate, the statutory rate would be 0.25%. The tool should record the tax **actually deducted**, not infer it from a rate.

#### 1b. Is it a final tax, a minimum tax or adjustable?

- **Final tax, subject to conditions.** Under s.154A(2), the tax is "a final tax on the income arising from the transactions … upon fulfilment of the following conditions" [PRIMARY, S1 p.349–350]:
  - (a) the return has been filed;
  - (b) withholding statements for the tax year have been filed, if required;
  - (c) sales-tax returns under federal or provincial law have been filed, if required. A proviso waives this condition **only** for clause (a) exporters, meaning PSEB IT exporters;
  - (d) no credit for foreign taxes is allowed.
- **Opting out.** Under s.154A(3), sub-section (2) does not apply to a person who fails the conditions "or who opts not to be subject to final taxation". The option is exercised every year when the return is filed [PRIMARY, S1 p.350].
- **What "final" means.** s.169(1)(b) lists s.154A(2) among the final-tax provisions. Under s.169(2) [PRIMARY, S1 p.369–370]:
  - the income is not chargeable under any head;
  - no expense is deductible;
  - it is not reduced by deductible allowances or loss set-off;
  - the tax is not reduced by tax credits;
  - there is no refund unless the tax deducted exceeds the liability;
  - tax that was not deducted "may be recovered under section 162" (s.169(2)(f)).
- **Finance Act 2024** [PRIMARY, S1 p.348 fn 10, p.369 fn 6, p.321]:
  - changed s.154(4) (exports of **goods**) from "final" to "minimum";
  - removed s.154(4) from s.169;
  - added s.147(6C), a 1% advance tax on exporters of goods.

  **It did not touch s.154A.** The s.154A and Division IVA footnotes cite only FA 2021, 2022 and 2023 [PRIMARY, S1 p.349–350, p.548].
- **Finance Act 2025** made no change to s.154A. FBR's Finance Act 2025 circular says withholding "under section 154 and 154A will fall outside the ambit" of the new s.6A e-commerce regime [PRIMARY, S6 p.1].
- **No mid-year change.** The text up to 20.02.2026 is the same [PRIMARY, S2 p.349].
- **Finance Act 2026 (TY2027+)** only extended the 0.25% time limit and added a new s.154B, a 5% tax on social-media revenue [PRIMARY, S3 p.356–357; S7 p.43, p.58].
- **Where the income sits in the TY2026 return.** The individual return has the path Business → Data → **Tax Deduction → Final Tax**, and lists [PRIMARY (scan, confirmed by eye), S11 p.15]:
  - "Export of IT/ITeS Services u/s 154A @ 0.25%" — **64060290**
  - "Foreign Indenting Commission u/s 154A(1)(da)" — 64070151
  - "Export of services u/s 154A @1%" — **64060285**

  Each line carries the note "You may offer this receipt under Normal Tax regime by clicking ⇄ icon", which is the s.154A(3) opt-out. The next group on the screen is "Minimum Tax".

  So, by default, export receipts are declared as **receipts in the final-tax section**. They are not normal business income (profit and loss), and they stay out of the taxable income that sets the salary slab rate [PRIMARY, S1 s.169(2)(a)].
- **If the owner opts out or fails a condition,** the receipts become ordinary business income taxed at slab rates. The statute does not call the 1% a minimum tax in that case, so it would presumably be an ordinary credit under s.168 [UNVERIFIED].
- **Sales-tax condition applies to the 1% band.** Because the proviso waives condition (c) only for PSEB IT exporters, an exporter at 1% must meet the "sales-tax returns filed, if required" condition. Whether an individual exporting services must register and file under a provincial sales-tax-on-services law was not researched [UNVERIFIED — open question].

#### 1c. How the tax is collected; Payoneer, Wise, Remitly and Thunes; banks versus EMIs

- **Statutory mechanism.** "Every authorized dealer in foreign exchange shall, at the time of realization of foreign exchange proceeds … deduct tax" [PRIMARY, S1 p.349]. When the section was introduced, FBR described it as "1% withholding tax … on their export proceeds remitted in Pakistan through Banks and authorized dealers of foreign exchange. This would be final tax" [PRIMARY, S9 p.10].
- **Procedure rules.** s.154A(5) says the Board, with SBP, "shall prescribe mode, manner and procedure of payment of tax". No such rule exists in the Income Tax Rules 2002 as amended to 15.09.2026; a text search for "154A" found nothing [PRIMARY, S10, negative search]. No FBR circular dealing specifically with Payoneer, Wise, Remitly or Thunes was found [UNVERIFIED — absence of evidence].
- **If the tax was not deducted.** s.169(2)(f) and s.162 let the Commissioner recover it from the person who received the payment [PRIMARY, S1 p.370, p.357]. In practice the shortfall would be paid through IRIS (a PSID payment that produces a CPR), but the exact payment mechanics and code were not verified [UNVERIFIED].
- **SBP rules on freelancers' export proceeds:**
  - **FE Manual, Chapter 12, para 12** (EPD Circular Letter 17 of 2023) [PRIMARY, S13 para 12]:
    - It defines "Freelancers" as "all individuals, resident in Pakistan, engaged in provision of any digital/online services, including IT and IT related services, against which payments are received from outside Pakistan".
    - A freelancer's proceeds "could also be processed on self-declaration basis", given once when the account is opened.
    - The bank must open an Exporters' Special Foreign Currency Account (ESFCA) alongside the rupee account. The freelancer can keep up to USD 5,000 a month or 50% of proceeds, whichever is higher, in that account.
    - Banks must report these transactions "under the relevant purpose and scheme codes".
  - **FE Manual, para 7:** where the remittance message does not identify the purpose as payment against exports, the retention clock starts only "once the same is determined by the Authorized Dealer" [PRIMARY, S13 para 7]. In other words, banks classify each inflow by purpose.
  - **SBP BPRD Circular 05 of 2023** (23 Oct 2023) sets the "Framework for Freelancers Accounts" (Freelancer Digital Account / ESFCA) [PRIMARY, S16].
- **SBP receipt purpose codes** (Code List No. 5; archive copy dated Sept 2021, and the current revision was not checked) [PRIMARY, S14]:
  - 9181–9185 — computer services;
  - **9186** — "Freelance of computer and information services — remittances received by resident individuals/households from reputed overseas IT firms and online platforms";
  - **9471** — workers' remittances for family maintenance;
  - **9473** — private donations: gifts, dowries, inheritances.
- **EMIs (SadaPay, NayaPay).** SBP's EMI Regulations (2023), para 13(III), are headed "Inward Remittances (Received through Home Remittance/PRI Channel)". They say: "EMIs are allowed to disburse inward remittances in PKR to their wallet holders, mobilized by Authorized Dealers (under home remittance arrangement), through IBFT functionality" [PRIMARY, S15 p.17–18]. So:
  - The EMI is **not** the authorized dealer. A partner bank realizes the foreign exchange and pushes rupees to the wallet by IBFT, which matches descriptions like "IBFT In … from Thunes".
  - NayaPay lists Wise, ACE, Remitly, Payoneer and Western Union among its remittance partners [PRIMARY for NayaPay's statement, S29].
  - No source says whether the partner bank deducts s.154A tax on EMI-routed credits. Because the regulations frame these as **home remittances**, they may be processed as remittances rather than export proceeds, with **no s.154A deduction at source** [UNVERIFIED inference].
  - A vendor blog says NayaPay can obtain PRCs coded 9186, through its partner bank, for one specific payroll product [SECONDARY, S30].
- **Banks.** Freelancer guides say banks deduct 0.25% (if a PSEB certificate is on file) or 1% on Payoneer inflows [SECONDARY, freelancer guides; not verified].
- **What counts as evidence.** A statement label ("Payoneer", "Thunes", "Wise", "Remitly", "Inward Foreign Remittance") proves neither the purpose code nor whether tax was deducted. The evidence is:
  - the bank's certificate of deduction under Rule 42 (s.154A is in Division III of Part V of Chapter X) [PRIMARY, S10 p.196; S1 p.358];
  - the PRC or e-PRC [PRIMARY, S13 para 31].

#### 1d. Conditions: banking channels, PRCs, purpose codes

- **Conditions in the statute.** s.154A contains **no** PRC or purpose-code condition. The statutory conditions are the four in s.154A(2) [PRIMARY, S1 p.349–350]. The requirement that proceeds come through the banking system is built into the mechanism, which is deduction by an authorized dealer at realization [PRIMARY, S1 p.349].
- **PRCs.** Banks "may issue Proceed Realization Certificate (PRC) to the exporter upon realization"; e-PRCs replace duplicates. Where money arrives through an intermediary bank, "the beneficiary bank will issue e-PRC and S-PRC" [PRIMARY, S13 para 31]. The PRC is the usual proof of export realization for PSEB registration and audits [SECONDARY].
- **Purpose codes.** Banks report each inflow under an SBP purpose code [PRIMARY, S13 para 12(iv); S14]. The code (9186 versus 9471 or 9473) is what separates export proceeds from family remittances in the banking record.
- **Retention.** Freelancers can keep up to USD 5,000 a month or 50% of proceeds in an ESFCA; other service exporters can keep 35% [PRIMARY, S13 paras 12, 36]. Part of the proceeds may therefore sit in a foreign-currency account the owner holds and never appear on a rupee statement.

### Q2. Profit on debt (bank savings profit)

- **Withholding under s.151(1)(b).** A bank or financial institution paying profit on an account or deposit deducts tax at the Division IA (Part III) rate "from the gross amount of the yield or profit paid as reduced by the amount of Zakat, if any, paid by the recipient under the Zakat and Ushr Ordinance, 1980 … at the time the profit is paid" [PRIMARY, S1 p.329–330].
- **TY2026 rates (Division IA, substituted by FA 2025):**
  - (a) **20%** on profit from bank or financial-institution accounts and deposits;
  - (b) 20% on government securities paid to non-individuals;
  - (c) 15% in other cases, such as National Savings, Post Office and government securities held by individuals [PRIMARY, S1 p.540].

  FBR explains: "The tax rate on profit on debt derived from deposits in banking companies … have been increased from 15% to 20%" [PRIMARY, S6 p.10]. **TY2025:** a flat 15% [PRIMARY, S4 p.531].
- **Non-ATL rates.** Before FA 2025, the Tenth Schedule fixed a special non-ATL rate of 35% for s.151. FA 2025 removed that entry, and "for tax year 2026 and onwards hundred percent increase in tax rates for non-filers" applies [PRIMARY, S6 p.10; S1 p.781 fn]. That gives **40% non-ATL in TY2026**, which is also what the rate card shows [PRIMARY, S5 p.3]. **TY2025:** 35% [PRIMARY, S4 p.763].
- **Separate taxation under s.7B.** A tax applies to "every person, other than a company, who receives a profit on debt" from a payer listed in s.151(1)(a)–(d), at the Division IIIA (Part I) rate on the **gross** profit [PRIMARY, S1 p.58]. Division IIIA, as amended by FA 2025, charges **20%** on bank deposits, 20% on government securities held by non-individuals, and 15% on everything else [PRIMARY, S1 p.519]. **TY2025:** 15% [PRIMARY, S4 p.511].
- **Rs 5 million threshold.** s.7B(3) says the section "shall not apply to a profit on debt that … (b) exceeds five million Rupees" (FA 2021 changed "thirty six" to "five") [PRIMARY, S1 p.59]. The statute does not say how the threshold is measured. KPMG summarises bank profit as "Final / Minimum (if more than Rs. 5 million)", which treats it as the total for the year [SECONDARY, S21 p.36].
- **Final or adjustable:**
  - s.8 makes s.7B tax a **final tax**: the profit is outside every head of income, gets no deductions, is not reduced by deductible allowances or losses, and the tax cannot be reduced by credits [PRIMARY, S1 p.63].
  - s.151(3): the withholding is "a minimum tax on the profit on debt … except where (a) taxpayer is a company; or (b) profit on debt is taxable under section 7B" [PRIMARY, S1 p.330].

  Putting these together:
  - **Individual whose profit is ≤ Rs 5m:** a separate final tax of 20% (TY2026). The ATL-rate withholding settles it, and the withholding **is not an adjustable credit against other tax**.
  - **Individual whose profit is > Rs 5m:** the profit is taxed in the normal regime under "Income from Other Sources", and the withholding is a **minimum tax**.
- **Non-ATL excess.** s.169(4) says that where tax is final and the Tenth Schedule rate was doubled, the final tax is the First Schedule rate and the excess is adjustable, provided the return is filed before a provisional assessment is finalised [PRIMARY, S1 p.371]. Whether this covers s.151 withholding on s.7B income is unclear, because s.169(1) does not list s.151 [UNVERIFIED].
- **Where it sits in the TY2026 return.** Other Sources → Tax Deduction → **Final Tax** → "Profit on Debt u/s 151(1)(b) from Bank Accounts / Deposits" **64040052**. The "Adjustable Tax" list has a twin line with code 64040002 (the image is slightly blurred) [PRIMARY (scan), S11 p.23, p.29]. The brief's code 64040052 is therefore the **final-tax** line.
- **Records.** Rule 31(4)(c) requires keeping "evidence of profit on debt and tax deducted thereon, like certificate in the prescribed form or bank account statement", plus "evidence of Zakat deducted, if any" [PRIMARY, S10 p.151].

### Q3. Section 236Y — advance tax on card payments abroad

- **Charge.** "Every banking company shall collect advance tax, at the time of transfer of any sum remitted outside Pakistan, on behalf of any person who has completed a credit card or debit card or prepaid card transaction with a person outside Pakistan". Under s.236Y(2): "The advance tax collected under this section shall be adjustable." The section was omitted by FA 2021 and re-inserted by FA 2022 [PRIMARY, S1 p.496–497].
- **Rate.** Division XXVII of Part IV sets it at **5%** of the gross amount remitted abroad; FA 2023 raised it from 1% [PRIMARY, S1 p.573]. It was also 5% in **TY2025** [PRIMARY, S4 p.563].
- **Non-ATL rate: 10%** [PRIMARY, S5 p.14]. This is consistent with the Tenth Schedule's general doubling, because s.236Y is not among the rule 10 exclusions [PRIMARY, S1 p.785].
- **TY2027 onward:** 0.5% (FA 2026) [PRIMARY, S7 p.58; S3 p.590], and 1% non-ATL [SECONDARY, S21 p.50].
- **Certificate.**
  - s.164(1): the collector must give the payer a copy of the CPR and a certificate [PRIMARY, S1 p.358].
  - Rule 42(1)(c): anyone "collecting or deducting tax under Chapter XII" (which contains s.236Y) "shall issue a certificate … in the form as set out in Part VII of the Second Schedule to these rules, within fifteen days after the end of the financial year".
  - Rule 42(2): mid-year, within seven days of a request.
  - Rule 42(3)–(5): duplicates on loss; certificates serially numbered [PRIMARY, S10 p.196].
- **Where it sits in the TY2026 return.** Under Adjustable Tax: "Persons remitting amount abroad through credit / debits / prepaid cards u/s 236Y" **64151905** [PRIMARY (scan), S11 p.30].
- **EMIs.** The statute names "banking company". The brief reports that NayaPay issues a Rule 42 certificate; whether EMIs collect in their own right or through a partner bank was not verified [UNVERIFIED]. The tool should take the certificate at face value.

### Q4. Zakat

- **Relief under the ITO:**
  - s.60(1): "A person shall be entitled to a deductible allowance for the amount of any Zakat paid by the person in a tax year under the Zakat and Ushr Ordinance, 1980" [PRIMARY, S1 p.136].
  - s.60(2) excludes Zakat already deducted under s.40(2), which allows Zakat paid "at the time the profit is paid" against profit on debt taxed under "Income from Other Sources" [PRIMARY, S1 p.117].
  - s.60(3): any unused allowance is not refunded or carried forward or back [PRIMARY, S1 p.136].
- **How the allowance works:**
  - A deductible allowance reduces **total income to taxable income** (s.9) under the normal regime. It is **not a tax credit** [PRIMARY, S1 s.9].
  - Final-tax amounts (s.7B profit, s.154A receipts) cannot be reduced by deductible allowances [PRIMARY, S1 p.63 (s.8(1)(c)), p.370 (s.169(2)(c))].
  - For this taxpayer, Zakat therefore effectively reduces normal-regime taxable income only, which is mainly salary [UNVERIFIED application; the rule itself is PRIMARY].
- **How banks deduct Zakat** [PRIMARY, S17]:
  - The First Schedule, S.No.1, covers "Savings Bank Accounts and similar accounts": 2.5% of the balance "at the commencement of the day on the Valuation Date".
  - No deduction is made if the balance does not exceed the amount the Administrator General notifies (the Nisab). The deducting agency is the bank.
  - "Valuation Date" is the first day of the Zakat year, and the Zakat year begins on 1st Ramadan.
  - Current accounts are not in that entry.
  - A person may file a declaration that their fiqh does not require Zakat to be deducted. The form name "CZ-50" is common usage [UNVERIFIED].
- **Nisab.**
  - Ramadan 1447 AH: Rs 503,529, notified 16 Feb 2026, with deduction on 1st Ramadan, about 19–20 Feb 2026 [SECONDARY, S28].
  - The previous year, relevant to TY2025: Rs 179,689 [SECONDARY, S28].
- **Where it sits in the return:**
  - TY2026 IRIS: Allowances, Reductions and Credits → **Deductible Allowances → "Zakat u/s 60"** [PRIMARY (scan), S11 p.26].
  - FBR's TY2024 paper return uses code **9001** "Zakat u/s 60" under Deductible Allowances (9009) [PRIMARY, S10 p.970]. The TY2026 e-return code is in file 02.
- **Evidence:** the bank's Zakat deduction certificate or statement (Rule 31(4)(c)(iii)) [PRIMARY, S10 p.151].
- **Zakat is not income tax** and must never be added to withholding totals.

### Q5. Section 111(4) and foreign remittances that are not export income

- **s.111(1).** Unexplained credits, investments, money or expenditure are treated as income, under "Income from Other Sources" or, for suppressed receipts, "Income from Business" [PRIMARY, S1 p.231].
- **s.111(4)** (as substituted by FA 2021): "Sub-section (1) does not apply to any amount of foreign exchange remitted from outside Pakistan through normal banking channels not exceeding five million Rupees in a tax year that is en-cashed into rupees by a scheduled bank and a certificate from such bank is produced to that effect" [PRIMARY, S1 p.233].
  - An Explanation added in FA 2022 says remittances through "money service bureaus, exchange companies or money transfer operators" count as normal banking channels [PRIMARY, S1 p.233].
  - The text is the same for TY2025 [S4] and unchanged to 30.06.2026 [S3] [PRIMARY].
- **Consequences:**
  - Up to Rs 5m a year of genuine remittances, received with a bank encashment certificate, cannot be treated as unexplained income.
  - Above Rs 5m, or without the certificate, the taxpayer must explain the nature and source (for example, a gift from a relative) [PRIMARY, follows from s.111(1) and (4)].
  - EMIs are not scheduled banks. Whether an EMI or its partner bank can issue a certificate that satisfies s.111(4) is [UNVERIFIED].
- **Gifts:**
  - s.39(1)(la) treats gifts as income from other sources, **except** gifts from a "relative" as defined in s.85(5): an ancestor, a descendant of any grandparent, or an adopted child of the individual or the spouse, plus the spouses of those people [PRIMARY, S1 p.115, p.172].
  - s.39(3) treats a loan, advance or **gift** as income if it is received "otherwise than by a crossed cheque drawn on a bank or through a banking channel or through digital means from a person holding a National Tax Number". The words "or through digital means" were added by FA 2025 [PRIMARY, S1 p.115–116].
  - How s.39(3) applies to a banking-channel gift from a relative abroad who has no NTN is unclear [UNVERIFIED — ask an advisor].
- **Final-tax income used to explain wealth (s.111(4A), FA 2022).** A taxpayer who explains wealth using income subject to final tax "shall not be entitled to take credit of any sum as is in excess of imputable income, unless the excess amount is reasonably attributed to the business activities subject to final tax and the taxpayer furnishes financial statements and accounts duly audited by a chartered accountant" [PRIMARY, S1 p.233–234].
  - "Imputable income" is "the income which would have resulted in the same tax, had this amount not been subject to final tax" (s.2(28A)) [PRIMARY, S1 p.33].
  - At a 1% final tax, imputable income can be much smaller than gross receipts [UNVERIFIED arithmetic]. How FBR applies this to freelancers' wealth reconciliations is [UNVERIFIED].
- **Why misclassification matters.**
  - Family money wrongly booked as s.154A receipts overstates final-tax income, and so the 1% tax.
  - Export proceeds wrongly booked as family remittances understate income, and may push remittances over the Rs 5m s.111(4) cap.
  - In the banking record, the purpose code separates the two: 9186 for freelance IT receipts, 9471 for family remittances, 9473 for gifts [PRIMARY, S14].

### Q6. Items on bank statements that are not income tax

- **Federal excise duty.** The FED Act 2005, First Schedule, Table II, S.No.8 covers "Services provided or rendered by banking companies [excluding Merchant Discount Rate (MDR) for accepting digital payment], insurance companies, … non-banking financial institutions …" at **"Sixteen percent of the charges"**. A Note says the duty "shall not be levied on services provided in a Province where the provincial sales tax has been levied thereon". The Act also defines "non-fund banking services" as fee, commission or charge-based services [PRIMARY, S12 p.9, p.86–87].
- **Provincial sales tax.** Provinces charge sales tax on banking services under their own laws, for example the Punjab Revenue Authority (PRA) [SECONDARY; the provincial rates were not checked].
- **Neither FED nor provincial sales tax is income tax.** They are indirect taxes on the fee, cannot be credited against income tax, and have no place in the income-tax return [PRIMARY, S12, for the nature of the levy].
- **Other non-income-tax items:**
  - **Zakat:** a deductible allowance, not a tax credit (see Q4).
  - **Bank fees and charges,** such as SMS alerts, card fees, IBFT fees and cheque books.
  - **Currency-conversion markups** on card transactions. Neither of these is a tax.
- **Items that *are* income tax and may appear as debits:**
  - s.151 withholding on profit;
  - s.236Y on card spending abroad;
  - s.231AB on cash withdrawals, only if the account holder is **not on the ATL**: 0.8% in TY2026 and 0.6% in TY2025, adjustable [PRIMARY, S1 p.475; S6 p.3; S4 p.469];
  - s.154A tax on export proceeds, which may be netted out of the credit rather than shown as a separate debit.
- **Obsolete labels.** s.231A, s.231AA and s.236P were repealed by FA 2021 [PRIMARY, S9 p.10; S1 footnotes], so those labels should not appear in TY2025–TY2026 statements.
- **Label wording varies by bank** [UNVERIFIED]: for example "FED", "Excise Duty", "Sales Tax", "PST", "SST" and "PRA". This belongs in the per-bank profile.

### Q7. Salary (s.149)

- **How it is withheld.** The payer of salary deducts tax "at the employee's average rate of tax computed at the rates specified in Division I of Part I of the First Schedule on the estimated income of the employee chargeable under the head 'Salary' … including tax under section 4AB after making adjustment of tax withheld from employee under other heads and tax credit admissible under section 61 and 63 … after obtaining documentary evidence" [PRIMARY, S1 p.327].
- **It is adjustable.** Deducted tax is a credit under s.168, not a final tax [PRIMARY, S1 p.366]. The Tenth Schedule does not apply to s.149 (rule 10(a)) [PRIMARY, S1 p.785].
- **Evidence and pre-filled data.**
  - Salaried taxpayers must keep a "Salary certificate indicating the amount of salary and tax deducted" (Rule 31(1)) [PRIMARY, S10 p.150].
  - The TY2026 IRIS return opens with a "Summary of Economic Transactions" and a "Summary of Withholding Tax as withheld" table (Description, Taxable Value, Tax Withheld) [PRIMARY (scan, poor OCR), S11 p.3].
  - That these tables are filled from withholding agents' statements, including the employer's, is an inference [UNVERIFIED].
  - The adjustable-tax list includes "Salary of Employees u/s 149" [PRIMARY (scan/OCR), S11 p.29].
- **Surcharge (s.4(4AB)).** 10% of the Division I tax where taxable income exceeds Rs 10m. A FA 2025 proviso sets **9% for an individual "deriving income chargeable under the head Salary"** from TY2026 [PRIMARY, S1 p.52]. How the proviso applies to someone with both salary and other income is [UNVERIFIED].
- **For the tool:**
  - Bank statements show **net pay**. Gross salary and s.149 tax must come from the employer's certificate or IRIS, never from statements.
  - Salary credits should be labelled as salary so they are not flagged as unexplained large credits.
  - If the employee gave the employer evidence of other withholding (for example s.236Y) to be adjusted under s.149(1), claiming that tax again in the return would double-count it [UNVERIFIED application; the mechanism is PRIMARY].

### Q8. Filing: due date, extension, and wealth statement

- **Due date.**
  - s.118(3): a return for any person other than a company, whether a salaried e-filer or not, is due "on or before the 30th day of September next following the end of the tax year" [PRIMARY, S2 p.256; unchanged in S3].
  - s.118(4): the wealth statement is due on the same date [PRIMARY, S2 p.256].
  - FBR's due-dates page: "On or before 30th September" for individuals and AOPs [PRIMARY, S19].
  - **TY2026 due date: 30 September 2026.**
- **Extension status, as of 27 Sep 2026.**
  - FBR's press-release index, checked 27 Sep 2026, shows **no extension announcement** up to its 26 Sep 2026 entry [PRIMARY, S18, negative check].
  - Business Recorder (26 Sep 2026): tax practitioners asked the Prime Minister to extend the deadline to 30 Nov 2026, and no extension had been granted [SECONDARY, S22].
  - The Karachi Tax Bar Association raised the deadline with FBR in September 2026 [SECONDARY, S23].
  - **TY2025 precedent:** FBR said on 29 Sep 2025 that there would be no extension, then extended the deadline under s.214A to 15 Oct 2025 as it expired [SECONDARY, S24], and later to 31 Oct 2025 [SECONDARY, S25, seen only as a search-result snippet].
  - FA 2025 limits the Board's power to condone delay to two years [PRIMARY, S6 p.9].
  - An extension can arrive at the last minute, but the tool should not assume one.
- **TY2026 return forms.**
  - SRO 1495(I)/2026, dated 2 Sep 2026, added Parts II-ZE (individuals), ZF (SMEs), ZG (AOPs) and ZH (companies) to the Rules. The draft had been published as SRO 835(I)/2026 in May 2026 [PRIMARY (scan), S11 p.1–2; S27].
  - Filing opened on IRIS on 27 Jul 2026 [SECONDARY, S26].
- **Wealth statement:**
  - s.116(2): every resident individual filing a return "shall furnish a wealth statement and wealth reconciliation statement for that year along with such return" [PRIMARY, S1 p.255].
  - s.116(1) sets the content [PRIMARY, S1 p.254]:
    - assets and liabilities, **including foreign assets and liabilities** (words added by FA 2024);
    - the same for the spouse (only if dependent), minor children and other dependents;
    - assets transferred to others;
    - total expenditure;
    - the reconciliation.
  - s.116(3): a revised statement, with a revised reconciliation and reasons, may be filed until notice under s.122(9) is received [PRIMARY, S1 p.255].
  - s.116A: a foreign income and assets statement is required if foreign income is at least USD 10,000 or foreign assets are at least USD 100,000 [PRIMARY, S1 p.256].
  - Balances held in Payoneer or Wise accounts are money held abroad and should appear as foreign assets [UNVERIFIED interpretation].
- **Opening and closing wealth in IRIS TY2026** [PRIMARY (scan, OCR); codes to be confirmed in file 02, S11 p.38–40]:
  - The Personal Assets/Liabilities screen totals assets and liabilities into "Net Assets Current Year" (703001).
  - "Reconciliation of Net Assets" compares that with "Net Assets Previous Year" (703002). The difference, "Increase / Decrease in Assets" (703003), is explained by Inflows less Outflows, leaving an "Unreconciled Amount" (703000).
- **In practice:**
  - The previous year's net assets are those declared in the TY2025 wealth statement [UNVERIFIED — how IRIS pre-fills them].
  - The per-account "opening balance at 1 July 2025" should equal the balance declared at 30 June 2025.
  - The inflow and outflow lines could not be read in the scan. These include income subject to final tax, remittances and gifts, personal expenses, and where Zakat and taxes paid go [UNVERIFIED — see file 02].
- **Data matching (s.175AA, FA 2025).** FBR may share declared return and wealth data with scheduled banks for cross-matching, and banks report transactions that do not match [PRIMARY, S6 p.9]. Every figure the tool produces should therefore reconcile to the bank records.

## Implications for the tool

1. **Rates are keyed by tax year and used only for sanity checks.** Keep a small rates table with a citation per row. The tool must **never compute a figure for IRIS from a rate**; it should use the deductions actually shown on statements and certificates, and use rates only to flag anomalies.

   | Item | TY2025 | TY2026 | TY2027 |
   |---|---|---|---|
   | s.151(1)(b), ATL / non-ATL | 15% / 35% | 20% / 40% | 20% / 40% |
   | s.7B | 15% | 20% | 20% |
   | s.236Y, ATL / non-ATL | 5% / 10% | 5% / 10% | 0.5% / 1% |
   | s.231AB (non-ATL) | 0.6% | 0.8% | not checked for TY2027 |
   | s.154A, non-PSEB (not doubled for non-ATL) | 1% | 1% | 1% |
   | s.154A, PSEB-certified IT/ITeS | 0.25% | 0.25% | 0.25% (runs to TY2029) |

   Each transaction's tax year comes from its date, 1 July to 30 June (s.74).

2. **Split export receipts into more than one category.** A keyword match ("Payoneer", "Thunes", "Wise", "Remitly", "Inward Foreign Remittance") should only *propose* a category, and the user confirms it per counterparty. Suggested categories:
   - `export_proceeds_154A`: date, rupee proceeds, foreign-currency amount if shown, **tax deducted at source (zero allowed)**, channel (bank or EMI via home remittance), rate band (1% for the owner by default; 0.25% only with a PSEB certificate), and evidence references (PRC or e-PRC number, purpose code, bank certificate).
   - `foreign_remittance_personal`: not income. Keep a running total against the **Rs 5,000,000** s.111(4) cap and flag the need for a bank encashment certificate.
   - `own_funds_from_abroad`: not income, but the owner still needs to be able to explain it.
   - Do not mark Remitly, Western Union or ACE credits as export receipts by default. These are consumer remittance brands, and SBP routes EMI inflows through the **home-remittance** channel.

3. **Report the s.154A tax shortfall instead of assuming 1% was withheld.** Output total receipts (to go on the "Export of services u/s 154A @1%" line, code 64060285), total tax deducted with evidence, the 1% expected amount, and the difference. Flag the difference as "possibly payable before filing; confirm with advisor". EMI-routed credits are the most likely to show no deduction.

4. **Handle gross versus net amounts.** A bank may deduct s.154A tax from the credit itself rather than posting a separate debit. The parser should look for both patterns and fall back to the PRC or certificate for the gross figure.

5. **Include foreign-currency accounts.** Up to 50% or USD 5,000 a month of proceeds may land in an ESFCA. Parse those statements too. Conversions from the ESFCA to rupees are internal transfers; the export receipt should be counted once, when it is realized.

6. **Do not lump withholding into one "adjustable tax / 9201" bucket.** Keep three groups:
   - **(a) Final or separate-block tax:**
     - s.154A tax;
     - s.151 withholding on bank profit while total profit is **≤ Rs 5m**. This goes on Other Sources → Final Tax, 64040052, not in adjustable tax.
   - **(b) Adjustable tax:**
     - s.149, from the employer's certificate;
     - s.236Y, from the Rule 42 certificate;
     - s.231AB;
     - s.151 once profit exceeds Rs 5m.
   - **(c) Not income tax at all:** FED, provincial sales tax, bank charges, and Zakat.

   How IRIS totals these (for example what code 9201 contains) is for file 02 to settle.

7. **Profit-on-debt pairing.**
   - Expect withholding of about 20% of gross profit in TY2026 (40% if not on the ATL), and 15% / 35% in TY2025.
   - Flag deviations, which may come from a Zakat-reduced base, a change in ATL status, or a payment near the tax-year boundary.
   - Sum gross profit across **all** accounts and warn when it exceeds Rs 5,000,000, because s.7B then stops applying and the return treatment changes.

8. **Zakat.**
   - Detect Zakat debits. Expect them around 1st Ramadan: about 19–20 Feb 2026 for TY2026; the TY2025 date was not checked.
   - Total them separately as "Zakat u/s 60 — deductible allowance, needs bank certificate".
   - Never add Zakat to withholding.

9. **Indirect taxes.** Add a configurable per-bank dictionary for FED, sales-tax, PST and similar labels, and exclude those amounts from income-tax totals.

10. **s.236Y certificates.**
    - Parse the amount and the tax from Rule 42 certificates.
    - Sanity-check the tax against 5% (ATL) or 10% (non-ATL) for TY2025–TY2026, and 0.5% or 1% from TY2027.
    - Where card-tax debits appear on the statement, reconcile them with the certificate.

11. **Salary.** Users configure employer names; matching credits are labelled "salary, net pay". Gross salary and s.149 tax are entered by hand or from the certificate.

12. **Wealth statement.**
    - Closing balances at 30 June.
    - An opening reference taken from the TY2025 wealth statement, with any mismatch flagged.
    - Manual entries for foreign assets (Payoneer, Wise, foreign-currency accounts), dependents' assets and cash.
    - Reconciliation helpers:
      - net assets this year minus last year;
      - inflows: declared incomes, final-tax receipts, remittances and gifts;
      - outflows: personal expenses, taxes, Zakat;
      - an unreconciled amount.
    - Warn about the s.111(4A) "imputable income" limit on explaining wealth with final-tax income.

13. **Cross-check against IRIS.** Provide a view that mirrors IRIS's pre-filled "Summary of Economic Transactions / Withholding Tax" so the user can compare third-party-reported figures with the tool's.

14. **Audit trail.** Every item should link to the statement page, line, reference or STAN number, and certificate ID. Rule 31(4)(c) requires this evidence, and s.175AA data-matching and s.111 scrutiny make it important.

## Could not verify / open questions

1. Whether SadaPay or NayaPay, or the banks behind them, **deduct s.154A tax** on inward credits from Thunes, Payoneer, Wise or Remitly. SBP's EMI rules describe these as home remittances, which suggests no deduction, but that is an inference [UNVERIFIED].
2. How to **pay s.154A tax that was not deducted** through IRIS: the payment section, the CPR code, and whether IRIS works out the shortfall itself [UNVERIFIED].
3. Whether banks decide to deduct s.154A tax purely from the SBP purpose code (9186 versus 9471) [UNVERIFIED practice].
4. Whether an **EMI or its partner bank can issue the s.111(4) encashment certificate**; the law requires a scheduled bank [UNVERIFIED].
5. **s.154A(2)(c):** whether a non-PSEB individual exporting services must register or file under a provincial sales-tax-on-services law. If so, and returns are not filed, final-tax treatment is at risk [UNVERIFIED — needs an advisor].
6. How FBR applies **s.111(4A)** (the imputable-income limit) to freelancers' wealth reconciliations in practice [UNVERIFIED].
7. How to treat **export earnings still held abroad** (Payoneer or Wise balances) at 30 June: when they count as income, how they are taxed, and how they are reconciled [UNVERIFIED].
8. Whether the s.154A "proceeds" are the rupees realized in Pakistan or the gross invoice before platform fees [UNVERIFIED].
9. How the **s.7B Rs 5m threshold** is measured (total profit for the year is the common reading [SECONDARY]), and whether a non-ATL excess on s.151 withholding under s.7B can be adjusted under s.169(4) [UNVERIFIED].
10. **Contradiction:** FBR's rate card shows 0.5% / 2% non-ATL rates for s.154A, but the statute (Tenth Schedule rule 10(ca)) and FBR Circular 15/2022-23 say there is no doubling. If a bank applied 2%, the recovery route is [UNVERIFIED].
11. Several IRIS details could not be read reliably in the scanned SRO and belong to file 02: the exact inflow and outflow lines of the wealth reconciliation (remittances, gifts, final-tax receipts, where Zakat and taxes paid go), the composition of code 9201, and the salary line code.
12. Whether the FA 2025 **9% salaried surcharge** proviso applies to someone with both salary and business income [UNVERIFIED].
13. **Extension for TY2026:** none as of 26–27 Sep 2026. Check FBR's press releases and SROs again on 29–30 Sep 2026.
14. **1st Ramadan dates** (the Zakat deduction dates) for 1446 and 1447 AH are approximate [SECONDARY]. The SBP purpose-code list used is the archived 2021 version; later revisions were not checked.
15. PSEB's process for **registering individual freelancers** was confirmed only through secondary sources; PSEB's own page mentions only companies.

## Sources

Primary:

- **S1** — FBR, *Income Tax Ordinance, 2001 — amended up to 31.07.2025* (consolidation after the Finance Act 2025). PDF page numbers are from the 822-page copy downloaded 27 Sep 2026. https://download1.fbr.gov.pk/Docs/2025881983148210Income-Tax-Ordinance,-2001-Amended-upto-31.07.2025.pdf
- **S2** — FBR, *Income Tax Ordinance, 2001 — amended up to 20.02.2026*. https://download1.fbr.gov.pk/Docs/2026226162211364IncomeTaxOrdinance2001-Amended-20.02.2026.pdf
- **S3** — FBR, *Income Tax Ordinance, 2001 — amended up to 30.06.2026* (includes the Finance Act 2026). https://download1.fbr.gov.pk/Docs/2026724177725705IncomeTaxOrdinanace2001.pdf
- **S4** — FBR, *Income Tax Ordinance, 2001 — amended up to 30.06.2024* (law for TY2025). https://download1.fbr.gov.pk/Docs/2024751675120641IncomeTaxOrdinance,2001-amended-upto30.06.2024.pdf
- **S5** — FBR, *Withholding Income Tax Rate Card — updated up to June 30, 2025 as per Finance Act, 2025*: p.3 (s.151), p.7 (s.154, s.154A), p.8 (s.231AB), p.14 (s.236Y). https://download1.fbr.gov.pk/Docs/20258181281745641WHT-RateCard.pdf
- **S6** — FBR, *Circular No. 01 of 2025-26 (Income Tax), 2 Aug 2025 — Finance Act 2025 explanation*: para 1 (p.1), para 3 (p.3), paras 22–23 (p.9), para 26 (p.10). https://download1.fbr.gov.pk/Docs/2025841183918948CircularNo01of2025-26IncomeTax.pdf
- **S7** — *Finance Act, 2026 (Act No. XLIII of 2026)*, Gazette of Pakistan, 26 Jun 2026: commencement p.2, s.154B p.43, Division IVA and Division XXVII amendments p.58. https://download1.fbr.gov.pk/Docs/20266291261044366FinanceAct2026.pdf
- **S8** — FBR, *Circular No. 15 of 2022-23 (Income Tax and CVT), 21 Jul 2022*: "Export of services", p.9. https://download1.fbr.gov.pk/Docs/2022721177241469circular15of2002-23.pdf
- **S9** — FBR, *Circular No. 2 of 2021-22, 1 Jul 2021 — Finance Act 2021 explanation*: para 24 "Export of services" and para 25 (repealed withholding provisions), p.10. https://download1.fbr.gov.pk/Docs/20217118751147CircularNo.2of2021-22.pdf
- **S10** — FBR, *Income Tax Rules, 2002 — amended up to 15.09.2026*: Rule 31 (p.150–151), Rule 42 (p.196), TY2024 paper return with Zakat code 9001 (p.970). https://download1.fbr.gov.pk/Docs/20269211394336470IncomeTaxRules2002.pdf
- **S11** — FBR, *S.R.O. 1495(I)/2026, 2 Sep 2026 — Income Tax Return for Tax Year 2026* (scanned; read by OCR and by eye): p.1 notification, p.2 individual return, p.3 Summary of Economic Transactions, p.15 Business Final Tax (s.154A lines), p.23 Other Sources Final Tax (s.151(1)(b)), p.26 Deductible Allowances, p.29–30 Adjustable Tax (s.151, s.149, s.236Y), p.38–40 wealth statement and reconciliation. https://download1.fbr.gov.pk/SROs/2026921792446743SRO1495.pdf
- **S12** — FBR, *Federal Excise Act, 2005 — updated up to 30.06.2025*: s.2(16a) (p.9); First Schedule Table II S.No.8 and Note (p.86–87). https://download1.fbr.gov.pk/Docs/202588138517680FEDAct,2005withindexupdatedupto30-06-2025.pdf
- **S13** — SBP, *Foreign Exchange Manual, Chapter 12 — Exports*: paras 7, 12, 31, 36. https://www.sbp.org.pk/assets/document/Chapter-12-foreign-exchange-manual.pdf
- **S14** — SBP, *Code List No. 5 — Invisible and Capital Receipts* (archive copy dated Sep 2021): codes 9181–9186, 9471, 9473. https://archive.sbp.org.pk/fe_returns/cod5.pdf
- **S15** — SBP, *Regulations for Electronic Money Institutions (EMIs)* (2023): para 13(III) (p.17–18), para 14(VI). https://archive.sbp.org.pk/psd/2023/C3-Enclosure-Regulations-EMIs.pdf
- **S16** — SBP, *BPRD Circular No. 05 of 2023 — Framework for Freelancers Accounts* (23 Oct 2023). https://www.sbp.org.pk/circulars/bprd-circular-no-05-of-2023
- **S17** — *Zakat and Ushr Ordinance, 1980* (Punjab Zakat & Ushr Department copy): s.2(ix), (xxx), (xxxii); First Schedule S.No.1. https://zakat.punjab.gov.pk/system/files/zakatushr1980.pdf
- **S18** — FBR, Press Releases index (checked 27 Sep 2026). https://www.fbr.gov.pk/pr
- **S19** — FBR, *Income Tax due dates*. https://www.fbr.gov.pk/categ/income-tax-due-dates/51147/40846/81148
- **S20** — PSEB (Pakistan Software Export Board), *Membership Benefits*. https://techdestination.com/membership-benefits/

Secondary:

- **S21** — KPMG Taseer Hadi & Co., *A Brief of Finance Act, 2026* (Jul 2026): Division IVA and Division XXVII narrative p.20; rate tables p.36 (s.151), p.44 (s.154, s.154A), p.50 (s.236Y) (PDF page numbers). https://assets.kpmg.com/content/dam/kpmgsites/pk/pdf/2026/07/A%20Brief%20of%20Finance%20Act%202026.pdf.coredownload.inline.pdf
- **S22** — Business Recorder, 26 Sep 2026, *Income tax returns, wealth statements: PM urged to extend deadline*. https://www.brecorder.com/news/40441291/income-tax-returns-wealth-statements-pm-urged-to-extend-deadline
- **S23** — TechJuice, Sep 2026, *Tax Lawyers Ask FBR to Extend Return Deadline*. https://www.techjuice.pk/tax-lawyers-ask-fbr-to-extend-return-deadline/
- **S24** — Dawn, 1 Oct 2025, *FBR extends deadline for filing income tax returns till Oct 15* (TY2025). https://www.dawn.com/news/1945674
- **S25** — FBR Spokesperson on X: TY2025 extension to 31 Oct 2025 (seen only as a search-result snippet). https://x.com/FBRSpokesperson/status/1978464777916526994
- **S26** — ProPakistani, 24 Jul 2026, *FBR Announces Date for Filing 2026 Tax Returns*. https://propakistani.pk/2026/07/24/fbr-announces-date-for-filing-2026-tax-returns/
- **S27** — ProPakistani, 3 Sep 2026, *FBR Again Changes 2026 Tax Return Form*. https://propakistani.pk/2026/09/03/fbr-again-changes-2026-tax-return-form/
- **S28** — Profit (Pakistan Today), 17 Feb 2026, *Pakistan fixes zakat nisab at Rs503,529 for Ramadan 2026*. https://profit.pakistantoday.com.pk/2026/02/17/pakistan-fixes-zakat-nisab-at-rs503529-for-ramadan-2026/
- **S29** — NayaPay Help Center, *From which countries can I receive remittance from?* (NayaPay's own statement about its partners). https://help.nayapay.com/article/250-from-which-countries-can-i-receive-remittance-from
- **S30** — Elevate Pay blog, *9186 PRC Certificate Now Available for NayaPay Freelancers*. https://www.elevatepay.co/blog/9186-prc-nayapay
