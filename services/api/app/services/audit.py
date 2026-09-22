from sqlalchemy.orm import Session

from app.models.audit import AuditEvent, AuditEventType


def record_inspection_event(
    db: Session,
    *,
    inspection_id: str,
    actor_user_id: str,
    event_type: AuditEventType,
    details: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        inspection_id=inspection_id,
        actor_user_id=actor_user_id,
        event_type=event_type.value,
        details=details or {},
    )
    db.add(event)
    return event
