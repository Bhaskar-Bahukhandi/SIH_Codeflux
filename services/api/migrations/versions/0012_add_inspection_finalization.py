"""Add immutable inspection finalization and report metadata.

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-23
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inspection_finalizations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("inspection_id", sa.String(length=36), nullable=False),
        sa.Column("finalized_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("rule_evaluation_run_id", sa.String(length=36), nullable=False),
        sa.Column("rule_pack_id", sa.String(length=100), nullable=False),
        sa.Column("rule_pack_version", sa.String(length=64), nullable=False),
        sa.Column("rule_pack_sha256", sa.String(length=64), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("snapshot_sha256", sa.String(length=64), nullable=False),
        sa.Column("report_id", sa.String(length=36), nullable=False),
        sa.Column("report_version", sa.String(length=32), nullable=False),
        sa.Column("report_storage_key", sa.String(length=500), nullable=False),
        sa.Column("report_sha256", sa.String(length=64), nullable=False),
        sa.Column("report_size_bytes", sa.Integer(), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "report_size_bytes > 0",
            name="ck_inspection_finalizations_report_size_positive",
        ),
        sa.ForeignKeyConstraint(
            ["finalized_by_user_id"],
            ["users.id"],
            name="fk_inspection_finalizations_user",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["inspection_id"],
            ["inspections.id"],
            name="fk_inspection_finalizations_inspection",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rule_evaluation_run_id"],
            ["rule_evaluation_runs.id"],
            name="fk_inspection_finalizations_rule_run",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "inspection_id",
            name="uq_inspection_finalizations_inspection_id",
        ),
        sa.UniqueConstraint(
            "report_id",
            name="uq_inspection_finalizations_report_id",
        ),
        sa.UniqueConstraint(
            "report_storage_key",
            name="uq_inspection_finalizations_report_storage_key",
        ),
    )
    op.create_index(
        "ix_inspection_finalizations_finalized_at",
        "inspection_finalizations",
        ["finalized_at"],
        unique=False,
    )
    op.create_index(
        "ix_inspection_finalizations_finalized_by_user_id",
        "inspection_finalizations",
        ["finalized_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_inspection_finalizations_inspection_id",
        "inspection_finalizations",
        ["inspection_id"],
        unique=False,
    )
    op.create_index(
        "ix_inspection_finalizations_rule_evaluation_run_id",
        "inspection_finalizations",
        ["rule_evaluation_run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_inspection_finalizations_rule_evaluation_run_id",
        table_name="inspection_finalizations",
    )
    op.drop_index(
        "ix_inspection_finalizations_inspection_id",
        table_name="inspection_finalizations",
    )
    op.drop_index(
        "ix_inspection_finalizations_finalized_by_user_id",
        table_name="inspection_finalizations",
    )
    op.drop_index(
        "ix_inspection_finalizations_finalized_at",
        table_name="inspection_finalizations",
    )
    op.drop_table("inspection_finalizations")
