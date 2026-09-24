from sqlalchemy.orm import Session

from app.errors import not_found
from app.models.capture import Capture


def get_capture_or_raise(
    db: Session,
    *,
    inspection_id: str,
    capture_id: str,
    include_discarded: bool = False,
) -> Capture:
    capture = db.get(Capture, capture_id)
    if (
        capture is None
        or capture.inspection_id != inspection_id
        or (capture.discarded_at is not None and not include_discarded)
    ):
        raise not_found("capture_not_found", "Capture not found.")
    return capture
