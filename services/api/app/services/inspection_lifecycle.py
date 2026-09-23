from datetime import datetime, timezone

from app.errors import conflict
from app.models.inspection import Inspection, InspectionStatus


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def require_draft(inspection: Inspection) -> None:
    if inspection.status is not InspectionStatus.DRAFT:
        raise conflict(
            "inspection_not_editable",
            "Only draft inspections can be edited.",
        )


def require_pending_review(inspection: Inspection) -> None:
    if inspection.status is not InspectionStatus.PENDING_REVIEW:
        raise conflict(
            "inspection_not_pending_review",
            "This action is available only after the inspection is submitted for review.",
        )


def submit_for_review(inspection: Inspection) -> None:
    require_draft(inspection)
    inspection.status = InspectionStatus.PENDING_REVIEW
    inspection.submitted_at = utcnow()
