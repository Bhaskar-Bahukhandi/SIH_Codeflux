from __future__ import annotations

from hashlib import sha256
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy import select
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


@router.post("/analyze", response_model=GeometryAnalysisResult)
def analyze_capture_geometry(
    inspection_id: str,
    capture_id: str,
    db: Session = Depends(get_db),
    officer: User = Depends(require_officer),
    settings: Settings = Depends(get_settings),
    storage: LocalMediaStorage = Depends(get_media_storage),
) -> dict:
    inspection = get_visible_inspection_or_raise(db, inspection_id, officer)
    require_draft(inspection)
    capture = get_capture_or_raise(
        db,
        inspection_id=inspection.id,
        capture_id=capture_id,
    )

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

    corrected_derivative: CaptureDerivative | None = None
    corrected_key: str | None = None

    if analysis.corrected_jpeg is not None:
        corrected_id = str(uuid4())
        corrected_key = (
            f"inspections/{inspection.id}/captures/{capture.id}/derivatives/"
            f"{corrected_id}.jpg"
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
                "geometry_status": geometry.status.value,
                "geometry_algorithm_version": GEOMETRY_ALGORITHM_VERSION,
            },
        )
        db.commit()
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
