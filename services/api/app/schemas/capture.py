from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.capture import CaptureViewType


class CaptureRead(BaseModel):
    id: str
    inspection_id: str
    uploader_user_id: str
    view_type: CaptureViewType
    original_filename: str | None
    sha256: str
    mime_type: str
    size_bytes: int
    width_px: int
    height_px: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
