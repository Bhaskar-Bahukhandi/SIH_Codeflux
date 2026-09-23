from hashlib import sha256
from io import BytesIO
from uuid import uuid4

from PIL import Image, ImageDraw
from sqlalchemy import select

from app.models.audit import AuditEvent, AuditEventType
from app.models.ocr import OcrBlock, OcrRun
from app.models.quality import CaptureDerivative
from app.models.user import UserRole
from app.services.ocr_engine import (
    OcrDetection,
    OcrInferenceFailed,
    get_ocr_engine,
)


class FakeOcrEngine:
    name = "fake-ocr"
    version = "test-1"
    model_version = "fake-model"
    language = "en"
    parameters = {"source": "test-fixture"}

    def __init__(self, detections=None, *, fail=False):
        self._detections = detections or [
            OcrDetection(
                text="MRP Rs. 50.00",
                confidence=0.93,
                polygon=[
                    [10.0, 10.0],
                    [150.0, 10.0],
                    [150.0, 30.0],
                    [10.0, 30.0],
                ],
            ),
            OcrDetection(
                text="Net Qty 100 g",
                confidence=0.88,
                polygon=[
                    [12.0, 42.0],
                    [160.0, 42.0],
                    [160.0, 62.0],
                    [12.0, 62.0],
                ],
            ),
        ]
        self._fail = fail

    def extract(self, _image_bytes):
        if self._fail:
            raise OcrInferenceFailed("synthetic OCR failure")
        return list(self._detections)


def blank_package_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (320, 240), (120, 120, 120)).save(
        buffer,
        format="JPEG",
        quality=95,
    )
    return buffer.getvalue()


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


def create_inspection(client, headers):
    response = client.post(
        "/api/v1/inspections",
        headers=headers,
        json={"product_name": "OCR Test Product"},
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
    response = client.post(
        f"/api/v1/inspections/{inspection_id}/captures/{capture_id}/process",
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()


def analyze_geometry(client, inspection_id, capture_id, headers):
    response = client.post(
        (
            f"/api/v1/inspections/{inspection_id}/captures/"
            f"{capture_id}/geometry/analyze"
        ),
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()


def install_fake_engine(client, engine=None):
    fake = engine or FakeOcrEngine()
    client.app.dependency_overrides[get_ocr_engine] = lambda: fake
    return fake


def run_ocr(client, inspection_id, capture_id, headers, *, run_id=None):
    return client.post(
        f"/api/v1/inspections/{inspection_id}/captures/{capture_id}/ocr/run",
        headers=headers,
        json={"id": run_id} if run_id is not None else None,
    )


def test_ocr_requires_preprocessing(
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
    install_fake_engine(client)

    response = run_ocr(
        client,
        inspection["id"],
        capture["id"],
        headers,
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "capture_preprocessing_required"


def test_ocr_persists_ordered_blocks_and_provenance_even_when_quality_recommends_retake(
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
    processed = process_capture(
        client,
        inspection["id"],
        capture["id"],
        headers,
    )
    assert processed["quality"]["status"] == "retake_recommended"

    install_fake_engine(client)
    response = run_ocr(
        client,
        inspection["id"],
        capture["id"],
        headers,
    )

    assert response.status_code == 200
    payload = response.json()
    run = payload["run"]
    blocks = payload["blocks"]

    assert run["source_derivative_id"] == processed["derivative"]["id"]
    assert run["source_sha256"] == processed["derivative"]["sha256"]
    assert run["engine_name"] == "fake-ocr"
    assert run["engine_version"] == "test-1"
    assert run["model_version"] == "fake-model"
    assert run["language"] == "en"
    assert run["block_count"] == 2
    assert [block["order_index"] for block in blocks] == [0, 1]
    assert [block["text"] for block in blocks] == [
        "MRP Rs. 50.00",
        "Net Qty 100 g",
    ]
    assert [block["confidence"] for block in blocks] == [0.93, 0.88]

    persisted_blocks = list(
        db_session.scalars(
            select(OcrBlock)
            .where(OcrBlock.run_id == run["id"])
            .order_by(OcrBlock.order_index.asc())
        ).all()
    )
    assert len(persisted_blocks) == 2

    latest = client.get(
        f"/api/v1/inspections/{inspection['id']}/captures/{capture['id']}/ocr/latest",
        headers=headers,
    )
    assert latest.status_code == 200
    assert latest.json()["run"]["id"] == run["id"]
    assert latest.json()["blocks"] == blocks

    events = list(
        db_session.scalars(
            select(AuditEvent).where(
                AuditEvent.inspection_id == inspection["id"],
                AuditEvent.event_type == AuditEventType.CAPTURE_OCR_COMPLETED.value,
            )
        ).all()
    )
    assert len(events) == 1
    assert events[0].details["ocr_run_id"] == run["id"]
    assert events[0].details["block_count"] == 2


def test_ocr_prefers_current_perspective_corrected_derivative(
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
        planar_package_bytes(),
    )
    processed = process_capture(
        client,
        inspection["id"],
        capture["id"],
        headers,
    )
    geometry = analyze_geometry(
        client,
        inspection["id"],
        capture["id"],
        headers,
    )
    assert geometry["geometry"]["status"] == "correction_available"

    corrected_id = geometry["corrected_derivative"]["id"]
    corrected = db_session.get(CaptureDerivative, corrected_id)
    assert corrected is not None
    assert corrected.derivative_type == "perspective_corrected"
    assert geometry["geometry"]["source_derivative_id"] == processed["derivative"]["id"]

    install_fake_engine(client)
    response = run_ocr(
        client,
        inspection["id"],
        capture["id"],
        headers,
    )

    assert response.status_code == 200
    assert response.json()["run"]["source_derivative_id"] == corrected_id


def test_newer_preprocessing_invalidates_older_perspective_source_for_ocr(
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

    first_process = process_capture(
        client,
        inspection["id"],
        capture["id"],
        headers,
    )
    geometry = analyze_geometry(
        client,
        inspection["id"],
        capture["id"],
        headers,
    )
    assert geometry["geometry"]["status"] == "correction_available"

    second_process = process_capture(
        client,
        inspection["id"],
        capture["id"],
        headers,
    )
    assert (
        second_process["derivative"]["id"]
        != first_process["derivative"]["id"]
    )

    install_fake_engine(client)
    response = run_ocr(
        client,
        inspection["id"],
        capture["id"],
        headers,
    )

    assert response.status_code == 200
    assert (
        response.json()["run"]["source_derivative_id"]
        == second_process["derivative"]["id"]
    )
    assert (
        response.json()["run"]["source_derivative_id"]
        != geometry["corrected_derivative"]["id"]
    )


def test_ocr_rejects_tampered_source_derivative_without_persisting_run(
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
        blank_package_bytes(),
    )
    processed = process_capture(
        client,
        inspection["id"],
        capture["id"],
        headers,
    )

    derivative = db_session.get(
        CaptureDerivative,
        processed["derivative"]["id"],
    )
    assert derivative is not None
    media_storage.path_for(derivative.storage_key).write_bytes(b"tampered")

    install_fake_engine(client)
    response = run_ocr(
        client,
        inspection["id"],
        capture["id"],
        headers,
    )

    assert response.status_code == 503
    assert (
        response.json()["error"]["code"]
        == "capture_derivative_integrity_mismatch"
    )
    assert db_session.scalar(select(OcrRun)) is None


def test_ocr_engine_failure_is_explicit_and_does_not_create_run(
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
    process_capture(
        client,
        inspection["id"],
        capture["id"],
        headers,
    )

    install_fake_engine(client, FakeOcrEngine(fail=True))
    response = run_ocr(
        client,
        inspection["id"],
        capture["id"],
        headers,
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ocr_inference_failed"
    assert db_session.scalar(select(OcrRun)) is None


def test_ocr_client_run_id_replay_is_exactly_once(
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
    process_capture(
        client,
        inspection["id"],
        capture["id"],
        headers,
    )
    install_fake_engine(client)

    run_id = str(uuid4())
    first = run_ocr(
        client,
        inspection["id"],
        capture["id"],
        headers,
        run_id=run_id,
    )
    replay = run_ocr(
        client,
        inspection["id"],
        capture["id"],
        headers,
        run_id=run_id,
    )

    assert first.status_code == 200
    assert replay.status_code == 200
    assert first.json()["run"]["id"] == run_id
    assert replay.json() == first.json()
    assert len(list(db_session.scalars(select(OcrRun)).all())) == 1

    events = list(
        db_session.scalars(
            select(AuditEvent).where(
                AuditEvent.inspection_id == inspection["id"],
                AuditEvent.event_type
                == AuditEventType.CAPTURE_OCR_COMPLETED.value,
            )
        ).all()
    )
    assert len(events) == 1

    exact = client.get(
        (
            f"/api/v1/inspections/{inspection['id']}/captures/"
            f"{capture['id']}/ocr/runs/{run_id}"
        ),
        headers=headers,
    )
    assert exact.status_code == 200
    assert exact.json()["run"]["id"] == run_id

    other_capture = upload_capture(
        client,
        inspection["id"],
        headers,
        blank_package_bytes(),
    )
    process_capture(
        client,
        inspection["id"],
        other_capture["id"],
        headers,
    )
    conflict = run_ocr(
        client,
        inspection["id"],
        other_capture["id"],
        headers,
        run_id=run_id,
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "client_resource_id_conflict"


def test_supervisor_can_read_latest_ocr_but_cannot_run_it(
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
    process_capture(
        client,
        inspection["id"],
        capture["id"],
        officer_headers,
    )
    install_fake_engine(client)

    completed = run_ocr(
        client,
        inspection["id"],
        capture["id"],
        officer_headers,
    )
    assert completed.status_code == 200

    latest = client.get(
        f"/api/v1/inspections/{inspection['id']}/captures/{capture['id']}/ocr/latest",
        headers=supervisor_headers,
    )
    assert latest.status_code == 200

    rejected = run_ocr(
        client,
        inspection["id"],
        capture["id"],
        supervisor_headers,
    )
    assert rejected.status_code == 403


def test_other_officer_cannot_read_or_run_ocr(
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
    process_capture(
        client,
        inspection["id"],
        capture["id"],
        owner_headers,
    )
    install_fake_engine(client)
    assert run_ocr(
        client,
        inspection["id"],
        capture["id"],
        owner_headers,
    ).status_code == 200

    latest = client.get(
        f"/api/v1/inspections/{inspection['id']}/captures/{capture['id']}/ocr/latest",
        headers=other_headers,
    )
    assert latest.status_code == 404

    rejected = run_ocr(
        client,
        inspection["id"],
        capture["id"],
        other_headers,
    )
    assert rejected.status_code == 404
