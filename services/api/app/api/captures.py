from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_officer
from app.core.config import Settings, get_settings
from app.db import get_db
from app.errors import not_found, payload_too_large, service_unavailable
from app.models.audit import AuditEventType
from app.models.capture import Capture, CaptureViewType
from app.models.user import User
from app.schemas.capture import CaptureRead
from app.services.audit import record_inspection_event
from app.services.image_validation import verify_capture_image
from app.services.inspection_access import get_visible_inspection_or_raise
from app.services.inspection_lifecycle import require_draft
from app.services.media_storage import LocalMediaStorage, get_media_storage

router = APIRouter(
    prefix="/inspections/{inspection_id}/captures",
    tags=["captures"],
)


@router.post("", response_model=CaptureRead, status_code=status.HTTP_201_CREATED)
async def upload_capture(
    inspection_id: str,
    view_type: CaptureViewType = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    officer: User = Depends(require_officer),
    settings: Settings = Depends(get_settings),
    storage: LocalMediaStorage = Depends(get_media_storage),
) -> Capture:
    inspection = get_visible_inspection_or_raise(db, inspection_id, officer)
    require_draft(inspection)

    data = await file.read(settings.max_capture_bytes + 1)
    if len(data) > settings.max_capture_bytes:
        raise payload_too_large(
            "capture_too_large",
            f"Image exceeds the {settings.max_capture_mb} MB prototype limit.",
        )

    verified = verify_capture_image(
        data,
        max_pixels=settings.max_capture_pixels,
    )

    capture_id = str(uuid4())
    storage_key = (
        f"inspections/{inspection.id}/captures/"
        f"{capture_id}{verified.extension}"
    )
    safe_filename = Path(file.filename).name[:255] if file.filename else None
    digest = sha256(data).hexdigest()

    storage.save(storage_key, data)

    capture = Capture(
        id=capture_id,
        inspection_id=inspection.id,
        uploader_user_id=officer.id,
        view_type=view_type,
        original_filename=safe_filename,
        storage_key=storage_key,
        sha256=digest,
        mime_type=verified.mime_type,
        size_bytes=len(data),
        width_px=verified.width_px,
        height_px=verified.height_px,
    )
    db.add(capture)

    record_inspection_event(
        db,
        inspection_id=inspection.id,
        actor_user_id=officer.id,
        event_type=AuditEventType.CAPTURE_UPLOADED,
        details={
            "capture_id": capture.id,
            "view_type": capture.view_type.value,
            "sha256": capture.sha256,
        },
    )

    try:
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(storage_key)
        raise

    db.refresh(capture)
    return capture


@router.get("", response_model=list[CaptureRead])
def list_captures(
    inspection_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Capture]:
    inspection = get_visible_inspection_or_raise(db, inspection_id, user)
    statement = (
        select(Capture)
        .where(Capture.inspection_id == inspection.id)
        .order_by(Capture.created_at.asc())
    )
    return list(db.scalars(statement).all())


@router.get("/{capture_id}/content")
def get_capture_content(
    inspection_id: str,
    capture_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    storage: LocalMediaStorage = Depends(get_media_storage),
) -> FileResponse:
    inspection = get_visible_inspection_or_raise(db, inspection_id, user)
    capture = db.get(Capture, capture_id)

    if capture is None or capture.inspection_id != inspection.id:
        raise not_found("capture_not_found", "Capture not found.")

    path = storage.path_for(capture.storage_key)
    if not path.is_file():
        raise service_unavailable(
            "capture_storage_unavailable",
            "Capture content is temporarily unavailable.",
        )

    return FileResponse(
        path=path,
        media_type=capture.mime_type,
        filename=capture.original_filename or path.name,
    )
