# tests/test_paths.py
from pathlib import Path

import pytest

from fbr import paths


def test_defaults_to_home_fbr_private(monkeypatch):
    monkeypatch.delenv("FBR_PRIVATE_DIR", raising=False)
    assert paths.private_root() == Path.home() / "fbr-private"


def test_env_var_overrides_root(monkeypatch, tmp_path):
    monkeypatch.setenv("FBR_PRIVATE_DIR", str(tmp_path / "elsewhere"))
    assert paths.private_root() == tmp_path / "elsewhere"


def test_subpaths_hang_off_the_root(monkeypatch, tmp_path):
    monkeypatch.setenv("FBR_PRIVATE_DIR", str(tmp_path))
    assert paths.statements_dir("TY2026") == tmp_path / "statements" / "TY2026"
    assert paths.dumps_dir() == tmp_path / "dumps"
    assert paths.dump_candidates_dir() == tmp_path / "dump-candidates"
    assert paths.decisions_path("TY2026") == tmp_path / "decisions" / "TY2026.json"
    assert paths.manual_path("TY2026") == tmp_path / "manual" / "TY2026.toml"
    assert paths.registry_path() == tmp_path / "accounts.toml"
    assert paths.local_rules_path() == tmp_path / "rules.local.toml"


def test_ensure_creates_the_expected_layout(monkeypatch, tmp_path):
    monkeypatch.setenv("FBR_PRIVATE_DIR", str(tmp_path / "priv"))
    root = paths.ensure_private_layout()
    for sub in ("statements", "dumps", "dump-candidates", "decisions", "manual"):
        assert (root / sub).is_dir()


def test_refuses_a_root_inside_the_repo(monkeypatch):
    repo_child = Path(__file__).resolve().parents[1] / "private"
    monkeypatch.setenv("FBR_PRIVATE_DIR", str(repo_child))
    with pytest.raises(paths.PrivatePathError, match="inside the repository"):
        paths.ensure_private_layout()


@pytest.mark.parametrize("folder", ["Documents", "Desktop"])
def test_refuses_cloud_synced_folders(monkeypatch, folder):
    monkeypatch.setenv("FBR_PRIVATE_DIR", str(Path.home() / folder / "fbr-private"))
    with pytest.raises(paths.PrivatePathError, match="may be synced"):
        paths.ensure_private_layout()


def test_describe_reports_existence(monkeypatch, tmp_path):
    monkeypatch.setenv("FBR_PRIVATE_DIR", str(tmp_path / "priv"))
    before = dict(paths.describe_private_layout())
    assert all(exists is False for exists in before.values())
    paths.ensure_private_layout()
    after = dict(paths.describe_private_layout())
    assert any(exists for exists in after.values())
