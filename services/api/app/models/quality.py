from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import DateTime, Enum as SqlEnum, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CaptureQualityStatus(str, Enum):
    PASS = "pass"
    REVIEW_RECOMMENDED = "review_recommended"
    RETAKE_RECOMMENDED = "retake_recommended"


class CaptureDerivative(Base):
    __tablename__ = "capture_derivatives"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    capture_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("captures.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    derivative_type: Mapped[str] = mapped_column(String(64), nullable=False)
    processing_version: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    width_px: Mapped[int] = mapped_column(Integer, nullable=False)
    height_px: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
        index=True,
    )


class CaptureQualityAssessment(Base):
    __tablename__ = "capture_quality_assessments"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    capture_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("captures.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    derivative_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("capture_derivatives.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    algorithm_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[CaptureQualityStatus] = mapped_column(
        SqlEnum(CaptureQualityStatus, native_enum=False),
        nullable=False,
        index=True,
    )
    sharpness_score: Mapped[float] = mapped_column(Float, nullable=False)
    brightness_mean: Mapped[float] = mapped_column(Float, nullable=False)
    dark_fraction: Mapped[float] = mapped_column(Float, nullable=False)
    bright_fraction: Mapped[float] = mapped_column(Float, nullable=False)
    glare_fraction: Mapped[float] = mapped_column(Float, nullable=False)
    reasons: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    thresholds: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
        index=True,
    )
