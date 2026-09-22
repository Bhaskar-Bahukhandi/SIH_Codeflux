from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.inspection import Inspection
from app.schemas.inspection import InspectionCreate, InspectionRead

router = APIRouter(prefix="/inspections", tags=["inspections"])


@router.post("", response_model=InspectionRead, status_code=status.HTTP_201_CREATED)
def create_inspection(payload: InspectionCreate, db: Session = Depends(get_db)) -> Inspection:
    inspection = Inspection(
        product_name=payload.product_name.strip(),
        product_identifier=(
            payload.product_identifier.strip() if payload.product_identifier else None
        ),
    )
    db.add(inspection)
    db.commit()
    db.refresh(inspection)
    return inspection


@router.get("", response_model=list[InspectionRead])
def list_inspections(db: Session = Depends(get_db)) -> list[Inspection]:
    statement = select(Inspection).order_by(Inspection.created_at.desc())
    return list(db.scalars(statement).all())


@router.get("/{inspection_id}", response_model=InspectionRead)
def get_inspection(inspection_id: str, db: Session = Depends(get_db)) -> Inspection:
    inspection = db.get(Inspection, inspection_id)
    if inspection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection not found",
        )
    return inspection
