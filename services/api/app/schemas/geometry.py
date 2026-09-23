from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from app.models.geometry import GeometryStatus
from app.schemas.quality import CaptureDerivativeRead


class GeometryAnalysisRequest(BaseModel):
    geometry_assessment_id: UUID | None = None
    corrected_derivative_id: UUID | None = None

    @model_validator(mode="after")
    def validate_stable_identity_pair(self) -> "GeometryAnalysisRequest":
        has_geometry = self.geometry_assessment_id is not None
        has_corrected = self.corrected_derivative_id is not None
        if has_geometry != has_corrected:
            raise ValueError(
                "geometry_assessment_id and corrected_derivative_id must be supplied together."
            )
        return self


class CaptureGeometryAssessmentRead(BaseModel):
    id: str
    capture_id: str
    source_derivative_id: str
    corrected_derivative_id: str | None
    algorithm_version: str
    status: GeometryStatus
    corners: list[list[float]] | None
    area_ratio: float | None
    angle_score: float | None
    geometry_score: float | None
    reasons: list[str]
    thresholds: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GeometryAnalysisResult(BaseModel):
    geometry: CaptureGeometryAssessmentRead
    corrected_derivative: CaptureDerivativeRead | None
