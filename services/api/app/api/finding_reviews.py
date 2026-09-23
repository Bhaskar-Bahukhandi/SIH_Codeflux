from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_officer
from app.db import get_db
from app.errors import conflict, not_found
from app.models.audit import AuditEventType
from app.models.finding_review import OfficerFindingReview
from app.models.rule_evaluation import RuleEvaluationResult
from app.models.user import User
from app.schemas.finding_review import (
    FindingReviewWorkspaceRead,
    OfficerFindingReviewCreate,
    OfficerFindingReviewRead,
)
from app.services.audit import record_inspection_event
from app.services.finding_review import (
    resolve_review,
    validate_evidence_captures,
)
from app.services.inspection_access import get_visible_inspection_or_raise
from app.services.inspection_lifecycle import require_draft
from app.services.rule_evaluation_access import (
    assert_rule_evaluation_is_latest_and_current,
    get_rule_evaluation_run_or_raise,
    latest_rule_evaluation_run,
)

router = APIRouter(
    prefix="/inspections/{inspection_id}/finding-reviews",
    tags=["finding-reviews"],
)


def _result_or_raise(
    db: Session,
    *,
    evaluation_run_id: str,
    result_id: str,
) -> RuleEvaluationResult:
    result = db.get(RuleEvaluationResult, result_id)
    if result is None or result.evaluation_run_id != evaluation_run_id:
        raise not_found(
            "rule_evaluation_result_not_found",
            "Rule evaluation result not found.",
        )
    return result


@router.post(
    "",
    response_model=OfficerFindingReviewRead,
    status_code=status.HTTP_201_CREATED,
)
def create_finding_review(
    inspection_id: str,
    payload: OfficerFindingReviewCreate,
    db: Session = Depends(get_db),
    officer: User = Depends(require_officer),
) -> OfficerFindingReview:
    inspection = get_visible_inspection_or_raise(db, inspection_id, officer)
    require_draft(inspection)

    evaluation_run = latest_rule_evaluation_run(
        db,
        inspection_id=inspection.id,
    )
    if evaluation_run is None:
        raise conflict(
            "current_rule_evaluation_required",
            "Run the current rule evaluation before officer review.",
        )

    assert_rule_evaluation_is_latest_and_current(
        db,
        inspection_id=inspection.id,
        evaluation_run=evaluation_run,
    )

    machine_result = _result_or_raise(
        db,
        evaluation_run_id=evaluation_run.id,
        result_id=payload.rule_evaluation_result_id,
    )

    validate_evidence_captures(
        db,
        inspection_id=inspection.id,
        capture_ids=payload.evidence_capture_ids,
    )
    outcome, normalized_correction = resolve_review(
        machine_result=machine_result,
        decision=payload.decision,
        corrected_value=payload.corrected_value,
        evidence_capture_ids=payload.evidence_capture_ids,
        note=payload.note,
    )

    review = OfficerFindingReview(
        inspection_id=inspection.id,
        evaluation_run_id=evaluation_run.id,
        rule_evaluation_result_id=machine_result.id,
        officer_user_id=officer.id,
        decision=payload.decision,
        outcome=outcome,
        corrected_value=normalized_correction,
        evidence_capture_ids=payload.evidence_capture_ids,
        note=payload.note,
    )
    db.add(review)
    db.flush()

    record_inspection_event(
        db,
        inspection_id=inspection.id,
        actor_user_id=officer.id,
        event_type=AuditEventType.FINDING_REVIEW_RECORDED,
        details={
            "finding_review_id": review.id,
            "evaluation_run_id": evaluation_run.id,
            "rule_evaluation_result_id": machine_result.id,
            "rule_id": machine_result.rule_id,
            "machine_status": machine_result.status.value,
            "decision": review.decision.value,
            "outcome": review.outcome.value,
            "evidence_capture_ids": review.evidence_capture_ids,
            "has_corrected_value": review.corrected_value is not None,
        },
    )

    db.commit()
    db.refresh(review)
    return review


@router.get("/latest", response_model=FindingReviewWorkspaceRead)
def latest_finding_review_workspace(
    inspection_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    inspection = get_visible_inspection_or_raise(db, inspection_id, user)

    evaluation_run = latest_rule_evaluation_run(
        db,
        inspection_id=inspection.id,
    )
    if evaluation_run is None:
        raise not_found(
            "rule_evaluation_not_found",
            "No rule evaluation exists for this inspection.",
        )

    machine_results = list(
        db.scalars(
            select(RuleEvaluationResult)
            .where(
                RuleEvaluationResult.evaluation_run_id
                == evaluation_run.id
            )
            .order_by(
                RuleEvaluationResult.rule_id.asc(),
                RuleEvaluationResult.id.asc(),
            )
        ).all()
    )

    reviews = list(
        db.scalars(
            select(OfficerFindingReview)
            .where(
                OfficerFindingReview.evaluation_run_id
                == evaluation_run.id
            )
            .order_by(
                OfficerFindingReview.created_at.desc(),
                OfficerFindingReview.id.desc(),
            )
        ).all()
    )
    latest_by_result: dict[str, OfficerFindingReview] = {}
    for review in reviews:
        latest_by_result.setdefault(
            review.rule_evaluation_result_id,
            review,
        )

    return {
        "evaluation_run": evaluation_run,
        "items": [
            {
                "machine_result": result,
                "latest_review": latest_by_result.get(result.id),
            }
            for result in machine_results
        ],
    }


@router.get(
    "/{rule_evaluation_result_id}/history",
    response_model=list[OfficerFindingReviewRead],
)
def finding_review_history(
    inspection_id: str,
    rule_evaluation_result_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[OfficerFindingReview]:
    inspection = get_visible_inspection_or_raise(db, inspection_id, user)

    result = db.get(RuleEvaluationResult, rule_evaluation_result_id)
    if result is None:
        raise not_found(
            "rule_evaluation_result_not_found",
            "Rule evaluation result not found.",
        )

    evaluation_run = get_rule_evaluation_run_or_raise(
        db,
        inspection_id=inspection.id,
        evaluation_run_id=result.evaluation_run_id,
    )

    return list(
        db.scalars(
            select(OfficerFindingReview)
            .where(
                OfficerFindingReview.evaluation_run_id
                == evaluation_run.id,
                OfficerFindingReview.rule_evaluation_result_id
                == result.id,
            )
            .order_by(
                OfficerFindingReview.created_at.asc(),
                OfficerFindingReview.id.asc(),
            )
        ).all()
    )
