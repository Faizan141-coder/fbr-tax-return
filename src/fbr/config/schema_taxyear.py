# src/fbr/config/schema_taxyear.py
"""Schema for taxyears/TY*.toml: IRIS codes, thresholds, rates, templates.

Codes live in per-year config because FBR regrouped the wealth statement
between TY2025 and TY2026, and the live IRIS form can differ from the
published one. Each code carries how it was verified, so the UI can mark a
figure the owner still has to confirm.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_STRICT = ConfigDict(extra="forbid", frozen=True)

Verification = Literal[
    "iris_verified",        # owner confirmed in live IRIS        -> shown as tick
    "form_text",            # read from a form's text layer       -> shown as warn
    "form_scan",            # read by OCR from a scanned form     -> shown as warn
    "prior_year_assumed",   # carried over from the year before   -> shown as warn
    "unknown",              # code not known                      -> shown as cross
]


class CodeEntry(BaseModel):
    model_config = _STRICT
    code: str
    label: str
    tab: str
    columns: dict[str, str] = Field(default_factory=dict)
    source: str
    verification: Verification

    @model_validator(mode="after")
    def _blank_code_means_unknown(self) -> "CodeEntry":
        if not self.code and self.verification != "unknown":
            raise ValueError(
                f"{self.label!r} has a blank code but verification="
                f"{self.verification!r}; a blank code must be marked 'unknown'"
            )
        return self


class Thresholds(BaseModel):
    model_config = _STRICT
    profit_final_regime_max: int        # paisa
    s111_4_cap: int                     # paisa
    review_threshold: int               # paisa
    wht_ratio_tolerance_pp: float
    profit_wht_window_days: int
    tax154a_window_days: int
    tax154a_amount_tolerance: int       # paisa
    transfer_window_days: int
    transfer_fee_tolerance: int         # paisa
    reversal_window_days: int


class Rates(BaseModel):
    model_config = _STRICT
    s151_atl: float
    s151_non_atl: float
    s7b: float
    s236y_atl: float
    s236y_non_atl: float
    s231ab_non_atl: float
    s154a: float
    s154a_pseb: float


class Templates(BaseModel):
    model_config = _STRICT
    wealth_line: str
    profit_line: str


class TaxYear(BaseModel):
    model_config = _STRICT
    name: str
    period_start: date
    period_end: date
    atl: bool = True
    codes: dict[str, CodeEntry]
    thresholds: Thresholds
    rates: Rates
    templates: Templates

    @model_validator(mode="after")
    def _period_is_a_fiscal_year(self) -> "TaxYear":
        if (self.period_start.month, self.period_start.day) != (7, 1):
            raise ValueError("period_start must be 1 July")
        if (self.period_end.month, self.period_end.day) != (6, 30):
            raise ValueError("period_end must be 30 June")
        if self.period_end.year != self.period_start.year + 1:
            raise ValueError("a tax year spans exactly one 1 July to 30 June")
        return self
