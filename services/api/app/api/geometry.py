from __future__ import annotations

from hashlib import sha256
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_officer
from app.core.config import Settings, get_settings
from app.db import get_db
from app.errors import conflict, not_found, service_unavailable
from app.models.audit import AuditEventType
from app.models.geometry import CaptureGeometryAssessment
from app.models.quality import CaptureDerivative, CaptureQualityAssessment
from app.models.user import User
from app.schemas.geometry import (
    CaptureGeometryAssessmentRead,
    GeometryAnalysisRequest,
    GeometryAnalysisResult,
)
from app.services.audit import record_inspection_event
from app.services.capture_access import get_capture_or_raise
from app.services.inspection_access import get_visible_inspection_or_raise
from app.services.inspection_lifecycle import require_draft
from app.services.media_storage import LocalMediaStorage, get_media_storage
from app.services.perspective import (
    GEOMETRY_ALGORITHM_VERSION,
    PERSPECTIVE_PROCESSING_VERSION,
    analyze_perspective,
    geometry_thresholds_from_settings,
)

router = APIRouter(
    prefix="/inspections/{inspection_id}/captures/{capture_id}/geometry",
    tags=["capture-geometry"],
)


def latest_quality_assessment_or_raise(
    db: Session,
    capture_id: str,
) -> CaptureQualityAssessment:
    statement = (
        select(CaptureQualityAssessment)
        .where(CaptureQualityAssessment.capture_id == capture_id)
        .order_by(
            CaptureQualityAssessment.created_at.desc(),
            CaptureQualityAssessment.id.desc(),
        )
        .limit(1)
    )
    assessment = db.scalar(statement)
    if assessment is None:
        raise conflict(
            "capture_preprocessing_required",
            "Run capture preprocessing before geometry analysis.",
        )
    return assessment


def _verify_corrected_derivative_storage(
    storage: LocalMediaStorage,
    derivative: CaptureDerivative,
) -> None:
    path = storage.path_for(derivative.storage_key)
    if not path.is_file():
        raise service_unavailable(
            "capture_storage_unavailable",
            "Perspective-corrected derivative is unavailable.",
        )

    try:
        data = path.read_bytes()
    except OSError:
        raise service_unavailable(
            "capture_storage_unavailable",
            "Perspective-corrected derivative is unavailable.",
        )

    if (
        len(data) != derivative.size_bytes
        or sha256(data).hexdigest() != derivative.sha256
    ):
        raise service_unavailable(
            "capture_derivative_integrity_mismatch",
            "Perspective-corrected derivative failed its integrity check.",
        )


def _raise_client_geometry_id_conflict() -> None:
    raise conflict(
        "client_resource_id_conflict",
        "The supplied geometry resource IDs are already associated with different geometry data.",
    )


def _existing_geometry_replay_or_raise(
    db: Session,
    storage: LocalMediaStorage,
    *,
    capture_id: str,
    geometry_assessment_id: str,
    corrected_derivative_id: str,
) -> dict | None:
    geometry = db.get(CaptureGeometryAssessment, geometry_assessment_id)
    if geometry is None:
        return None

    if geometry.capture_id != capture_id:
        _raise_client_geometry_id_conflict()

    if geometry.corrected_derivative_id is None:
        return {
            "geometry": geometry,
            "corrected_derivative": None,
        }

    if geometry.corrected_derivative_id != corrected_derivative_id:
        _raise_client_geometry_id_conflict()

    corrected = db.get(CaptureDerivative, corrected_derivative_id)
    if corrected is None:
        raise service_unavailable(
            "capture_geometry_unavailable",
            "The persisted corrected derivative is unavailable.",
        )
    if (
        corrected.capture_id != capture_id
        or corrected.derivative_type != "perspective_corrected"
    ):
        _raise_client_geometry_id_conflict()

    _verify_corrected_derivative_storage(storage, corrected)
    return {
        "geometry": geometry,
        "corrected_derivative": corrected,
    }


@router.post("/analyze", response_model=GeometryAnalysisResult)
def analyze_capture_geometry(
    inspection_id: str,
    capture_id: str,
    payload: GeometryAnalysisRequest | None = None,
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

    client_geometry_id = (
        str(payload.geometry_assessment_id)
        if payload is not None and payload.geometry_assessment_id is not None
        else None
    )
    client_corrected_id = (
        str(payload.corrected_derivative_id)
        if payload is not None and payload.corrected_derivative_id is not None
        else None
    )

    if client_geometry_id is not None and client_corrected_id is not None:
        replay = _existing_geometry_replay_or_raise(
            db,
            storage,
            capture_id=capture.id,
            geometry_assessment_id=client_geometry_id,
            corrected_derivative_id=client_corrected_id,
        )
        if replay is not None:
            return replay

    require_draft(inspection)

    quality_assessment = latest_quality_assessment_or_raise(db, capture.id)
    source_derivative = db.get(
        CaptureDerivative,
        quality_assessment.derivative_id,
    )
    if source_derivative is None or source_derivative.capture_id != capture.id:
        raise service_unavailable(
            "capture_preprocessing_unavailable",
            "The normalized capture derivative is unavailable.",
        )

    source_path = storage.path_for(source_derivative.storage_key)
    if not source_path.is_file():
        raise service_unavailable(
            "capture_storage_unavailable",
            "The normalized capture derivative is unavailable.",
        )

    try:
        source_data = source_path.read_bytes()
    except OSError:
        raise service_unavailable(
            "capture_storage_unavailable",
            "The normalized capture derivative is unavailable.",
        )

    if sha256(source_data).hexdigest() != source_derivative.sha256:
        raise service_unavailable(
            "capture_derivative_integrity_mismatch",
            "The normalized capture derivative failed its integrity check.",
        )

    thresholds = geometry_thresholds_from_settings(settings)
    analysis = analyze_perspective(
        source_data,
        thresholds=thresholds,
    )

    geometry_id = client_geometry_id or str(uuid4())
    corrected_derivative: CaptureDerivative | None = None
    corrected_key: str | None = None

    if analysis.corrected_jpeg is not None:
        corrected_id = client_corrected_id or str(uuid4())

        existing_corrected = db.get(CaptureDerivative, corrected_id)
        if existing_corrected is not None:
            _raise_client_geometry_id_conflict()

        storage_object_id = (
            str(uuid4()) if client_corrected_id is not None else corrected_id
        )
        corrected_key = (
            f"inspections/{inspection.id}/captures/{capture.id}/derivatives/"
            f"{storage_object_id}.jpg"
        )
        corrected_digest = sha256(analysis.corrected_jpeg).hexdigest()

        try:
            storage.save(corrected_key, analysis.corrected_jpeg)
        except OSError:
            raise service_unavailable(
                "capture_storage_unavailable",
                "Perspective-corrected derivative could not be stored.",
            )

        corrected_derivative = CaptureDerivative(
            id=corrected_id,
            capture_id=capture.id,
            derivative_type="perspective_corrected",
            processing_version=PERSPECTIVE_PROCESSING_VERSION,
            storage_key=corrected_key,
            sha256=corrected_digest,
            mime_type="image/jpeg",
            size_bytes=len(analysis.corrected_jpeg),
            width_px=analysis.corrected_width_px,
            height_px=analysis.corrected_height_px,
        )

    geometry = CaptureGeometryAssessment(
        id=geometry_id,
        capture_id=capture.id,
        source_derivative_id=source_derivative.id,
        corrected_derivative_id=(
            corrected_derivative.id if corrected_derivative is not None else None
        ),
        algorithm_version=GEOMETRY_ALGORITHM_VERSION,
        status=analysis.status,
        corners=analysis.corners,
        area_ratio=analysis.area_ratio,
        angle_score=analysis.angle_score,
        geometry_score=analysis.geometry_score,
        reasons=analysis.reasons,
        thresholds=thresholds.as_dict(),
    )

    try:
        if corrected_derivative is not None:
            db.add(corrected_derivative)
            db.flush()
        db.add(geometry)
        db.flush()

        record_inspection_event(
            db,
            inspection_id=inspection.id,
            actor_user_id=officer.id,
            event_type=AuditEventType.CAPTURE_GEOMETRY_ANALYZED,
            details={
                "capture_id": capture.id,
                "source_derivative_id": source_derivative.id,
                "corrected_derivative_id": geometry.corrected_derivative_id,
                "geometry_assessment_id": geometry.id,
                "geometry_status": geometry.status.value,
                "geometry_algorithm_version": GEOMETRY_ALGORITHM_VERSION,
            },
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        if corrected_key is not None:
            storage.delete(corrected_key)

        if client_geometry_id is not None and client_corrected_id is not None:
            replay = _existing_geometry_replay_or_raise(
                db,
                storage,
                capture_id=capture.id,
                geometry_assessment_id=client_geometry_id,
                corrected_derivative_id=client_corrected_id,
            )
            if replay is not None:
                return replay

            if db.get(CaptureDerivative, client_corrected_id) is not None:
                _raise_client_geometry_id_conflict()
        raise
    except Exception:
        db.rollback()
        if corrected_key is not None:
            storage.delete(corrected_key)
        raise

    if corrected_derivative is not None:
        db.refresh(corrected_derivative)
    db.refresh(geometry)

    return {
        "geometry": geometry,
        "corrected_derivative": corrected_derivative,
    }


@router.get(
    "/runs/{geometry_assessment_id}",
    response_model=GeometryAnalysisResult,
)
def get_geometry_run(
    inspection_id: str,
    capture_id: str,
    geometry_assessment_id: str,
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

    geometry = db.get(CaptureGeometryAssessment, geometry_assessment_id)
    if geometry is None or geometry.capture_id != capture.id:
        raise not_found(
            "capture_geometry_not_found",
            "Geometry assessment not found for this capture.",
        )

    corrected: CaptureDerivative | None = None
    if geometry.corrected_derivative_id is not None:
        corrected = db.get(
            CaptureDerivative,
            geometry.corrected_derivative_id,
        )
        if (
            corrected is None
            or corrected.capture_id != capture.id
            or corrected.derivative_type != "perspective_corrected"
        ):
            raise service_unavailable(
                "capture_geometry_unavailable",
                "The persisted corrected derivative is unavailable.",
            )
        _verify_corrected_derivative_storage(storage, corrected)

    return {
        "geometry": geometry,
        "corrected_derivative": corrected,
    }


@router.get("/latest", response_model=CaptureGeometryAssessmentRead)
def latest_geometry(
    inspection_id: str,
    capture_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CaptureGeometryAssessment:
    inspection = get_visible_inspection_or_raise(db, inspection_id, user)
    capture = get_capture_or_raise(
        db,
        inspection_id=inspection.id,
        capture_id=capture_id,
    )

    statement = (
        select(CaptureGeometryAssessment)
        .where(CaptureGeometryAssessment.capture_id == capture.id)
        .order_by(
            CaptureGeometryAssessment.created_at.desc(),
            CaptureGeometryAssessment.id.desc(),
        )
        .limit(1)
    )
    geometry = db.scalar(statement)
    if geometry is None:
        raise not_found(
            "capture_geometry_not_found",
            "No geometry assessment exists for this capture.",
        )
    return geometry
