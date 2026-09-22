from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.quality import CaptureQualityStatus


class CaptureDerivativeRead(BaseModel):
    id: str
    capture_id: str
    derivative_type: str
    processing_version: str
    sha256: str
    mime_type: str
    size_bytes: int
    width_px: int
    height_px: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CaptureQualityAssessmentRead(BaseModel):
    id: str
    capture_id: str
    derivative_id: str
    algorithm_version: str
    status: CaptureQualityStatus
    sharpness_score: float
    brightness_mean: float
    dark_fraction: float
    bright_fraction: float
    glare_fraction: float
    reasons: list[str]
    thresholds: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CaptureProcessingResult(BaseModel):
    derivative: CaptureDerivativeRead
    quality: CaptureQualityAssessmentRead
