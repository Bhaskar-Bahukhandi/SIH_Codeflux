"""Add capture derivatives and quality assessments.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-23
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "capture_derivatives",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("capture_id", sa.String(length=36), nullable=False),
        sa.Column("derivative_type", sa.String(length=64), nullable=False),
        sa.Column("processing_version", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("width_px", sa.Integer(), nullable=False),
        sa.Column("height_px", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["capture_id"],
            ["captures.id"],
            name="fk_capture_derivatives_capture_id_captures",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key", name="uq_capture_derivatives_storage_key"),
    )
    op.create_index(
        "ix_capture_derivatives_capture_id",
        "capture_derivatives",
        ["capture_id"],
        unique=False,
    )
    op.create_index(
        "ix_capture_derivatives_created_at",
        "capture_derivatives",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_capture_derivatives_sha256",
        "capture_derivatives",
        ["sha256"],
        unique=False,
    )

    op.create_table(
        "capture_quality_assessments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("capture_id", sa.String(length=36), nullable=False),
        sa.Column("derivative_id", sa.String(length=36), nullable=False),
        sa.Column("algorithm_version", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PASS",
                "REVIEW_RECOMMENDED",
                "RETAKE_RECOMMENDED",
                name="capturequalitystatus",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("sharpness_score", sa.Float(), nullable=False),
        sa.Column("brightness_mean", sa.Float(), nullable=False),
        sa.Column("dark_fraction", sa.Float(), nullable=False),
        sa.Column("bright_fraction", sa.Float(), nullable=False),
        sa.Column("glare_fraction", sa.Float(), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("thresholds", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["capture_id"],
            ["captures.id"],
            name="fk_capture_quality_capture_id_captures",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["derivative_id"],
            ["capture_derivatives.id"],
            name="fk_capture_quality_derivative_id_derivatives",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_capture_quality_capture_id",
        "capture_quality_assessments",
        ["capture_id"],
        unique=False,
    )
    op.create_index(
        "ix_capture_quality_created_at",
        "capture_quality_assessments",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_capture_quality_derivative_id",
        "capture_quality_assessments",
        ["derivative_id"],
        unique=False,
    )
    op.create_index(
        "ix_capture_quality_status",
        "capture_quality_assessments",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_capture_quality_status", table_name="capture_quality_assessments")
    op.drop_index(
        "ix_capture_quality_derivative_id",
        table_name="capture_quality_assessments",
    )
    op.drop_index(
        "ix_capture_quality_created_at",
        table_name="capture_quality_assessments",
    )
    op.drop_index(
        "ix_capture_quality_capture_id",
        table_name="capture_quality_assessments",
    )
    op.drop_table("capture_quality_assessments")

    op.drop_index("ix_capture_derivatives_sha256", table_name="capture_derivatives")
    op.drop_index(
        "ix_capture_derivatives_created_at",
        table_name="capture_derivatives",
    )
    op.drop_index(
        "ix_capture_derivatives_capture_id",
        table_name="capture_derivatives",
    )
    op.drop_table("capture_derivatives")
