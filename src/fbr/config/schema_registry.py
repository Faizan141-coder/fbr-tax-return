# src/fbr/config/schema_registry.py
"""Schema for ~/fbr-private/accounts.toml, the owner's account registry."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from fbr.model import Account, Owner, Registry

_STRICT = ConfigDict(extra="forbid")


class OwnerEntry(BaseModel):
    model_config = _STRICT
    name: str


class AccountEntry(BaseModel):
    model_config = _STRICT
    id: str
    institution: str
    kind: Literal["bank", "wallet", "foreign"]
    iban: str = ""
    account_number: str = ""
    wallet_number: str = ""
    title: str
    type: str = ""
    ownership: str = "Self"
    currency: str = "PKR"
    statement_expected: bool = True
    match_hints: list[str] = Field(default_factory=list)
    opened_on: date | None = None
    closed_on: date | None = None

    @model_validator(mode="after")
    def _has_an_identifier(self) -> "AccountEntry":
        # Without one of these, a parsed statement can never be linked to this
        # account automatically, and internal-transfer matching has nothing to
        # match on.
        if not (self.iban or self.account_number or self.wallet_number):
            raise ValueError(
                f"account {self.id!r} needs an identifier: iban, account_number "
                "or wallet_number"
            )
        return self


class RegistryFile(BaseModel):
    model_config = _STRICT
    owner: OwnerEntry
    account: list[AccountEntry] = Field(min_length=1)

    @model_validator(mode="after")
    def _ids_are_unique(self) -> "RegistryFile":
        seen: set[str] = set()
        for a in self.account:
            if a.id in seen:
                raise ValueError(f"duplicate account id {a.id!r}")
            seen.add(a.id)
        return self

    def to_model(self) -> Registry:
        return Registry(
            owner=Owner(name=self.owner.name),
            accounts=tuple(
                Account(
                    id=a.id, institution=a.institution, kind=a.kind, iban=a.iban,
                    account_number=a.account_number, wallet_number=a.wallet_number,
                    title=a.title, type=a.type, ownership=a.ownership,
                    currency=a.currency, statement_expected=a.statement_expected,
                    match_hints=tuple(a.match_hints),
                    opened_on=a.opened_on, closed_on=a.closed_on,
                )
                for a in self.account
            ),
        )
