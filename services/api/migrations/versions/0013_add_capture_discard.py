from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "captures",
        sa.Column("discarded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_captures_discarded_at",
        "captures",
        ["discarded_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_captures_discarded_at", table_name="captures")
    op.drop_column("captures", "discarded_at")
