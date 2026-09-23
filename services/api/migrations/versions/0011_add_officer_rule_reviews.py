"""Add append-only officer reviews for preliminary rule results.

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-23
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("inspections") as batch_op:
        batch_op.add_column(
            sa.Column(
                "reopened_for_recheck_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )

    op.create_table(
        "officer_rule_reviews",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("inspection_id", sa.String(length=36), nullable=False),
        sa.Column("officer_user_id", sa.String(length=36), nullable=False),
        sa.Column("rule_evaluation_run_id", sa.String(length=36), nullable=False),
        sa.Column("rule_evaluation_result_id", sa.String(length=36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column(
            "decision",
            sa.Enum(
                "ACCEPTED",
                "CORRECTED",
                "RECHECK_REQUIRED",
                name="officerreviewdecision",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("corrected_value", sa.JSON(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "revision >= 1",
            name="ck_officer_rule_reviews_revision_positive",
        ),
        sa.ForeignKeyConstraint(
            ["inspection_id"],
            ["inspections.id"],
            name="fk_officer_rule_reviews_inspection",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["officer_user_id"],
            ["users.id"],
            name="fk_officer_rule_reviews_officer",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rule_evaluation_run_id"],
            ["rule_evaluation_runs.id"],
            name="fk_officer_rule_reviews_run",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rule_evaluation_result_id"],
            ["rule_evaluation_results.id"],
            name="fk_officer_rule_reviews_result",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "rule_evaluation_result_id",
            "revision",
            name="uq_officer_rule_reviews_result_revision",
        ),
    )
    op.create_index(
        "ix_officer_rule_reviews_created_at",
        "officer_rule_reviews",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_officer_rule_reviews_decision",
        "officer_rule_reviews",
        ["decision"],
        unique=False,
    )
    op.create_index(
        "ix_officer_rule_reviews_inspection_id",
        "officer_rule_reviews",
        ["inspection_id"],
        unique=False,
    )
    op.create_index(
        "ix_officer_rule_reviews_officer_user_id",
        "officer_rule_reviews",
        ["officer_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_officer_rule_reviews_rule_evaluation_run_id",
        "officer_rule_reviews",
        ["rule_evaluation_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_officer_rule_reviews_rule_evaluation_result_id",
        "officer_rule_reviews",
        ["rule_evaluation_result_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_officer_rule_reviews_rule_evaluation_result_id",
        table_name="officer_rule_reviews",
    )
    op.drop_index(
        "ix_officer_rule_reviews_rule_evaluation_run_id",
        table_name="officer_rule_reviews",
    )
    op.drop_index(
        "ix_officer_rule_reviews_officer_user_id",
        table_name="officer_rule_reviews",
    )
    op.drop_index(
        "ix_officer_rule_reviews_inspection_id",
        table_name="officer_rule_reviews",
    )
    op.drop_index(
        "ix_officer_rule_reviews_decision",
        table_name="officer_rule_reviews",
    )
    op.drop_index(
        "ix_officer_rule_reviews_created_at",
        table_name="officer_rule_reviews",
    )
    op.drop_table("officer_rule_reviews")

    with op.batch_alter_table("inspections") as batch_op:
        batch_op.drop_column("reopened_for_recheck_at")
