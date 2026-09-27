# src/fbr/paths.py
"""Where the owner's data lives.

Every read and write of owner data goes through this module, so that no
other module can put a statement inside the repository by accident. The
guards below are cheap and catch the two mistakes that would matter:
pointing the private folder at the repo (git would see statements) or at a
cloud-synced folder (the brief requires that nothing leaves the machine).
"""

from __future__ import annotations

import os
from pathlib import Path

_DEFAULT = "fbr-private"
_SUBDIRS = ("statements", "dumps", "dump-candidates", "decisions", "manual")
# macOS syncs these to iCloud Drive when Desktop & Documents sync is on.
_CLOUD_SYNCED = ("Documents", "Desktop")


class PrivatePathError(RuntimeError):
    """The configured private folder is not a safe place for owner data."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def private_root() -> Path:
    env = os.environ.get("FBR_PRIVATE_DIR")
    return Path(env).expanduser() if env else Path.home() / _DEFAULT


def statements_dir(tax_year: str) -> Path:
    return private_root() / "statements" / tax_year


def dumps_dir() -> Path:
    return private_root() / "dumps"


def dump_candidates_dir() -> Path:
    return private_root() / "dump-candidates"


def decisions_path(tax_year: str) -> Path:
    return private_root() / "decisions" / f"{tax_year}.json"


def manual_path(tax_year: str) -> Path:
    return private_root() / "manual" / f"{tax_year}.toml"


def registry_path() -> Path:
    return private_root() / "accounts.toml"


def local_rules_path() -> Path:
    return private_root() / "rules.local.toml"


def dump_allowlist_path() -> Path:
    return private_root() / "dump-allowlist.txt"


def _validate(root: Path) -> None:
    resolved = root.expanduser().resolve()
    repo = _repo_root()
    if resolved == repo or repo in resolved.parents:
        raise PrivatePathError(
            f"{resolved} is inside the repository; git would see owner data. "
            "Set FBR_PRIVATE_DIR to a folder outside the repo."
        )
    home = Path.home().resolve()
    for name in _CLOUD_SYNCED:
        synced = home / name
        if resolved == synced or synced in resolved.parents:
            raise PrivatePathError(
                f"{resolved} is under ~/{name}, which may be synced to iCloud. "
                "Choose a folder that stays on this machine."
            )


def ensure_private_layout() -> Path:
    """Create the private folder layout, refusing unsafe locations."""
    root = private_root()
    _validate(root)
    for sub in _SUBDIRS:
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


def describe_private_layout() -> list[tuple[str, bool]]:
    """(path, exists) pairs for the Setup page. Never lists file contents."""
    root = private_root()
    entries = [(str(root), root.is_dir())]
    entries += [(str(root / s), (root / s).is_dir()) for s in _SUBDIRS]
    entries.append((str(registry_path()), registry_path().is_file()))
    return entries
