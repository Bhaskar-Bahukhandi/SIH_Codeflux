from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SqlEnum,
    Float,
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


class DeclarationType(str, Enum):
    MRP = "mrp"
    NET_QUANTITY = "net_quantity"


class DeclarationFusionStatus(str, Enum):
    NOT_DETECTED = "not_detected"
    SINGLE_SOURCE = "single_source"
    CONSISTENT = "consistent"
    CONFLICT = "conflict"


class DeclarationExtractionRun(Base):
    __tablename__ = "declaration_extraction_runs"
    __table_args__ = (
        CheckConstraint(
            "inspection_capture_count >= 0",
            name="ck_declaration_runs_capture_count_nonnegative",
        ),
        CheckConstraint(
            "source_capture_count >= 0",
            name="ck_declaration_runs_source_capture_count_nonnegative",
        ),
        CheckConstraint(
            "observation_count >= 0",
            name="ck_declaration_runs_observation_count_nonnegative",
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
    extractor_version: Mapped[str] = mapped_column(String(64), nullable=False)
    fusion_version: Mapped[str] = mapped_column(String(64), nullable=False)
    inspection_capture_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_capture_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_capture_ids: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    source_ocr_run_ids: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    skipped_sources: Mapped[list[dict]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
        index=True,
    )


class DeclarationObservation(Base):
    __tablename__ = "declaration_observations"
    __table_args__ = (
        CheckConstraint(
            "ocr_confidence_min >= 0.0 AND ocr_confidence_min <= 1.0",
            name="ck_declaration_obs_conf_min_range",
        ),
        CheckConstraint(
            "ocr_confidence_mean >= 0.0 AND ocr_confidence_mean <= 1.0",
            name="ck_declaration_obs_conf_mean_range",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    extraction_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("declaration_extraction_runs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    declaration_type: Mapped[DeclarationType] = mapped_column(
        SqlEnum(DeclarationType, native_enum=False),
        nullable=False,
        index=True,
    )
    capture_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("captures.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    ocr_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ocr_runs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_value: Mapped[dict] = mapped_column(JSON, nullable=False)
    ocr_confidence_min: Mapped[float] = mapped_column(Float, nullable=False)
    ocr_confidence_mean: Mapped[float] = mapped_column(Float, nullable=False)
    extractor_method: Mapped[str] = mapped_column(String(100), nullable=False)


class DeclarationObservationBlock(Base):
    __tablename__ = "declaration_observation_blocks"
    __table_args__ = (
        UniqueConstraint(
            "observation_id",
            "ocr_block_id",
            name="uq_declaration_observation_block",
        ),
        CheckConstraint(
            "block_order >= 0",
            name="ck_declaration_observation_block_order_nonnegative",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    observation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("declaration_observations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    ocr_block_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ocr_blocks.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    block_order: Mapped[int] = mapped_column(Integer, nullable=False)


class DeclarationSummary(Base):
    __tablename__ = "declaration_summaries"
    __table_args__ = (
        UniqueConstraint(
            "extraction_run_id",
            "declaration_type",
            name="uq_declaration_summary_run_type",
        ),
        CheckConstraint(
            "observation_count >= 0",
            name="ck_declaration_summary_observation_count_nonnegative",
        ),
        CheckConstraint(
            "capture_count >= 0",
            name="ck_declaration_summary_capture_count_nonnegative",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    extraction_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("declaration_extraction_runs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    declaration_type: Mapped[DeclarationType] = mapped_column(
        SqlEnum(DeclarationType, native_enum=False),
        nullable=False,
        index=True,
    )
    status: Mapped[DeclarationFusionStatus] = mapped_column(
        SqlEnum(DeclarationFusionStatus, native_enum=False),
        nullable=False,
        index=True,
    )
    canonical_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    candidate_values: Mapped[list[dict]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    capture_count: Mapped[int] = mapped_column(Integer, nullable=False)
