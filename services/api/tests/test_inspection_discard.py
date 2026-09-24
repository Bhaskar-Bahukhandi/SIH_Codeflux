from sqlalchemy import select

from app.models.audit import AuditEvent, AuditEventType
from app.models.user import UserRole


def _create(client, headers, name="Disposable Product"):
    response = client.post(
        "/api/v1/inspections",
        headers=headers,
        json={"product_name": name},
    )
    assert response.status_code == 201
    return response.json()


def test_officer_can_discard_owned_draft_and_it_disappears_from_list(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    created = _create(client, headers)

    response = client.post(
        f"/api/v1/inspections/{created['id']}/discard",
        headers=headers,
    )

    assert response.status_code == 200
    discarded = response.json()
    assert discarded["status"] == "discarded"

    listing = client.get("/api/v1/inspections", headers=headers)
    assert listing.status_code == 200
    assert created["id"] not in {item["id"] for item in listing.json()}

    direct = client.get(
        f"/api/v1/inspections/{created['id']}",
        headers=headers,
    )
    assert direct.status_code == 200
    assert direct.json()["status"] == "discarded"

    events = list(
        db_session.scalars(
            select(AuditEvent)
            .where(AuditEvent.inspection_id == created["id"])
            .order_by(AuditEvent.created_at.asc())
        ).all()
    )
    assert events[-1].event_type == AuditEventType.INSPECTION_DISCARDED.value
    assert events[-1].actor_user_id == officer.id
    assert events[-1].details == {
        "from_status": "draft",
        "to_status": "discarded",
    }


def test_discarded_inspection_cannot_be_edited_or_submitted(
    client,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    created = _create(client, headers)

    discarded = client.post(
        f"/api/v1/inspections/{created['id']}/discard",
        headers=headers,
    )
    assert discarded.status_code == 200

    edit = client.patch(
        f"/api/v1/inspections/{created['id']}",
        headers=headers,
        json={"product_name": "Should not apply"},
    )
    assert edit.status_code == 409
    assert edit.json()["error"]["code"] == "inspection_not_editable"

    submit = client.post(
        f"/api/v1/inspections/{created['id']}/submit",
        headers=headers,
    )
    assert submit.status_code == 409
    assert submit.json()["error"]["code"] == "inspection_not_editable"


def test_submitted_inspection_cannot_be_discarded(
    client,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    created = _create(client, headers)

    submitted = client.post(
        f"/api/v1/inspections/{created['id']}/submit",
        headers=headers,
    )
    assert submitted.status_code == 200

    discard = client.post(
        f"/api/v1/inspections/{created['id']}/discard",
        headers=headers,
    )
    assert discard.status_code == 409
    assert discard.json()["error"]["code"] == "inspection_not_editable"


def test_supervisor_cannot_discard_officer_inspection(
    client,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    supervisor = user_factory(UserRole.SUPERVISOR)
    created = _create(client, auth_headers(officer))

    response = client.post(
        f"/api/v1/inspections/{created['id']}/discard",
        headers=auth_headers(supervisor),
    )
    assert response.status_code == 403
