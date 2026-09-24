from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_officer
from app.db import get_db
from app.errors import conflict
from app.models.audit import AuditEventType
from app.models.inspection import Inspection, InspectionStatus
from app.models.officer_review import OfficerReviewDecision
from app.models.user import User, UserRole
from app.schemas.inspection import InspectionCreate, InspectionRead, InspectionUpdate
from app.services.audit import record_inspection_event
from app.services.inspection_access import get_visible_inspection_or_raise
from app.services.inspection_lifecycle import (
    discard_draft,
    reopen_for_recheck,
    require_draft,
    require_pending_review,
    submit_for_review,
)
from app.services.officer_review_state import (
    has_current_rule_evaluation_after,
    latest_officer_reviews_by_result,
    latest_rule_evaluation_run,
)

router = APIRouter(prefix="/inspections", tags=["inspections"])


def _matches_create_replay(
    inspection: Inspection,
    *,
    officer_id: str,
    payload: InspectionCreate,
) -> bool:
    return (
        inspection.officer_id == officer_id
        and inspection.product_name == payload.product_name
        and inspection.product_identifier == payload.product_identifier
    )


def _raise_client_id_conflict() -> None:
    raise conflict(
        "client_resource_id_conflict",
        "The supplied client resource ID is already associated with different inspection data.",
    )


@router.post("", response_model=InspectionRead, status_code=status.HTTP_201_CREATED)
def create_inspection(
    payload: InspectionCreate,
    db: Session = Depends(get_db),
    officer: User = Depends(require_officer),
) -> Inspection:
    client_id = str(payload.id) if payload.id is not None else None

    if client_id is not None:
        existing = db.get(Inspection, client_id)
        if existing is not None:
            if _matches_create_replay(
                existing,
                officer_id=officer.id,
                payload=payload,
            ):
                return existing
            _raise_client_id_conflict()

    inspection_kwargs = {
        "product_name": payload.product_name,
        "product_identifier": payload.product_identifier,
        "officer_id": officer.id,
    }
    if client_id is not None:
        inspection_kwargs["id"] = client_id

    inspection = Inspection(**inspection_kwargs)
    db.add(inspection)

    try:
        db.flush()

        record_inspection_event(
            db,
            inspection_id=inspection.id,
            actor_user_id=officer.id,
            event_type=AuditEventType.INSPECTION_CREATED,
            details={"status": inspection.status.value},
        )

        db.commit()
    except IntegrityError:
        db.rollback()
        if client_id is not None:
            existing = db.get(Inspection, client_id)
            if existing is not None:
                if _matches_create_replay(
                    existing,
                    officer_id=officer.id,
                    payload=payload,
                ):
                    return existing
                _raise_client_id_conflict()
        raise

    db.refresh(inspection)
    return inspection


@router.get("", response_model=list[InspectionRead])
def list_inspections(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Inspection]:
    statement = (
        select(Inspection)
        .where(Inspection.status != InspectionStatus.DISCARDED)
        .order_by(Inspection.created_at.desc())
    )
    if user.role is UserRole.OFFICER:
        statement = statement.where(Inspection.officer_id == user.id)
    return list(db.scalars(statement).all())


@router.get("/{inspection_id}", response_model=InspectionRead)
def get_inspection(
    inspection_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Inspection:
    return get_visible_inspection_or_raise(db, inspection_id, user)


@router.patch("/{inspection_id}", response_model=InspectionRead)
def update_draft_inspection(
    inspection_id: str,
    payload: InspectionUpdate,
    db: Session = Depends(get_db),
    officer: User = Depends(require_officer),
) -> Inspection:
    inspection = get_visible_inspection_or_raise(db, inspection_id, officer)
    require_draft(inspection)

    changes: dict[str, dict[str, str | None]] = {}
    fields_set = payload.model_fields_set

    if "product_name" in fields_set and payload.product_name is not None:
        if inspection.product_name != payload.product_name:
            changes["product_name"] = {
                "from": inspection.product_name,
                "to": payload.product_name,
            }
            inspection.product_name = payload.product_name

    if "product_identifier" in fields_set:
        if inspection.product_identifier != payload.product_identifier:
            changes["product_identifier"] = {
                "from": inspection.product_identifier,
                "to": payload.product_identifier,
            }
            inspection.product_identifier = payload.product_identifier

    if changes:
        record_inspection_event(
            db,
            inspection_id=inspection.id,
            actor_user_id=officer.id,
            event_type=AuditEventType.INSPECTION_UPDATED,
            details={"changes": changes},
        )

    db.commit()
    db.refresh(inspection)
    return inspection


@router.post("/{inspection_id}/discard", response_model=InspectionRead)
def discard_inspection(
    inspection_id: str,
    db: Session = Depends(get_db),
    officer: User = Depends(require_officer),
) -> Inspection:
    inspection = get_visible_inspection_or_raise(db, inspection_id, officer)
    if inspection.status is InspectionStatus.DISCARDED:
        return inspection

    previous_status = inspection.status.value
    discard_draft(inspection)

    record_inspection_event(
        db,
        inspection_id=inspection.id,
        actor_user_id=officer.id,
        event_type=AuditEventType.INSPECTION_DISCARDED,
        details={
            "from_status": previous_status,
            "to_status": inspection.status.value,
        },
    )

    db.commit()
    db.refresh(inspection)
    return inspection


@router.post("/{inspection_id}/submit", response_model=InspectionRead)
def submit_inspection_for_review(
    inspection_id: str,
    db: Session = Depends(get_db),
    officer: User = Depends(require_officer),
) -> Inspection:
    inspection = get_visible_inspection_or_raise(db, inspection_id, officer)
    if (
        inspection.reopened_for_recheck_at is not None
        and not has_current_rule_evaluation_after(
            db,
            inspection_id=inspection.id,
            after=inspection.reopened_for_recheck_at,
        )
    ):
        raise conflict(
            "fresh_rule_evaluation_required",
            "Run a new preliminary rule evaluation after reopening for recheck before submitting again.",
        )

    previous_status = inspection.status.value
    submit_for_review(inspection)

    record_inspection_event(
        db,
        inspection_id=inspection.id,
        actor_user_id=officer.id,
        event_type=AuditEventType.INSPECTION_SUBMITTED,
        details={
            "from_status": previous_status,
            "to_status": inspection.status.value,
        },
    )

    db.commit()
    db.refresh(inspection)
    return inspection


@router.post("/{inspection_id}/reopen-for-recheck", response_model=InspectionRead)
def reopen_inspection_for_recheck(
    inspection_id: str,
    db: Session = Depends(get_db),
    officer: User = Depends(require_officer),
) -> Inspection:
    inspection = get_visible_inspection_or_raise(db, inspection_id, officer)
    require_pending_review(inspection)

    latest_run = latest_rule_evaluation_run(
        db,
        inspection_id=inspection.id,
    )
    if latest_run is None:
        raise conflict(
            "rule_evaluation_required",
            "A preliminary rule evaluation is required before reopening for recheck.",
        )

    latest_reviews = latest_officer_reviews_by_result(
        db,
        inspection_id=inspection.id,
        rule_evaluation_run_id=latest_run.id,
    )
    recheck_reviews = [
        review
        for review in latest_reviews.values()
        if review.decision is OfficerReviewDecision.RECHECK_REQUIRED
    ]
    if not recheck_reviews:
        raise conflict(
            "recheck_review_required",
            "Record a latest Officer review with recheck_required before reopening the inspection.",
        )

    previous_status = inspection.status.value
    reopen_for_recheck(inspection)

    record_inspection_event(
        db,
        inspection_id=inspection.id,
        actor_user_id=officer.id,
        event_type=AuditEventType.INSPECTION_REOPENED_FOR_RECHECK,
        details={
            "from_status": previous_status,
            "to_status": inspection.status.value,
            "rule_evaluation_run_id": latest_run.id,
            "trigger_review_ids": sorted(review.id for review in recheck_reviews),
        },
    )

    db.commit()
    db.refresh(inspection)
    return inspection
