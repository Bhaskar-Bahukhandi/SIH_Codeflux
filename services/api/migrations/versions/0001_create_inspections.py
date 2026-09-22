"""Create inspections table.

Revision ID: 0001
Revises:
Create Date: 2026-09-22
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inspections",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("product_name", sa.String(length=200), nullable=False),
        sa.Column("product_identifier", sa.String(length=200), nullable=True),
        sa.Column(
            "status",
            sa.Enum("DRAFT", "FINALIZED", name="inspectionstatus", native_enum=False),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("inspections")
