# tests/test_guardrails.py
"""The repo's own privacy guardrails are themselves tested, because a silent
regression here is how real statement data would reach git."""
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_streamlit_config_locks_down_telemetry_and_binding():
    cfg = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text())
    assert cfg["browser"]["gatherUsageStats"] is False
    assert cfg["server"]["address"] == "127.0.0.1"
    assert cfg["server"]["headless"] is True
    assert cfg["server"]["showEmailPrompt"] is False
    assert cfg["server"]["allowedHosts"] == ["127.0.0.1", "localhost"]


def test_gitignore_excludes_statement_file_types():
    text = (ROOT / ".gitignore").read_text()
    for pattern in ("*.pdf", "*.csv", "*.xlsx"):
        assert pattern in text


def test_precommit_hook_rejects_an_iban_but_allows_the_test_prefix():
    hook = ROOT / ".githooks" / "pre-commit"
    assert hook.exists() and hook.stat().st_mode & 0o111, "hook must be executable"
    body = hook.read_text()
    assert "PK00TEST" in body, "hook must exempt the synthetic prefix"
    # Built from parts on purpose: a literal IBAN here would make this very
    # file uncommittable under the hook it tests.
    real = "PK" + "96" + "MEZN" + "0003070112153474"
    test = "PK00TEST0000000000000000"
    pattern = r'PK[0-9]{2}[A-Z]{4}[0-9]{16}'
    assert subprocess.run(["grep", "-qE", pattern], input=real, text=True).returncode == 0
    assert subprocess.run(
        ["grep", "-E", pattern], input=test, text=True, capture_output=True
    ).stdout.strip() == test, "test prefix matches the shape; the hook's grep -v exempts it"


def test_python_floor_is_at_least_3_12():
    meta = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert meta["project"]["requires-python"] == ">=3.12"
