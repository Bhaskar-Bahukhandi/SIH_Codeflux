"""Add append-only officer finding reviews.

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
    op.create_table(
        "officer_finding_reviews",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("inspection_id", sa.String(length=36), nullable=False),
        sa.Column("evaluation_run_id", sa.String(length=36), nullable=False),
        sa.Column("rule_evaluation_result_id", sa.String(length=36), nullable=False),
        sa.Column("officer_user_id", sa.String(length=36), nullable=False),
        sa.Column(
            "decision",
            sa.Enum(
                "CONFIRM_PRESENT",
                "CONFIRM_ABSENT",
                "CORRECT_VALUE",
                "REQUEST_RECHECK",
                name="officerreviewdecision",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "outcome",
            sa.Enum(
                "VERIFIED_DECLARATION_PRESENT",
                "POTENTIAL_NON_COMPLIANCE",
                "RECHECK_REQUIRED",
                name="officerreviewoutcome",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("corrected_value", sa.JSON(), nullable=True),
        sa.Column("evidence_capture_ids", sa.JSON(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["evaluation_run_id"],
            ["rule_evaluation_runs.id"],
            name="fk_officer_reviews_evaluation_run",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["inspection_id"],
            ["inspections.id"],
            name="fk_officer_reviews_inspection",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["officer_user_id"],
            ["users.id"],
            name="fk_officer_reviews_officer",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rule_evaluation_result_id"],
            ["rule_evaluation_results.id"],
            name="fk_officer_reviews_rule_result",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_officer_reviews_inspection_id",
        "officer_finding_reviews",
        ["inspection_id"],
        unique=False,
    )
    op.create_index(
        "ix_officer_reviews_evaluation_run_id",
        "officer_finding_reviews",
        ["evaluation_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_officer_reviews_rule_result_id",
        "officer_finding_reviews",
        ["rule_evaluation_result_id"],
        unique=False,
    )
    op.create_index(
        "ix_officer_reviews_officer_user_id",
        "officer_finding_reviews",
        ["officer_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_officer_reviews_decision",
        "officer_finding_reviews",
        ["decision"],
        unique=False,
    )
    op.create_index(
        "ix_officer_reviews_outcome",
        "officer_finding_reviews",
        ["outcome"],
        unique=False,
    )
    op.create_index(
        "ix_officer_reviews_created_at",
        "officer_finding_reviews",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_officer_reviews_created_at", table_name="officer_finding_reviews")
    op.drop_index("ix_officer_reviews_outcome", table_name="officer_finding_reviews")
    op.drop_index("ix_officer_reviews_decision", table_name="officer_finding_reviews")
    op.drop_index(
        "ix_officer_reviews_officer_user_id",
        table_name="officer_finding_reviews",
    )
    op.drop_index(
        "ix_officer_reviews_rule_result_id",
        table_name="officer_finding_reviews",
    )
    op.drop_index(
        "ix_officer_reviews_evaluation_run_id",
        table_name="officer_finding_reviews",
    )
    op.drop_index(
        "ix_officer_reviews_inspection_id",
        table_name="officer_finding_reviews",
    )
    op.drop_table("officer_finding_reviews")
