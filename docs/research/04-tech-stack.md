# 04 — Tech stack for the local statement tool (Python)

## Scope & date researched

- **Date researched:** 2026-09-27. Every version number, release date and `Requires-Python` value below was read from the PyPI JSON API on that day. [PRIMARY] [S1]
- **Questions covered:** the eight in the research request:
  1. PDF extraction
  2. Password-protected PDFs
  3. Streamlit
  4. pandas and exact money arithmetic
  5. Excel export
  6. Bank-profile config
  7. Synthetic test data
  8. Environment

  The requirements are in [../requirements.md](../requirements.md).
- **This Mac (read-only checks):**
  - macOS 27.0 on arm64.
  - Pythons: `/usr/bin/python3` is 3.9.6. Homebrew has `python3.12` (3.12.13) and `python3.14` (3.14.6), and both are PEP 668 "externally managed".
  - Installed: poppler `pdftotext`/`pdfinfo` 26.04.0, and Homebrew OpenJDK 25.0.2 and 17.0.19.
  - Not installed: `uv`, `qpdf`, Ghostscript (`gs`). [PRIMARY] [S2]
- **Method:**
  - Official docs, source code at release tags, PyPI metadata and wheel tags, and GitHub API repo data.
  - The released Streamlit 1.64.0 and reportlab 5.0.1 wheels were streamed into Python and inspected in memory, never written to disk.
  - The locally installed XlsxWriter 3.2.9 and openpyxl 3.1.5 sources were read. Both are the latest PyPI releases.
  - `pdftotext` and `pdfinfo` were run on a macOS system PDF that contains no personal data.
  - Nothing was installed. No files other than this one were created.
- **Limits:**
  - No real Meezan, MCB, SadaPay or NayaPay statement was available. Every claim about those layouts is therefore [UNVERIFIED] until it is checked locally against real files.
  - Licence readings below are not legal advice.
- **Confidence tags:**
  - [PRIMARY]: official docs, source code, PyPI metadata, a licence file, or local inspection of the released artefact.
  - [SECONDARY]: third-party material, such as another project's benchmark, GitHub issues or PRs, or other people's READMEs.
  - [UNVERIFIED]: my own inference, or general knowledge not checked against a source for this report.
  - `[S#]` identifiers link to the URLs listed in "Sources".

## Recommendation

| Layer | Pick (version on 2026-09-27) | Why |
|---|---|---|
| Python | CPython **3.14** (Homebrew 3.14.6, already installed); declare `requires-python = ">=3.12"` | Every compiled dependency ships cp314 macOS-arm64 wheels. 3.14 is supported until 2030-10. System 3.9.6 reached end of life on 2025-10-31 and is too old for current Streamlit, pandas and pdfplumber. |
| Project / environment | `pyproject.toml` + **uv** (`brew install uv`) with a committed `uv.lock`. Fallback: `python3.14 -m venv` + pip 26 | A hash-pinned, cross-platform lockfile means next year's run can reproduce this year's environment exactly (useful for audit). Homebrew Python is externally managed, so a venv is needed either way. |
| PDF text and coordinates | **pdfplumber 0.11.10** (MIT) | Word bounding boxes, crop, de-duplication and explicit column lines. Opens `BytesIO` with a password, AES-256 included. Text parsing is pure Python (pdfminer.six), and the project is actively maintained. |
| Second engine (debug and cross-check) | poppler **`pdftotext -tsv` / `-layout`** 26.04 (already installed), run as a subprocess | Fast and independent of pdfplumber. Use it only on unencrypted files, because the password would have to go on the command line. |
| Credit/debit sign logic | Column bands anchored on the header positions (primary), plus a **running-balance check** (required validation, and a flagged fallback), plus reconciliation of statement totals | Meezan's amounts are unsigned. Two independent signals catch each other's errors. |
| Decryption | `pdfplumber.open(uploaded_bytes, password=...)` in memory; **pikepdf 10.14** as an optional fallback | The owner no longer has to save an unlocked copy. |
| UI | **Streamlit 1.64.0** with a locked-down `.streamlit/config.toml` (Q3) | No telemetry, loopback only, and no startup external-IP lookup. |
| Tables and aggregation | **pandas 3.0.6**. Money as **integer paisa** (`int64`, or `Int64` when values can be missing). `Decimal` only when parsing text and for rate calculations. | Exact, vectorised, and matching amounts becomes integer comparison. |
| Excel | **XlsxWriter 3.2.9** through `pd.ExcelWriter(BytesIO, engine="xlsxwriter", engine_kwargs={"options": {"in_memory": True, "strings_to_formulas": False, "strings_to_urls": False}})` | No temp files, no accidental formulas, and good formatting control. openpyxl writes every sheet to a temp file. |
| Bank profiles | **TOML** read with stdlib `tomllib`, validated by **pydantic 2.13.5** (`extra="forbid"`, `re.Pattern` fields) | The reader needs no extra dependency. TOML literal strings hold regexes without escaping, and TOML has none of YAML's implicit typing surprises. |
| Tests | **pytest 9.1.1** + a **reportlab 5.0.1** canvas generator for fake statements + **pypdf 6.19 `[crypto]`** for encrypted variants. Hypothesis optional. | Look-alike statements with no personal data. Tests render a statement, parse it back, and compare. |
| Not chosen | PyMuPDF 1.28.2 (AGPL; optional later), camelot 2.0.0 (heavy OpenCV stack, table-only), tabula-py 2.10.0 (Java; stale), openpyxl as writer (temp files; last release 2024-06-28) | See Q1 and Q5. |

This table only summarises. Every fact in it is sourced and tagged in the detailed findings (Q1–Q8). The design choices are my recommendations.

## Detailed findings

### Q1. PDF extraction for bank-statement tables

#### 1.1 Candidates

| Library | Latest (released) | Requires-Python | Licence | Word coordinates | Table finder | Dependencies / notes | Repo activity | Evidence |
|---|---|---|---|---|---|---|---|---|
| pdfplumber | 0.11.10 (2026-06-15) | `>=3.8` on PyPI, but it pins pdfminer.six 20260107, which needs `>=3.10`. README: tested on 3.10–3.14 | MIT | `extract_words()` returns dicts with `text, x0, x1, top, doctop, bottom, upright, height, width, direction` | Strategies `lines`, `lines_strict`, `text`, `explicit` | pdfminer.six (with `charset-normalizer`, `cryptography`), Pillow ≥12.2, pypdfium2 ≥5.9 | pushed 2026-08-06 | [PRIMARY] [S1], [S3], [S5], [S7] |
| PyMuPDF | 1.28.2 (2026-08-06) | `>=3.10` (cp310-abi3 wheel) | AGPL-3.0 **or** Artifex commercial | `get_text("words")` returns `(x0, y0, x1, y1, "word", block_no, line_no, word_no)` | `find_tables()`, code ported from pdfplumber | No Python dependencies; among the fastest (see Speed) | pushed 2026-09-26 | [PRIMARY] [S1], [S3], [S14], [S15], [S18] |
| poppler `pdftotext` | 26.04.0 installed; 26.09.0 is the latest (2026-09-03) | n/a (command-line tool) | GPL ("not the LGPL") | `-tsv` gives per-word `left top width height text`; `-bbox-layout` gives XHTML block/line/word boxes | None (`-layout` is a character grid) | Reads stdin with `-` | n/a | [PRIMARY] [S2], [S24], [S25], [S26] |
| camelot-py | 2.0.0 (2026-06-04) | `>=3.10` | MIT | Via its backend | `lattice` (default), `stream`, `network`, `hybrid`, `ml`, `auto`; stream mode takes a `columns=` list of x-coordinates | 2.0 moved from pypdf + pdfminer.six to `playa-pdf`. Pulls in opencv-python-headless, pandas, openpyxl, pypdfium2. Ghostscript is optional since 1.0 | pushed 2026-09-19 | [PRIMARY] [S1], [S3], [S27], [S28], [S29] |
| tabula-py | 2.10.0 (2024-10-17) | `>=3.9` (classifiers stop at 3.13) | MIT | No | `lattice` / `stream`, `area`, `columns` | Needs "Java 8+". Wraps tabula-java, whose latest release is v1.0.5 (2021-08-17) | pushed 2024-12-05 | [PRIMARY] [S1], [S3], [S4], [S30], [S31] |
| pypdfium2 (already a pdfplumber dependency) | 5.13.0 (2026-08-13) | `>=3.6` | BSD-3-Clause / Apache-2.0 | Character boxes (`get_charbox`), `get_text_bounded()` | None | Fast PDFium binding; no word grouping | pushed 2026-09-24 | [PRIMARY] [S1], [S3], [S32] |

How each library performs on the criteria:

- **Accuracy of column assignment.**
  - pdfplumber, PyMuPDF and `pdftotext -tsv` all give real per-word boxes. [PRIMARY] [S7], [S15], [S2]
  - `pdftotext -layout` only reproduces the layout "as best as possible" as monospaced text. [PRIMARY] [S24] Column positions counted in characters drift with proportional fonts, so it is weaker for a statement whose columns are separated by position alone, like Meezan's. [UNVERIFIED]
  - camelot `stream` and tabula `stream` guess columns from whitespace unless you pass fixed x-coordinates. [PRIMARY] [S28], [S31]
  - pdfplumber splits words where the gap exceeds `x_tolerance` (default 3 pt). [PRIMARY] [S7] Two amounts printed close together can therefore merge into one "word". Full-match every amount token (Q6) and treat a numeric blob that doesn't match as an error.
- **Descriptions that wrap onto several lines.**
  - No library rebuilds a multi-line row in a borderless statement for you.
  - The `lines` strategies (pdfplumber, PyMuPDF) only help when the PDF draws cell borders. [PRIMARY] [S5], [S14]
  - Otherwise the parser must rebuild rows from lines that start with a date (algorithm in 1.2). [UNVERIFIED]
- **Repeated page headers and footers.**
  - pdfplumber has `crop`, `within_bbox`, `outside_bbox` and `filter`, and `search()` returns regex matches with their bounding boxes. [PRIMARY] [S5]
  - PyMuPDF `find_tables()` takes `clip=`. [PRIMARY] [S14]
  - `pdftotext` can only apply one crop rectangle (`-x -y -W -H`) to every page. `-nodiag` drops diagonal watermarks. [PRIMARY] [S24]
  - In pdfplumber, `dedupe_chars()` removes duplicated characters (bold text is often drawn twice). Character `upright` and `matrix` properties let you drop rotated watermark text. [PRIMARY] [S5]
- **Speed.**
  - PyMuPDF's own benchmark on 7,031 pages: PyMuPDF 8.01 s, XPDF 27.42 s, PyPDF2 101.64 s, PDFMiner 227.27 s. This is the vendor's own benchmark. [PRIMARY] [S13]
  - The independent py-pdf/benchmarks averages: PyMuPDF 0.1 s, pypdfium2 0.1 s, pdftotext 0.3 s, pypdf 3.5 s, pdfminer.six 5.8 s, pdfplumber 9.5 s. Those runs used pdfplumber 0.11.7 and PyMuPDF 1.26.1. [SECONDARY] [S33]
  - pdfplumber's own README says "`pymupdf` is substantially faster than `pdfminer.six` (and thus also `pdfplumber`)". [PRIMARY] [S5]
  - A few hundred statement pages a year should take seconds to tens of seconds with pdfplumber, which is acceptable for a once-a-year tool. [UNVERIFIED — measure this]
- **Licences.**
  - pdfplumber, pdfminer.six, camelot and tabula-py are MIT. pypdfium2 is BSD/Apache. PyMuPDF is AGPL-3.0 or commercial. Poppler is GPL. [PRIMARY] [S1], [S26]
  - AGPL §13 applies "if you modify the Program" and "users interact with it remotely through a computer network". [PRIMARY] [S22]
  - Artifex: "You cannot deploy our open-source as part of a server-based application or service, without disclosing your own application's full source code under AGPL to any users interacting with it". [PRIMARY] [S20] The PyMuPDF FAQ adds that inside "a commercial product's data pipeline … the AGPL obligations apply". [PRIMARY] [S21]
  - My reading: a single-user tool on the owner's own machine creates no practical obligation. It would, however, limit the licence if the repo were ever shared or published. [UNVERIFIED; not legal advice]
  - For poppler, the GPL FAQ says "pipes, sockets and command-line arguments are communication mechanisms normally used between two separate programs". It also says modified versions may be used "privately, without ever releasing them". [PRIMARY] [S23]
- **Maintenance and Python versions:** see the table. tabula is effectively stagnant: tabula-java has had no release since 2021. [PRIMARY] [S4]
- **Scanned PDFs and broken fonts.**
  - pdfplumber "Works best on machine-generated, rather than scanned, PDFs", and OCR is not provided. [PRIMARY] [S5]
  - pdfminer outputs `(cid:x)` when a PDF has "incomplete unicode mappings". [PRIMARY] [S12]
  - The parser should detect pages with no characters, or with `(cid:`, and stop with a clear message rather than guess. [UNVERIFIED — design advice]

**Choice.** pdfplumber is the primary engine. `pdftotext -tsv` (or `-layout`) is a debugging and second-opinion tool for unencrypted files. PyMuPDF is optional later, if speed ever matters and the AGPL is acceptable. camelot and tabula are not used: they solve whole-table extraction, but this job needs row assembly and sign logic. `pdfplumber`'s experimental `extract_text(layout=True)` gives a layout-preserving debug view without leaving Python. [PRIMARY] [S5]

#### 1.2 The Meezan problem: unsigned amounts in separate Credit and Debit columns

**(a) Column bands anchored on the header, used as the primary mechanism.** These steps are a design built on the pdfplumber API. [PRIMARY] for the API calls cited; [UNVERIFIED] for fit with real Meezan PDFs.

1. Open the PDF in memory. Optionally call `page.dedupe_chars()`, and drop rotated watermark characters using `upright`/`matrix`. [S5]
2. Find the header row on **every** page with `page.search()` using the profile's header patterns (for example "Booking Date", "Description", "Credit", "Debit", "Available Balance"). Require all of them on one visual line, meaning the same `top` within a small tolerance. [S5]
3. Build a horizontal band for each column. Text columns use the midpoints between neighbouring header boxes as boundaries. Numeric columns are usually right-aligned, so assign an amount token to the column whose header right edge (`x1`) is nearest the token's `x1`, within a tolerance. A token outside every band, or equally close to two, is marked **ambiguous** and never guessed. Alignment is set per column in the profile.
4. Crop each page to the body, between the bottom of the header and the top of the first footer match (for example "Page x of y" or a disclaimer), using `page.crop((x0, top, x1, bottom))`. [S5] A continuation page without a header reuses the previous page's bands.
5. Group words into visual lines by `top`. Keep them in printed order using `doctop`, the top position measured across the whole document, so page breaks don't reorder rows. [S7]
6. A line whose date column holds a date token starts a new transaction. A line with description text but no date is a continuation, appended to the open transaction. If descriptions are vertically centred around the date line, append it instead to the nearest date line, set by a profile switch. Rows such as "Opening balance", "B/F", "Total" or "Closing balance" are matched explicitly by profile patterns, never parsed as transactions.
7. pdfplumber can do the cell assignment itself: pass the computed boundaries as `explicit_vertical_lines` (numbers are x-coordinates) with `vertical_strategy="explicit"`. [PRIMARY] [S5] Wrapped text still needs step 6 unless the PDF draws row borders. [UNVERIFIED]
8. Fallback: if the header can't be found, use x-boundaries stored in the profile. This is the same idea as tabula's and camelot's `columns` options. [PRIMARY] [S28], [S31]

Failure modes:
- A header label is renamed.
- Amounts are centred rather than right-aligned.
- Columns are so close that tokens merge.

All of these surface as "ambiguous" or as regex failures, not as silent wrong signs.

**(b) Inferring the sign from the running balance, used as validation.** The formulas are arithmetic; how well they fit Meezan's balance column is [UNVERIFIED].

- For each row *i*, parse the printed balance `B_i` and the unsigned amount `A_i` into integer paisa, and compute `Δ_i = B_i − B_{i−1}`. `B_0` is the printed opening balance. A credit should give `Δ_i = +A_i` and a debit `Δ_i = −A_i`. This is an exact integer comparison with no tolerance.
- **As validation:**
  - If the sign from (a) agrees with Δ, the row is marked `validated`.
  - If the sign disagrees, the row is flagged `conflict`.
  - If `|Δ_i| ≠ A_i`, the row is flagged `chain_break`. Likely causes: a missed row, two rows merged, a misread number, or a balance column that isn't a simple running balance.
- **As a fallback:** only when (a) marked the amount ambiguous *and* `|Δ_i| = A_i`, take the sign from Δ and record `sign_source = "balance"` in the audit trail.
- **At statement level:** check `B_0 + ΣCredits − ΣDebits = printed closing balance`, and check the printed totals where present. The brief asks for exactly this sanity check in its output section 6.
- **Limits:**
  - Every row needs a printed balance. If balances appear only once per day or page, check only at those points.
  - Rows must stay in printed order: never sort by date before validating.
  - Δ alone cannot separate a row that has both a credit and a debit, or a fee netted into the balance.
  - The "Available Balance" column may differ from the ledger balance when funds are on hold. [UNVERIFIED for Meezan]
- **Verdict:** use (a) as the primary signal and (b) as required validation, plus a flagged fallback. Never use (b) alone, because one misread balance would silently flip the signs of neighbouring rows.

**Prior art.**
- pdf-bank-statement-parser checks "(for every transaction extracted) that the balance amount is the sum of the previous balance and the transaction amount". [SECONDARY] [S35]
- pdf_statement_reader keeps, per bank, "The right x coordinate of each column in the table in pts" in a config file, and has a command that "Validates the csv statement rolling balance". [SECONDARY] [S34]
- monopoly uses per-bank regex configs with named groups (including `polarity`) and a totals "safety check". It is AGPL-3.0, so borrow ideas, not code. [SECONDARY] [S36]

**Other banks, as described in the brief** [UNVERIFIED against real PDFs]:
- **MCB:** the Dr/Cr suffix gives the sign in the text itself. Still validate against the running balance.
- **SadaPay:** signed +/- amounts, and no balance at all. The only check is against the printed Total Debit / Total Credit.
- **NayaPay:** has a running-balance column, so use check (b).

### Q2. Password-protected PDFs, opened in memory

| Library | Opens from memory | Password API | Encryption handled | Extra packages | Wrong password | Evidence |
|---|---|---|---|---|---|---|
| pdfplumber 0.11.10 (via pdfminer.six 20260107) | Yes: `open(path_or_fp)` accepts `BytesIO` | `password=` | RC4 (revisions 2–3), RC4 or AES-128 (revision 4), AES-256 (revisions 5 and 6) | None extra: `cryptography>=36.0.0` is a required dependency of pdfminer.six | `PdfminerException`, whose `args[0]` is pdfminer's `PDFPasswordIncorrect` | [PRIMARY] [S1], [S5], [S6], [S9], [S10] |
| pypdf 6.19.0 | Yes: `PdfReader(stream)` accepts "A File object or an object that supports the standard read and seek methods" | `password=` or `decrypt()` returning `PasswordType` | RC4-40, RC4-128, AES-128, AES-256-R5, AES-256 | AES needs `cryptography` (extra `pypdf[crypto]`) or pycryptodome | `decrypt()` returns `NOT_DECRYPTED = 0` | [PRIMARY] [S1], [S37], [S38] |
| pikepdf 10.14.0 | Yes: a stream is "accessed as a readable binary stream" | `password=` | RC4/MD5 (revisions 2–4) and AES-256 revision 6, via qpdf's native crypto in the Linux and macOS wheels | None; the wheels are self-contained. Requires Python ≥3.11 and macOS 15+ on Apple Silicon | `pikepdf.PasswordError` | [PRIMARY] [S1], [S39], [S40], [S41] |
| PyMuPDF 1.28.2 | Yes: `stream=` accepts bytes, bytearray or BytesIO | `authenticate(pw)` returns 0 on failure, 2 for the user password, 4 for the owner password, 6 if both are equal | MuPDF supports security revisions 1–6, including AESV2 (AES-128) and AESV3 (AES-256) | None | Returns 0 | [PRIMARY] [S16], [S17], [S19] |
| `pdftotext` 26.04 | Reads stdin with `-` | `-upw` / `-opw` **on the command line** | Poppler's `CryptAlgorithm` enum has `cryptRC4`, `cryptAES`, `cryptAES256` | n/a | Exit code 1 or 3 | [PRIMARY] [S24], [S26] |

- **Yes, the owner never needs to save an unlocked copy.**
  1. `st.file_uploader` returns a `BytesIO` subclass. [PRIMARY] [S49]
  2. Pass it straight to `pdfplumber.open(uploaded_file, password=pw)`.
  3. Catch `PdfminerException` and check `isinstance(exc.args[0], PDFPasswordIncorrect)` to re-prompt. [PRIMARY] [S6], [S9], [S10]

  The brief's step "I'll unlock before upload" can be dropped. That removes a plaintext copy from disk.
- **Password input:**
  - `st.text_input(..., type="password")` "masks the user's typed value". Its `bind` option (which syncs to URL query parameters) "can't be used with type="password"", and `persist_state` defaults to `None`, meaning the value is not kept after the widget stops rendering. [PRIMARY] [S62]
  - Keep the password only in a local variable or in `st.session_state`, which is lost when the tab closes. [PRIMARY] [S59]
- **Avoid command-line passwords.** `pdftotext -upw` and pdfplumber's `repair=True` put the password in process arguments; `repair=True` runs Ghostscript with `-sPDFPassword=...`, and Ghostscript isn't installed anyway. [PRIMARY] [S8], [S2] Process arguments are visible to other local processes, for example via `ps`. [UNVERIFIED general Unix behaviour] Use the in-process libraries for encrypted files.
- **pikepdf as fallback:** `Pdf.save()` removes encryption "If `False` or omitted". [PRIMARY] [S40] If pikepdf is used to decrypt a file pdfminer can't, save into a `BytesIO` and hand those bytes to pdfplumber. Never save to a path.
- **Permission-only restrictions:** pdfminer.six's page iterator only logs a warning when a PDF forbids text extraction, unless `check_extractable=True`. [PRIMARY] [S11] Statements protected only by an owner password should therefore open. [UNVERIFIED for pdfplumber's code path]
- **Which encryption the banks use** is unknown. The owner can check locally with `pdfinfo`, which prints an `Encrypted:` line (seen on an unencrypted file here). [PRIMARY] [S2] That it names the algorithm for encrypted files is [UNVERIFIED].

### Q3. Streamlit

#### 3.1 Version, Python support, server

- Latest is **1.64.0**, released 2026-09-15, with `Requires-Python >=3.10`. [PRIMARY] [S1], [S43]
- "Due to end of life, Python 3.9 is no longer supported" as of 1.51.0 (2025-10-29). "Streamlit supports Python 3.14" as of 1.52.0 (2025-12-03). [PRIMARY] [S44] **The system Python 3.9.6 cannot run current Streamlit.**
- Since 1.57.0 (2026-04-29), "Streamlit now uses Starlette/Uvicorn instead of Tornado". [PRIMARY] [S45] The 1.64.0 wheel contains no `import tornado` anywhere. [PRIMARY] [S46]

#### 3.2 What can leave the machine, and how to stop it

This comes from a code scan of the 1.64.0 wheel and the `develop` branch source. It is static analysis only, not a network capture.

| Trigger | Destination | Prevent with | Evidence |
|---|---|---|---|
| `browser.gatherUsageStats` (default `true`) | The browser fetches `https://data.streamlit.io/metrics.json` and sends events containing `machineIdV3`/`V4`, `sessionId`, `pythonVersion`, `serverOs`, `contextPageUrl`, `contextPageTitle`, `contextUserAgent` and more | `gatherUsageStats = false`. The code is `actuallySendMetrics = gatherUsageStats && this.metricsUrl !== 'off'`, and the config fetch only happens when that is true. Server-side collection also stops ("If gatherUsageStats is False skip this whole code") | [PRIMARY] [S42], [S46], [S47] |
| First-run email prompt (`server.showEmailPrompt`, default `true`; skipped when `server.headless = true`) | If an email is typed, it is POSTed to the URL listed in `metrics.json` | `server.headless = true` and/or `server.showEmailPrompt = false` | [PRIMARY] [S46], [S48] |
| Startup banner when `server.headless = true` and no specific `server.address` or `browser.serverAddress` is set (or a wildcard `0.0.0.0` or `::`) | `get_external_ip()`: GET `http://checkip.amazonaws.com`, then HTTPS, with a 1 s timeout | Set `server.address = "127.0.0.1"`. A specific, non-wildcard address takes the single-URL branch, which never looks up the external IP | [PRIMARY] [S46] |
| `get_internal_ip()` (banner) | A UDP socket `connect(("8.8.8.8", 1))` to learn the LAN IP | Same fix as above. A UDP `connect` sends no packet. [UNVERIFIED general socket behaviour] | [PRIMARY] [S46] |
| Only on explicit use: `streamlit run <URL>`, a theme file given as a URL | The URL given | Don't do either | [PRIMARY] [S46] |
| Browser side, only on explicit use: `page_icon=":material/…:"` | Favicon from `fonts.gstatic.com` | Use an emoji or a local image as the page icon | [PRIMARY] [S46] |
| Browser side, only on explicit use: map and chart elements (pydeck, Plotly maps) | `api.mapbox.com`, `basemaps.cartocdn.com`, `unpkg.com`, `cdn.jsdelivr.net` | Don't use map elements | [PRIMARY] [S46] |
| Static-app viewer mode | `data.streamlit.io/static.json` | Not reached by a normal `streamlit run` session. Traced in the minified bundle only | [PRIMARY] [S46] + [UNVERIFIED completeness] |

- XSRF protection (`server.enableXsrfProtection`) and CORS protection (`server.enableCORS`) both default to `true`.
- `server.allowedHosts` defaults to an empty list, which accepts any `Host` header. Set it to protect against DNS-rebinding attacks. [PRIMARY] [S46]
- The app has no login. Any local process can reach the loopback port while the app runs, so stop the server after use. [UNVERIFIED general]

Recommended project `.streamlit/config.toml`. Every option below exists in the 1.64.0 `config.py`. The project file takes precedence over `~/.streamlit/config.toml`, and environment variables and command-line flags override both. [PRIMARY] [S42], [S46]

```toml
[browser]
gatherUsageStats = false
serverAddress = "127.0.0.1"

[server]
address = "127.0.0.1"          # loopback only; also skips the checkip.amazonaws.com lookup
port = 8501
headless = true                # no browser auto-open, no email prompt
showEmailPrompt = false
enableXsrfProtection = true    # default, stated explicitly
enableCORS = true              # default, stated explicitly
allowedHosts = ["127.0.0.1", "localhost"]
maxUploadSize = 25             # MB; the default is 200
runOnSave = false
fileWatcherType = "none"       # optional: no auto-reload while developing

[client]
toolbarMode = "viewer"         # hides the Deploy button and developer menu items
```

Belt and braces: have the launcher script also pass `--browser.gatherUsageStats false --server.address 127.0.0.1`.

#### 3.3 `st.file_uploader`: memory or disk, and size limit

- The widget returns an `UploadedFile`, "a subclass of BytesIO". Files are "limited to 200 MB each" by default. The limit is set globally with `server.maxUploadSize`, or per widget with `max_upload_size`. [PRIMARY] [S49]
- Streamlit's knowledge base says uploads are held "in a BytesIO buffer in Python memory (i.e. RAM, not disk)" until the next rerun, until another file replaces them, or until the tab closes. [PRIMARY] [S50] The Starlette app wires in `MemoryUploadedFileManager` for uploads and `MemoryMediaFileStorage` for media, in `starlette_app.py`. [PRIMARY] [S46]
- **Caveat from the 1.64.0 code:** the upload HTTP handler parses the body with Starlette's `request.form()`, then `upload.read()`, then `upload.file.close()`. The handler's own comment says data is buffered "in memory (upload.read()) or spooled to disk (request.form())". [PRIMARY] [S46]
  - Starlette's multipart parser holds each file in `SpooledTemporaryFile(max_size=self.spool_max_size)`, where `spool_max_size = 1024 * 1024` (1 MB). [PRIMARY] [S51]
  - A spooled file writes its contents to disk once it exceeds `max_size`. On Unix, the temp file's directory entry "is removed immediately". [PRIMARY] [S52]
  - So an upload over 1 MB briefly lands in an unnamed file under `$TMPDIR`.
  - The spilled bytes are the uploaded file itself, which stays encrypted if the statement is password-protected. Text-only statements are probably under 1 MB. [UNVERIFIED]
  - Mitigations: accept it; or keep the default and treat files over 1 MB as an exception; or add a "read from a local path" input, since the PDFs are already on disk.

#### 3.4 Review lists with `st.data_editor` and `st.session_state`

- **Signature:** `st.data_editor(data, *, …, hide_index=None, column_order=None, column_config=None, num_rows="fixed", disabled=False, key=None, on_change=None, …)`. `disabled` accepts a list of column names. `num_rows="fixed"` means "The user can't add or delete rows". [PRIMARY] [S53]
- **Column types:**
  - `CheckboxColumn` for confirm/reject.
  - `SelectboxColumn(options=[...], required=True)` for "pending / confirmed / rejected".
  - `NumberColumn(format="localized" | "accounting" | printf-style)` for read-only amounts. [PRIMARY] [S56], [S57], [S54]
- **Edits:** with a `key`, edits are stored in session state as `edited_rows` ("Keys are zero-based row indices"), `added_rows` and `deleted_rows`. [PRIMARY] [S53], [S54] Because edits are keyed by row position, store decisions in a separate dict keyed by a stable `txn_id` column, and keep the input DataFrame unchanged in `st.session_state` between reruns. [UNVERIFIED — design advice]
- **Widget identity:** "The key is the primary determinant of the widget's identity", but constraining parameters can still reset a widget. [PRIMARY] [S55] Whether a changed `data` argument resets `st.data_editor` specifically is [UNVERIFIED]; test it.
- **Decimal columns:** "Allows editing of decimal columns" landed in 1.28.0 (PR #7475). [SECONDARY] [S58] Keep amount columns read-only anyway.
- **Session state:** "exists for as long as the tab is open and connected", is "not persisted", and is wiped if the server crashes. That is the right place for parsed transactions and review decisions. [PRIMARY] [S59]
- **Not `st.cache_data`:** its values "are available to all users of your app", so they outlive the tab. `persist="disk"` "will persist the cached data to the local disk". [PRIMARY] [S61], [S46]

#### 3.5 `st.download_button` for the Excel file

- `data` accepts "str, bytes, file-like, or callable". Data passed directly "is stored in-memory while the user is connected". [PRIMARY] [S60] The media store behind it is `MemoryMediaFileStorage`. [PRIMARY] [S46]
- `on_click="ignore"` (since 1.43.0) downloads without rerunning the app. A callable `data` (since 1.52.0) builds the file on demand. [PRIMARY] [S60], [S44]
- Pattern: build the workbook bytes in memory (Q5), then call `st.download_button("Download Excel", data=xlsx_bytes, file_name="…xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", on_click="ignore")`.

**Alternatives to Streamlit:** none recommended. The only privacy caveat (spooling of uploads over 1 MB) is easier to fix with a local-path input than by changing frameworks.

### Q4. pandas and exact money arithmetic

- **Version:** latest is **3.0.6**, released 2026-09-17, with `Requires-Python >=3.11`. pandas 3.0.0 was released on 2026-01-21 and "supports Python 3.11 and higher". [PRIMARY] [S1], [S64]
- **numpy:** the latest, 2.5.3, needs Python ≥3.12. On Python 3.14, pandas requires `numpy>=2.3.3`. [PRIMARY] [S1]
- **pandas 3.0 changes that matter here:** [PRIMARY] [S64], [S65]
  - Text columns get a dedicated `str` dtype by default. It is "backed by PyArrow under the hood, if installed", and Streamlit installs pyarrow.
  - Copy-on-Write is the default. "'Chained assignment' … will stop working".
  - Datetimes parsed from strings default to microsecond resolution.
  - `to_json()` "now encodes `Decimal` as strings".
- **Regex engine pitfall:** in the 3.0.6 source, pyarrow-backed `.str.contains()`, `.str.match()` and `.str.fullmatch()` use pyarrow's `match_substring_regex` (RE2). They fall back to Python `re` only when the pattern carries flags other than IGNORECASE/UNICODE, or contains lookarounds or backreferences. [PRIMARY] [S66], [S67]
  - In RE2, `\b` is an "ASCII word boundary", `\d` is `[0-9]`, `\w` is `[0-9A-Za-z_]`, and possessive quantifiers and atomic groups are "NOT SUPPORTED". [PRIMARY] [S68]
  - In Python `re`, `\d` matches any Unicode decimal digit. [PRIMARY] [S90]
  - **Therefore apply profile regexes with Python `re` directly**, for example with a compiled pattern over a list, not through `.str` methods. The same regex then behaves identically in tests and in the app.

Money representation options:

| Option | Exact? | Speed | Missing values | Pitfalls | Evidence |
|---|---|---|---|---|---|
| `decimal.Decimal` in `object` columns | Yes. "Decimal numbers can be represented exactly" | Python-level. One report: about 70 s to aggregate 1 M rows, versus under 1 s for floats (irrelevant at statement scale) | `None`/NaN mixing | Mixing with `float` raises `TypeError`, which is a safe failure. Easy to lose exactness via `astype(float)` or `pd.to_numeric`. `groupby().sum()` works (pandas' own guide sums a Decimal column). Some operations have historically failed, e.g. `groupby().cumsum()` raising "No numeric types to aggregate" in pandas 0.22 | [PRIMARY] [S74], [S71]; [SECONDARY] [S72], [S73] |
| `pd.ArrowDtype(pa.decimal128(p, s))` | Yes | Vectorised in pyarrow compute ("Numeric aggregations", "Numeric arithmetic") | `<NA>` | Less battle-tested; how many operations are covered is unknown | [PRIMARY] [S70]; coverage [UNVERIFIED] |
| **Integer paisa** (`int64`, or `Int64` when values can be missing) | Yes | Fully vectorised | NaN turns `int64` into `float64` ("this forces an array of integers with any missing values to become floating point"); use nullable `Int64` | Parse strings straight to integers, never through `float`. Round rates and percentages explicitly (`Decimal.quantize`; the default context rounding is `ROUND_HALF_EVEN`). Divide by 100 only for display and export | [PRIMARY] [S69], [S74] |

- **Recommendation:** integer paisa inside DataFrames. `Decimal` when parsing text (via `quantize(Decimal("0.01"))`, rejecting anything that isn't already exactly two decimal places) and for any rate or percentage calculation. Format to 2 dp only at the UI and Excel edges.
- **Transfer matching:** amounts equal or within a fee become integer comparisons.
- **Range:** `int64` holds about 9.2 × 10^18 paisa, far beyond any personal balance. [UNVERIFIED — own arithmetic]
- **Excel precision:** Excel keeps "15 digits" of precision. [PRIMARY] [S82] So any amount below 10^13 PKR survives to the paisa. [UNVERIFIED — own arithmetic]

### Q5. Excel export: openpyxl vs XlsxWriter through `pandas.ExcelWriter`

- **pandas side:**
  - `pd.ExcelWriter(path, engine=None, …, engine_kwargs=None)`. For `.xlsx` the default is "xlsxwriter for xlsx files if xlsxwriter is installed otherwise openpyxl". [PRIMARY] [S75]
  - `engine_kwargs` goes to `xlsxwriter.Workbook(file, **engine_kwargs)`, to `openpyxl.Workbook(**engine_kwargs)`, or, in append mode, to `openpyxl.load_workbook(file, **engine_kwargs)`. [PRIMARY] [S75]
  - The pandas docs show writing to `io.BytesIO`. [PRIMARY] [S75]
  - Writing several sheets needs one `ExcelWriter` object. [PRIMARY] [S76]
  - pandas 3.0.6's minimum optional versions are xlsxwriter 3.2.0, openpyxl 3.1.5 and pyarrow 13.0.0. [PRIMARY] [S63]
  - `DataFrame.to_excel()` has `freeze_panes` ("one-based bottommost row and rightmost column") and `autofilter`. [PRIMARY] [S76]

| | XlsxWriter 3.2.9 | openpyxl 3.1.5 |
|---|---|---|
| Latest release / activity | 2025-09-16; repo pushed 2026-08-04 [PRIMARY] [S1], [S3] | 2024-06-28; no release since [PRIMARY] [S1] |
| Licence | BSD-2-Clause [PRIMARY] [S1] | MIT [PRIMARY] [S1] |
| Append to an existing workbook | No: pandas raises "Append mode is not supported with xlsxwriter!" [PRIMARY] [S107] | Yes, via `openpyxl.load_workbook` [PRIMARY] [S75] |
| **Temp files while saving** | Yes by default. "XlsxWriter stores workbook data in temporary files prior to assembling the final XLSX file" in the system temp directory, using `tempfile.mkstemp()` for each XML part, then `os.remove()` after zipping. `{"in_memory": True}` uses `StringIO` instead [PRIMARY] [S77], [S80] | Yes, **always**. Every sheet goes through `WorksheetWriter`, which creates `NamedTemporaryFile(prefix='openpyxl.', delete=False)`, zips it, then removes it (with an `atexit` cleanup). This happens even when the target is a `BytesIO`. No in-memory switch found in 3.1.5 [PRIMARY] [S81] |
| Accidental formulas and links | By default `strings_to_formulas=True` (a string starting with `=` becomes a formula) and `strings_to_urls=True`. Both can be turned off [PRIMARY] [S77], [S80] | A string starting with `=` (longer than 1 character) is stored as a formula [PRIMARY] [S81] |
| `Decimal` cells | `write()` sends `int, float, Decimal, Fraction` to `write_number()`; numbers are serialised with `{:.16G}` [PRIMARY] [S79], [S80] | `Decimal` is in `NUMERIC_TYPES` [PRIMARY] [S81] |
| Formatting | `writer.book.add_format({'num_format': '#,##0.00'})`, `worksheet.set_column(first, last, width, fmt)`, `freeze_panes(row, col)`, `autofit(max_width=1790)` ("approximately"; based on Calibri 11), `add_table`, `autofilter` [PRIMARY] [S78], [S79], [S80] | `cell.number_format`, `column_dimensions[...].width`, `ws.freeze_panes` [PRIMARY] [S81] |
| Formatting limitation | Cells that pandas already formatted (header, index, dates) "isn't possible to format" again. Use `set_column()` for data columns, or write the section sheets directly with XlsxWriter [PRIMARY] [S78] | — |

- **Pick: XlsxWriter.** An illustrative writer setup; every parameter is documented in [S75], [S76], [S77], [S78] and [S79]:

```python
buf = io.BytesIO()
with pd.ExcelWriter(
    buf,
    engine="xlsxwriter",
    engine_kwargs={"options": {"in_memory": True,            # no temp files
                               "strings_to_formulas": False,  # "=..." descriptions stay text
                               "strings_to_urls": False}},
) as writer:
    raw.to_excel(writer, sheet_name="Raw transactions", index=False,
                 freeze_panes=(1, 0), autofilter=True)
    money = writer.book.add_format({"num_format": "#,##0.00"})
    writer.sheets["Raw transactions"].set_column("F:H", 16, money)
xlsx_bytes = buf.getvalue()
```

- **Excel limits:** 1,048,576 rows by 16,384 columns per sheet, "15 digits" of number precision, and 32,767 characters per cell. [PRIMARY] [S82]

### Q6. Config and bank profiles

| Format / library | Read / write | Pros | Cons | Evidence |
|---|---|---|---|---|
| **TOML + `tomllib`** (stdlib since 3.11) | Read only ("does not support writing TOML"). Write with tomli-w 1.2.0, or with tomlkit 0.15.1, a "style-preserving" library "recommended … for editing already existing TOML files" | No dependency. Parses TOML 1.0.0. "Literal strings" in single quotes have "no escaping" (the spec's own example is a regex); `'''…'''` literals may span lines. Keys are case-sensitive, and "Defining a key multiple times is invalid". `parse_float=decimal.Decimal` is available | Nested lists of tables are more verbose than YAML | [PRIMARY] [S83], [S84], [S1] |
| YAML + PyYAML 6.0.3 | Read/write | Readable nesting | YAML 1.1. "It is not safe to call `yaml.load` with any data received from an untrusted source", so always use `safe_load`. Implicit typing: `y, yes, no, on, off` (all cases) become booleans, and dates become `datetime` objects. An unquoted header label such as `No` or `On` silently becomes a bool | [PRIMARY] [S85], [S86], [S1] |
| YAML + ruamel.yaml 0.19.1 | Round-trip read/write | YAML 1.2; preserves comments and key order | PyPI classifier "Development Status :: 4 - Beta"; the author warns about API changes and asks users to pin versions | [PRIMARY] [S87], [S1] |

- **Pick: TOML**, hand-edited, read with `tomllib`. If the UI ever edits profiles, switch the writer to tomlkit so comments survive.
- **pydantic 2.13.5** (released 2026-08-28, `Requires-Python >=3.9`; pins pydantic-core 2.46.5, which ships cp314 arm64 wheels): [PRIMARY] [S1]
  - `ConfigDict(extra="forbid")` makes a typo in a key a `ValidationError`. The default `"ignore"` silently drops unknown keys. `frozen=True` and `strict=True` are also available. [PRIMARY] [S88]
  - Fields typed `re.Pattern` are compiled with Python's `re.compile()`. [PRIMARY] [S89] String constraints like `Field(pattern=...)` use `regex_engine="rust-regex"` by default. That engine is "non-backtracking … but does not support all regex features". [PRIMARY] [S88] Store profile regexes as `re.Pattern` fields, not as `pattern=` constraints.
  - Load-time checks worth adding:
    - Required named groups are present, via `Pattern.groupindex`. [PRIMARY] [S90]
    - Each profile carries sample lines that must match (a self-test).
    - Date formats round-trip.
    - A `valid_from` date, so a bank's format change next year becomes a new profile version rather than an edit.
- **Regexes for amounts:**
  - Use named groups (`(?P<amount>…)`, read back with `Match.groupdict()`). [PRIMARY] [S90]
  - Apply them with `re.fullmatch` to one column cell or token, not with `search` over a whole line. That avoids matching digits inside an IBAN, a STAN or a reference number.
  - Verbose mode `(?x)` ignores whitespace except inside character classes or when escaped. It pairs well with TOML `'''…'''` strings. [PRIMARY] [S90]
  - Use `[0-9]` or the `(?a)` flag if only ASCII digits are acceptable. [PRIMARY] [S90]
  - Atomic groups and possessive quantifiers (Python 3.11+) limit backtracking in user-written patterns. [PRIMARY] [S90]
  - Normalise text first. pdfplumber's `unicode_norm="NFKC"` handles non-breaking spaces. [PRIMARY] [S5] Map the Unicode minus sign `U+2212` to `-` explicitly. [UNVERIFIED]
  - An illustrative token pattern, to be tuned per profile; it is a sketch and has not been tested:

```text
(?x) ^
(?P<lparen>\()?                       # (1,234.00) accounting negative
(?P<sign>[-+−])? \s*             # SadaPay-style +/- (incl. Unicode minus)
(?:Rs\.?|PKR)? \s*                    # optional currency label
(?P<int>[0-9]{1,3}(?:,[0-9]{2,3})*|[0-9]+)   # 1,234,567 or lakh-style 12,34,567
(?:\.(?P<frac>[0-9]{1,2}))?
(?P<rparen>\))?
\s* (?P<suffix>-|(?i:cr|dr)\.?)?      # trailing minus, or MCB-style Cr/Dr
$
```

  After matching:
  - Check that the parentheses are balanced.
  - Map `suffix` through the profile's own `debit_suffixes`/`credit_suffixes`, not hard-coded meanings.
  - Build the integer paisa value from `int` and `frac`, without going through `float`.
- **Dates:**
  - Give each profile an explicit list of `strptime` formats. `%b` is "locale-dependent". [PRIMARY] [S91] Programs start in the `C` locale unless the code changes it, so English month abbreviations parse by default. [PRIMARY] [S92]
  - A format without a year triggers a `DeprecationWarning` and "may raise an error as of Python 3.15". Insert the statement's year explicitly, taking care with the July–June fiscal year that crosses December/January. [PRIMARY] [S91]
  - `%y` maps 69–99 to the 1900s. [PRIMARY] [S91]
  - Read ambiguous dates like `03/04/2025` as day/month for Pakistan, and reject dates outside the statement period. [UNVERIFIED — design advice]
- **Classification keywords:** use `(?i)\bWise\b` so "otherwise" doesn't match. Python's `\b` is a Unicode word boundary. [PRIMARY] [S90] Escape literal dots, as in `Rs\.`.

### Q7. Testing without real data

| Generator | Latest | Licence | Fit | Encryption | Evidence |
|---|---|---|---|---|---|
| **reportlab** | 5.0.1 (2026-08-20), `Requires-Python >=3.9,<4`, pure-Python wheel | BSD | Canvas `drawString`, `drawRightString` and `drawCentredString` at exact (x, y) points, origin at bottom-left; `showPage()` for page breaks. Exact geometry exercises the column-band logic | `encrypt=` argument. Strength 40 or 128 is RC4; 256 is AES-256 **revision 5** and only works "if package pyaes is … importable" | [PRIMARY] [S1], [S93], [S94] |
| fpdf2 | 2.8.8 (2026-08-09), `Requires-Python >=3.10` | LGPL-3.0-only | `pdf.table()` with `col_widths`, per-column `text_align` (e.g. `"RIGHT"`), `borders_layout`, headings repeated on each page by default, wrapped cells | `set_encryption()`: RC4 (the default), AES-128 or AES-256; AES "Requires the `cryptography` package" | [PRIMARY] [S1], [S95], [S96] |

- **Pick: reportlab canvas for layout, plus pypdf for encryption.**
  - Encrypt with `writer.encrypt(pw, algorithm="AES-256")`, and also produce RC4 and AES-128 variants. [PRIMARY] [S37]
  - `cryptography` is already present through pdfminer.six. Declare `pypdf[crypto]` anyway. [PRIMARY] [S1]
  - pikepdf's `Encryption()` (default `R=6`, `aes=True`) works too. [PRIMARY] [S40]
- **Fixture design (recommendation):**
  1. Build a synthetic statement model: fake account title, a clearly fake IBAN such as `PK00TEST…`, a period, an opening balance, and transactions with computed balances.
  2. Render it with one layout per bank profile: repeated table headers, footers with "Page x of y", right-aligned Credit/Debit columns, wrapped descriptions, a page break in the middle of a wrapped description, and optionally a diagonal watermark and characters drawn twice.
  3. Parse it and assert that the result equals the model. This is a round-trip test.
  4. Use fixed random seeds.
  5. Generate PDFs at test time, in memory or under `tmp_path`, rather than committing binary files.
- **pytest 9.1.1:** `tmp_path` gives each test a unique `pathlib.Path`. `tmp_path_factory` is session-scoped. By default "the last 3 temporary directories are kept" under `{temproot}/pytest-of-{user}/`. [PRIMARY] [S1], [S97] That is fine for synthetic files. **Never copy real statements into `tmp_path`.**
- **Hypothesis 6.168.1** (MPL-2.0) is optional, for property tests of the amount and date parsers and of the round trip. [PRIMARY] [S1]
- **Limits and mitigation:**
  - reportlab's standard fonts produce clean text, so synthetic PDFs won't reproduce `(cid:x)` glyphs [S12], characters drawn twice, or odd glyph order.
  - Keep a private regression suite outside the repo, or in a git-ignored folder, enabled by an environment variable and a pytest marker.
  - Optionally build a "layout replica": extract word boxes from a real statement locally, then re-render the same geometry with scrambled text. That gives realistic structure with no personal data. Review each replica before committing it. [UNVERIFIED — design advice]
- **Guardrails (recommendation):**
  - `.gitignore` ignores `*.pdf` everywhere except the synthetic-fixture folder.
  - A pre-commit check blocks IBAN-like strings (`PK\d{2}[A-Z]{4}\d{16}`) and CNIC-like strings (`\d{5}-\d{7}-\d`).

### Q8. Environment

- **Python support windows:** [PRIMARY] [S98]
  - 3.9 reached end of life on 2025-10-31.
  - 3.10 has security support until 2026-10.
  - 3.11 has security support until 2027-10.
  - 3.12 has security support until 2028-10.
  - 3.13 has bugfix support, ending 2029-10.
  - 3.14 has bugfix support, ending 2030-10.
  - 3.15 is scheduled for release on 2026-10-01.
- **Stack minimums:**
  - pandas 3.0 needs ≥3.11, pikepdf ≥3.11, and numpy 2.5 ≥3.12.
  - Streamlit, pdfminer.six, PyMuPDF, fpdf2 and pytest need ≥3.10. [PRIMARY] [S1]
  - **The system Python 3.9.6 is ruled out.**
- **Wheels on macOS arm64** (checked by wheel tags on PyPI, not by installing): [PRIMARY] [S1]
  - Every compiled package checked has a cp314 and a cp312 wheel, or an abi3 or pure wheel. That covers the chosen stack and its transitive dependencies: pypdfium2, cryptography, charset-normalizer, pillow, numpy, pandas, pyarrow, pydantic-core 2.46.5, protobuf, httptools, websockets, markupsafe, rpds-py, and optionally pikepdf with lxml. It also covers the alternatives: pymupdf, pyyaml, ruamel.yaml.clib, uvloop, opencv-python-headless, playa-pdf.
  - The only gap is watchdog 6.0.0, which has no cp314 wheel. Streamlit only requires it when `platform_system != "Darwin"`.
- **Pick: Python 3.14** (Homebrew 3.14.6 is installed), declared as `requires-python = ">=3.12"` so the installed 3.12 also works. Both Homebrew Pythons carry an `EXTERNALLY-MANAGED` marker, so packages must go into a venv. [PRIMARY] [S2]
- **uv or venv + pip:**
  - **uv 0.12.19** (2026-09-25): [PRIMARY] [S1], [S99], [S100], [S101], [S102], [S106]
    - Install with `brew install uv`.
    - `uv.lock` is "a *universal* or *cross-platform* lockfile". It "should be checked into version control" and "should not be edited manually".
    - Astral's example lockfile records a `sha256` hash for every sdist and wheel.
    - The environment lives in `.venv` next to `pyproject.toml`. `uv python pin` writes `.python-version`.
    - uv "uses the `[dependency-groups]` table" (PEP 735).
    - The default Python preference, `managed`, still prefers an installed system Python over downloading one. Set `python-downloads = "manual"` (or pass `--no-python-downloads`) to make sure uv always uses the Homebrew 3.14.
  - **venv + pip 26.2.1:** [PRIMARY] [S1], [S103], [S104], [S105]
    - No new tool.
    - `--group` installs PEP 735 dependency groups (since pip 25.1, 2025-04-26).
    - `pip lock` is "EXPERIMENTAL", writes `pylock.toml`, and "is only guaranteed to be valid for the current python version and platform".
    - Hash checking is available with `--require-hashes`.
  - **Pick: uv.** The tool runs once a year on sensitive data, so an exact, hash-pinned environment matters: it guards against dependency drift, and it can reproduce last year's numbers if FBR asks. The project stays plain `pyproject.toml`, so `python3.14 -m venv .venv && pip install -e . --group dev` remains a fallback.
- **Illustrative `pyproject.toml` shape** (not committed; the lower bounds are this report's versions):

```toml
[project]
name = "fbr-tax-return"
requires-python = ">=3.12"
dependencies = [
  "pdfplumber>=0.11.10",
  "pandas>=3.0.6",
  "streamlit>=1.64",
  "xlsxwriter>=3.2.9",
  "pydantic>=2.13.5",
]

[project.optional-dependencies]
decrypt-fallback = ["pikepdf>=10.14"]

[dependency-groups]
dev = ["pytest>=9.1", "reportlab>=5.0", "pypdf[crypto]>=6.19", "hypothesis>=6.168"]
```

## Implications for the tool

1. **Parsing pipeline.**
   - Steps: open in memory with a password → per page, find the header, crop, extract words → rebuild rows using the profile's column bands → typed rows in integer paisa → validations (running balance, opening + credits − debits = closing, printed totals) → classification → review.
   - Every row carries its provenance: file hash, page, y-position, raw line text, `sign_source` (`column`, `suffix`, `signed` or `balance`), validation status, and the rule that classified it. All of this goes to the "raw transactions" sheet as the audit trail.
2. **Validation is part of the output.** A "Checks" sheet and UI panel list every reconciliation (for example, statement totals versus parsed totals, or chain breaks) with pass/fail. This implements the brief's section 6 sanity check, and makes the Meezan sign question auditable.
3. **The profile schema follows from the parser.** Header patterns per column role, column alignment, optional fallback x-boundaries, `sign_mode` (`columns` | `suffix` | `signed`), amount and date patterns, date formats, skip patterns for header/footer/total rows, a continuation rule (`below` | `nearest`), balance semantics, printed-total patterns, sample lines for self-tests, and `valid_from`.
4. **Privacy posture.**
   - Streamlit locked down as in Q3: no usage stats, loopback only, no external-IP lookup, allowed hosts set.
   - Parsed data in `st.session_state`, not `st.cache_data`.
   - Excel built in memory with XlsxWriter `in_memory=True`.
   - Passwords never on a command line.
   - Known remaining disk exposures:
     - Uploads over 1 MB spool to an unnamed temp file; these are the encrypted bytes when the statement is password-protected.
     - OS swap is not researched.
     - Anything the owner saves deliberately, such as the exported workbook.
5. **Drop "unlock before upload"** from the workflow. The app asks for the password and decrypts in memory.
6. **Regexes run through Python `re` only.** Don't route them through pandas `.str` methods, which may use RE2 semantics.
7. **Excel cells must be data only.** Turn formula and URL conversion off, write amounts as numbers with format `#,##0.00`, freeze the header row, add autofilters, and treat any description beginning with `=` as text.
8. **Tests:** a synthetic statement generator per profile is part of the codebase from day one. Real statements only ever feed a private, git-ignored regression suite.
9. **Environment:** Python 3.14 and uv with a committed `uv.lock`. Add a README note on disabling uv's Python downloads. Include a launcher that passes the privacy flags.

## Could not verify / open questions

1. **Real statement internals:**
   - Is there a text layer, or are any statements scanned?
   - Do the fonts map to Unicode, or does `(cid:x)` appear?
   - Are rows or cells ruled?
   - Where do wrapped descriptions sit relative to the date/amount line?
   - What date and amount formats are used, and what are the exact Dr/Cr tokens?
   - Is a balance printed on every row?
   - Does Meezan's "Available Balance" equal the ledger running balance?
   - Which encryption algorithm is used?

   The owner should check each of these locally, with `pdfinfo` and a debug page listing pdfplumber words with their coordinates.
2. **pdfplumber's speed** on real statement volumes has not been measured.
3. **Streamlit behaviour:** whether `st.data_editor` resets edits when its `data` argument changes. The widget-identity docs don't say specifically for `data`.
4. **Streamlit network calls:** the list in Q3 comes from static analysis of the 1.64.0 wheel and the `develop` branch. To confirm empirically, run the app once with an outbound firewall monitor, or check `lsof -i` while it runs. Some doc pages could not be fetched: the Artifex AGPL sub-page returned HTTP 500, and poppler's GitLab blocked automated access. Local or alternate primary sources were used instead.
5. **Starlette spooling:** that uploads over 1 MB spool to disk is a code-level finding (Streamlit 1.64.0 with Starlette `main`), not an observed one. Typical statement file sizes are unknown.
6. **pandas behaviour:** how completely pandas 3.0.6 handles `Decimal` object columns and `ArrowDtype(decimal128)` was not tested, because pandas is not installed on this machine and nothing was installed.
7. **pypdf's `"AES-256"` option** is assumed to be revision 6 (versus `"AES-256-R5"`). Not confirmed in its docs.
8. **Licences:** the AGPL and GPL readings are interpretations, not legal advice. They only matter if the tool is ever distributed or hosted for other people.
9. **uv network use:** whether uv makes any network calls beyond package and Python downloads (for example telemetry) was not researched.
10. **macOS disk writes:** whether swap or hibernation could write in-memory statement data to disk, and whether that storage is encrypted, was not researched.

## Sources

Retrieved 2026-09-27. Local checks were read-only commands on this Mac.

- **S1** — PyPI JSON API, per package (`info.version`, `requires_python`, `requires_dist`, licence, classifiers, `urls` for release dates and wheel tags): https://pypi.org/pypi/{package}/json. Packages queried: pdfplumber, pdfminer.six, pymupdf, pypdfium2, camelot-py, tabula-py, pypdf, pikepdf, cryptography, streamlit, pandas, numpy, pyarrow, openpyxl, xlsxwriter, pyyaml, ruamel.yaml, tomlkit, tomli-w, pydantic, pydantic-core (plus https://pypi.org/pypi/pydantic-core/2.46.5/json), reportlab, fpdf2, pytest, hypothesis, uv, pip, pillow, ruamel.yaml.clib, charset-normalizer, protobuf, watchdog, tornado, httptools, websockets, markupsafe, rpds-py, lxml, uvloop, python-multipart, narwhals, jsonschema, altair, pydeck, gitpython, starlette, uvicorn, anyio, itsdangerous, et-xmlfile, playa-pdf, opencv-python-headless, tabulate.
- **S2** — Local read-only checks on this Mac (no URL). Commands: `python3 --version`; `python3.12`/`python3.14 --version`; `ls …/EXTERNALLY-MANAGED`; `pip --version`; `which uv qpdf gs`; `/usr/libexec/java_home -V`; `pdftotext -v`/`-h`; `pdfinfo`/`pdftotext -tsv`/`-bbox-layout` on `/System/Library/Frameworks/SecurityInterface.framework/Versions/A/Resources/key.pdf`.
- **S3** — GitHub REST API repository metadata (`archived`, `pushed_at`, licence): https://api.github.com/repos/{owner}/{repo} for jsvine/pdfplumber, pdfminer/pdfminer.six, pymupdf/PyMuPDF, camelot-dev/camelot, chezou/tabula-py, py-pdf/pypdf, pikepdf/pikepdf, streamlit/streamlit, jmcnamara/XlsxWriter, py-pdf/fpdf2, pypdfium2-team/pypdfium2, yaml/pyyaml, pydantic/pydantic, astral-sh/uv, tabulapdf/tabula-java, dhdaines/playa.
- **S4** — tabula-java latest release: https://api.github.com/repos/tabulapdf/tabula-java/releases/latest
- **S5** — pdfplumber README: https://github.com/jsvine/pdfplumber/blob/stable/README.md
- **S6** — pdfplumber `pdf.py`: https://github.com/jsvine/pdfplumber/blob/stable/pdfplumber/pdf.py
- **S7** — pdfplumber `utils/text.py`: https://github.com/jsvine/pdfplumber/blob/stable/pdfplumber/utils/text.py
- **S8** — pdfplumber `repair.py`: https://github.com/jsvine/pdfplumber/blob/stable/pdfplumber/repair.py
- **S9** — pdfplumber `utils/exceptions.py`: https://github.com/jsvine/pdfplumber/blob/stable/pdfplumber/utils/exceptions.py
- **S10** — pdfminer.six `pdfdocument.py`: https://github.com/pdfminer/pdfminer.six/blob/master/pdfminer/pdfdocument.py
- **S11** — pdfminer.six `pdfpage.py`: https://github.com/pdfminer/pdfminer.six/blob/master/pdfminer/pdfpage.py
- **S12** — pdfminer.six FAQ: https://pdfminersix.readthedocs.io/en/latest/faq.html
- **S13** — PyMuPDF features, licence and performance: https://pymupdf.readthedocs.io/en/latest/about.html
- **S14** — PyMuPDF `Page` (`find_tables`): https://pymupdf.readthedocs.io/en/latest/page.html
- **S15** — PyMuPDF `TextPage.extractWORDS`: https://pymupdf.readthedocs.io/en/latest/textpage.html
- **S16** — PyMuPDF `Document` (stream, authenticate): https://pymupdf.readthedocs.io/en/latest/document.html
- **S17** — PyMuPDF constants (encryption methods): https://pymupdf.readthedocs.io/en/latest/vars.html
- **S18** — PyMuPDF `src/table.py` (port from pdfplumber): https://github.com/pymupdf/PyMuPDF/blob/main/src/table.py
- **S19** — MuPDF `pdf-crypt.c`: https://github.com/ArtifexSoftware/mupdf/blob/master/source/pdf/pdf-crypt.c
- **S20** — Artifex licensing: https://artifex.com/licensing
- **S21** — PyMuPDF FAQ: https://pymupdf.readthedocs.io/en/latest/faq/index.html
- **S22** — GNU AGPLv3 text: https://www.gnu.org/licenses/agpl-3.0.html
- **S23** — GNU GPL FAQ: https://www.gnu.org/licenses/gpl-faq.html
- **S24** — `pdftotext` man page and `-h` output (poppler 26.04.0, local Homebrew install); upstream https://poppler.freedesktop.org/
- **S25** — Poppler homepage (latest release 26.09.0, 2026-09-03): https://poppler.freedesktop.org/
- **S26** — Poppler `README.md`, `COPYING` and `include/poppler/Stream.h` in `/opt/homebrew/Cellar/poppler/26.04.0/`, plus `brew info poppler` (licence field). Upstream: https://gitlab.freedesktop.org/poppler/poppler
- **S27** — camelot releases: https://github.com/camelot-dev/camelot/releases
- **S28** — camelot API: https://camelot-py.readthedocs.io/en/latest/api.html
- **S29** — camelot dependencies: https://camelot-py.readthedocs.io/en/latest/user/install-deps.html
- **S30** — tabula-py README: https://github.com/chezou/tabula-py
- **S31** — tabula-py API: https://tabula-py.readthedocs.io/en/latest/tabula.html
- **S32** — pypdfium2 API: https://pypdfium2.readthedocs.io/en/stable/python_api.html
- **S33** — py-pdf benchmarks: https://github.com/py-pdf/benchmarks
- **S34** — pdf_statement_reader: https://github.com/marlanperumal/pdf_statement_reader
- **S35** — pdf-bank-statement-parser: https://github.com/J-sephB-lt-n/pdf-bank-statement-parser
- **S36** — monopoly: https://github.com/benjamin-awd/monopoly
- **S37** — pypdf encryption and decryption: https://pypdf.readthedocs.io/en/stable/user/encryption-decryption.html
- **S38** — pypdf `PdfReader`: https://pypdf.readthedocs.io/en/stable/modules/PdfReader.html
- **S39** — pikepdf security: https://pikepdf.readthedocs.io/en/latest/topics/security.html
- **S40** — pikepdf API: https://pikepdf.readthedocs.io/en/latest/api/main.html
- **S41** — pikepdf installation: https://pikepdf.readthedocs.io/en/latest/installation.html
- **S42** — Streamlit `config.toml` reference: https://docs.streamlit.io/develop/api-reference/configuration/config.toml
- **S43** — Streamlit release notes (1.64.0): https://docs.streamlit.io/develop/quick-reference/release-notes
- **S44** — Streamlit release notes 2025: https://docs.streamlit.io/develop/quick-reference/release-notes/2025
- **S45** — Streamlit release notes 2026: https://docs.streamlit.io/develop/quick-reference/release-notes/2026
- **S46** — Streamlit 1.64.0 wheel, inspected in memory: https://files.pythonhosted.org/packages/d7/8e/e635448a7fd6d92211d4ff2150356b8dffd3fcdc05c00511c61110078871/streamlit-1.64.0-py3-none-any.whl. Files read: `streamlit/config.py`, `net_util.py`, `web/bootstrap.py`, `runtime/credentials.py`, `runtime/metrics_util.py`, `runtime/memory_uploaded_file_manager.py`, `web/server/starlette/starlette_routes.py`, `runtime/caching/cache_data_api.py`, `config_util.py`, `web/cli.py`, and the `static/` JS bundles.
- **S47** — Streamlit `MetricsManager.ts` (`develop` branch): https://github.com/streamlit/streamlit/blob/develop/frontend/app/src/MetricsManager.ts
- **S48** — Streamlit `credentials.py` (`develop` branch): https://github.com/streamlit/streamlit/blob/develop/lib/streamlit/runtime/credentials.py
- **S49** — `st.file_uploader`: https://docs.streamlit.io/develop/api-reference/widgets/st.file_uploader
- **S50** — Streamlit knowledge base, where uploaded files are stored: https://docs.streamlit.io/knowledge-base/using-streamlit/where-file-uploader-store-when-deleted
- **S51** — Starlette `formparsers.py`: https://github.com/Kludex/starlette/blob/main/starlette/formparsers.py
- **S52** — Python `tempfile`: https://docs.python.org/3/library/tempfile.html
- **S53** — `st.data_editor`: https://docs.streamlit.io/develop/api-reference/data/st.data_editor
- **S54** — Streamlit dataframes guide: https://docs.streamlit.io/develop/concepts/design/dataframes
- **S55** — Streamlit widget behaviour: https://docs.streamlit.io/develop/concepts/architecture/widget-behavior
- **S56** — `st.column_config.NumberColumn`: https://docs.streamlit.io/develop/api-reference/data/st.column_config/st.column_config.numbercolumn
- **S57** — `st.column_config.SelectboxColumn`: https://docs.streamlit.io/develop/api-reference/data/st.column_config/st.column_config.selectboxcolumn
- **S58** — Streamlit PR #7475 (Decimal support): https://github.com/streamlit/streamlit/pull/7475
- **S59** — Streamlit Session State: https://docs.streamlit.io/develop/concepts/architecture/session-state
- **S60** — `st.download_button`: https://docs.streamlit.io/develop/api-reference/widgets/st.download_button
- **S61** — Streamlit caching: https://docs.streamlit.io/develop/concepts/architecture/caching
- **S62** — `st.text_input`: https://docs.streamlit.io/develop/api-reference/widgets/st.text_input
- **S63** — pandas installation: https://pandas.pydata.org/docs/getting_started/install.html
- **S64** — pandas 3.0.0 release notes: https://pandas.pydata.org/docs/whatsnew/v3.0.0.html
- **S65** — pandas string migration guide: https://pandas.pydata.org/docs/user_guide/migration-3-strings.html
- **S66** — pandas `string_arrow.py` at v3.0.6: https://github.com/pandas-dev/pandas/blob/v3.0.6/pandas/core/arrays/string_arrow.py
- **S67** — pandas `_arrow_string_mixins.py` at v3.0.6: https://github.com/pandas-dev/pandas/blob/v3.0.6/pandas/core/arrays/_arrow_string_mixins.py
- **S68** — RE2 syntax: https://github.com/google/re2/wiki/Syntax
- **S69** — pandas nullable integers: https://pandas.pydata.org/docs/user_guide/integer_na.html
- **S70** — pandas PyArrow functionality: https://pandas.pydata.org/docs/user_guide/pyarrow.html
- **S71** — pandas groupby guide (Decimal example): https://pandas.pydata.org/docs/user_guide/groupby.html
- **S72** — pandas issue #20539: https://github.com/pandas-dev/pandas/issues/20539
- **S73** — pandas issue #25168: https://github.com/pandas-dev/pandas/issues/25168
- **S74** — Python `decimal`: https://docs.python.org/3/library/decimal.html
- **S75** — `pandas.ExcelWriter`: https://pandas.pydata.org/docs/reference/api/pandas.ExcelWriter.html
- **S76** — `DataFrame.to_excel`: https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_excel.html
- **S77** — XlsxWriter `Workbook` options: https://xlsxwriter.readthedocs.io/workbook.html
- **S78** — XlsxWriter "Working with Pandas": https://xlsxwriter.readthedocs.io/working_with_pandas.html
- **S79** — XlsxWriter `Worksheet`: https://xlsxwriter.readthedocs.io/worksheet.html
- **S80** — XlsxWriter 3.2.9 source (the local install equals the PyPI latest): `workbook.py`, `packager.py`, `worksheet.py`, `xmlwriter.py`. Upstream: https://github.com/jmcnamara/XlsxWriter/tree/main/xlsxwriter
- **S81** — openpyxl 3.1.5 source (the local install equals the PyPI latest): `worksheet/_writer.py`, `writer/excel.py`, `cell/cell.py`, `compat/numbers.py`. Upstream: https://foss.heptapod.net/openpyxl/openpyxl
- **S82** — Excel specifications and limits: https://support.microsoft.com/en-us/office/excel-specifications-and-limits-1672b34d-7043-467e-8e27-269d656771c3
- **S83** — Python `tomllib`: https://docs.python.org/3/library/tomllib.html
- **S84** — TOML v1.0.0 specification: https://toml.io/en/v1.0.0
- **S85** — PyYAML documentation: https://pyyaml.org/wiki/PyYAMLDocumentation
- **S86** — YAML 1.1 bool type: https://yaml.org/type/bool.html
- **S87** — ruamel.yaml documentation: https://yaml.dev/doc/ruamel.yaml/
- **S88** — pydantic `ConfigDict`: https://pydantic.dev/docs/validation/latest/api/pydantic/config/
- **S89** — pydantic standard-library types: https://pydantic.dev/docs/validation/latest/api/pydantic/standard_library_types/
- **S90** — Python `re`: https://docs.python.org/3/library/re.html
- **S91** — Python `datetime` (strftime/strptime): https://docs.python.org/3/library/datetime.html
- **S92** — Python `locale`: https://docs.python.org/3/library/locale.html
- **S93** — reportlab user guide, chapter 2: https://docs.reportlab.com/reportlab/userguide/ch2_graphics/
- **S94** — reportlab 5.0.1 wheel, `reportlab/lib/pdfencrypt.py`, inspected in memory: https://files.pythonhosted.org/packages/db/cb/dacbc268cb68d0428ea2cbd85266195a9ab3e677449589ddae59bd7542ac/reportlab-5.0.1-py3-none-any.whl
- **S95** — fpdf2 encryption: https://py-pdf.github.io/fpdf2/Encryption.html
- **S96** — fpdf2 tables: https://py-pdf.github.io/fpdf2/Tables.html
- **S97** — pytest `tmp_path`: https://docs.pytest.org/en/stable/how-to/tmp_path.html
- **S98** — Python version status: https://devguide.python.org/versions/
- **S99** — uv installation: https://docs.astral.sh/uv/getting-started/installation/
- **S100** — uv project layout: https://docs.astral.sh/uv/concepts/projects/layout/
- **S101** — Astral's example `uv.lock`: https://github.com/astral-sh/uv-fastapi-example/blob/main/uv.lock
- **S102** — uv Python versions: https://docs.astral.sh/uv/concepts/python-versions/
- **S103** — pip changelog: https://pip.pypa.io/en/stable/news/
- **S104** — `pip lock`: https://pip.pypa.io/en/stable/cli/pip_lock/
- **S105** — `pip install` options: https://pip.pypa.io/en/stable/cli/pip_install/
- **S106** — uv dependencies and dependency groups: https://docs.astral.sh/uv/concepts/projects/dependencies/
- **S107** — pandas `io/excel/_xlsxwriter.py` at v3.0.6 (the append-mode `ValueError`): https://github.com/pandas-dev/pandas/blob/v3.0.6/pandas/io/excel/_xlsxwriter.py

[S1]: https://docs.pypi.org/api/json/
[S3]: https://docs.github.com/en/rest/repos/repos#get-a-repository
[S4]: https://api.github.com/repos/tabulapdf/tabula-java/releases/latest
[S5]: https://github.com/jsvine/pdfplumber/blob/stable/README.md
[S6]: https://github.com/jsvine/pdfplumber/blob/stable/pdfplumber/pdf.py
[S7]: https://github.com/jsvine/pdfplumber/blob/stable/pdfplumber/utils/text.py
[S8]: https://github.com/jsvine/pdfplumber/blob/stable/pdfplumber/repair.py
[S9]: https://github.com/jsvine/pdfplumber/blob/stable/pdfplumber/utils/exceptions.py
[S10]: https://github.com/pdfminer/pdfminer.six/blob/master/pdfminer/pdfdocument.py
[S11]: https://github.com/pdfminer/pdfminer.six/blob/master/pdfminer/pdfpage.py
[S12]: https://pdfminersix.readthedocs.io/en/latest/faq.html
[S13]: https://pymupdf.readthedocs.io/en/latest/about.html
[S14]: https://pymupdf.readthedocs.io/en/latest/page.html
[S15]: https://pymupdf.readthedocs.io/en/latest/textpage.html
[S16]: https://pymupdf.readthedocs.io/en/latest/document.html
[S17]: https://pymupdf.readthedocs.io/en/latest/vars.html
[S18]: https://github.com/pymupdf/PyMuPDF/blob/main/src/table.py
[S19]: https://github.com/ArtifexSoftware/mupdf/blob/master/source/pdf/pdf-crypt.c
[S20]: https://artifex.com/licensing
[S21]: https://pymupdf.readthedocs.io/en/latest/faq/index.html
[S22]: https://www.gnu.org/licenses/agpl-3.0.html
[S23]: https://www.gnu.org/licenses/gpl-faq.html
[S24]: https://poppler.freedesktop.org/
[S25]: https://poppler.freedesktop.org/
[S26]: https://gitlab.freedesktop.org/poppler/poppler
[S27]: https://github.com/camelot-dev/camelot/releases
[S28]: https://camelot-py.readthedocs.io/en/latest/api.html
[S29]: https://camelot-py.readthedocs.io/en/latest/user/install-deps.html
[S30]: https://github.com/chezou/tabula-py
[S31]: https://tabula-py.readthedocs.io/en/latest/tabula.html
[S32]: https://pypdfium2.readthedocs.io/en/stable/python_api.html
[S33]: https://github.com/py-pdf/benchmarks
[S34]: https://github.com/marlanperumal/pdf_statement_reader
[S35]: https://github.com/J-sephB-lt-n/pdf-bank-statement-parser
[S36]: https://github.com/benjamin-awd/monopoly
[S37]: https://pypdf.readthedocs.io/en/stable/user/encryption-decryption.html
[S38]: https://pypdf.readthedocs.io/en/stable/modules/PdfReader.html
[S39]: https://pikepdf.readthedocs.io/en/latest/topics/security.html
[S40]: https://pikepdf.readthedocs.io/en/latest/api/main.html
[S41]: https://pikepdf.readthedocs.io/en/latest/installation.html
[S42]: https://docs.streamlit.io/develop/api-reference/configuration/config.toml
[S43]: https://docs.streamlit.io/develop/quick-reference/release-notes
[S44]: https://docs.streamlit.io/develop/quick-reference/release-notes/2025
[S45]: https://docs.streamlit.io/develop/quick-reference/release-notes/2026
[S46]: https://files.pythonhosted.org/packages/d7/8e/e635448a7fd6d92211d4ff2150356b8dffd3fcdc05c00511c61110078871/streamlit-1.64.0-py3-none-any.whl
[S47]: https://github.com/streamlit/streamlit/blob/develop/frontend/app/src/MetricsManager.ts
[S48]: https://github.com/streamlit/streamlit/blob/develop/lib/streamlit/runtime/credentials.py
[S49]: https://docs.streamlit.io/develop/api-reference/widgets/st.file_uploader
[S50]: https://docs.streamlit.io/knowledge-base/using-streamlit/where-file-uploader-store-when-deleted
[S51]: https://github.com/Kludex/starlette/blob/main/starlette/formparsers.py
[S52]: https://docs.python.org/3/library/tempfile.html
[S53]: https://docs.streamlit.io/develop/api-reference/data/st.data_editor
[S54]: https://docs.streamlit.io/develop/concepts/design/dataframes
[S55]: https://docs.streamlit.io/develop/concepts/architecture/widget-behavior
[S56]: https://docs.streamlit.io/develop/api-reference/data/st.column_config/st.column_config.numbercolumn
[S57]: https://docs.streamlit.io/develop/api-reference/data/st.column_config/st.column_config.selectboxcolumn
[S58]: https://github.com/streamlit/streamlit/pull/7475
[S59]: https://docs.streamlit.io/develop/concepts/architecture/session-state
[S60]: https://docs.streamlit.io/develop/api-reference/widgets/st.download_button
[S61]: https://docs.streamlit.io/develop/concepts/architecture/caching
[S62]: https://docs.streamlit.io/develop/api-reference/widgets/st.text_input
[S63]: https://pandas.pydata.org/docs/getting_started/install.html
[S64]: https://pandas.pydata.org/docs/whatsnew/v3.0.0.html
[S65]: https://pandas.pydata.org/docs/user_guide/migration-3-strings.html
[S66]: https://github.com/pandas-dev/pandas/blob/v3.0.6/pandas/core/arrays/string_arrow.py
[S67]: https://github.com/pandas-dev/pandas/blob/v3.0.6/pandas/core/arrays/_arrow_string_mixins.py
[S68]: https://github.com/google/re2/wiki/Syntax
[S69]: https://pandas.pydata.org/docs/user_guide/integer_na.html
[S70]: https://pandas.pydata.org/docs/user_guide/pyarrow.html
[S71]: https://pandas.pydata.org/docs/user_guide/groupby.html
[S72]: https://github.com/pandas-dev/pandas/issues/20539
[S73]: https://github.com/pandas-dev/pandas/issues/25168
[S74]: https://docs.python.org/3/library/decimal.html
[S75]: https://pandas.pydata.org/docs/reference/api/pandas.ExcelWriter.html
[S76]: https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_excel.html
[S77]: https://xlsxwriter.readthedocs.io/workbook.html
[S78]: https://xlsxwriter.readthedocs.io/working_with_pandas.html
[S79]: https://xlsxwriter.readthedocs.io/worksheet.html
[S80]: https://github.com/jmcnamara/XlsxWriter/tree/main/xlsxwriter
[S81]: https://foss.heptapod.net/openpyxl/openpyxl
[S82]: https://support.microsoft.com/en-us/office/excel-specifications-and-limits-1672b34d-7043-467e-8e27-269d656771c3
[S83]: https://docs.python.org/3/library/tomllib.html
[S84]: https://toml.io/en/v1.0.0
[S85]: https://pyyaml.org/wiki/PyYAMLDocumentation
[S86]: https://yaml.org/type/bool.html
[S87]: https://yaml.dev/doc/ruamel.yaml/
[S88]: https://pydantic.dev/docs/validation/latest/api/pydantic/config/
[S89]: https://pydantic.dev/docs/validation/latest/api/pydantic/standard_library_types/
[S90]: https://docs.python.org/3/library/re.html
[S91]: https://docs.python.org/3/library/datetime.html
[S92]: https://docs.python.org/3/library/locale.html
[S93]: https://docs.reportlab.com/reportlab/userguide/ch2_graphics/
[S94]: https://files.pythonhosted.org/packages/db/cb/dacbc268cb68d0428ea2cbd85266195a9ab3e677449589ddae59bd7542ac/reportlab-5.0.1-py3-none-any.whl
[S95]: https://py-pdf.github.io/fpdf2/Encryption.html
[S96]: https://py-pdf.github.io/fpdf2/Tables.html
[S97]: https://docs.pytest.org/en/stable/how-to/tmp_path.html
[S98]: https://devguide.python.org/versions/
[S99]: https://docs.astral.sh/uv/getting-started/installation/
[S100]: https://docs.astral.sh/uv/concepts/projects/layout/
[S101]: https://github.com/astral-sh/uv-fastapi-example/blob/main/uv.lock
[S102]: https://docs.astral.sh/uv/concepts/python-versions/
[S103]: https://pip.pypa.io/en/stable/news/
[S104]: https://pip.pypa.io/en/stable/cli/pip_lock/
[S105]: https://pip.pypa.io/en/stable/cli/pip_install/
[S106]: https://docs.astral.sh/uv/concepts/projects/dependencies/
[S107]: https://github.com/pandas-dev/pandas/blob/v3.0.6/pandas/io/excel/_xlsxwriter.py
