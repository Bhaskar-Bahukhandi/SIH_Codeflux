from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.officer_review import OfficerReviewDecision


class OfficerRuleReviewCreate(BaseModel):
    id: UUID | None = None
    decision: OfficerReviewDecision
    corrected_value: dict | None = None
    note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_decision_payload(self) -> "OfficerRuleReviewCreate":
        note = self.note.strip() if self.note else None
        self.note = note or None

        if self.decision is OfficerReviewDecision.CORRECTED:
            if self.corrected_value is None:
                raise ValueError("corrected_value is required for a corrected review.")
            if not note:
                raise ValueError("note is required for a corrected review.")
        elif self.corrected_value is not None:
            raise ValueError(
                "corrected_value is allowed only when decision is corrected."
            )

        if self.decision is OfficerReviewDecision.RECHECK_REQUIRED and not note:
            raise ValueError("note is required when recheck is requested.")

        return self


class OfficerRuleReviewRead(BaseModel):
    id: str
    inspection_id: str
    officer_user_id: str
    rule_evaluation_run_id: str
    rule_evaluation_result_id: str
    revision: int
    decision: OfficerReviewDecision
    corrected_value: dict | None
    note: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OfficerRuleReviewHistoryRead(BaseModel):
    reviews: list[OfficerRuleReviewRead]
    latest_by_rule_result: dict[str, OfficerRuleReviewRead]
