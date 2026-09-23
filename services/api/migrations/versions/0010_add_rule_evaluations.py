"""Add versioned preliminary rule evaluations.

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-23
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rule_evaluation_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("inspection_id", sa.String(length=36), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=False),
        sa.Column("source_extraction_run_id", sa.String(length=36), nullable=False),
        sa.Column("rule_pack_id", sa.String(length=100), nullable=False),
        sa.Column("rule_pack_version", sa.String(length=64), nullable=False),
        sa.Column("rule_pack_sha256", sa.String(length=64), nullable=False),
        sa.Column("rule_pack_snapshot", sa.JSON(), nullable=False),
        sa.Column("context_snapshot", sa.JSON(), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "result_count >= 0",
            name="ck_rule_evaluation_runs_result_count_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_rule_evaluation_runs_actor_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["inspection_id"],
            ["inspections.id"],
            name="fk_rule_evaluation_runs_inspection_inspections",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_extraction_run_id"],
            ["declaration_extraction_runs.id"],
            name="fk_rule_evaluation_runs_extraction_declaration_runs",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_rule_evaluation_runs_actor_user_id",
        "rule_evaluation_runs",
        ["actor_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_rule_evaluation_runs_created_at",
        "rule_evaluation_runs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_rule_evaluation_runs_inspection_id",
        "rule_evaluation_runs",
        ["inspection_id"],
        unique=False,
    )
    op.create_index(
        "ix_rule_evaluation_runs_source_extraction_run_id",
        "rule_evaluation_runs",
        ["source_extraction_run_id"],
        unique=False,
    )

    op.create_table(
        "rule_evaluation_results",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("evaluation_run_id", sa.String(length=36), nullable=False),
        sa.Column("rule_id", sa.String(length=160), nullable=False),
        sa.Column("provision", sa.String(length=100), nullable=False),
        sa.Column("declaration_type", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PASS",
                "POTENTIAL_NON_COMPLIANCE",
                "INDETERMINATE",
                "NOT_APPLICABLE",
                "MANUAL_VERIFICATION_REQUIRED",
                "NOT_EVALUATED",
                name="ruleevaluationstatus",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("evidence_summary_id", sa.String(length=36), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["evaluation_run_id"],
            ["rule_evaluation_runs.id"],
            name="fk_rule_evaluation_results_run_runs",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_summary_id"],
            ["declaration_summaries.id"],
            name="fk_rule_evaluation_results_summary_declaration_summaries",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "evaluation_run_id",
            "rule_id",
            name="uq_rule_evaluation_result_run_rule",
        ),
    )
    op.create_index(
        "ix_rule_evaluation_results_evaluation_run_id",
        "rule_evaluation_results",
        ["evaluation_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_rule_evaluation_results_evidence_summary_id",
        "rule_evaluation_results",
        ["evidence_summary_id"],
        unique=False,
    )
    op.create_index(
        "ix_rule_evaluation_results_rule_id",
        "rule_evaluation_results",
        ["rule_id"],
        unique=False,
    )
    op.create_index(
        "ix_rule_evaluation_results_status",
        "rule_evaluation_results",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_rule_evaluation_results_status",
        table_name="rule_evaluation_results",
    )
    op.drop_index(
        "ix_rule_evaluation_results_rule_id",
        table_name="rule_evaluation_results",
    )
    op.drop_index(
        "ix_rule_evaluation_results_evidence_summary_id",
        table_name="rule_evaluation_results",
    )
    op.drop_index(
        "ix_rule_evaluation_results_evaluation_run_id",
        table_name="rule_evaluation_results",
    )
    op.drop_table("rule_evaluation_results")

    op.drop_index(
        "ix_rule_evaluation_runs_source_extraction_run_id",
        table_name="rule_evaluation_runs",
    )
    op.drop_index(
        "ix_rule_evaluation_runs_inspection_id",
        table_name="rule_evaluation_runs",
    )
    op.drop_index(
        "ix_rule_evaluation_runs_created_at",
        table_name="rule_evaluation_runs",
    )
    op.drop_index(
        "ix_rule_evaluation_runs_actor_user_id",
        table_name="rule_evaluation_runs",
    )
    op.drop_table("rule_evaluation_runs")
