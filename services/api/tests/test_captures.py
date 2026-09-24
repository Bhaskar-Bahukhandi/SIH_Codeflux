from hashlib import sha256
from io import BytesIO

from PIL import Image
from sqlalchemy import select

from app.models.audit import AuditEvent, AuditEventType
from app.models.capture import Capture
from app.models.user import UserRole


def image_bytes(fmt="JPEG", size=(32, 24)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, (120, 90, 60)).save(buffer, format=fmt)
    return buffer.getvalue()


def create_inspection(client, headers):
    response = client.post(
        "/api/v1/inspections",
        headers=headers,
        json={"product_name": "Capture Test Product"},
    )
    assert response.status_code == 201
    return response.json()


def upload_image(client, inspection_id, headers, data, *, name="front.jpg", view="front"):
    return client.post(
        f"/api/v1/inspections/{inspection_id}/captures",
        headers=headers,
        data={"view_type": view},
        files={"file": (name, data, "application/octet-stream")},
    )


def test_owner_can_upload_list_and_retrieve_original_bytes(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)
    original = image_bytes("JPEG", (40, 30))

    upload = upload_image(
        client,
        inspection["id"],
        headers,
        original,
        name="../../unsafe-name.jpg",
        view="front",
    )

    assert upload.status_code == 201
    capture = upload.json()
    assert capture["inspection_id"] == inspection["id"]
    assert capture["uploader_user_id"] == officer.id
    assert capture["view_type"] == "front"
    assert capture["original_filename"] == "unsafe-name.jpg"
    assert capture["mime_type"] == "image/jpeg"
    assert capture["width_px"] == 40
    assert capture["height_px"] == 30
    assert capture["size_bytes"] == len(original)
    assert capture["sha256"] == sha256(original).hexdigest()

    stored = db_session.get(Capture, capture["id"])
    assert stored is not None
    assert stored.storage_key.startswith(
        f"inspections/{inspection['id']}/captures/"
    )

    listing = client.get(
        f"/api/v1/inspections/{inspection['id']}/captures",
        headers=headers,
    )
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()] == [capture["id"]]

    content = client.get(
        f"/api/v1/inspections/{inspection['id']}/captures/{capture['id']}/content",
        headers=headers,
    )
    assert content.status_code == 200
    assert content.content == original

    events = list(
        db_session.scalars(
            select(AuditEvent).where(
                AuditEvent.inspection_id == inspection["id"],
                AuditEvent.event_type == AuditEventType.CAPTURE_UPLOADED.value,
            )
        ).all()
    )
    assert len(events) == 1
    assert events[0].details["capture_id"] == capture["id"]
    assert events[0].details["sha256"] == capture["sha256"]


def test_other_officer_cannot_list_or_read_capture(
    client,
    user_factory,
    auth_headers,
):
    owner = user_factory(UserRole.OFFICER)
    other = user_factory(UserRole.OFFICER)
    owner_headers = auth_headers(owner)
    inspection = create_inspection(client, owner_headers)
    upload = upload_image(
        client,
        inspection["id"],
        owner_headers,
        image_bytes(),
    )
    capture_id = upload.json()["id"]
    other_headers = auth_headers(other)

    listing = client.get(
        f"/api/v1/inspections/{inspection['id']}/captures",
        headers=other_headers,
    )
    assert listing.status_code == 404

    content = client.get(
        f"/api/v1/inspections/{inspection['id']}/captures/{capture_id}/content",
        headers=other_headers,
    )
    assert content.status_code == 404


def test_supervisor_can_review_capture_but_cannot_upload(
    client,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    supervisor = user_factory(UserRole.SUPERVISOR)
    officer_headers = auth_headers(officer)
    inspection = create_inspection(client, officer_headers)
    upload = upload_image(
        client,
        inspection["id"],
        officer_headers,
        image_bytes(),
    )
    capture_id = upload.json()["id"]
    supervisor_headers = auth_headers(supervisor)

    listing = client.get(
        f"/api/v1/inspections/{inspection['id']}/captures",
        headers=supervisor_headers,
    )
    assert listing.status_code == 200

    content = client.get(
        f"/api/v1/inspections/{inspection['id']}/captures/{capture_id}/content",
        headers=supervisor_headers,
    )
    assert content.status_code == 200

    rejected = upload_image(
        client,
        inspection["id"],
        supervisor_headers,
        image_bytes(),
    )
    assert rejected.status_code == 403


def test_corrupt_image_is_rejected_without_capture_record(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)

    response = upload_image(
        client,
        inspection["id"],
        headers,
        b"not-an-image",
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_image"
    assert db_session.scalar(select(Capture)) is None


def test_unsupported_image_format_is_rejected(
    client,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)

    response = upload_image(
        client,
        inspection["id"],
        headers,
        image_bytes("GIF"),
        name="package.gif",
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_image_format"


def test_capture_upload_is_blocked_after_submission(
    client,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)

    submitted = client.post(
        f"/api/v1/inspections/{inspection['id']}/submit",
        headers=headers,
    )
    assert submitted.status_code == 200

    response = upload_image(
        client,
        inspection["id"],
        headers,
        image_bytes(),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "inspection_not_editable"


def test_owner_can_discard_draft_capture_without_deleting_audit_record(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)
    upload = upload_image(
        client,
        inspection["id"],
        headers,
        image_bytes(),
    )
    assert upload.status_code == 201
    capture_id = upload.json()["id"]

    discarded = client.post(
        f"/api/v1/inspections/{inspection['id']}/captures/{capture_id}/discard",
        headers=headers,
    )
    assert discarded.status_code == 200
    assert discarded.json()["id"] == capture_id
    assert discarded.json()["discarded_at"] is not None

    repeated = client.post(
        f"/api/v1/inspections/{inspection['id']}/captures/{capture_id}/discard",
        headers=headers,
    )
    assert repeated.status_code == 200
    assert repeated.json()["discarded_at"] == discarded.json()["discarded_at"]

    listing = client.get(
        f"/api/v1/inspections/{inspection['id']}/captures",
        headers=headers,
    )
    assert listing.status_code == 200
    assert listing.json() == []

    content = client.get(
        f"/api/v1/inspections/{inspection['id']}/captures/{capture_id}/content",
        headers=headers,
    )
    assert content.status_code == 404

    stored = db_session.get(Capture, capture_id)
    assert stored is not None
    assert stored.discarded_at is not None

    events = list(
        db_session.scalars(
            select(AuditEvent).where(
                AuditEvent.inspection_id == inspection["id"],
                AuditEvent.event_type == AuditEventType.CAPTURE_DISCARDED.value,
            )
        ).all()
    )
    assert len(events) == 1
    assert events[0].details["capture_id"] == capture_id


def test_capture_discard_is_blocked_after_submission(
    client,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)
    upload = upload_image(
        client,
        inspection["id"],
        headers,
        image_bytes(),
    )
    capture_id = upload.json()["id"]

    submitted = client.post(
        f"/api/v1/inspections/{inspection['id']}/submit",
        headers=headers,
    )
    assert submitted.status_code == 200

    response = client.post(
        f"/api/v1/inspections/{inspection['id']}/captures/{capture_id}/discard",
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "inspection_not_editable"
