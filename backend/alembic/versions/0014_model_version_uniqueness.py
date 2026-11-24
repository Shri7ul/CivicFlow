"""Allow distinct model version labels to share one runtime configuration.

Revision ID: 0014_model_version_uniqueness
Revises: 0013_phase7_hardening
Create Date: 2026-11-24
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0014_model_version_uniqueness"
down_revision: Union[str, None] = "0013_phase7_hardening"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # A model version is identified by its version label. Requiring a unique
    # config hash per model name made a second label with the same configuration
    # return the first version, silently ignoring the requested label.
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE model_versions "
            "DROP CONSTRAINT IF EXISTS uq_model_versions_name_hash"
        )
    else:
        with op.batch_alter_table("model_versions") as batch_op:
            batch_op.drop_constraint(
                "uq_model_versions_name_hash", type_="unique"
            )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.create_unique_constraint(
            "uq_model_versions_name_hash",
            "model_versions",
            ["model_name", "config_hash"],
        )
    else:
        with op.batch_alter_table("model_versions") as batch_op:
            batch_op.create_unique_constraint(
                "uq_model_versions_name_hash",
                ["model_name", "config_hash"],
            )
