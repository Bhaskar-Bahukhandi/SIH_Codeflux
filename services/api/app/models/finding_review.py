from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OfficerReviewDecision(str, Enum):
    CONFIRM_PRESENT = "confirm_present"
    CONFIRM_ABSENT = "confirm_absent"
    CORRECT_VALUE = "correct_value"
    REQUEST_RECHECK = "request_recheck"


class OfficerReviewOutcome(str, Enum):
    VERIFIED_DECLARATION_PRESENT = "verified_declaration_present"
    POTENTIAL_NON_COMPLIANCE = "potential_non_compliance"
    RECHECK_REQUIRED = "recheck_required"


class OfficerFindingReview(Base):
    __tablename__ = "officer_finding_reviews"

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
    evaluation_run_id: Mapped[str] = mapped_column(
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
    officer_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    decision: Mapped[OfficerReviewDecision] = mapped_column(
        SqlEnum(OfficerReviewDecision, native_enum=False),
        nullable=False,
        index=True,
    )
    outcome: Mapped[OfficerReviewOutcome] = mapped_column(
        SqlEnum(OfficerReviewOutcome, native_enum=False),
        nullable=False,
        index=True,
    )
    corrected_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evidence_capture_ids: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
        index=True,
    )
