# src/fbr/config/schema_profile.py
"""Schema for a layout profile: one TOML file per statement layout.

`extra="forbid"` throughout. A mistyped key in a profile must fail loudly at
load time, not silently disable the setting and let a real statement parse
with the wrong rules.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_STRICT = ConfigDict(extra="forbid", frozen=True)


def _compile(pattern: str, *, require_group: str | None = None) -> re.Pattern:
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"invalid regex {pattern!r}: {exc}") from exc
    if require_group and require_group not in compiled.groupindex:
        raise ValueError(f"regex {pattern!r} must define a (?P<{require_group}>...) group")
    return compiled


class Detect(BaseModel):
    model_config = _STRICT
    header_contains: list[str] = Field(min_length=1)
    title_regex: str | None = None

    @field_validator("title_regex")
    @classmethod
    def _valid_regex(cls, v: str | None) -> str | None:
        if v is not None:
            _compile(v)
        return v


class ColumnAlign(BaseModel):
    model_config = _STRICT
    debit: Literal["left", "right", "center"] = "right"
    credit: Literal["left", "right", "center"] = "right"
    amount: Literal["left", "right", "center"] = "right"
    balance: Literal["left", "right", "center"] = "right"


class Columns(BaseModel):
    """Role -> header label. A list of labels means "any of these"."""

    model_config = _STRICT
    date: str | list[str]
    value_date: str | list[str] | None = None
    description: str | list[str]
    reference: str | list[str] | None = None
    debit: str | list[str] | None = None
    credit: str | list[str] | None = None
    amount: str | list[str] | None = None
    balance: str | list[str] | None = None
    type: str | list[str] | None = None
    align: ColumnAlign = ColumnAlign()


class Formats(BaseModel):
    model_config = _STRICT
    dates: list[str] = Field(min_length=1)
    sign: Literal["columns", "suffix", "signed"]
    debit_tokens: list[str] = Field(default_factory=list)
    credit_tokens: list[str] = Field(default_factory=list)
    decimals: int = 2

    @field_validator("decimals")
    @classmethod
    def _only_two_decimals_can_be_honoured(cls, v: int) -> int:
        # The knob is documented in spec §5.4 and was accepted at any value,
        # but money.parse_paisa cannot honour anything but 2: PAISA_PER_RUPEE
        # is 100 and the amount grammar caps the fraction at two digits, so a
        # different value did not rescale, it corrupted - decimals = 3 turned
        # "1.50" into 600 paisa (Rs 6.00) and decimals = 1 turned "1.5" into
        # 105 paisa (Rs 1.05). Refuse the profile at load time, where the
        # author can see it, rather than shipping a wrong figure.
        if v != 2:
            raise ValueError(
                f"decimals = {v} cannot be honoured: money is integer paisa "
                "throughout this codebase (1 rupee = 100 paisa) and the amount "
                "grammar accepts at most two decimal places. Any other value "
                "silently miscomputed every amount in the statement - "
                "decimals = 3 read 1.50 as Rs 6.00. Remove the setting or set "
                "it to 2."
            )
        return v

    @field_validator("dates")
    @classmethod
    def _formats_include_a_year(cls, v: list[str]) -> list[str]:
        for fmt in v:
            if "%Y" not in fmt and "%y" not in fmt:
                raise ValueError(
                    f"date format {fmt!r} has no year directive; Python defaults the "
                    "year to 1900, which would silently mis-date every row"
                )
        return v


class Rows(BaseModel):
    model_config = _STRICT
    skip: list[str] = Field(default_factory=list)
    summary: list[str] = Field(default_factory=list)
    footer: list[str] = Field(default_factory=list)
    continuation: Literal["below", "nearest"] = "below"
    row_anchor: Literal["date", "amount"] = "date"

    @model_validator(mode="after")
    def _regexes_compile(self) -> "Rows":
        for group in (self.skip, self.summary, self.footer):
            for pattern in group:
                _compile(pattern)
        return self


class SummaryPatterns(BaseModel):
    """Regexes over the preamble/page text. Each must expose a `value` group."""

    model_config = _STRICT
    opening: str | None = None
    closing: str | None = None
    total_credit: str | None = None
    total_debit: str | None = None
    period_from: str | None = None
    period_to: str | None = None
    account_id: str | None = None

    @model_validator(mode="after")
    def _all_expose_value(self) -> "SummaryPatterns":
        for name in type(self).model_fields:
            pattern = getattr(self, name)
            if pattern is not None:
                _compile(pattern, require_group="value")
        return self

    def compiled(self) -> dict[str, re.Pattern]:
        return {
            name: _compile(getattr(self, name))
            for name in type(self).model_fields
            if getattr(self, name) is not None
        }


class BalanceSpec(BaseModel):
    model_config = _STRICT
    semantics: Literal["running", "none"] = "running"
    kind: Literal["ledger", "available"] = "ledger"


class SelfTestCase(BaseModel):
    model_config = _STRICT
    row: dict[str, str]
    expect_date: date
    expect_amount: int          # signed paisa


class SelfTest(BaseModel):
    model_config = _STRICT
    cases: list[SelfTestCase]

    @field_validator("cases")
    @classmethod
    def _at_least_one(cls, v: list[SelfTestCase]) -> list[SelfTestCase]:
        if not v:
            raise ValueError("a profile must carry at least one selftest case")
        return v


class Profile(BaseModel):
    model_config = _STRICT
    id: str
    institution: str
    container: Literal["csv", "xlsx", "pdf"]
    valid_from: date
    valid_to: date | None = None
    notes: str = ""
    detect: Detect
    columns: Columns
    formats: Formats
    rows: Rows = Rows()
    summary: SummaryPatterns = SummaryPatterns()
    balance: BalanceSpec = BalanceSpec()
    selftest: SelfTest

    @model_validator(mode="after")
    def _columns_match_sign_mode(self) -> "Profile":
        c, mode = self.columns, self.formats.sign
        if mode == "columns":
            if not (c.debit and c.credit):
                raise ValueError("sign='columns' needs both debit and credit columns")
            if c.amount:
                raise ValueError("sign='columns' must not also define an amount column")
        else:
            if not c.amount:
                raise ValueError(f"sign={mode!r} needs a single amount column")
            if c.debit or c.credit:
                raise ValueError(f"sign={mode!r} must not define debit/credit columns")
        if mode == "suffix" and not (self.formats.debit_tokens and self.formats.credit_tokens):
            raise ValueError("sign='suffix' needs debit_tokens and credit_tokens")
        return self
