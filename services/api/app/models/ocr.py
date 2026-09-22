from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
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


class OcrRun(Base):
    __tablename__ = "ocr_runs"
    __table_args__ = (
        CheckConstraint("block_count >= 0", name="ck_ocr_runs_block_count_nonnegative"),
    )

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
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    engine_name: Mapped[str] = mapped_column(String(100), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    language: Mapped[str] = mapped_column(String(32), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    block_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
        index=True,
    )


class OcrBlock(Base):
    __tablename__ = "ocr_blocks"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "order_index",
            name="uq_ocr_blocks_run_order",
        ),
        CheckConstraint(
            "order_index >= 0",
            name="ck_ocr_blocks_order_nonnegative",
        ),
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_ocr_blocks_confidence_range",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ocr_runs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    polygon: Mapped[list[list[float]]] = mapped_column(JSON, nullable=False)
