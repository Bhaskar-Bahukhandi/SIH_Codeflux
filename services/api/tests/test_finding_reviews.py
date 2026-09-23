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


def create_inspection(client, headers, name="Finding Review Product"):
    response = client.post(
        "/api/v1/inspections",
        headers=headers,
        json={"product_name": name},
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


def extract_and_evaluate(client, inspection_id, headers, context=None):
    extraction = client.post(
        f"/api/v1/inspections/{inspection_id}/declarations/extract",
        headers=headers,
    )
    assert extraction.status_code == 200

    evaluation = client.post(
        f"/api/v1/inspections/{inspection_id}/rule-evaluations/evaluate",
        headers=headers,
        json={"context": context if context is not None else SUPPORTED_CONTEXT},
    )
    assert evaluation.status_code == 200
    return extraction.json(), evaluation.json()


def machine_result(payload, declaration_type):
    return next(
        item
        for item in payload["results"]
        if item["declaration_type"] == declaration_type
    )


def create_review(
    client,
    inspection_id,
    headers,
    *,
    result_id,
    decision,
    evidence_capture_ids=None,
    corrected_value=None,
    note=None,
):
    return client.post(
        f"/api/v1/inspections/{inspection_id}/finding-reviews",
        headers=headers,
        json={
            "rule_evaluation_result_id": result_id,
            "decision": decision,
            "evidence_capture_ids": evidence_capture_ids or [],
            "corrected_value": corrected_value,
            "note": note,
        },
    )


def test_officer_confirm_present_keeps_machine_result_immutable(
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
    _, evaluation = extract_and_evaluate(
        client, inspection["id"], headers
    )
    mrp = machine_result(evaluation, "mrp")
    machine_details_before = mrp["details"].copy()

    response = create_review(
        client,
        inspection["id"],
        headers,
        result_id=mrp["id"],
        decision="confirm_present",
        evidence_capture_ids=[capture["id"]],
    )

    assert response.status_code == 201
    review = response.json()
    assert review["decision"] == "confirm_present"
    assert review["outcome"] == "verified_declaration_present"
    assert review["corrected_value"] is None
    assert review["evidence_capture_ids"] == [capture["id"]]

    latest_machine = client.get(
        f"/api/v1/inspections/{inspection['id']}/rule-evaluations/latest",
        headers=headers,
    )
    assert latest_machine.status_code == 200
    latest_mrp = machine_result(latest_machine.json(), "mrp")
    assert latest_mrp["details"] == machine_details_before
    assert latest_mrp["status"] == "pass"

    events = list(
        db_session.scalars(
            select(AuditEvent).where(
                AuditEvent.inspection_id == inspection["id"],
                AuditEvent.event_type
                == AuditEventType.FINDING_REVIEW_RECORDED.value,
            )
        ).all()
    )
    assert len(events) == 1
    assert events[0].details["outcome"] == "verified_declaration_present"


def test_confirmed_absence_is_only_human_path_to_potential_non_compliance(
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
        texts=["MRP Rs. 50.00"],
    )
    _, evaluation = extract_and_evaluate(
        client, inspection["id"], headers
    )
    quantity = machine_result(evaluation, "net_quantity")
    assert quantity["status"] == "manual_verification_required"

    response = create_review(
        client,
        inspection["id"],
        headers,
        result_id=quantity["id"],
        decision="confirm_absent",
        evidence_capture_ids=[capture["id"]],
        note="Checked the visible package panel; net quantity declaration was not present.",
    )

    assert response.status_code == 201
    review = response.json()
    assert review["outcome"] == "potential_non_compliance"
    assert review["decision"] == "confirm_absent"
    assert review["note"]


def test_officer_correction_is_separate_and_normalized(
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
    _, evaluation = extract_and_evaluate(
        client, inspection["id"], headers
    )
    mrp = machine_result(evaluation, "mrp")
    assert mrp["status"] == "manual_verification_required"
    machine_candidates = list(mrp["details"]["candidate_values"])

    response = create_review(
        client,
        inspection["id"],
        headers,
        result_id=mrp["id"],
        decision="correct_value",
        evidence_capture_ids=[front["id"], back["id"]],
        corrected_value={"currency": "inr", "amount": "55"},
        note="Manual reading confirms MRP as Rs. 55.00.",
    )

    assert response.status_code == 201
    review = response.json()
    assert review["outcome"] == "verified_declaration_present"
    assert review["corrected_value"] == {
        "currency": "INR",
        "amount": "55.00",
    }

    latest_machine = client.get(
        f"/api/v1/inspections/{inspection['id']}/rule-evaluations/latest",
        headers=headers,
    ).json()
    assert machine_result(
        latest_machine, "mrp"
    )["details"]["candidate_values"] == machine_candidates


def test_review_history_is_append_only_and_workspace_uses_latest(
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
    _, evaluation = extract_and_evaluate(
        client, inspection["id"], headers
    )
    mrp = machine_result(evaluation, "mrp")

    first = create_review(
        client,
        inspection["id"],
        headers,
        result_id=mrp["id"],
        decision="request_recheck",
        note="Need a closer image of the price declaration.",
    )
    assert first.status_code == 201

    second = create_review(
        client,
        inspection["id"],
        headers,
        result_id=mrp["id"],
        decision="confirm_present",
        evidence_capture_ids=[capture["id"]],
    )
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]

    history = client.get(
        (
            f"/api/v1/inspections/{inspection['id']}/finding-reviews/"
            f"{mrp['id']}/history"
        ),
        headers=headers,
    )
    assert history.status_code == 200
    assert [item["id"] for item in history.json()] == [
        first.json()["id"],
        second.json()["id"],
    ]

    workspace = client.get(
        f"/api/v1/inspections/{inspection['id']}/finding-reviews/latest",
        headers=headers,
    )
    assert workspace.status_code == 200
    mrp_item = next(
        item
        for item in workspace.json()["items"]
        if item["machine_result"]["id"] == mrp["id"]
    )
    assert mrp_item["latest_review"]["id"] == second.json()["id"]


def test_review_rejects_stale_rule_evaluation(
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
    _, evaluation = extract_and_evaluate(
        client, inspection["id"], headers
    )
    mrp = machine_result(evaluation, "mrp")

    reprocess = client.post(
        f"/api/v1/inspections/{inspection['id']}/captures/{capture['id']}/process",
        headers=headers,
    )
    assert reprocess.status_code == 200

    response = create_review(
        client,
        inspection["id"],
        headers,
        result_id=mrp["id"],
        decision="confirm_present",
        evidence_capture_ids=[capture["id"]],
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "current_rule_evaluation_required"


def test_indeterminate_rule_result_cannot_be_turned_into_finding(
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
    _, evaluation = extract_and_evaluate(
        client,
        inspection["id"],
        headers,
        context={
            "intended_for_retail_sale": True,
            "industrial_or_institutional_consumer": None,
            "package_exceeds_25kg_or_25l": False,
        },
    )
    mrp = machine_result(evaluation, "mrp")
    assert mrp["status"] == "indeterminate"

    response = create_review(
        client,
        inspection["id"],
        headers,
        result_id=mrp["id"],
        decision="confirm_absent",
        evidence_capture_ids=[capture["id"]],
        note="Should not be accepted until applicability is resolved.",
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "rule_result_not_reviewable"


def test_review_rejects_cross_inspection_evidence_and_bad_correction(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)

    inspection = create_inspection(client, headers, "Primary")
    capture, derivative = upload_and_process(
        client, inspection["id"], headers, "front"
    )
    seed_ocr(
        db_session,
        capture_id=capture["id"],
        derivative=derivative,
        texts=["MRP Rs. 50.00", "Net Qty 100 g"],
    )
    _, evaluation = extract_and_evaluate(
        client, inspection["id"], headers
    )
    mrp = machine_result(evaluation, "mrp")

    other_inspection = create_inspection(client, headers, "Other")
    other_capture, _ = upload_and_process(
        client, other_inspection["id"], headers, "front"
    )

    bad_evidence = create_review(
        client,
        inspection["id"],
        headers,
        result_id=mrp["id"],
        decision="confirm_present",
        evidence_capture_ids=[other_capture["id"]],
    )
    assert bad_evidence.status_code == 422
    assert bad_evidence.json()["error"]["code"] == "invalid_review_evidence"

    bad_correction = create_review(
        client,
        inspection["id"],
        headers,
        result_id=mrp["id"],
        decision="correct_value",
        evidence_capture_ids=[capture["id"]],
        corrected_value={"currency": "USD", "amount": "50"},
        note="Invalid correction fixture.",
    )
    assert bad_correction.status_code == 422
    assert bad_correction.json()["error"]["code"] == "invalid_corrected_value"


def test_supervisor_can_read_reviews_but_cannot_create_them(
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
    _, evaluation = extract_and_evaluate(
        client, inspection["id"], officer_headers
    )
    mrp = machine_result(evaluation, "mrp")

    created = create_review(
        client,
        inspection["id"],
        officer_headers,
        result_id=mrp["id"],
        decision="confirm_present",
        evidence_capture_ids=[capture["id"]],
    )
    assert created.status_code == 201

    workspace = client.get(
        f"/api/v1/inspections/{inspection['id']}/finding-reviews/latest",
        headers=supervisor_headers,
    )
    assert workspace.status_code == 200

    history = client.get(
        (
            f"/api/v1/inspections/{inspection['id']}/finding-reviews/"
            f"{mrp['id']}/history"
        ),
        headers=supervisor_headers,
    )
    assert history.status_code == 200

    rejected = create_review(
        client,
        inspection["id"],
        supervisor_headers,
        result_id=mrp["id"],
        decision="confirm_present",
        evidence_capture_ids=[capture["id"]],
    )
    assert rejected.status_code == 403
