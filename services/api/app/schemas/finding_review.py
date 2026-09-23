from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.finding_review import (
    OfficerReviewDecision,
    OfficerReviewOutcome,
)
from app.schemas.rule_evaluation import (
    RuleEvaluationResultRead,
    RuleEvaluationRunRead,
)


class OfficerFindingReviewCreate(BaseModel):
    rule_evaluation_result_id: str
    decision: OfficerReviewDecision
    corrected_value: dict | None = None
    evidence_capture_ids: list[str] = Field(default_factory=list, max_length=20)
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("evidence_capture_ids")
    @classmethod
    def normalize_capture_ids(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if item.strip()]
        if len(normalized) != len(set(normalized)):
            raise ValueError("evidence_capture_ids must not contain duplicates")
        return normalized

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class OfficerFindingReviewRead(BaseModel):
    id: str
    inspection_id: str
    evaluation_run_id: str
    rule_evaluation_result_id: str
    officer_user_id: str
    decision: OfficerReviewDecision
    outcome: OfficerReviewOutcome
    corrected_value: dict | None
    evidence_capture_ids: list[str]
    note: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FindingReviewItemRead(BaseModel):
    machine_result: RuleEvaluationResultRead
    latest_review: OfficerFindingReviewRead | None


class FindingReviewWorkspaceRead(BaseModel):
    evaluation_run: RuleEvaluationRunRead
    items: list[FindingReviewItemRead]
