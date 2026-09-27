# app/main.py
"""Local UI entry point. Run it with ./run, never `streamlit run` directly,
so the privacy flags are always applied."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

st.set_page_config(page_title="FBR Tax Return Aggregator", page_icon="📄", layout="wide")

st.title("FBR Tax Return Aggregator")
st.caption(
    "Local only. Nothing leaves this machine. Figures are for you to enter into "
    "IRIS by hand."
)

st.markdown(
    """
**Order of work**

1. **Setup** — check the private folder, accounts and profiles.
2. **Load** — read this year's statements and see which layout and account each one matched.
3. **Checks** — confirm every statement reconciles before believing any figure.

Classification, review, the IRIS summary and the Excel export arrive in later phases.
"""
)

st.info("Phase 0–1: CSV/XLSX statements only. PDF support arrives in phase 2.")
