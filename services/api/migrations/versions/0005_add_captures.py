"""Add inspection image captures.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-22
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "captures",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("inspection_id", sa.String(length=36), nullable=False),
        sa.Column("uploader_user_id", sa.String(length=36), nullable=False),
        sa.Column(
            "view_type",
            sa.Enum(
                "FRONT",
                "BACK",
                "LEFT",
                "RIGHT",
                "TOP",
                "BOTTOM",
                "DETAIL",
                "OTHER",
                name="captureviewtype",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("width_px", sa.Integer(), nullable=False),
        sa.Column("height_px", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["inspection_id"],
            ["inspections.id"],
            name="fk_captures_inspection_id_inspections",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["uploader_user_id"],
            ["users.id"],
            name="fk_captures_uploader_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key", name="uq_captures_storage_key"),
    )
    op.create_index(
        "ix_captures_created_at",
        "captures",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_captures_inspection_id",
        "captures",
        ["inspection_id"],
        unique=False,
    )
    op.create_index(
        "ix_captures_sha256",
        "captures",
        ["sha256"],
        unique=False,
    )
    op.create_index(
        "ix_captures_uploader_user_id",
        "captures",
        ["uploader_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_captures_uploader_user_id", table_name="captures")
    op.drop_index("ix_captures_sha256", table_name="captures")
    op.drop_index("ix_captures_inspection_id", table_name="captures")
    op.drop_index("ix_captures_created_at", table_name="captures")
    op.drop_table("captures")
