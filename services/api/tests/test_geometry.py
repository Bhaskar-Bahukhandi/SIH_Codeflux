from hashlib import sha256
from io import BytesIO

from PIL import Image, ImageDraw
from sqlalchemy import select

from app.models.audit import AuditEvent, AuditEventType
from app.models.geometry import CaptureGeometryAssessment
from app.models.quality import CaptureDerivative, CaptureQualityAssessment
from app.models.user import UserRole


def planar_package_bytes() -> bytes:
    image = Image.new("RGB", (420, 320), (28, 32, 36))
    draw = ImageDraw.Draw(image)

    polygon = [(18, 22), (400, 38), (382, 300), (30, 286)]
    draw.polygon(polygon, fill=(145, 150, 155))
    draw.line(polygon + [polygon[0]], fill=(245, 245, 245), width=7)

    for x in range(70, 350, 42):
        draw.line((x, 70, x - 8, 255), fill=(70, 70, 70), width=3)
    for y in range(82, 250, 34):
        draw.line((70, y, 350, y + 7), fill=(205, 205, 205), width=3)

    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=96)
    return buffer.getvalue()


def blank_package_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (320, 240), (120, 120, 120)).save(
        buffer,
        format="JPEG",
        quality=95,
    )
    return buffer.getvalue()


def create_inspection(client, headers):
    response = client.post(
        "/api/v1/inspections",
        headers=headers,
        json={"product_name": "Geometry Test Product"},
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


def preprocess(client, inspection_id, capture_id, headers):
    response = client.post(
        f"/api/v1/inspections/{inspection_id}/captures/{capture_id}/process",
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()


def analyze(client, inspection_id, capture_id, headers):
    return client.post(
        (
            f"/api/v1/inspections/{inspection_id}/captures/"
            f"{capture_id}/geometry/analyze"
        ),
        headers=headers,
    )


def test_clear_planar_package_creates_separate_perspective_derivative(
    client,
    db_session,
    media_storage,
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
        planar_package_bytes(),
    )
    processed = preprocess(client, inspection["id"], capture["id"], headers)

    source_id = processed["derivative"]["id"]
    source = db_session.get(CaptureDerivative, source_id)
    assert source is not None
    source_path = media_storage.path_for(source.storage_key)
    source_before = source_path.read_bytes()
    source_hash_before = sha256(source_before).hexdigest()
    assert source_hash_before == source.sha256

    response = analyze(client, inspection["id"], capture["id"], headers)

    assert response.status_code == 200
    result = response.json()
    geometry = result["geometry"]
    corrected = result["corrected_derivative"]

    assert geometry["status"] == "correction_available"
    assert geometry["source_derivative_id"] == source_id
    assert geometry["corrected_derivative_id"] is not None
    assert geometry["corners"] is not None
    assert len(geometry["corners"]) == 4
    assert geometry["area_ratio"] > 0.20
    assert geometry["angle_score"] >= 0.60
    assert geometry["geometry_score"] >= geometry["thresholds"]["correction_score"]
    assert geometry["reasons"] == []

    assert corrected is not None
    assert corrected["derivative_type"] == "perspective_corrected"
    assert corrected["processing_version"] == "perspective-v1"
    assert corrected["id"] == geometry["corrected_derivative_id"]

    corrected_content = client.get(
        (
            f"/api/v1/inspections/{inspection['id']}/captures/"
            f"{capture['id']}/derivatives/{corrected['id']}/content"
        ),
        headers=headers,
    )
    assert corrected_content.status_code == 200
    assert sha256(corrected_content.content).hexdigest() == corrected["sha256"]

    assert source_path.read_bytes() == source_before
    assert sha256(source_path.read_bytes()).hexdigest() == source_hash_before

    events = list(
        db_session.scalars(
            select(AuditEvent).where(
                AuditEvent.inspection_id == inspection["id"],
                AuditEvent.event_type
                == AuditEventType.CAPTURE_GEOMETRY_ANALYZED.value,
            )
        ).all()
    )
    assert len(events) == 1
    assert events[0].details["geometry_status"] == "correction_available"


def test_ambiguous_image_falls_back_without_corrected_derivative(
    client,
    db_session,
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
        blank_package_bytes(),
    )
    preprocess(client, inspection["id"], capture["id"], headers)

    response = analyze(client, inspection["id"], capture["id"], headers)

    assert response.status_code == 200
    result = response.json()
    assert result["geometry"]["status"] == "not_detected"
    assert result["geometry"]["corrected_derivative_id"] is None
    assert result["corrected_derivative"] is None
    assert "no_reliable_quadrilateral" in result["geometry"]["reasons"]

    geometry = db_session.get(
        CaptureGeometryAssessment,
        result["geometry"]["id"],
    )
    assert geometry is not None
    assert geometry.corrected_derivative_id is None


def test_geometry_requires_prior_preprocessing(
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
        planar_package_bytes(),
    )

    response = analyze(client, inspection["id"], capture["id"], headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "capture_preprocessing_required"


def test_geometry_rejects_tampered_source_derivative(
    client,
    db_session,
    media_storage,
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
        planar_package_bytes(),
    )
    processed = preprocess(client, inspection["id"], capture["id"], headers)

    source = db_session.get(
        CaptureDerivative,
        processed["derivative"]["id"],
    )
    assert source is not None
    media_storage.path_for(source.storage_key).write_bytes(b"tampered derivative")

    response = analyze(client, inspection["id"], capture["id"], headers)

    assert response.status_code == 503
    assert (
        response.json()["error"]["code"]
        == "capture_derivative_integrity_mismatch"
    )
    assert db_session.scalar(select(CaptureGeometryAssessment)) is None


def test_latest_geometry_returns_most_recent_assessment(
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
        blank_package_bytes(),
    )
    preprocess(client, inspection["id"], capture["id"], headers)

    first = analyze(client, inspection["id"], capture["id"], headers)
    second = analyze(client, inspection["id"], capture["id"], headers)
    assert first.status_code == 200
    assert second.status_code == 200

    latest = client.get(
        (
            f"/api/v1/inspections/{inspection['id']}/captures/"
            f"{capture['id']}/geometry/latest"
        ),
        headers=headers,
    )

    assert latest.status_code == 200
    assert latest.json()["id"] == second.json()["geometry"]["id"]


def test_supervisor_can_read_geometry_but_cannot_analyze(
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
        blank_package_bytes(),
    )
    preprocess(client, inspection["id"], capture["id"], officer_headers)
    result = analyze(
        client,
        inspection["id"],
        capture["id"],
        officer_headers,
    )
    assert result.status_code == 200

    latest = client.get(
        (
            f"/api/v1/inspections/{inspection['id']}/captures/"
            f"{capture['id']}/geometry/latest"
        ),
        headers=supervisor_headers,
    )
    assert latest.status_code == 200

    rejected = analyze(
        client,
        inspection["id"],
        capture["id"],
        supervisor_headers,
    )
    assert rejected.status_code == 403


def test_other_officer_cannot_analyze_or_read_geometry(
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
        blank_package_bytes(),
    )
    preprocess(client, inspection["id"], capture["id"], owner_headers)

    rejected = analyze(
        client,
        inspection["id"],
        capture["id"],
        other_headers,
    )
    assert rejected.status_code == 404

    latest = client.get(
        (
            f"/api/v1/inspections/{inspection['id']}/captures/"
            f"{capture['id']}/geometry/latest"
        ),
        headers=other_headers,
    )
    assert latest.status_code == 404


def test_geometry_analysis_is_blocked_after_submission(
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
        blank_package_bytes(),
    )
    preprocess(client, inspection["id"], capture["id"], headers)

    submit = client.post(
        f"/api/v1/inspections/{inspection['id']}/submit",
        headers=headers,
    )
    assert submit.status_code == 200

    response = analyze(client, inspection["id"], capture["id"], headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "inspection_not_editable"
