# app/pages/2_Load.py
"""Load: read this year's statements and report what matched."""

from __future__ import annotations

import streamlit as st

from app.state import summarize_run
from fbr import paths
from fbr.pipeline import InputFile, load_files, read_statement_dir

st.header("Load statements")

tax_year = st.session_state.get("tax_year", "TY2026")
registry = st.session_state.get("registry")
profiles = st.session_state.get("profiles")
ty_config = st.session_state.get("tax_year_config")

if not (registry and profiles and ty_config):
    st.warning("Open **Setup** first so the registry, profiles and codes are loaded.")
    st.stop()

folder = paths.statements_dir(tax_year)
st.caption(
    f"Reading from `{folder}`. Files are read straight from disk rather than "
    "uploaded, because Streamlit writes uploads over 1 MB to a temporary file."
)

files: list[InputFile] = []
source = st.radio("Source", ["Private folder", "Upload"], horizontal=True)

if source == "Private folder":
    files = read_statement_dir(tax_year)
    st.write(f"{len(files)} file(s) found.")
else:
    uploaded = st.file_uploader(
        "Statements", type=["csv", "xlsx"], accept_multiple_files=True
    )
    files = [InputFile(f.name, f.getvalue()) for f in (uploaded or [])]

if files and st.button("Parse", type="primary"):
    run = load_files(files, registry=registry, profiles=profiles, tax_year=ty_config)
    st.session_state["run"] = run

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
        st.warning(
            f"{len(run.unassigned)} file(s) matched no account. Add the account's "
            "IBAN or number to accounts.toml, then parse again."
        )
