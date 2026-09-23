from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_officer
from app.db import get_db
from app.errors import conflict, not_found
from app.models.audit import AuditEventType
from app.models.officer_review import OfficerReviewDecision, OfficerRuleReview
from app.models.rule_evaluation import RuleEvaluationResult, RuleEvaluationRun
from app.models.user import User
from app.schemas.officer_review import (
    OfficerRuleReviewCreate,
    OfficerRuleReviewHistoryRead,
    OfficerRuleReviewRead,
)
from app.services.audit import record_inspection_event
from app.services.inspection_access import get_visible_inspection_or_raise
from app.services.inspection_lifecycle import require_pending_review
from app.services.officer_review_state import (
    latest_officer_reviews_by_result,
    latest_rule_evaluation_run,
)
from app.services.officer_review_validation import normalize_officer_corrected_value

router = APIRouter(
    prefix="/inspections/{inspection_id}/rule-reviews",
    tags=["officer-rule-reviews"],
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
    require_pending_review(inspection)

    latest_run = latest_rule_evaluation_run(
        db,
        inspection_id=inspection.id,
    )
    if latest_run is None:
        raise conflict(
            "rule_evaluation_required",
            "A preliminary rule evaluation is required before officer review.",
        )

    result = db.scalar(
        select(RuleEvaluationResult)
        .where(RuleEvaluationResult.id == rule_evaluation_result_id)
        .with_for_update()
    )
    if result is None or result.evaluation_run_id != latest_run.id:
        raise not_found(
            "rule_evaluation_result_not_found",
            "Rule evaluation result not found in the latest inspection evaluation.",
        )

    corrected_value = payload.corrected_value
    if payload.decision is OfficerReviewDecision.CORRECTED:
        corrected_value = normalize_officer_corrected_value(
            declaration_type=result.declaration_type,
            value=payload.corrected_value or {},
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
        corrected_value=corrected_value,
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

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise conflict(
            "officer_review_revision_conflict",
            "The review changed concurrently. Reload the review history and retry.",
        )

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

    latest_by_result = latest_officer_reviews_by_result(
        db,
        inspection_id=inspection.id,
    )

    return {
        "reviews": reviews,
        "latest_by_rule_result": latest_by_result,
    }
