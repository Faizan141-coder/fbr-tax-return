# app/pages/3_Checks.py
"""Checks: prove every statement reconciles before believing any figure."""

from __future__ import annotations

import streamlit as st

from app.state import STATUS_ICON
from fbr.money import format_paisa

st.header("Checks")

run = st.session_state.get("run")
registry = st.session_state.get("registry")
if not run:
    st.warning("Load statements first.")
    st.stop()

st.subheader("Accounts")
rows = []
for account_id, ledger in run.ledgers.items():
    account = registry.by_id(account_id) if registry else None
    rows.append({
        "": STATUS_ICON[ledger.status],
        "account": account.institution if account else account_id,
        "transactions": len(ledger.transactions),
        "opening 1 Jul": format_paisa(ledger.opening) if ledger.opening is not None else "unknown",
        "from": ledger.opening_source,
        "closing 30 Jun": format_paisa(ledger.closing) if ledger.closing is not None else "unknown",
        "from ": ledger.closing_source,
    })
st.dataframe(rows, hide_index=True)
st.caption(
    "A balance shown as **unknown** is never treated as zero. Enter the 1 July "
    "balance in manual inputs for accounts whose statements print no balance."
)

failed = [c for c in run.all_checks if c.status == "fail"]
warned = [c for c in run.all_checks if c.status == "warn"]

if failed:
    st.error(
        f"{len(failed)} check(s) failed. Those statements contribute nothing to "
        "any total until the cause is fixed."
    )
    st.dataframe(
        [
            {"check": c.kind, "expected": c.expected, "found": c.actual,
             "where": c.locator or c.scope, "detail": c.detail}
            for c in failed
        ],
        hide_index=True,
    )

if warned:
    st.warning(f"{len(warned)} warning(s).")
    st.dataframe(
        [
            {"check": c.kind, "expected": c.expected, "found": c.actual,
             "where": c.locator or c.scope, "detail": c.detail}
            for c in warned
        ],
        hide_index=True,
    )

with st.expander(f"All {len(run.all_checks)} checks"):
    st.dataframe(
        [
            {"status": c.status, "scope": c.scope, "check": c.kind,
             "expected": c.expected, "found": c.actual, "detail": c.detail}
            for c in run.all_checks
        ],
        hide_index=True,
    )
