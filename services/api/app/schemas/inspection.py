from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.inspection import InspectionStatus


class InspectionCreate(BaseModel):
    product_name: str = Field(min_length=1, max_length=200)
    product_identifier: str | None = Field(default=None, max_length=200)


class InspectionRead(BaseModel):
    id: str
    product_name: str
    product_identifier: str | None
    status: InspectionStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
