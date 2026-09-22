"""Add declaration extraction observations and fusion summaries.

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-23
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "declaration_extraction_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("inspection_id", sa.String(length=36), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=False),
        sa.Column("extractor_version", sa.String(length=64), nullable=False),
        sa.Column("fusion_version", sa.String(length=64), nullable=False),
        sa.Column("inspection_capture_count", sa.Integer(), nullable=False),
        sa.Column("source_capture_count", sa.Integer(), nullable=False),
        sa.Column("source_capture_ids", sa.JSON(), nullable=False),
        sa.Column("source_ocr_run_ids", sa.JSON(), nullable=False),
        sa.Column("skipped_sources", sa.JSON(), nullable=False),
        sa.Column("observation_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "inspection_capture_count >= 0",
            name="ck_declaration_runs_capture_count_nonnegative",
        ),
        sa.CheckConstraint(
            "source_capture_count >= 0",
            name="ck_declaration_runs_source_capture_count_nonnegative",
        ),
        sa.CheckConstraint(
            "observation_count >= 0",
            name="ck_declaration_runs_observation_count_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_declaration_runs_actor_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["inspection_id"],
            ["inspections.id"],
            name="fk_declaration_runs_inspection_inspections",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_declaration_runs_actor_user_id",
        "declaration_extraction_runs",
        ["actor_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_declaration_runs_created_at",
        "declaration_extraction_runs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_declaration_runs_inspection_id",
        "declaration_extraction_runs",
        ["inspection_id"],
        unique=False,
    )

    op.create_table(
        "declaration_observations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("extraction_run_id", sa.String(length=36), nullable=False),
        sa.Column(
            "declaration_type",
            sa.Enum(
                "MRP",
                "NET_QUANTITY",
                name="declarationtype",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("capture_id", sa.String(length=36), nullable=False),
        sa.Column("ocr_run_id", sa.String(length=36), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("normalized_value", sa.JSON(), nullable=False),
        sa.Column("ocr_confidence_min", sa.Float(), nullable=False),
        sa.Column("ocr_confidence_mean", sa.Float(), nullable=False),
        sa.Column("extractor_method", sa.String(length=100), nullable=False),
        sa.CheckConstraint(
            "ocr_confidence_min >= 0.0 AND ocr_confidence_min <= 1.0",
            name="ck_declaration_obs_conf_min_range",
        ),
        sa.CheckConstraint(
            "ocr_confidence_mean >= 0.0 AND ocr_confidence_mean <= 1.0",
            name="ck_declaration_obs_conf_mean_range",
        ),
        sa.ForeignKeyConstraint(
            ["capture_id"],
            ["captures.id"],
            name="fk_declaration_obs_capture_captures",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["extraction_run_id"],
            ["declaration_extraction_runs.id"],
            name="fk_declaration_obs_run_runs",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ocr_run_id"],
            ["ocr_runs.id"],
            name="fk_declaration_obs_ocr_run_ocr_runs",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_declaration_obs_capture_id",
        "declaration_observations",
        ["capture_id"],
        unique=False,
    )
    op.create_index(
        "ix_declaration_obs_declaration_type",
        "declaration_observations",
        ["declaration_type"],
        unique=False,
    )
    op.create_index(
        "ix_declaration_obs_extraction_run_id",
        "declaration_observations",
        ["extraction_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_declaration_obs_ocr_run_id",
        "declaration_observations",
        ["ocr_run_id"],
        unique=False,
    )

    op.create_table(
        "declaration_observation_blocks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("observation_id", sa.String(length=36), nullable=False),
        sa.Column("ocr_block_id", sa.String(length=36), nullable=False),
        sa.Column("block_order", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "block_order >= 0",
            name="ck_declaration_observation_block_order_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["observation_id"],
            ["declaration_observations.id"],
            name="fk_declaration_obs_blocks_observation",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ocr_block_id"],
            ["ocr_blocks.id"],
            name="fk_declaration_obs_blocks_ocr_block",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "observation_id",
            "ocr_block_id",
            name="uq_declaration_observation_block",
        ),
    )
    op.create_index(
        "ix_declaration_obs_blocks_observation_id",
        "declaration_observation_blocks",
        ["observation_id"],
        unique=False,
    )
    op.create_index(
        "ix_declaration_obs_blocks_ocr_block_id",
        "declaration_observation_blocks",
        ["ocr_block_id"],
        unique=False,
    )

    op.create_table(
        "declaration_summaries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("extraction_run_id", sa.String(length=36), nullable=False),
        sa.Column(
            "declaration_type",
            sa.Enum(
                "MRP",
                "NET_QUANTITY",
                name="declarationtype_summary",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "NOT_DETECTED",
                "SINGLE_SOURCE",
                "CONSISTENT",
                "CONFLICT",
                name="declarationfusionstatus",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("canonical_value", sa.JSON(), nullable=True),
        sa.Column("candidate_values", sa.JSON(), nullable=False),
        sa.Column("observation_count", sa.Integer(), nullable=False),
        sa.Column("capture_count", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "observation_count >= 0",
            name="ck_declaration_summary_observation_count_nonnegative",
        ),
        sa.CheckConstraint(
            "capture_count >= 0",
            name="ck_declaration_summary_capture_count_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["extraction_run_id"],
            ["declaration_extraction_runs.id"],
            name="fk_declaration_summary_run_runs",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "extraction_run_id",
            "declaration_type",
            name="uq_declaration_summary_run_type",
        ),
    )
    op.create_index(
        "ix_declaration_summary_declaration_type",
        "declaration_summaries",
        ["declaration_type"],
        unique=False,
    )
    op.create_index(
        "ix_declaration_summary_extraction_run_id",
        "declaration_summaries",
        ["extraction_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_declaration_summary_status",
        "declaration_summaries",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_declaration_summary_status",
        table_name="declaration_summaries",
    )
    op.drop_index(
        "ix_declaration_summary_extraction_run_id",
        table_name="declaration_summaries",
    )
    op.drop_index(
        "ix_declaration_summary_declaration_type",
        table_name="declaration_summaries",
    )
    op.drop_table("declaration_summaries")

    op.drop_index(
        "ix_declaration_obs_blocks_ocr_block_id",
        table_name="declaration_observation_blocks",
    )
    op.drop_index(
        "ix_declaration_obs_blocks_observation_id",
        table_name="declaration_observation_blocks",
    )
    op.drop_table("declaration_observation_blocks")

    op.drop_index(
        "ix_declaration_obs_ocr_run_id",
        table_name="declaration_observations",
    )
    op.drop_index(
        "ix_declaration_obs_extraction_run_id",
        table_name="declaration_observations",
    )
    op.drop_index(
        "ix_declaration_obs_declaration_type",
        table_name="declaration_observations",
    )
    op.drop_index(
        "ix_declaration_obs_capture_id",
        table_name="declaration_observations",
    )
    op.drop_table("declaration_observations")

    op.drop_index(
        "ix_declaration_runs_inspection_id",
        table_name="declaration_extraction_runs",
    )
    op.drop_index(
        "ix_declaration_runs_created_at",
        table_name="declaration_extraction_runs",
    )
    op.drop_index(
        "ix_declaration_runs_actor_user_id",
        table_name="declaration_extraction_runs",
    )
    op.drop_table("declaration_extraction_runs")
