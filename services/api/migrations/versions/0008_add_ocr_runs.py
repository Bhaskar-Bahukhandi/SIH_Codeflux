"""Add OCR runs and text blocks.

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-23
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ocr_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("capture_id", sa.String(length=36), nullable=False),
        sa.Column("source_derivative_id", sa.String(length=36), nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column("engine_name", sa.String(length=100), nullable=False),
        sa.Column("engine_version", sa.String(length=100), nullable=False),
        sa.Column("model_version", sa.String(length=100), nullable=False),
        sa.Column("language", sa.String(length=32), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("block_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["capture_id"],
            ["captures.id"],
            name="fk_ocr_runs_capture_id_captures",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_derivative_id"],
            ["capture_derivatives.id"],
            name="fk_ocr_runs_source_derivative_id_derivatives",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "block_count >= 0",
            name="ck_ocr_runs_block_count_nonnegative",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ocr_runs_capture_id", "ocr_runs", ["capture_id"], unique=False)
    op.create_index("ix_ocr_runs_created_at", "ocr_runs", ["created_at"], unique=False)
    op.create_index(
        "ix_ocr_runs_source_derivative_id",
        "ocr_runs",
        ["source_derivative_id"],
        unique=False,
    )

    op.create_table(
        "ocr_blocks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("polygon", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["ocr_runs.id"],
            name="fk_ocr_blocks_run_id_ocr_runs",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "order_index >= 0",
            name="ck_ocr_blocks_order_nonnegative",
        ),
        sa.CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_ocr_blocks_confidence_range",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "order_index",
            name="uq_ocr_blocks_run_order",
        ),
    )
    op.create_index("ix_ocr_blocks_run_id", "ocr_blocks", ["run_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ocr_blocks_run_id", table_name="ocr_blocks")
    op.drop_table("ocr_blocks")

    op.drop_index(
        "ix_ocr_runs_source_derivative_id",
        table_name="ocr_runs",
    )
    op.drop_index("ix_ocr_runs_created_at", table_name="ocr_runs")
    op.drop_index("ix_ocr_runs_capture_id", table_name="ocr_runs")
    op.drop_table("ocr_runs")
