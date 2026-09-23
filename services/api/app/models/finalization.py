from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InspectionFinalization(Base):
    __tablename__ = "inspection_finalizations"
    __table_args__ = (
        CheckConstraint(
            "report_size_bytes > 0",
            name="ck_inspection_finalizations_report_size_positive",
        ),
        UniqueConstraint(
            "inspection_id",
            name="uq_inspection_finalizations_inspection_id",
        ),
        UniqueConstraint(
            "report_id",
            name="uq_inspection_finalizations_report_id",
        ),
        UniqueConstraint(
            "report_storage_key",
            name="uq_inspection_finalizations_report_storage_key",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    inspection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("inspections.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    finalized_by_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    rule_evaluation_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rule_evaluation_runs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    rule_pack_id: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_pack_version: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_pack_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    snapshot_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    report_id: Mapped[str] = mapped_column(String(36), nullable=False)
    report_version: Mapped[str] = mapped_column(String(32), nullable=False)
    report_storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    report_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    report_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    finalized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
        index=True,
    )
