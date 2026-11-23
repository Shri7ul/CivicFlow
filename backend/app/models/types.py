"""Enum column helpers for portable CHECK-constrained string enums."""

from __future__ import annotations

from enum import Enum
from typing import TypeVar

from sqlalchemy import Enum as SAEnum

EnumT = TypeVar("EnumT", bound=Enum)


def enum_column(enum_cls: type[EnumT], name: str) -> SAEnum:
    """Return a VARCHAR enum backed by a named CHECK constraint.

    PostgreSQL native enum types complicate reversible migrations and Supabase
    schema changes, so Phase 1 uses validated strings with CHECK constraints.
    """
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        length=max(len(member.value) for member in enum_cls),
        values_callable=lambda cls: [member.value for member in cls],
    )
