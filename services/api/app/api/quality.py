from __future__ import annotations

from hashlib import sha256
from uuid import uuid4

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_officer
from app.core.config import Settings, get_settings
from app.db import get_db
from app.errors import conflict, not_found, service_unavailable
from app.models.audit import AuditEventType
from app.models.quality import CaptureDerivative, CaptureQualityAssessment
from app.models.user import User
from app.schemas.quality import (
    CaptureProcessingRequest,
    CaptureProcessingResult,
    CaptureQualityAssessmentRead,
)
from app.services.audit import record_inspection_event
from app.services.capture_access import get_capture_or_raise
from app.services.image_quality import (
    PREPROCESSING_VERSION,
    QUALITY_ALGORITHM_VERSION,
    assess_quality,
    normalize_capture,
    quality_thresholds_from_settings,
)
from app.services.inspection_access import get_visible_inspection_or_raise
from app.services.inspection_lifecycle import require_draft
from app.services.media_storage import LocalMediaStorage, get_media_storage

router = APIRouter(
    prefix="/inspections/{inspection_id}/captures/{capture_id}",
    tags=["capture-quality"],
)


def _verify_derivative_storage(
    storage: LocalMediaStorage,
    derivative: CaptureDerivative,
) -> None:
    path = storage.path_for(derivative.storage_key)
    if not path.is_file():
        raise service_unavailable(
            "capture_storage_unavailable",
            "Capture derivative is temporarily unavailable.",
        )

    try:
        data = path.read_bytes()
    except OSError:
        raise service_unavailable(
            "capture_storage_unavailable",
            "Capture derivative is temporarily unavailable.",
        )

    if (
        len(data) != derivative.size_bytes
        or sha256(data).hexdigest() != derivative.sha256
    ):
        raise service_unavailable(
            "capture_derivative_integrity_mismatch",
            "Capture derivative failed its integrity check.",
        )


def _raise_client_processing_id_conflict() -> None:
    raise conflict(
        "client_resource_id_conflict",
        "The supplied preprocessing resource IDs are already associated with different processing data.",
    )


def _existing_processing_replay_or_raise(
    db: Session,
    storage: LocalMediaStorage,
    *,
    capture_id: str,
    derivative_id: str,
    quality_assessment_id: str,
) -> dict | None:
    derivative = db.get(CaptureDerivative, derivative_id)
    assessment = db.get(CaptureQualityAssessment, quality_assessment_id)

    if derivative is None and assessment is None:
        return None

    if (
        derivative is None
        or assessment is None
        or derivative.capture_id != capture_id
        or derivative.derivative_type != "normalized"
        or assessment.capture_id != capture_id
        or assessment.derivative_id != derivative.id
    ):
        _raise_client_processing_id_conflict()

    _verify_derivative_storage(storage, derivative)
    return {
        "derivative": derivative,
        "quality": assessment,
    }


@router.post("/process", response_model=CaptureProcessingResult)
def process_capture(
    inspection_id: str,
    capture_id: str,
    payload: CaptureProcessingRequest | None = None,
    db: Session = Depends(get_db),
    officer: User = Depends(require_officer),
    settings: Settings = Depends(get_settings),
    storage: LocalMediaStorage = Depends(get_media_storage),
) -> dict:
    inspection = get_visible_inspection_or_raise(db, inspection_id, officer)
    capture = get_capture_or_raise(
        db,
        inspection_id=inspection.id,
        capture_id=capture_id,
    )

    client_derivative_id = (
        str(payload.derivative_id)
        if payload is not None and payload.derivative_id is not None
        else None
    )
    client_quality_id = (
        str(payload.quality_assessment_id)
        if payload is not None and payload.quality_assessment_id is not None
        else None
    )

    if client_derivative_id is not None and client_quality_id is not None:
        replay = _existing_processing_replay_or_raise(
            db,
            storage,
            capture_id=capture.id,
            derivative_id=client_derivative_id,
            quality_assessment_id=client_quality_id,
        )
        if replay is not None:
            return replay

    require_draft(inspection)

    original_path = storage.path_for(capture.storage_key)
    if not original_path.is_file():
        raise service_unavailable(
            "capture_storage_unavailable",
            "Capture content is temporarily unavailable.",
        )

    try:
        original_data = original_path.read_bytes()
    except OSError:
        raise service_unavailable(
            "capture_storage_unavailable",
            "Capture content is temporarily unavailable.",
        )

    if sha256(original_data).hexdigest() != capture.sha256:
        raise service_unavailable(
            "capture_integrity_mismatch",
            "Capture evidence failed its integrity check.",
        )

    try:
        normalized = normalize_capture(original_data)
    except OSError:
        raise service_unavailable(
            "capture_processing_unavailable",
            "Capture processing is temporarily unavailable.",
        )

    thresholds = quality_thresholds_from_settings(settings)
    quality_result = assess_quality(
        normalized.data,
        thresholds=thresholds,
    )

    derivative_id = client_derivative_id or str(uuid4())
    quality_assessment_id = client_quality_id or str(uuid4())
    storage_object_id = (
        str(uuid4()) if client_derivative_id is not None else derivative_id
    )
    derivative_key = (
        f"inspections/{inspection.id}/captures/{capture.id}/derivatives/"
        f"{storage_object_id}{normalized.extension}"
    )
    derivative_digest = sha256(normalized.data).hexdigest()

    try:
        storage.save(derivative_key, normalized.data)
    except OSError:
        raise service_unavailable(
            "capture_storage_unavailable",
            "Capture derivative could not be stored.",
        )

    derivative = CaptureDerivative(
        id=derivative_id,
        capture_id=capture.id,
        derivative_type="normalized",
        processing_version=PREPROCESSING_VERSION,
        storage_key=derivative_key,
        sha256=derivative_digest,
        mime_type=normalized.mime_type,
        size_bytes=len(normalized.data),
        width_px=normalized.width_px,
        height_px=normalized.height_px,
    )
    assessment = CaptureQualityAssessment(
        id=quality_assessment_id,
        capture_id=capture.id,
        derivative_id=derivative.id,
        algorithm_version=QUALITY_ALGORITHM_VERSION,
        status=quality_result.status,
        sharpness_score=quality_result.sharpness_score,
        brightness_mean=quality_result.brightness_mean,
        dark_fraction=quality_result.dark_fraction,
        bright_fraction=quality_result.bright_fraction,
        glare_fraction=quality_result.glare_fraction,
        reasons=quality_result.reasons,
        thresholds=thresholds.as_dict(),
    )

    try:
        db.add(derivative)
        db.flush()
        db.add(assessment)
        db.flush()

        record_inspection_event(
            db,
            inspection_id=inspection.id,
            actor_user_id=officer.id,
            event_type=AuditEventType.CAPTURE_PROCESSED,
            details={
                "capture_id": capture.id,
                "derivative_id": derivative.id,
                "quality_assessment_id": assessment.id,
                "quality_status": assessment.status.value,
                "processing_version": PREPROCESSING_VERSION,
                "quality_algorithm_version": QUALITY_ALGORITHM_VERSION,
            },
        )

        db.commit()
    except IntegrityError:
        db.rollback()
        storage.delete(derivative_key)

        if client_derivative_id is not None and client_quality_id is not None:
            replay = _existing_processing_replay_or_raise(
                db,
                storage,
                capture_id=capture.id,
                derivative_id=client_derivative_id,
                quality_assessment_id=client_quality_id,
            )
            if replay is not None:
                return replay
        raise
    except Exception:
        db.rollback()
        storage.delete(derivative_key)
        raise

    db.refresh(derivative)
    db.refresh(assessment)
    return {
        "derivative": derivative,
        "quality": assessment,
    }


@router.get(
    "/process-runs/{quality_assessment_id}",
    response_model=CaptureProcessingResult,
)
def get_processing_run(
    inspection_id: str,
    capture_id: str,
    quality_assessment_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    storage: LocalMediaStorage = Depends(get_media_storage),
) -> dict:
    inspection = get_visible_inspection_or_raise(db, inspection_id, user)
    capture = get_capture_or_raise(
        db,
        inspection_id=inspection.id,
        capture_id=capture_id,
    )

    assessment = db.get(CaptureQualityAssessment, quality_assessment_id)
    if assessment is None or assessment.capture_id != capture.id:
        raise not_found(
            "capture_processing_not_found",
            "Capture preprocessing result not found.",
        )

    derivative = db.get(CaptureDerivative, assessment.derivative_id)
    if (
        derivative is None
        or derivative.capture_id != capture.id
        or derivative.derivative_type != "normalized"
    ):
        raise service_unavailable(
            "capture_preprocessing_unavailable",
            "The normalized capture derivative is unavailable.",
        )

    _verify_derivative_storage(storage, derivative)
    return {
        "derivative": derivative,
        "quality": assessment,
    }


@router.get("/quality/latest", response_model=CaptureQualityAssessmentRead)
def latest_quality(
    inspection_id: str,
    capture_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CaptureQualityAssessment:
    inspection = get_visible_inspection_or_raise(db, inspection_id, user)
    capture = get_capture_or_raise(
        db,
        inspection_id=inspection.id,
        capture_id=capture_id,
    )

    statement = (
        select(CaptureQualityAssessment)
        .where(CaptureQualityAssessment.capture_id == capture.id)
        .order_by(
            CaptureQualityAssessment.created_at.desc(),
            CaptureQualityAssessment.id.desc(),
        )
        .limit(1)
    )
    assessment = db.scalar(statement)
    if assessment is None:
        raise not_found(
            "capture_quality_not_found",
            "No quality assessment exists for this capture.",
        )
    return assessment


@router.get("/derivatives/{derivative_id}/content")
def get_derivative_content(
    inspection_id: str,
    capture_id: str,
    derivative_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    storage: LocalMediaStorage = Depends(get_media_storage),
) -> FileResponse:
    inspection = get_visible_inspection_or_raise(db, inspection_id, user)
    capture = get_capture_or_raise(
        db,
        inspection_id=inspection.id,
        capture_id=capture_id,
    )
    derivative = db.get(CaptureDerivative, derivative_id)
    if derivative is None or derivative.capture_id != capture.id:
        raise not_found("capture_derivative_not_found", "Capture derivative not found.")

    path = storage.path_for(derivative.storage_key)
    if not path.is_file():
        raise service_unavailable(
            "capture_storage_unavailable",
            "Capture derivative is temporarily unavailable.",
        )

    return FileResponse(
        path=path,
        media_type=derivative.mime_type,
        filename=f"{derivative.id}.jpg",
    )
