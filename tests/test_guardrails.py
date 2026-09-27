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
    assert cfg["server"]["maxUploadSize"] == 25
    assert cfg["client"]["toolbarMode"] == "viewer"


def test_gitignore_excludes_statement_file_types():
    text = (ROOT / ".gitignore").read_text()
    for pattern in ("*.pdf", "*.csv", "*.xlsx"):
        assert pattern in text


def _init_repo_with_active_hook(tmp_path):
    """A throwaway git repo with core.hooksPath pointed at this repo's real
    .githooks directory, so the tests below exercise the actual hook script
    end to end rather than re-implementing its regex and testing that copy."""
    hook = ROOT / ".githooks" / "pre-commit"
    assert hook.exists() and hook.stat().st_mode & 0o111, "hook must be executable"

    def run(*args):
        return subprocess.run(args, cwd=tmp_path, capture_output=True, text=True)

    init = run("git", "init")
    assert init.returncode == 0, init.stdout + init.stderr
    assert run("git", "config", "user.email", "test@example.invalid").returncode == 0
    assert run("git", "config", "user.name", "Guardrail Test").returncode == 0
    assert run("git", "config", "core.hooksPath", str(ROOT / ".githooks")).returncode == 0

    # An initial commit so `git diff --cached` has a HEAD to diff against.
    # Harmless content, so it also passes cleanly through the real hook.
    (tmp_path / "README.md").write_text("placeholder\n")
    run("git", "add", "README.md")
    initial = run("git", "commit", "-m", "initial")
    assert initial.returncode == 0, initial.stdout + initial.stderr

    return run


def test_precommit_hook_blocks_a_real_shaped_iban_end_to_end(tmp_path):
    run = _init_repo_with_active_hook(tmp_path)
    # Built from parts on purpose: a literal IBAN here would make this very
    # file uncommittable under the hook it tests.
    real_iban = "PK" + "96" + "MEZN" + "0003070112153474"
    (tmp_path / "leak.txt").write_text(real_iban + "\n")
    run("git", "add", "leak.txt")

    result = run("git", "commit", "-m", "add leak")

    assert result.returncode != 0
    assert "IBAN-shaped" in (result.stdout + result.stderr)


def test_precommit_hook_allows_the_pk00test_prefix_end_to_end(tmp_path):
    run = _init_repo_with_active_hook(tmp_path)
    test_iban = "PK00TEST0000000000000000"
    (tmp_path / "fixture.txt").write_text(test_iban + "\n")
    run("git", "add", "fixture.txt")

    result = run("git", "commit", "-m", "add fixture")

    assert result.returncode == 0, result.stdout + result.stderr


def test_precommit_hook_blocks_a_cnic_shaped_string_end_to_end(tmp_path):
    run = _init_repo_with_active_hook(tmp_path)
    # Built from parts for the same reason as the IBAN above.
    cnic = "12345" + "-" + "1234567" + "-" + "1"
    (tmp_path / "cnic.txt").write_text(cnic + "\n")
    run("git", "add", "cnic.txt")

    result = run("git", "commit", "-m", "add cnic")

    assert result.returncode != 0
    assert "CNIC-shaped" in (result.stdout + result.stderr)


def test_python_floor_is_at_least_3_12():
    meta = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert meta["project"]["requires-python"] == ">=3.12"
