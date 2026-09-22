from hashlib import sha256
from io import BytesIO

from PIL import Image, ImageDraw
from sqlalchemy import select

from app.models.audit import AuditEvent, AuditEventType
from app.models.quality import CaptureDerivative, CaptureQualityAssessment
from app.models.user import UserRole


def sharp_pattern_bytes(*, oriented: bool = False) -> bytes:
    image = Image.new("RGB", (128, 96), (120, 120, 120))
    draw = ImageDraw.Draw(image)
    block = 8
    for y in range(0, image.height, block):
        for x in range(0, image.width, block):
            value = 60 if ((x // block + y // block) % 2 == 0) else 190
            draw.rectangle(
                [x, y, x + block - 1, y + block - 1],
                fill=(value, value, value),
            )

    buffer = BytesIO()
    if oriented:
        exif = image.getexif()
        exif[274] = 6
        image.save(buffer, format="JPEG", quality=95, exif=exif)
    else:
        image.save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()


def dark_image_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (96, 72), (18, 18, 18)).save(
        buffer,
        format="JPEG",
        quality=95,
    )
    return buffer.getvalue()


def create_inspection(client, headers):
    response = client.post(
        "/api/v1/inspections",
        headers=headers,
        json={"product_name": "Quality Test Product"},
    )
    assert response.status_code == 201
    return response.json()


def upload_capture(client, inspection_id, headers, data):
    response = client.post(
        f"/api/v1/inspections/{inspection_id}/captures",
        headers=headers,
        data={"view_type": "front"},
        files={"file": ("package.jpg", data, "image/jpeg")},
    )
    assert response.status_code == 201
    return response.json()


def process_capture(client, inspection_id, capture_id, headers):
    return client.post(
        f"/api/v1/inspections/{inspection_id}/captures/{capture_id}/process",
        headers=headers,
    )


def test_processing_preserves_original_and_creates_separate_derivative(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)
    original = sharp_pattern_bytes()
    capture = upload_capture(client, inspection["id"], headers, original)

    original_before = client.get(
        f"/api/v1/inspections/{inspection['id']}/captures/{capture['id']}/content",
        headers=headers,
    )
    assert original_before.status_code == 200
    assert original_before.content == original

    response = process_capture(
        client,
        inspection["id"],
        capture["id"],
        headers,
    )

    assert response.status_code == 200
    result = response.json()
    derivative = result["derivative"]
    quality = result["quality"]

    assert derivative["capture_id"] == capture["id"]
    assert derivative["derivative_type"] == "normalized"
    assert derivative["processing_version"] == "normalize-v1"
    assert derivative["mime_type"] == "image/jpeg"
    assert derivative["sha256"] != capture["sha256"]
    assert quality["capture_id"] == capture["id"]
    assert quality["derivative_id"] == derivative["id"]
    assert quality["algorithm_version"] == "quality-v1"
    assert quality["status"] == "pass"
    assert quality["reasons"] == []

    derivative_content = client.get(
        (
            f"/api/v1/inspections/{inspection['id']}/captures/"
            f"{capture['id']}/derivatives/{derivative['id']}/content"
        ),
        headers=headers,
    )
    assert derivative_content.status_code == 200
    assert sha256(derivative_content.content).hexdigest() == derivative["sha256"]

    original_after = client.get(
        f"/api/v1/inspections/{inspection['id']}/captures/{capture['id']}/content",
        headers=headers,
    )
    assert original_after.status_code == 200
    assert original_after.content == original
    assert sha256(original_after.content).hexdigest() == capture["sha256"]

    assert db_session.get(CaptureDerivative, derivative["id"]) is not None
    assert db_session.get(CaptureQualityAssessment, quality["id"]) is not None

    events = list(
        db_session.scalars(
            select(AuditEvent).where(
                AuditEvent.inspection_id == inspection["id"],
                AuditEvent.event_type == AuditEventType.CAPTURE_PROCESSED.value,
            )
        ).all()
    )
    assert len(events) == 1
    assert events[0].details["quality_status"] == "pass"


def test_orientation_metadata_is_applied_only_to_derivative(
    client,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)

    source = Image.new("RGB", (40, 20), (120, 80, 60))
    draw = ImageDraw.Draw(source)
    draw.line((0, 0, 39, 19), fill=(180, 180, 180), width=2)
    exif = source.getexif()
    exif[274] = 6
    buffer = BytesIO()
    source.save(buffer, format="JPEG", quality=95, exif=exif)
    original = buffer.getvalue()

    capture = upload_capture(client, inspection["id"], headers, original)
    assert capture["width_px"] == 40
    assert capture["height_px"] == 20

    processed = process_capture(
        client,
        inspection["id"],
        capture["id"],
        headers,
    )

    assert processed.status_code == 200
    derivative = processed.json()["derivative"]
    assert derivative["width_px"] == 20
    assert derivative["height_px"] == 40

    original_content = client.get(
        f"/api/v1/inspections/{inspection['id']}/captures/{capture['id']}/content",
        headers=headers,
    )
    assert original_content.content == original


def test_dark_blurry_capture_recommends_retake(
    client,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)
    capture = upload_capture(
        client,
        inspection["id"],
        headers,
        dark_image_bytes(),
    )

    response = process_capture(
        client,
        inspection["id"],
        capture["id"],
        headers,
    )

    assert response.status_code == 200
    quality = response.json()["quality"]
    assert quality["status"] == "retake_recommended"
    assert "low_sharpness" in quality["reasons"]
    assert "underexposed" in quality["reasons"]


def test_latest_quality_requires_processing_first(
    client,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)
    capture = upload_capture(
        client,
        inspection["id"],
        headers,
        sharp_pattern_bytes(),
    )

    response = client.get(
        (
            f"/api/v1/inspections/{inspection['id']}/captures/"
            f"{capture['id']}/quality/latest"
        ),
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "capture_quality_not_found"


def test_latest_quality_returns_most_recent_assessment(
    client,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)
    capture = upload_capture(
        client,
        inspection["id"],
        headers,
        sharp_pattern_bytes(),
    )

    first = process_capture(client, inspection["id"], capture["id"], headers)
    second = process_capture(client, inspection["id"], capture["id"], headers)
    assert first.status_code == 200
    assert second.status_code == 200

    latest = client.get(
        (
            f"/api/v1/inspections/{inspection['id']}/captures/"
            f"{capture['id']}/quality/latest"
        ),
        headers=headers,
    )

    assert latest.status_code == 200
    assert latest.json()["id"] == second.json()["quality"]["id"]


def test_supervisor_can_read_quality_but_cannot_process(
    client,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    supervisor = user_factory(UserRole.SUPERVISOR)
    officer_headers = auth_headers(officer)
    supervisor_headers = auth_headers(supervisor)
    inspection = create_inspection(client, officer_headers)
    capture = upload_capture(
        client,
        inspection["id"],
        officer_headers,
        sharp_pattern_bytes(),
    )
    processed = process_capture(
        client,
        inspection["id"],
        capture["id"],
        officer_headers,
    )
    assert processed.status_code == 200

    latest = client.get(
        (
            f"/api/v1/inspections/{inspection['id']}/captures/"
            f"{capture['id']}/quality/latest"
        ),
        headers=supervisor_headers,
    )
    assert latest.status_code == 200

    rejected = process_capture(
        client,
        inspection["id"],
        capture["id"],
        supervisor_headers,
    )
    assert rejected.status_code == 403


def test_other_officer_cannot_process_or_read_quality(
    client,
    user_factory,
    auth_headers,
):
    owner = user_factory(UserRole.OFFICER)
    other = user_factory(UserRole.OFFICER)
    owner_headers = auth_headers(owner)
    other_headers = auth_headers(other)
    inspection = create_inspection(client, owner_headers)
    capture = upload_capture(
        client,
        inspection["id"],
        owner_headers,
        sharp_pattern_bytes(),
    )

    process = process_capture(
        client,
        inspection["id"],
        capture["id"],
        other_headers,
    )
    assert process.status_code == 404

    latest = client.get(
        (
            f"/api/v1/inspections/{inspection['id']}/captures/"
            f"{capture['id']}/quality/latest"
        ),
        headers=other_headers,
    )
    assert latest.status_code == 404


def test_processing_is_blocked_after_inspection_submission(
    client,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)
    capture = upload_capture(
        client,
        inspection["id"],
        headers,
        sharp_pattern_bytes(),
    )

    submit = client.post(
        f"/api/v1/inspections/{inspection['id']}/submit",
        headers=headers,
    )
    assert submit.status_code == 200

    response = process_capture(
        client,
        inspection["id"],
        capture["id"],
        headers,
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "inspection_not_editable"
