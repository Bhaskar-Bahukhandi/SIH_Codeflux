from sqlalchemy import select

from app.models.audit import AuditEvent, AuditEventType
from app.models.user import UserRole


def create_inspection(client, headers):
    response = client.post(
        "/api/v1/inspections",
        headers=headers,
        json={
            "product_name": "Audit Test Product",
            "product_identifier": "AUDIT-001",
        },
    )
    assert response.status_code == 201
    return response.json()


def get_events(db_session, inspection_id):
    statement = (
        select(AuditEvent)
        .where(AuditEvent.inspection_id == inspection_id)
        .order_by(AuditEvent.created_at.asc())
    )
    return list(db_session.scalars(statement).all())


def test_inspection_state_changes_create_append_only_audit_events(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)

    inspection = create_inspection(client, headers)
    events = get_events(db_session, inspection["id"])

    assert len(events) == 1
    assert events[0].event_type == AuditEventType.INSPECTION_CREATED.value
    assert events[0].actor_user_id == officer.id

    update = client.patch(
        f"/api/v1/inspections/{inspection['id']}",
        headers=headers,
        json={"product_name": "Updated Audit Product"},
    )
    assert update.status_code == 200

    events = get_events(db_session, inspection["id"])
    assert len(events) == 2
    assert events[1].event_type == AuditEventType.INSPECTION_UPDATED.value
    assert events[1].details["changes"]["product_name"] == {
        "from": "Audit Test Product",
        "to": "Updated Audit Product",
    }

    submit = client.post(
        f"/api/v1/inspections/{inspection['id']}/submit",
        headers=headers,
    )
    assert submit.status_code == 200

    events = get_events(db_session, inspection["id"])
    assert len(events) == 3
    assert events[2].event_type == AuditEventType.INSPECTION_SUBMITTED.value
    assert events[2].details["from_status"] == "draft"
    assert events[2].details["to_status"] == "pending_review"

    failed_submit = client.post(
        f"/api/v1/inspections/{inspection['id']}/submit",
        headers=headers,
    )
    assert failed_submit.status_code == 409

    events_after_failure = get_events(db_session, inspection["id"])
    assert len(events_after_failure) == 3
