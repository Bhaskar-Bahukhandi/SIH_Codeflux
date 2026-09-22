from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import DateTime, Enum as SqlEnum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InspectionStatus(str, Enum):
    DRAFT = "draft"
    FINALIZED = "finalized"


class Inspection(Base):
    __tablename__ = "inspections"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    product_identifier: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[InspectionStatus] = mapped_column(
        SqlEnum(InspectionStatus, native_enum=False),
        default=InspectionStatus.DRAFT,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )
