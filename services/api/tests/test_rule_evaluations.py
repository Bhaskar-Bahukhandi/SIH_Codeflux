from datetime import datetime, timezone
from io import BytesIO

from PIL import Image
from sqlalchemy import select

from app.models.audit import AuditEvent, AuditEventType
from app.models.ocr import OcrBlock, OcrRun
from app.models.user import UserRole


SUPPORTED_CONTEXT = {
    "intended_for_retail_sale": True,
    "industrial_or_institutional_consumer": False,
    "package_exceeds_25kg_or_25l": False,
}


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
        json={"product_name": "Rule Engine Test Product"},
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


def seed_ocr(db_session, *, capture_id, derivative, texts):
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
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(run)
    db_session.flush()

    for index, text in enumerate(texts):
        db_session.add(
            OcrBlock(
                run_id=run.id,
                order_index=index,
                text=text,
                confidence=0.95,
                polygon=[
                    [0.0, float(index * 20)],
                    [200.0, float(index * 20)],
                    [200.0, float(index * 20 + 15)],
                    [0.0, float(index * 20 + 15)],
                ],
            )
        )

    db_session.commit()
    db_session.refresh(run)
    return run


def extract(client, inspection_id, headers):
    response = client.post(
        f"/api/v1/inspections/{inspection_id}/declarations/extract",
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()


def evaluate(client, inspection_id, headers, context=None):
    return client.post(
        f"/api/v1/inspections/{inspection_id}/rule-evaluations/evaluate",
        headers=headers,
        json={"context": context if context is not None else SUPPORTED_CONTEXT},
    )


def result_by_type(payload, declaration_type):
    return next(
        item
        for item in payload["results"]
        if item["declaration_type"] == declaration_type
    )


def test_supported_scope_passes_detected_declaration_evidence(
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
    seed_ocr(
        db_session,
        capture_id=capture["id"],
        derivative=derivative,
        texts=[
            "MRP Rs. 50.00",
            "Net Quantity 100 g",
        ],
    )
    extraction = extract(client, inspection["id"], headers)

    response = evaluate(client, inspection["id"], headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["source_extraction_run_id"] == extraction["run"]["id"]
    assert payload["run"]["rule_pack_id"] == "lmpc-retail-evidence"
    assert payload["run"]["rule_pack_version"] == "2026.09-v1"
    assert len(payload["run"]["rule_pack_sha256"]) == 64
    assert payload["run"]["context_snapshot"] == SUPPORTED_CONTEXT
    assert payload["run"]["result_count"] == 2

    mrp_result = result_by_type(payload, "mrp")
    net_quantity_result = result_by_type(payload, "net_quantity")
    assert mrp_result["status"] == "pass"
    assert net_quantity_result["status"] == "pass"
    assert mrp_result["details"]["effective_from"] == "2022-10-01"
    assert net_quantity_result["details"]["effective_from"] == "2011-04-01"
    assert mrp_result["details"]["source_ids"]
    assert net_quantity_result["details"]["applicability_note"]

    events = list(
        db_session.scalars(
            select(AuditEvent).where(
                AuditEvent.inspection_id == inspection["id"],
                AuditEvent.event_type
                == AuditEventType.RULE_EVALUATION_COMPLETED.value,
            )
        ).all()
    )
    assert len(events) == 1
    assert events[0].details["rule_pack_version"] == "2026.09-v1"


def test_conflict_and_not_detected_require_manual_verification(
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
    extract(client, inspection["id"], headers)

    response = evaluate(client, inspection["id"], headers)

    assert response.status_code == 200
    payload = response.json()
    assert result_by_type(payload, "mrp")["status"] == (
        "manual_verification_required"
    )
    assert result_by_type(payload, "net_quantity")["status"] == (
        "manual_verification_required"
    )
    assert "non-compliance" not in (
        result_by_type(payload, "net_quantity")["explanation"].lower()
    )


def test_incomplete_context_is_indeterminate(
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
    seed_ocr(
        db_session,
        capture_id=capture["id"],
        derivative=derivative,
        texts=["MRP Rs. 50.00", "Net Qty 100 g"],
    )
    extract(client, inspection["id"], headers)

    response = evaluate(
        client,
        inspection["id"],
        headers,
        context={
            "intended_for_retail_sale": True,
            "industrial_or_institutional_consumer": None,
            "package_exceeds_25kg_or_25l": False,
        },
    )

    assert response.status_code == 200
    assert {
        item["status"] for item in response.json()["results"]
    } == {"indeterminate"}


def test_unsupported_scope_is_not_evaluated(
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
    seed_ocr(
        db_session,
        capture_id=capture["id"],
        derivative=derivative,
        texts=["MRP Rs. 50.00", "Net Qty 100 g"],
    )
    extract(client, inspection["id"], headers)

    response = evaluate(
        client,
        inspection["id"],
        headers,
        context={
            "intended_for_retail_sale": True,
            "industrial_or_institutional_consumer": True,
            "package_exceeds_25kg_or_25l": False,
        },
    )

    assert response.status_code == 200
    assert {
        item["status"] for item in response.json()["results"]
    } == {"not_evaluated"}


def test_stale_extraction_is_rejected(
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
    seed_ocr(
        db_session,
        capture_id=capture["id"],
        derivative=derivative,
        texts=["MRP Rs. 50.00", "Net Qty 100 g"],
    )
    extract(client, inspection["id"], headers)

    reprocess = client.post(
        f"/api/v1/inspections/{inspection['id']}/captures/{capture['id']}/process",
        headers=headers,
    )
    assert reprocess.status_code == 200

    response = evaluate(client, inspection["id"], headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == (
        "current_declaration_extraction_required"
    )


def test_supervisor_can_read_latest_but_cannot_evaluate(
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
        client, inspection["id"], officer_headers, "front"
    )
    seed_ocr(
        db_session,
        capture_id=capture["id"],
        derivative=derivative,
        texts=["MRP Rs. 50.00", "Net Qty 100 g"],
    )
    extract(client, inspection["id"], officer_headers)

    evaluated = evaluate(client, inspection["id"], officer_headers)
    assert evaluated.status_code == 200

    latest = client.get(
        f"/api/v1/inspections/{inspection['id']}/rule-evaluations/latest",
        headers=supervisor_headers,
    )
    assert latest.status_code == 200

    rejected = evaluate(client, inspection["id"], supervisor_headers)
    assert rejected.status_code == 403
