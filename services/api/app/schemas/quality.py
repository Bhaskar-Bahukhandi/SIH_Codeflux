from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from app.models.quality import CaptureQualityStatus


class CaptureProcessingRequest(BaseModel):
    derivative_id: UUID | None = None
    quality_assessment_id: UUID | None = None

    @model_validator(mode="after")
    def validate_stable_identity_pair(self) -> "CaptureProcessingRequest":
        has_derivative = self.derivative_id is not None
        has_quality = self.quality_assessment_id is not None
        if has_derivative != has_quality:
            raise ValueError(
                "derivative_id and quality_assessment_id must be supplied together."
            )
        return self


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
