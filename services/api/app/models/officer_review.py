from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OfficerReviewDecision(str, Enum):
    ACCEPTED = "accepted"
    CORRECTED = "corrected"
    RECHECK_REQUIRED = "recheck_required"


class OfficerRuleReview(Base):
    __tablename__ = "officer_rule_reviews"
    __table_args__ = (
        UniqueConstraint(
            "rule_evaluation_result_id",
            "revision",
            name="uq_officer_rule_reviews_result_revision",
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
    officer_user_id: Mapped[str] = mapped_column(
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
    rule_evaluation_result_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rule_evaluation_results.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    decision: Mapped[OfficerReviewDecision] = mapped_column(
        SqlEnum(OfficerReviewDecision, native_enum=False),
        nullable=False,
        index=True,
    )
    corrected_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
        index=True,
    )
