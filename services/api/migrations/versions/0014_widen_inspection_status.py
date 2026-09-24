"""Widen inspection lifecycle status storage.

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-24
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("inspections") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=sa.String(length=9),
            type_=sa.String(length=32),
            existing_nullable=False,
        )


def downgrade() -> None:
    # Deliberately do not narrow back to VARCHAR(9). Rows using
    # PENDING_REVIEW would no longer fit and a rollback must not destroy or
    # invalidate persisted inspection lifecycle state. Earlier downgrades
    # eventually drop/recreate the table when rolling all the way to base.
    pass
