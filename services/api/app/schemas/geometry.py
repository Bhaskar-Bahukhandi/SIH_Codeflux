from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.geometry import GeometryStatus
from app.schemas.quality import CaptureDerivativeRead


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
