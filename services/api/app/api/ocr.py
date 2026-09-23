from __future__ import annotations

from hashlib import sha256

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_officer
from app.db import get_db
from app.errors import conflict, not_found, service_unavailable
from app.models.audit import AuditEventType
from app.models.ocr import OcrBlock, OcrRun
from app.models.user import User
from app.schemas.ocr import OcrResultRead, OcrRunRequest
from app.services.audit import record_inspection_event
from app.services.capture_access import get_capture_or_raise
from app.services.inspection_access import get_visible_inspection_or_raise
from app.services.inspection_lifecycle import require_draft
from app.services.media_storage import LocalMediaStorage, get_media_storage
from app.services.ocr_engine import (
    OcrBackendUnavailable,
    OcrEngine,
    OcrInferenceFailed,
    get_ocr_engine,
)
from app.services.ocr_source import select_ocr_source_derivative

router = APIRouter(
    prefix="/inspections/{inspection_id}/captures/{capture_id}/ocr",
    tags=["ocr"],
)


def _load_ocr_source_bytes(
    *,
    storage: LocalMediaStorage,
    storage_key: str,
    expected_sha256: str,
) -> bytes:
    path = storage.path_for(storage_key)
    if not path.is_file():
        raise service_unavailable(
            "capture_storage_unavailable",
            "OCR source derivative is temporarily unavailable.",
        )

    try:
        data = path.read_bytes()
    except OSError:
        raise service_unavailable(
            "capture_storage_unavailable",
            "OCR source derivative is temporarily unavailable.",
        )

    if sha256(data).hexdigest() != expected_sha256:
        raise service_unavailable(
            "capture_derivative_integrity_mismatch",
            "OCR source derivative failed its integrity check.",
        )

    return data


def _result_for_run(db: Session, run: OcrRun) -> dict:
    blocks = list(
        db.scalars(
            select(OcrBlock)
            .where(OcrBlock.run_id == run.id)
            .order_by(OcrBlock.order_index.asc(), OcrBlock.id.asc())
        ).all()
    )
    return {"run": run, "blocks": blocks}


def _matches_run_replay(
    run: OcrRun,
    *,
    capture_id: str,
) -> bool:
    return run.capture_id == capture_id


def _raise_client_run_id_conflict() -> None:
    raise conflict(
        "client_resource_id_conflict",
        "The supplied client OCR run ID is already associated with a different capture.",
    )


@router.post("/run", response_model=OcrResultRead)
def run_ocr(
    inspection_id: str,
    capture_id: str,
    payload: OcrRunRequest | None = None,
    db: Session = Depends(get_db),
    officer: User = Depends(require_officer),
    storage: LocalMediaStorage = Depends(get_media_storage),
    engine: OcrEngine = Depends(get_ocr_engine),
) -> dict:
    inspection = get_visible_inspection_or_raise(db, inspection_id, officer)
    capture = get_capture_or_raise(
        db,
        inspection_id=inspection.id,
        capture_id=capture_id,
    )

    client_run_id = (
        str(payload.id)
        if payload is not None and payload.id is not None
        else None
    )
    if client_run_id is not None:
        existing = db.get(OcrRun, client_run_id)
        if existing is not None:
            if _matches_run_replay(
                existing,
                capture_id=capture.id,
            ):
                return _result_for_run(db, existing)
            _raise_client_run_id_conflict()

    require_draft(inspection)

    source = select_ocr_source_derivative(
        db,
        capture_id=capture.id,
    )
    source_data = _load_ocr_source_bytes(
        storage=storage,
        storage_key=source.storage_key,
        expected_sha256=source.sha256,
    )

    try:
        detections = engine.extract(source_data)
    except OcrBackendUnavailable:
        raise service_unavailable(
            "ocr_backend_unavailable",
            "OCR runtime is not available on this server.",
        )
    except OcrInferenceFailed:
        raise service_unavailable(
            "ocr_inference_failed",
            "OCR could not process this capture.",
        )

    run_kwargs = {
        "capture_id": capture.id,
        "source_derivative_id": source.id,
        "source_sha256": source.sha256,
        "engine_name": engine.name,
        "engine_version": engine.version,
        "model_version": engine.model_version,
        "language": engine.language,
        "parameters": engine.parameters,
        "block_count": len(detections),
    }
    if client_run_id is not None:
        run_kwargs["id"] = client_run_id

    run = OcrRun(**run_kwargs)
    db.add(run)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        if client_run_id is not None:
            existing = db.get(OcrRun, client_run_id)
            if existing is not None:
                if _matches_run_replay(
                    existing,
                    capture_id=capture.id,
                ):
                    return _result_for_run(db, existing)
                _raise_client_run_id_conflict()
        raise

    for index, detection in enumerate(detections):
        db.add(
            OcrBlock(
                run_id=run.id,
                order_index=index,
                text=detection.text,
                confidence=detection.confidence,
                polygon=detection.polygon,
            )
        )

    record_inspection_event(
        db,
        inspection_id=inspection.id,
        actor_user_id=officer.id,
        event_type=AuditEventType.CAPTURE_OCR_COMPLETED,
        details={
            "capture_id": capture.id,
            "ocr_run_id": run.id,
            "source_derivative_id": source.id,
            "engine_name": run.engine_name,
            "engine_version": run.engine_version,
            "model_version": run.model_version,
            "language": run.language,
            "block_count": run.block_count,
        },
    )

    db.commit()
    db.refresh(run)
    return _result_for_run(db, run)


@router.get("/runs/{run_id}", response_model=OcrResultRead)
def get_ocr_run(
    inspection_id: str,
    capture_id: str,
    run_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    inspection = get_visible_inspection_or_raise(db, inspection_id, user)
    capture = get_capture_or_raise(
        db,
        inspection_id=inspection.id,
        capture_id=capture_id,
    )

    run = db.get(OcrRun, run_id)
    if run is None or run.capture_id != capture.id:
        raise not_found(
            "capture_ocr_not_found",
            "OCR result not found for this capture.",
        )

    return _result_for_run(db, run)


@router.get("/latest", response_model=OcrResultRead)
def latest_ocr(
    inspection_id: str,
    capture_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    inspection = get_visible_inspection_or_raise(db, inspection_id, user)
    capture = get_capture_or_raise(
        db,
        inspection_id=inspection.id,
        capture_id=capture_id,
    )

    run = db.scalar(
        select(OcrRun)
        .where(OcrRun.capture_id == capture.id)
        .order_by(OcrRun.created_at.desc(), OcrRun.id.desc())
        .limit(1)
    )
    if run is None:
        raise not_found(
            "capture_ocr_not_found",
            "No OCR result exists for this capture.",
        )

    return _result_for_run(db, run)
