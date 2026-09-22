from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RuleEvaluationStatus(str, Enum):
    PASS = "pass"
    POTENTIAL_NON_COMPLIANCE = "potential_non_compliance"
    INDETERMINATE = "indeterminate"
    NOT_APPLICABLE = "not_applicable"
    MANUAL_VERIFICATION_REQUIRED = "manual_verification_required"
    NOT_EVALUATED = "not_evaluated"


class RuleEvaluationRun(Base):
    __tablename__ = "rule_evaluation_runs"
    __table_args__ = (
        CheckConstraint(
            "result_count >= 0",
            name="ck_rule_evaluation_runs_result_count_nonnegative",
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
    actor_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source_extraction_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("declaration_extraction_runs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    rule_pack_id: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_pack_version: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_pack_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    context_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
        index=True,
    )


class RuleEvaluationResult(Base):
    __tablename__ = "rule_evaluation_results"
    __table_args__ = (
        UniqueConstraint(
            "evaluation_run_id",
            "rule_id",
            name="uq_rule_evaluation_result_run_rule",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    evaluation_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rule_evaluation_runs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    rule_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    provision: Mapped[str] = mapped_column(String(100), nullable=False)
    declaration_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[RuleEvaluationStatus] = mapped_column(
        SqlEnum(RuleEvaluationStatus, native_enum=False),
        nullable=False,
        index=True,
    )
    evidence_summary_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("declaration_summaries.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
