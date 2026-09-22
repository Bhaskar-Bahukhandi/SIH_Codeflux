from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_officer
from app.db import get_db
from app.models.audit import AuditEventType
from app.models.inspection import Inspection
from app.models.user import User, UserRole
from app.schemas.inspection import InspectionCreate, InspectionRead, InspectionUpdate
from app.services.audit import record_inspection_event
from app.services.inspection_access import get_visible_inspection_or_raise
from app.services.inspection_lifecycle import require_draft, submit_for_review

router = APIRouter(prefix="/inspections", tags=["inspections"])


@router.post("", response_model=InspectionRead, status_code=status.HTTP_201_CREATED)
def create_inspection(
    payload: InspectionCreate,
    db: Session = Depends(get_db),
    officer: User = Depends(require_officer),
) -> Inspection:
    inspection = Inspection(
        product_name=payload.product_name,
        product_identifier=payload.product_identifier,
        officer_id=officer.id,
    )
    db.add(inspection)
    db.flush()

    record_inspection_event(
        db,
        inspection_id=inspection.id,
        actor_user_id=officer.id,
        event_type=AuditEventType.INSPECTION_CREATED,
        details={"status": inspection.status.value},
    )

    db.commit()
    db.refresh(inspection)
    return inspection


@router.get("", response_model=list[InspectionRead])
def list_inspections(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Inspection]:
    statement = select(Inspection).order_by(Inspection.created_at.desc())
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


@router.post("/{inspection_id}/submit", response_model=InspectionRead)
def submit_inspection_for_review(
    inspection_id: str,
    db: Session = Depends(get_db),
    officer: User = Depends(require_officer),
) -> Inspection:
    inspection = get_visible_inspection_or_raise(db, inspection_id, officer)
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
