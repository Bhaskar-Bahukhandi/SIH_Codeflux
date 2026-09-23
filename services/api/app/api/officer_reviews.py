from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_officer
from app.db import get_db
from app.errors import conflict, not_found
from app.models.audit import AuditEventType
from app.models.inspection import InspectionStatus
from app.models.officer_review import OfficerRuleReview
from app.models.rule_evaluation import RuleEvaluationResult, RuleEvaluationRun
from app.models.user import User
from app.schemas.officer_review import (
    OfficerRuleReviewCreate,
    OfficerRuleReviewHistoryRead,
    OfficerRuleReviewRead,
)
from app.services.audit import record_inspection_event
from app.services.inspection_access import get_visible_inspection_or_raise

router = APIRouter(
    prefix="/inspections/{inspection_id}/rule-reviews",
    tags=["officer-rule-reviews"],
)


def _require_pending_review(inspection_status: InspectionStatus) -> None:
    if inspection_status is not InspectionStatus.PENDING_REVIEW:
        raise conflict(
            "inspection_not_pending_review",
            "Officer rule review is available only after the inspection is submitted for review.",
        )


def _latest_rule_evaluation_run(
    db: Session,
    *,
    inspection_id: str,
) -> RuleEvaluationRun | None:
    return db.scalar(
        select(RuleEvaluationRun)
        .where(RuleEvaluationRun.inspection_id == inspection_id)
        .order_by(
            RuleEvaluationRun.created_at.desc(),
            RuleEvaluationRun.id.desc(),
        )
        .limit(1)
    )


@router.post(
    "/{rule_evaluation_result_id}",
    response_model=OfficerRuleReviewRead,
)
def review_rule_result(
    inspection_id: str,
    rule_evaluation_result_id: str,
    payload: OfficerRuleReviewCreate,
    db: Session = Depends(get_db),
    officer: User = Depends(require_officer),
) -> OfficerRuleReview:
    inspection = get_visible_inspection_or_raise(db, inspection_id, officer)
    _require_pending_review(inspection.status)

    latest_run = _latest_rule_evaluation_run(
        db,
        inspection_id=inspection.id,
    )
    if latest_run is None:
        raise conflict(
            "rule_evaluation_required",
            "A preliminary rule evaluation is required before officer review.",
        )

    result = db.get(RuleEvaluationResult, rule_evaluation_result_id)
    if (
        result is None
        or result.evaluation_run_id != latest_run.id
    ):
        raise not_found(
            "rule_evaluation_result_not_found",
            "Rule evaluation result not found in the latest inspection evaluation.",
        )

    latest_revision = db.scalar(
        select(func.max(OfficerRuleReview.revision)).where(
            OfficerRuleReview.rule_evaluation_result_id == result.id
        )
    )
    revision = (latest_revision or 0) + 1

    review = OfficerRuleReview(
        inspection_id=inspection.id,
        officer_user_id=officer.id,
        rule_evaluation_run_id=latest_run.id,
        rule_evaluation_result_id=result.id,
        revision=revision,
        decision=payload.decision,
        corrected_value=payload.corrected_value,
        note=payload.note,
    )
    db.add(review)
    db.flush()

    record_inspection_event(
        db,
        inspection_id=inspection.id,
        actor_user_id=officer.id,
        event_type=AuditEventType.OFFICER_RULE_REVIEW_RECORDED,
        details={
            "review_id": review.id,
            "rule_evaluation_run_id": latest_run.id,
            "rule_evaluation_result_id": result.id,
            "rule_id": result.rule_id,
            "revision": review.revision,
            "decision": review.decision.value,
        },
    )

    db.commit()
    db.refresh(review)
    return review


@router.get(
    "",
    response_model=OfficerRuleReviewHistoryRead,
)
def list_rule_reviews(
    inspection_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    inspection = get_visible_inspection_or_raise(db, inspection_id, user)

    reviews = list(
        db.scalars(
            select(OfficerRuleReview)
            .where(OfficerRuleReview.inspection_id == inspection.id)
            .order_by(
                OfficerRuleReview.created_at.asc(),
                OfficerRuleReview.id.asc(),
            )
        ).all()
    )

    latest_by_result: dict[str, OfficerRuleReview] = {}
    for review in reviews:
        current = latest_by_result.get(review.rule_evaluation_result_id)
        if current is None or review.revision > current.revision:
            latest_by_result[review.rule_evaluation_result_id] = review

    return {
        "reviews": reviews,
        "latest_by_rule_result": latest_by_result,
    }
