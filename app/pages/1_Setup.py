# app/pages/1_Setup.py
"""Setup: is everything this tool needs in place?"""

from __future__ import annotations

import streamlit as st

from app.state import VERIFICATION_HELP, VERIFICATION_MARK, mask_identifier
from fbr import paths
from fbr.config.loader import ConfigError, load_profiles, load_registry, load_tax_year
from fbr.engines.tabular import parse_row
from fbr.ingest import usable_profiles

st.header("Setup")

tax_year = st.selectbox("Tax year", ["TY2026"], index=0)
st.session_state["tax_year"] = tax_year

st.subheader("Private folder")
st.caption(
    "Owner data lives outside this repository. Set FBR_PRIVATE_DIR to move it."
)
for path, exists in paths.describe_private_layout():
    st.write(("✅ " if exists else "⬜ ") + f"`{path}`")
if st.button("Create missing folders"):
    try:
        paths.ensure_private_layout()
        st.success("Folder layout created.")
    except paths.PrivatePathError as exc:
        st.error(str(exc))

st.subheader("Accounts")
try:
    registry = load_registry()
    st.session_state["registry"] = registry
    st.write(f"Owner: **{registry.owner.name}**")
    st.dataframe(
        [
            {
                "id": a.id,
                "institution": a.institution,
                "kind": a.kind,
                "identifier": mask_identifier(a.iban or a.account_number or a.wallet_number),
                "statement expected": "yes" if a.statement_expected else "no",
            }
            for a in registry.accounts
        ],
        hide_index=True,
    )
except ConfigError as exc:
    st.error(str(exc))

st.subheader("Layout profiles")
try:
    profiles = load_profiles()
    st.session_state["profiles"] = profiles
    rows = []
    for container in ("csv", "xlsx", "pdf"):
        _, report = usable_profiles(profiles, container)
        for status in report:
            rows.append({
                "profile": status.profile_id,
                "self-test": "✅ pass" if status.ok else "❌ fail",
                "detail": status.message,
            })
    if rows:
        st.dataframe(rows, hide_index=True)
    st.caption("A profile that fails its own self-test is excluded from layout detection.")
except ConfigError as exc:
    st.error(str(exc))

st.subheader("IRIS codes")
try:
    ty = load_tax_year(tax_year)
    st.session_state["tax_year_config"] = ty
    st.dataframe(
        [
            {
                "": VERIFICATION_MARK[e.verification],
                "code": e.code or "(blank)",
                "label": e.label,
                "tab": e.tab,
                "state": VERIFICATION_HELP[e.verification],
            }
            for e in ty.codes.values()
        ],
        hide_index=True,
    )
    unknown = [e.label for e in ty.codes.values() if e.verification == "unknown"]
    if unknown:
        st.warning(
            "Read these off live IRIS before filing: " + ", ".join(unknown)
        )
except ConfigError as exc:
    st.error(str(exc))
