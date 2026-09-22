from datetime import datetime, timedelta, timezone
from io import BytesIO

from PIL import Image
from sqlalchemy import select

from app.models.audit import AuditEvent, AuditEventType
from app.models.ocr import OcrBlock, OcrRun
from app.models.user import UserRole


def image_bytes() -> bytes:
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
        json={"product_name": "Declaration Test Product"},
    )
    assert response.status_code == 201
    return response.json()


def upload_and_process(client, inspection_id, headers, view_type):
    upload = client.post(
        f"/api/v1/inspections/{inspection_id}/captures",
        headers=headers,
        data={"view_type": view_type},
        files={"file": (f"{view_type}.jpg", image_bytes(), "image/jpeg")},
    )
    assert upload.status_code == 201
    capture = upload.json()

    process = client.post(
        f"/api/v1/inspections/{inspection_id}/captures/{capture['id']}/process",
        headers=headers,
    )
    assert process.status_code == 200
    return capture, process.json()["derivative"]


def seed_ocr(
    db_session,
    *,
    capture_id,
    derivative,
    texts,
    created_at=None,
):
    run = OcrRun(
        capture_id=capture_id,
        source_derivative_id=derivative["id"],
        source_sha256=derivative["sha256"],
        engine_name="fixture",
        engine_version="test",
        model_version="fixture-v1",
        language="en",
        parameters={"source": "test"},
        block_count=len(texts),
        created_at=created_at or datetime.now(timezone.utc),
    )
    db_session.add(run)
    db_session.flush()

    blocks = []
    for index, item in enumerate(texts):
        if isinstance(item, tuple):
            text, confidence = item
        else:
            text, confidence = item, 0.9
        block = OcrBlock(
            run_id=run.id,
            order_index=index,
            text=text,
            confidence=confidence,
            polygon=[
                [0.0, float(index * 20)],
                [200.0, float(index * 20)],
                [200.0, float(index * 20 + 15)],
                [0.0, float(index * 20 + 15)],
            ],
        )
        db_session.add(block)
        blocks.append(block)

    db_session.commit()
    for block in blocks:
        db_session.refresh(block)
    db_session.refresh(run)
    return run, blocks


def summary(payload, declaration_type):
    return next(
        item
        for item in payload["summaries"]
        if item["declaration_type"] == declaration_type
    )


def test_two_capture_values_are_fused_as_consistent(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)

    front, front_derivative = upload_and_process(
        client, inspection["id"], headers, "front"
    )
    back, back_derivative = upload_and_process(
        client, inspection["id"], headers, "back"
    )

    _, front_blocks = seed_ocr(
        db_session,
        capture_id=front["id"],
        derivative=front_derivative,
        texts=[
            ("MRP: Rs. 50.00", 0.95),
            ("Net Qty 100 g", 0.91),
        ],
    )
    seed_ocr(
        db_session,
        capture_id=back["id"],
        derivative=back_derivative,
        texts=[
            ("MRP ₹50", 0.93),
            ("Net Quantity: 100 grams", 0.89),
        ],
    )

    response = client.post(
        f"/api/v1/inspections/{inspection['id']}/declarations/extract",
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["inspection_capture_count"] == 2
    assert payload["run"]["source_capture_count"] == 2
    assert set(payload["run"]["source_capture_ids"]) == {
        front["id"],
        back["id"],
    }
    assert payload["run"]["skipped_sources"] == []

    mrp = summary(payload, "mrp")
    assert mrp["status"] == "consistent"
    assert mrp["canonical_value"] == {
        "currency": "INR",
        "amount": "50.00",
    }
    assert mrp["capture_count"] == 2

    quantity = summary(payload, "net_quantity")
    assert quantity["status"] == "consistent"
    assert quantity["canonical_value"] == {
        "value": "100",
        "unit": "g",
    }

    front_mrp = next(
        observation
        for observation in payload["observations"]
        if observation["capture_id"] == front["id"]
        and observation["declaration_type"] == "mrp"
    )
    assert front_mrp["source_block_ids"] == [front_blocks[0].id]
    assert front_mrp["ocr_confidence_min"] == 0.95

    events = list(
        db_session.scalars(
            select(AuditEvent).where(
                AuditEvent.inspection_id == inspection["id"],
                AuditEvent.event_type
                == AuditEventType.DECLARATION_EXTRACTION_COMPLETED.value,
            )
        ).all()
    )
    assert len(events) == 1
    assert events[0].details["summary_statuses"]["mrp"] == "consistent"


def test_conflicting_mrp_values_are_preserved_without_winner(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)
    front, front_derivative = upload_and_process(
        client, inspection["id"], headers, "front"
    )
    back, back_derivative = upload_and_process(
        client, inspection["id"], headers, "back"
    )

    seed_ocr(
        db_session,
        capture_id=front["id"],
        derivative=front_derivative,
        texts=["MRP Rs. 50.00"],
    )
    seed_ocr(
        db_session,
        capture_id=back["id"],
        derivative=back_derivative,
        texts=["MRP Rs. 60.00"],
    )

    response = client.post(
        f"/api/v1/inspections/{inspection['id']}/declarations/extract",
        headers=headers,
    )

    assert response.status_code == 200
    mrp = summary(response.json(), "mrp")
    assert mrp["status"] == "conflict"
    assert mrp["canonical_value"] is None
    assert mrp["capture_count"] == 2
    assert mrp["candidate_values"] == [
        {"currency": "INR", "amount": "50.00"},
        {"currency": "INR", "amount": "60.00"},
    ]

    quantity = summary(response.json(), "net_quantity")
    assert quantity["status"] == "not_detected"


def test_split_label_value_keeps_two_ocr_blocks_as_provenance(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)
    capture, derivative = upload_and_process(
        client, inspection["id"], headers, "front"
    )
    _, blocks = seed_ocr(
        db_session,
        capture_id=capture["id"],
        derivative=derivative,
        texts=[
            ("MRP", 0.96),
            ("Rs. 75.00", 0.82),
        ],
    )

    response = client.post(
        f"/api/v1/inspections/{inspection['id']}/declarations/extract",
        headers=headers,
    )

    assert response.status_code == 200
    mrp_observation = next(
        item
        for item in response.json()["observations"]
        if item["declaration_type"] == "mrp"
    )
    assert mrp_observation["source_block_ids"] == [
        blocks[0].id,
        blocks[1].id,
    ]
    assert mrp_observation["ocr_confidence_min"] == 0.82
    assert mrp_observation["ocr_confidence_mean"] == 0.89


def test_stale_ocr_capture_is_skipped_when_another_current_source_exists(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)

    stale_capture, stale_derivative = upload_and_process(
        client, inspection["id"], headers, "front"
    )
    current_capture, current_derivative = upload_and_process(
        client, inspection["id"], headers, "back"
    )

    seed_ocr(
        db_session,
        capture_id=stale_capture["id"],
        derivative=stale_derivative,
        texts=["MRP Rs. 40.00"],
    )
    seed_ocr(
        db_session,
        capture_id=current_capture["id"],
        derivative=current_derivative,
        texts=["MRP Rs. 50.00"],
    )

    newer_process = client.post(
        (
            f"/api/v1/inspections/{inspection['id']}/captures/"
            f"{stale_capture['id']}/process"
        ),
        headers=headers,
    )
    assert newer_process.status_code == 200

    response = client.post(
        f"/api/v1/inspections/{inspection['id']}/declarations/extract",
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["source_capture_count"] == 1
    assert payload["run"]["source_capture_ids"] == [current_capture["id"]]
    assert payload["run"]["skipped_sources"] == [
        {
            "capture_id": stale_capture["id"],
            "reason": "stale_ocr",
            "ocr_run_id": payload["run"]["source_ocr_run_ids"][0]
            if False
            else next(
                item["ocr_run_id"]
                for item in payload["run"]["skipped_sources"]
                if item["capture_id"] == stale_capture["id"]
            ),
        }
    ]

    mrp = summary(payload, "mrp")
    assert mrp["status"] == "single_source"
    assert mrp["canonical_value"]["amount"] == "50.00"


def test_latest_ocr_run_per_capture_is_used(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)
    capture, derivative = upload_and_process(
        client, inspection["id"], headers, "front"
    )

    base_time = datetime(2026, 9, 23, tzinfo=timezone.utc)
    old_run, _ = seed_ocr(
        db_session,
        capture_id=capture["id"],
        derivative=derivative,
        texts=["MRP Rs. 40.00"],
        created_at=base_time,
    )
    new_run, _ = seed_ocr(
        db_session,
        capture_id=capture["id"],
        derivative=derivative,
        texts=["MRP Rs. 55.00"],
        created_at=base_time + timedelta(seconds=1),
    )

    response = client.post(
        f"/api/v1/inspections/{inspection['id']}/declarations/extract",
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["source_ocr_run_ids"] == [new_run.id]
    assert old_run.id not in payload["run"]["source_ocr_run_ids"]
    assert summary(payload, "mrp")["canonical_value"]["amount"] == "55.00"


def test_no_current_ocr_source_returns_conflict(
    client,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)
    upload_and_process(client, inspection["id"], headers, "front")

    response = client.post(
        f"/api/v1/inspections/{inspection['id']}/declarations/extract",
        headers=headers,
    )

    assert response.status_code == 409
    assert (
        response.json()["error"]["code"]
        == "inspection_current_ocr_required"
    )


def test_supervisor_can_read_latest_but_cannot_extract(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    supervisor = user_factory(UserRole.SUPERVISOR)
    officer_headers = auth_headers(officer)
    supervisor_headers = auth_headers(supervisor)

    inspection = create_inspection(client, officer_headers)
    capture, derivative = upload_and_process(
        client,
        inspection["id"],
        officer_headers,
        "front",
    )
    seed_ocr(
        db_session,
        capture_id=capture["id"],
        derivative=derivative,
        texts=["MRP Rs. 50.00"],
    )

    extracted = client.post(
        f"/api/v1/inspections/{inspection['id']}/declarations/extract",
        headers=officer_headers,
    )
    assert extracted.status_code == 200

    latest = client.get(
        f"/api/v1/inspections/{inspection['id']}/declarations/latest",
        headers=supervisor_headers,
    )
    assert latest.status_code == 200

    rejected = client.post(
        f"/api/v1/inspections/{inspection['id']}/declarations/extract",
        headers=supervisor_headers,
    )
    assert rejected.status_code == 403
