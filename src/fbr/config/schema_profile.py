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
    """Which printed lines are transactions and which are furniture.

    `skip` and `summary` are read by BOTH engines: a line matching either is
    passed over wherever it appears.

    `footer` is read by the PDF engine ONLY, and it means "the end of this
    page's body" - the PDF engine stops reading the page there. The tabular
    engine has no pages and does not read it at all; on a CSV or XLSX the
    equivalent trailing lines belong in `skip` or `summary`. That divergence
    used to be silent, so the same key meant two different things depending on
    the container; `Profile` now refuses `footer` on a non-PDF profile rather
    than accepting a setting nothing honours.

    Note for the next PDF profile author: a `footer` pattern is not a "skip
    anywhere" rule. It ends the page, so a pattern loose enough to match a line
    printed ABOVE real rows - `'(?i)^\\s*page\\s+\\d+'` against a "Page 2 of 2"
    banner at the top of a continuation page - would end the page before them.
    The engine will not drop them silently: it raises an UnresolvedRow naming
    the footer line and fails the statement. Tighten the pattern, or move it to
    `skip`.
    """

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


MONEY_ROLES = frozenset({"opening", "closing", "total_credit", "total_debit"})
PERIOD_ROLES = frozenset({"period_from", "period_to"})
TEXT_ROLES = frozenset({"account_id"})


class SelfTest(BaseModel):
    model_config = _STRICT
    cases: list[SelfTestCase]
    # Preamble text that every declared summary pattern must match. Without
    # this, a profile's self-test exercises only parse_row, and a summary
    # pattern that never matches ships silently - which is exactly how a
    # shipped Meezan XLSX profile spent a release with four dead patterns
    # and a disabled opening/closing check.
    summary_sample: str = ""
    # Role -> the value its pattern must CAPTURE out of `summary_sample`:
    # integer paisa for a money role, an ISO date string for a period role, the
    # exact text for account_id. `summary_sample` on its own only proves a
    # pattern matches SOMETHING, and run_selftest tested nothing but
    # `search()` truthiness - so a pattern that matched the WRONG line's number
    # passed for all six shipped profiles. Swapping `opening` and `closing`
    # made `opening` read Rs 25,935.59 instead of Rs 5,000.00 and the selftest
    # still said ok. "Pattern never matches" is caught by summary_sample;
    # "pattern captures the wrong figure" is the one that puts a wrong number
    # on a return, and this is what catches it. Optional, so a profile without
    # it still loads.
    summary_expect: dict[str, int | str | date] = Field(default_factory=dict)

    @field_validator("cases")
    @classmethod
    def _at_least_one(cls, v: list[SelfTestCase]) -> list[SelfTestCase]:
        if not v:
            raise ValueError("a profile must carry at least one selftest case")
        return v

    @field_validator("summary_expect", mode="before")
    @classmethod
    def _expectations_are_well_typed(cls, v: object) -> object:
        # mode="before" on purpose. Validated after coercion, pydantic had
        # already turned the float 5000.0 into the int 5000 - an accepted
        # expectation of Rs 50.00 where Rs 5,000.00 was meant - and the
        # isinstance check below could not see it had ever been a float.
        if not isinstance(v, dict):
            return v
        known = MONEY_ROLES | PERIOD_ROLES | TEXT_ROLES
        out: dict[str, int | str] = {}
        for role, expected in v.items():
            if role not in known:
                raise ValueError(
                    f"summary_expect role {role!r} is not a summary pattern; "
                    f"known roles are {sorted(known)}"
                )
            if role in MONEY_ROLES:
                # Money is integer paisa everywhere in this codebase. A float
                # or a "5,000.00" string here would compare unequal to the
                # engine's int forever, or worse, coerce and lose a paisa.
                if isinstance(expected, bool) or not isinstance(expected, int):
                    raise ValueError(
                        f"summary_expect.{role} = {expected!r} must be integer "
                        "paisa (Rs 5,000.00 is 500000), never a float, a string "
                        "or a date"
                    )
                out[role] = expected
            elif role in PERIOD_ROLES:
                # A bare TOML date (period_from = 2025-07-01) parses to a
                # datetime.date; accept it and normalise, rather than failing
                # on a spelling that reads perfectly well in the file.
                if isinstance(expected, date):
                    out[role] = expected.isoformat()
                    continue
                if not isinstance(expected, str):
                    raise ValueError(
                        f"summary_expect.{role} = {expected!r} must be an ISO "
                        "date string (YYYY-MM-DD)"
                    )
                try:
                    out[role] = date.fromisoformat(expected).isoformat()
                except ValueError:
                    raise ValueError(
                        f"summary_expect.{role} = {expected!r} is not an ISO "
                        "date (YYYY-MM-DD)"
                    ) from None
            else:
                if not isinstance(expected, str):
                    raise ValueError(
                        f"summary_expect.{role} = {expected!r} must be a string"
                    )
                out[role] = expected
        return out


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

    @model_validator(mode="after")
    def _footer_is_a_pdf_only_rule(self) -> "Profile":
        # rows.footer is honoured by the PDF engine and ignored outright by the
        # tabular one, so on a CSV or XLSX profile it is a setting that silently
        # does nothing - the same class of quiet failure `extra="forbid"` exists
        # to prevent for a mistyped key. Refuse it at load time, where the author
        # can see it, and name the keys that do work.
        if self.container != "pdf" and self.rows.footer:
            raise ValueError(
                f"rows.footer is a PDF-only rule (it ends a PAGE), but profile "
                f"{self.id!r} has container = {self.container!r}, whose engine "
                "never reads it. Put these patterns in rows.skip or rows.summary "
                "instead, which both engines honour."
            )
        return self

    @model_validator(mode="after")
    def _expectations_point_at_declared_patterns(self) -> "Profile":
        expect = self.selftest.summary_expect
        if not expect:
            return self
        declared = set(self.summary.compiled())
        unknown = sorted(set(expect) - declared)
        if unknown:
            raise ValueError(
                f"selftest.summary_expect names {unknown}, which this profile "
                "declares no [summary] pattern for; an expectation on a pattern "
                "that does not exist would silently never run"
            )
        if not self.selftest.summary_sample:
            raise ValueError(
                "selftest.summary_expect needs a selftest.summary_sample to "
                "check the captured values against"
            )
        return self
