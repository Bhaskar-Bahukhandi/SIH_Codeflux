from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.inspection import InspectionStatus


class InspectionCreate(BaseModel):
    id: UUID | None = None
    product_name: str = Field(min_length=1, max_length=200)
    product_identifier: str | None = Field(default=None, max_length=200)

    @field_validator("product_name")
    @classmethod
    def normalize_product_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("product_name must not be blank")
        return normalized

    @field_validator("product_identifier")
    @classmethod
    def normalize_product_identifier(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class InspectionUpdate(BaseModel):
    product_name: str | None = Field(default=None, min_length=1, max_length=200)
    product_identifier: str | None = Field(default=None, max_length=200)

    @field_validator("product_name")
    @classmethod
    def normalize_product_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("product_name must not be blank")
        return normalized

    @field_validator("product_identifier")
    @classmethod
    def normalize_product_identifier(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class InspectionRead(BaseModel):
    id: str
    product_name: str
    product_identifier: str | None
    officer_id: str | None
    status: InspectionStatus
    submitted_at: datetime | None
    reopened_for_recheck_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
