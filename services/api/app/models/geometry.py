from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import DateTime, Enum as SqlEnum, Float, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GeometryStatus(str, Enum):
    NOT_DETECTED = "not_detected"
    REVIEW_RECOMMENDED = "review_recommended"
    CORRECTION_AVAILABLE = "correction_available"


class CaptureGeometryAssessment(Base):
    __tablename__ = "capture_geometry_assessments"

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
    source_derivative_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("capture_derivatives.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    corrected_derivative_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("capture_derivatives.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    algorithm_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[GeometryStatus] = mapped_column(
        SqlEnum(GeometryStatus, native_enum=False),
        nullable=False,
        index=True,
    )
    corners: Mapped[list[list[float]] | None] = mapped_column(JSON, nullable=True)
    area_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    angle_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    geometry_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reasons: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    thresholds: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
        index=True,
    )
