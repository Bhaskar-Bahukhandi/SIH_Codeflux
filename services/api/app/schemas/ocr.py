from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OcrBlockRead(BaseModel):
    id: str
    run_id: str
    order_index: int
    text: str
    confidence: float
    polygon: list[list[float]]

    model_config = ConfigDict(from_attributes=True)


class OcrRunRead(BaseModel):
    id: str
    capture_id: str
    source_derivative_id: str
    source_sha256: str
    engine_name: str
    engine_version: str
    model_version: str
    language: str
    parameters: dict
    block_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OcrResultRead(BaseModel):
    run: OcrRunRead
    blocks: list[OcrBlockRead]
