from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_officer
from app.db import get_db
from app.errors import conflict, not_found, service_unavailable
from app.models.audit import AuditEventType
from app.models.finalization import InspectionFinalization
from app.models.user import User
from app.schemas.finalization import InspectionFinalizationRead
from app.services.audit import record_inspection_event
from app.services.finalization import build_finalization_snapshot, snapshot_sha256
from app.services.inspection_access import get_visible_inspection_or_raise
from app.services.inspection_lifecycle import finalize_inspection, require_pending_review
from app.services.media_storage import LocalMediaStorage, get_media_storage
from app.services.officer_review_state import (
    latest_rule_evaluation_run,
    rule_evaluation_matches_current_evidence,
)
from app.services.report_pdf import REPORT_VERSION, build_report_pdf

router = APIRouter(
    prefix="/inspections/{inspection_id}/finalization",
    tags=["inspection-finalization"],
)


def _get_finalization(
    db: Session,
    *,
    inspection_id: str,
) -> InspectionFinalization | None:
    return db.scalar(
        select(InspectionFinalization).where(
            InspectionFinalization.inspection_id == inspection_id
        )
    )


@router.post("", response_model=InspectionFinalizationRead)
def finalize_inspection_record(
    inspection_id: str,
    db: Session = Depends(get_db),
    officer: User = Depends(require_officer),
    storage: LocalMediaStorage = Depends(get_media_storage),
) -> InspectionFinalization:
    inspection = get_visible_inspection_or_raise(db, inspection_id, officer)
    require_pending_review(inspection)

    existing = _get_finalization(db, inspection_id=inspection.id)
    if existing is not None:
        raise conflict(
            "inspection_already_finalized",
            "This inspection already has an immutable finalization record.",
        )

    run = latest_rule_evaluation_run(
        db,
        inspection_id=inspection.id,
    )
    if run is None:
        raise conflict(
            "rule_evaluation_required",
            "A current preliminary rule evaluation is required before finalization.",
        )
    if not rule_evaluation_matches_current_evidence(
        db,
        inspection_id=inspection.id,
        run=run,
    ):
        raise conflict(
            "current_rule_evaluation_required",
            "The latest rule evaluation is stale. Refresh the evidence chain before finalization.",
        )

    finalization_id = str(uuid4())
    report_id = str(uuid4())
    finalized_at = datetime.now(timezone.utc)

    snapshot = build_finalization_snapshot(
        db,
        inspection=inspection,
        officer=officer,
        run=run,
        finalization_id=finalization_id,
        report_id=report_id,
        report_version=REPORT_VERSION,
        finalized_at=finalized_at,
    )
    snapshot_digest = snapshot_sha256(snapshot)
    report_bytes = build_report_pdf(snapshot)
    report_digest = hashlib.sha256(report_bytes).hexdigest()
    storage_key = (
        f"inspections/{inspection.id}/reports/"
        f"{report_id}-v{REPORT_VERSION}.pdf"
    )

    storage.save(storage_key, report_bytes)

    finalization = InspectionFinalization(
        id=finalization_id,
        inspection_id=inspection.id,
        finalized_by_user_id=officer.id,
        rule_evaluation_run_id=run.id,
        rule_pack_id=run.rule_pack_id,
        rule_pack_version=run.rule_pack_version,
        rule_pack_sha256=run.rule_pack_sha256,
        snapshot=snapshot,
        snapshot_sha256=snapshot_digest,
        report_id=report_id,
        report_version=REPORT_VERSION,
        report_storage_key=storage_key,
        report_sha256=report_digest,
        report_size_bytes=len(report_bytes),
        finalized_at=finalized_at,
    )
    db.add(finalization)

    previous_status = inspection.status.value
    finalize_inspection(inspection)

    record_inspection_event(
        db,
        inspection_id=inspection.id,
        actor_user_id=officer.id,
        event_type=AuditEventType.INSPECTION_FINALIZED,
        details={
            "finalization_id": finalization.id,
            "report_id": finalization.report_id,
            "report_version": finalization.report_version,
            "report_sha256": finalization.report_sha256,
            "snapshot_sha256": finalization.snapshot_sha256,
            "rule_evaluation_run_id": run.id,
            "from_status": previous_status,
            "to_status": inspection.status.value,
        },
    )

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        storage.delete(storage_key)
        raise conflict(
            "inspection_finalization_conflict",
            "The inspection was finalized concurrently. Reload it before retrying.",
        )
    except Exception:
        db.rollback()
        storage.delete(storage_key)
        raise

    db.refresh(finalization)
    return finalization


@router.get("", response_model=InspectionFinalizationRead)
def get_inspection_finalization(
    inspection_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> InspectionFinalization:
    inspection = get_visible_inspection_or_raise(db, inspection_id, user)
    finalization = _get_finalization(db, inspection_id=inspection.id)
    if finalization is None:
        raise not_found(
            "inspection_finalization_not_found",
            "No finalization record exists for this inspection.",
        )
    return finalization


@router.get("/report")
def get_finalized_report(
    inspection_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    storage: LocalMediaStorage = Depends(get_media_storage),
) -> FileResponse:
    inspection = get_visible_inspection_or_raise(db, inspection_id, user)
    finalization = _get_finalization(db, inspection_id=inspection.id)
    if finalization is None:
        raise not_found(
            "inspection_finalization_not_found",
            "No finalization record exists for this inspection.",
        )

    path = storage.path_for(finalization.report_storage_key)
    if not path.is_file():
        raise service_unavailable(
            "finalized_report_unavailable",
            "The finalized report file is temporarily unavailable.",
        )

    return FileResponse(
        path=path,
        media_type="application/pdf",
        filename=f"CODEFLUX-{finalization.report_id}.pdf",
    )
