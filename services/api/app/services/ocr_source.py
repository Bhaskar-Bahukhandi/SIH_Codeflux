from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import conflict, service_unavailable
from app.models.geometry import CaptureGeometryAssessment
from app.models.quality import CaptureDerivative, CaptureQualityAssessment


def select_ocr_source_derivative(
    db: Session,
    *,
    capture_id: str,
) -> CaptureDerivative:
    latest_quality = db.scalar(
        select(CaptureQualityAssessment)
        .where(CaptureQualityAssessment.capture_id == capture_id)
        .order_by(
            CaptureQualityAssessment.created_at.desc(),
            CaptureQualityAssessment.id.desc(),
        )
        .limit(1)
    )
    if latest_quality is None:
        raise conflict(
            "capture_preprocessing_required",
            "Run capture preprocessing before OCR.",
        )

    normalized = db.get(CaptureDerivative, latest_quality.derivative_id)
    if normalized is None or normalized.capture_id != capture_id:
        raise service_unavailable(
            "capture_preprocessing_unavailable",
            "The normalized capture derivative is unavailable.",
        )

    latest_geometry = db.scalar(
        select(CaptureGeometryAssessment)
        .where(CaptureGeometryAssessment.capture_id == capture_id)
        .order_by(
            CaptureGeometryAssessment.created_at.desc(),
            CaptureGeometryAssessment.id.desc(),
        )
        .limit(1)
    )

    if (
        latest_geometry is not None
        and latest_geometry.source_derivative_id == normalized.id
        and latest_geometry.corrected_derivative_id is not None
    ):
        corrected = db.get(
            CaptureDerivative,
            latest_geometry.corrected_derivative_id,
        )
        if corrected is not None and corrected.capture_id == capture_id:
            return corrected

    return normalized
