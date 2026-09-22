from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_officer
from app.db import get_db
from app.errors import not_found
from app.models.inspection import Inspection
from app.models.user import User, UserRole
from app.schemas.inspection import InspectionCreate, InspectionRead, InspectionUpdate
from app.services.inspection_lifecycle import require_draft, submit_for_review

router = APIRouter(prefix="/inspections", tags=["inspections"])


def get_visible_inspection_or_raise(
    db: Session,
    inspection_id: str,
    user: User,
) -> Inspection:
    inspection = db.get(Inspection, inspection_id)
    if inspection is None:
        raise not_found("inspection_not_found", "Inspection not found.")

    if user.role is UserRole.OFFICER and inspection.officer_id != user.id:
        raise not_found("inspection_not_found", "Inspection not found.")

    return inspection


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

    fields_set = payload.model_fields_set
    if "product_name" in fields_set and payload.product_name is not None:
        inspection.product_name = payload.product_name
    if "product_identifier" in fields_set:
        inspection.product_identifier = payload.product_identifier

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
    submit_for_review(inspection)

    db.commit()
    db.refresh(inspection)
    return inspection
