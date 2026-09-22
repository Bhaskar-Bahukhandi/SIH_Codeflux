"""Add capture geometry assessments.

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-23
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "capture_geometry_assessments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("capture_id", sa.String(length=36), nullable=False),
        sa.Column("source_derivative_id", sa.String(length=36), nullable=False),
        sa.Column("corrected_derivative_id", sa.String(length=36), nullable=True),
        sa.Column("algorithm_version", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "NOT_DETECTED",
                "REVIEW_RECOMMENDED",
                "CORRECTION_AVAILABLE",
                name="geometrystatus",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("corners", sa.JSON(), nullable=True),
        sa.Column("area_ratio", sa.Float(), nullable=True),
        sa.Column("angle_score", sa.Float(), nullable=True),
        sa.Column("geometry_score", sa.Float(), nullable=True),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("thresholds", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["capture_id"],
            ["captures.id"],
            name="fk_capture_geometry_capture_id_captures",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_derivative_id"],
            ["capture_derivatives.id"],
            name="fk_capture_geometry_source_derivative_id_derivatives",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["corrected_derivative_id"],
            ["capture_derivatives.id"],
            name="fk_capture_geometry_corrected_derivative_id_derivatives",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_capture_geometry_capture_id",
        "capture_geometry_assessments",
        ["capture_id"],
        unique=False,
    )
    op.create_index(
        "ix_capture_geometry_source_derivative_id",
        "capture_geometry_assessments",
        ["source_derivative_id"],
        unique=False,
    )
    op.create_index(
        "ix_capture_geometry_corrected_derivative_id",
        "capture_geometry_assessments",
        ["corrected_derivative_id"],
        unique=False,
    )
    op.create_index(
        "ix_capture_geometry_status",
        "capture_geometry_assessments",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_capture_geometry_created_at",
        "capture_geometry_assessments",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_capture_geometry_created_at",
        table_name="capture_geometry_assessments",
    )
    op.drop_index(
        "ix_capture_geometry_status",
        table_name="capture_geometry_assessments",
    )
    op.drop_index(
        "ix_capture_geometry_corrected_derivative_id",
        table_name="capture_geometry_assessments",
    )
    op.drop_index(
        "ix_capture_geometry_source_derivative_id",
        table_name="capture_geometry_assessments",
    )
    op.drop_index(
        "ix_capture_geometry_capture_id",
        table_name="capture_geometry_assessments",
    )
    op.drop_table("capture_geometry_assessments")
