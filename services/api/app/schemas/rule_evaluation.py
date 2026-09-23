from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.rule_evaluation import RuleEvaluationStatus


class RuleEvaluationContextInput(BaseModel):
    intended_for_retail_sale: bool | None = None
    industrial_or_institutional_consumer: bool | None = None
    package_exceeds_25kg_or_25l: bool | None = None


class RuleEvaluationRequest(BaseModel):
    id: UUID | None = None
    context: RuleEvaluationContextInput


class RuleEvaluationRunRead(BaseModel):
    id: str
    inspection_id: str
    actor_user_id: str
    source_extraction_run_id: str
    rule_pack_id: str
    rule_pack_version: str
    rule_pack_sha256: str
    rule_pack_snapshot: dict
    context_snapshot: dict
    result_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RuleEvaluationResultRead(BaseModel):
    id: str
    evaluation_run_id: str
    rule_id: str
    provision: str
    declaration_type: str
    status: RuleEvaluationStatus
    evidence_summary_id: str | None
    explanation: str
    details: dict

    model_config = ConfigDict(from_attributes=True)


class RuleEvaluationResponse(BaseModel):
    run: RuleEvaluationRunRead
    results: list[RuleEvaluationResultRead]
