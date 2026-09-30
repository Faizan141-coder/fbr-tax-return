"""Load and validate TOML configuration.

Every error names the file it came from. A profile problem discovered at
load time is cheap; the same problem discovered halfway through a tax return
is not.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from pydantic import ValidationError

from fbr import paths
from fbr.config.schema_profile import Profile
from fbr.config.schema_registry import RegistryFile
from fbr.config.schema_taxyear import TaxYear
from fbr.model import Registry


class ConfigError(RuntimeError):
    """Configuration is missing, malformed or contradictory."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _read_toml(path: Path) -> dict:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path.name}: malformed TOML: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"{path}: cannot read: {exc}") from exc


@dataclass(frozen=True, slots=True)
class ProfileStatus:
    """A profile's readiness, shown on the Setup page."""

    profile_id: str
    path: str
    ok: bool
    message: str


@dataclass(frozen=True, slots=True)
class ProfileSet:
    profiles: tuple[Profile, ...]
    report: tuple[ProfileStatus, ...]

    def for_container(self, container: str) -> tuple[Profile, ...]:
        return tuple(p for p in self.profiles if p.container == container)

    def by_id(self, profile_id: str) -> Profile | None:
        return next((p for p in self.profiles if p.id == profile_id), None)


def load_profiles(directory: Path | None = None) -> ProfileSet:
    """Load every *.toml profile in `directory`, rejecting duplicate ids."""
    directory = Path(directory) if directory else _repo_root() / "profiles"
    if not directory.is_dir():
        raise ConfigError(f"no profile directory at {directory}")

    files = sorted(directory.glob("*.toml"))
    if not files:
        raise ConfigError(f"no profiles found in {directory}")

    profiles: list[Profile] = []
    report: list[ProfileStatus] = []
    seen: dict[str, Path] = {}

    for path in files:
        data = _read_toml(path)
        try:
            profile = Profile.model_validate(data)
        except ValidationError as exc:
            raise ConfigError(f"{path.name}: invalid profile: {exc}") from exc
        if profile.id in seen:
            raise ConfigError(
                f"duplicate profile id {profile.id!r} in {path.name} and "
                f"{seen[profile.id].name}; ids must be unique so a statement "
                "cannot match two layouts"
            )
        seen[profile.id] = path
        profiles.append(profile)
        report.append(ProfileStatus(profile.id, str(path), True, "loaded"))

    return ProfileSet(tuple(profiles), tuple(report))


def run_selftest(
    profile: Profile,
    parse_row: Callable[[Profile, dict], tuple],
    *,
    summary_text: str | None = None,
) -> ProfileStatus:
    """Run a profile's own sample rows, and its summary patterns, through the code.

    A profile that cannot parse its own samples is excluded from detection: it
    would otherwise fail silently on the real statement it was written for.

    `summary_text` closes a second hole. Summary patterns are regexes in a TOML
    file and nothing else executes them, so a mistake - doubled backslashes in
    a literal string, say - leaves a pattern that never matches. The statement
    still parses, but a reconciliation check quietly stops running. When a
    sample is supplied, every declared pattern must match it.
    """
    for i, case in enumerate(profile.selftest.cases, start=1):
        try:
            got_date, got_amount = parse_row(profile, case.row)
        except Exception as exc:  # noqa: BLE001 - any failure is a failed self-test
            return ProfileStatus(profile.id, "", False, f"selftest case {i} raised: {exc}")
        if got_date != case.expect_date:
            return ProfileStatus(
                profile.id, "", False,
                f"selftest case {i}: date {got_date} != expected {case.expect_date}",
            )
        if got_amount != case.expect_amount:
            return ProfileStatus(
                profile.id, "", False,
                f"selftest case {i}: amount {got_amount} != expected {case.expect_amount}",
            )

    if summary_text:
        compiled = profile.summary.compiled()
        dead = [name for name, pattern in compiled.items()
                if not pattern.search(summary_text)]
        if dead:
            return ProfileStatus(
                profile.id, "", False,
                f"summary pattern(s) {', '.join(sorted(dead))} match nothing in "
                "the profile's own summary_sample; a pattern that never matches "
                "silently disables a reconciliation check",
            )
        return ProfileStatus(
            profile.id, "", True,
            f"{len(profile.selftest.cases)} selftest case(s) and "
            f"{len(compiled)} summary pattern(s) pass",
        )

    return ProfileStatus(
        profile.id, "", True,
        f"{len(profile.selftest.cases)} selftest case(s) pass",
    )


def load_registry(path: Path | None = None) -> Registry:
    path = Path(path) if path else paths.registry_path()
    if not path.is_file():
        raise ConfigError(
            f"no account registry at {path}. Create accounts.toml there with an "
            "[owner] name and one [[account]] block per account."
        )
    try:
        return RegistryFile.model_validate(_read_toml(path)).to_model()
    except ValidationError as exc:
        raise ConfigError(f"{path.name}: invalid registry: {exc}") from exc


def load_tax_year(name: str, directory: Path | None = None) -> TaxYear:
    directory = Path(directory) if directory else _repo_root() / "taxyears"
    path = directory / f"{name}.toml"
    if not path.is_file():
        available = ", ".join(sorted(p.stem for p in directory.glob("TY*.toml"))) or "none"
        raise ConfigError(f"no config for {name}; available: {available}")
    try:
        return TaxYear.model_validate(_read_toml(path))
    except ValidationError as exc:
        raise ConfigError(f"{path.name}: invalid tax year config: {exc}") from exc
