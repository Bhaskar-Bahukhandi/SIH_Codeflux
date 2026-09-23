from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.declaration import DeclarationFusionStatus, DeclarationType


class DeclarationExtractionRequest(BaseModel):
    id: UUID | None = None


class DeclarationExtractionRunRead(BaseModel):
    id: str
    inspection_id: str
    actor_user_id: str
    extractor_version: str
    fusion_version: str
    inspection_capture_count: int
    source_capture_count: int
    source_capture_ids: list[str]
    source_ocr_run_ids: list[str]
    skipped_sources: list[dict]
    observation_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeclarationObservationRead(BaseModel):
    id: str
    extraction_run_id: str
    declaration_type: DeclarationType
    capture_id: str
    ocr_run_id: str
    raw_text: str
    normalized_value: dict
    ocr_confidence_min: float
    ocr_confidence_mean: float
    extractor_method: str
    source_block_ids: list[str]


class DeclarationSummaryRead(BaseModel):
    id: str
    extraction_run_id: str
    declaration_type: DeclarationType
    status: DeclarationFusionStatus
    canonical_value: dict | None
    candidate_values: list[dict]
    observation_count: int
    capture_count: int

    model_config = ConfigDict(from_attributes=True)


class DeclarationExtractionResultRead(BaseModel):
    run: DeclarationExtractionRunRead
    observations: list[DeclarationObservationRead]
    summaries: list[DeclarationSummaryRead]
