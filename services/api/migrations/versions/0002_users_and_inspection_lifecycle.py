"""Add users and inspection lifecycle fields.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-22
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "OFFICER",
                "SUPERVISOR",
                "ADMIN",
                name="userrole",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    with op.batch_alter_table("inspections") as batch_op:
        batch_op.add_column(sa.Column("officer_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_foreign_key(
            "fk_inspections_officer_id_users",
            "users",
            ["officer_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("inspections") as batch_op:
        batch_op.drop_constraint("fk_inspections_officer_id_users", type_="foreignkey")
        batch_op.drop_column("submitted_at")
        batch_op.drop_column("officer_id")

    op.drop_table("users")
