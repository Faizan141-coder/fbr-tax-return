# app/pages/2_Load.py
"""Load: read this year's statements and report what matched."""

from __future__ import annotations

import streamlit as st

from app.state import summarize_run
from fbr import paths
from fbr.pipeline import InputFile, load_files_with_assignments, read_statement_dir

st.header("Load statements")

tax_year = st.session_state.get("tax_year", "TY2026")
registry = st.session_state.get("registry")
profiles = st.session_state.get("profiles")
ty_config = st.session_state.get("tax_year_config")

if not (registry and profiles and ty_config):
    st.warning("Open **Setup** first so the registry, profiles and codes are loaded.")
    st.stop()

folder = paths.statements_dir(tax_year)

files: list[InputFile] = []
source = st.radio(
    "Source", ["Private folder", "Upload"], horizontal=True,
    help=(
        "Private folder reads the bytes straight from where you put them. "
        "Upload hands them to Streamlit first, which writes any file over "
        "1 MB to a temporary file of its own outside the private folder."
    ),
)

if source == "Private folder":
    st.caption(
        f"Reading from `{folder}`. Nothing is copied: the bytes are read "
        "straight from where you put them."
    )
    files = read_statement_dir(tax_year)
    st.write(f"{len(files)} file(s) found.")
else:
    # Spec §8.1 keeps upload as the alternative to the private folder, but
    # it is not free and the page must say so: Streamlit writes any upload
    # over 1 MB to a temporary file in the OS temp directory, where a real
    # statement then sits outside ~/fbr-private until the OS clears it.
    st.caption(
        "Streamlit writes any upload over 1 MB to a temporary file in your "
        f"OS temp directory, outside `{folder}`. For real statements, prefer "
        "**Private folder**; use Upload for a one-off file you have not "
        "filed there yet."
    )
    uploaded = st.file_uploader(
        "Statements", type=["csv", "xlsx", "pdf"], accept_multiple_files=True
    )
    files = [InputFile(f.name, f.getvalue()) for f in (uploaded or [])]

pdf_names = [f.name for f in files if f.data[:4] == b"%PDF"]
passwords: dict[str, str] = {}
if pdf_names:
    st.caption(
        "PDF statements may be password-protected. A password typed here is "
        "held in memory for this run only: it is never written to disk, never "
        "logged, and never placed on a command line."
    )
    shared = st.text_input("PDF password (leave blank if none)", type="password")
    if shared:
        passwords = {name: shared for name in pdf_names}


def parse_now(file_list: list[InputFile]) -> None:
    """Run the pipeline over `file_list` and keep the result for this session.

    Every parse goes through here, including the one the account picker below
    triggers, so the owner's account choices are applied on a plain re-parse
    too and do not have to be made twice. The rule itself is
    `pipeline.load_files_with_assignments`; this page only collects the
    choices, because the pages hold no business logic.

    A password is attached here, per run, and lives only in the InputFile it is
    attached to. It is deliberately NOT kept in st.session_state.
    """
    prepared = [
        InputFile(f.name, f.data, account_id=f.account_id,
                  password=passwords.get(f.name))
        for f in file_list
    ]
    st.session_state["run"] = load_files_with_assignments(
        prepared,
        st.session_state.get("account_assignments", {}),
        registry=registry, profiles=profiles, tax_year=ty_config,
    )


if files and st.button("Parse", type="primary"):
    parse_now(files)

run = st.session_state.get("run")
if run:
    s = summarize_run(run)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Files parsed", s["files_ok"])
    c2.metric("Problems", s["files_problem"])
    c3.metric("Transactions", s["transactions"])
    c4.metric("Accounts", s["accounts"])

    st.subheader("Per file")
    st.dataframe(
        [
            {
                "file": o.name,
                "status": o.status,
                "layout": o.layout_id or "—",
                "account": o.account_id or "—",
                "rows": o.transactions_parsed,
                "detail": o.message,
            }
            for o in run.outcomes
        ],
        hide_index=True,
    )

    if run.unassigned:
        # Spec §4.2's account picker. A statement is normally linked by the
        # identifier it prints; when the owner's real statement prints one in a
        # form no profile anticipated, this is the route that does not require
        # editing accounts.toml and re-running on a guess. The per-file messages
        # in `outcomes` above name both routes, and so does this block - keep
        # the three in step.
        st.subheader("Files that matched no account")
        st.warning(
            f"{len(run.unassigned)} file(s) matched no account: "
            + ", ".join(f"`{f.name}`" for f in run.unassigned)
            + ". Each statement is normally linked by the IBAN, account number "
            "or wallet number it prints. Choose the account below, or add that "
            "identifier to the matching account in `accounts.toml` so the file "
            "matches on its own next time."
        )

        LEAVE = "— leave unassigned —"

        def describe(value: str) -> str:
            account = registry.by_id(value)
            return f"{value} — {account.institution}" if account else value

        # Default to leaving it alone. Nothing is assigned by accident, and a
        # statement booked to the wrong account produces confident, wrong
        # figures that no downstream check can catch.
        chosen: dict[str, str] = {}
        for f in run.unassigned:
            picked = st.selectbox(
                f"Account for `{f.name}`",
                [LEAVE, *(a.id for a in registry.accounts)],
                format_func=describe,
                key=f"account_for:{f.name}",
            )
            if picked != LEAVE:
                chosen[f.name] = picked

        if not files:
            st.caption(
                "Re-select the files above to apply an assignment: the bytes "
                "are read fresh on every parse and are never cached."
            )
        elif st.button("Parse again with these accounts", disabled=not chosen):
            # Session state, not st.cache_data: a choice belongs to this owner's
            # session and must never outlive it or be shared across runs.
            st.session_state["account_assignments"] = {
                **st.session_state.get("account_assignments", {}),
                **chosen,
            }
            # The WHOLE set is re-parsed, so the files that already resolved keep
            # their ledgers - see load_files_with_assignments for why merging
            # afterwards would be wrong.
            parse_now(files)
            st.rerun()
