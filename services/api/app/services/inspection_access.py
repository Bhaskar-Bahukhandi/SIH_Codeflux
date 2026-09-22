from sqlalchemy.orm import Session

from app.errors import not_found
from app.models.inspection import Inspection
from app.models.user import User, UserRole


def get_visible_inspection_or_raise(
    db: Session,
    inspection_id: str,
    user: User,
) -> Inspection:
    inspection = db.get(Inspection, inspection_id)
    if inspection is None:
        raise not_found("inspection_not_found", "Inspection not found.")

    if user.role is UserRole.OFFICER and inspection.officer_id != user.id:
        raise not_found("inspection_not_found", "Inspection not found.")

    return inspection
