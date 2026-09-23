from hashlib import sha256

from sqlalchemy import select

from app.models.audit import AuditEvent, AuditEventType
from app.models.capture import Capture, CaptureViewType
from app.models.declaration import (
    DeclarationExtractionRun,
    DeclarationFusionStatus,
    DeclarationSummary,
    DeclarationType,
)
from app.models.rule_evaluation import (
    RuleEvaluationResult,
    RuleEvaluationRun,
    RuleEvaluationStatus,
)
from app.models.user import UserRole
from app.services.report_pdf import build_report_pdf


def create_inspection(client, headers):
    response = client.post(
        "/api/v1/inspections",
        headers=headers,
        json={
            "product_name": "Finalization Test Product",
            "product_identifier": "FINAL-001",
        },
    )
    assert response.status_code == 201
    return response.json()


def seed_rule_result(
    db_session,
    *,
    inspection_id,
    officer_id,
    status=RuleEvaluationStatus.PASS,
    declaration_type=DeclarationType.MRP,
    canonical_value=None,
):
    capture = Capture(
        inspection_id=inspection_id,
        uploader_user_id=officer_id,
        view_type=CaptureViewType.FRONT,
        original_filename="front.jpg",
        storage_key=f"tests/finalization/{inspection_id}/front.jpg",
        sha256="a" * 64,
        mime_type="image/jpeg",
        size_bytes=512,
        width_px=640,
        height_px=480,
    )
    db_session.add(capture)
    db_session.flush()

    extraction = DeclarationExtractionRun(
        inspection_id=inspection_id,
        actor_user_id=officer_id,
        extractor_version="fixture-extractor",
        fusion_version="fixture-fusion",
        inspection_capture_count=1,
        source_capture_count=0,
        source_capture_ids=[],
        source_ocr_run_ids=[],
        skipped_sources=[
            {
                "capture_id": capture.id,
                "reason": "no_ocr",
            }
        ],
        observation_count=0,
    )
    db_session.add(extraction)
    db_session.flush()

    if canonical_value is None and status is RuleEvaluationStatus.PASS:
        if declaration_type is DeclarationType.MRP:
            canonical_value = {"currency": "INR", "amount": "50.00"}
        else:
            canonical_value = {"value": "100", "unit": "g"}

    summary_status = (
        DeclarationFusionStatus.SINGLE_SOURCE
        if canonical_value is not None
        else DeclarationFusionStatus.NOT_DETECTED
    )
    summary = DeclarationSummary(
        extraction_run_id=extraction.id,
        declaration_type=declaration_type,
        status=summary_status,
        canonical_value=canonical_value,
        candidate_values=[canonical_value] if canonical_value is not None else [],
        observation_count=0,
        capture_count=0,
    )
    db_session.add(summary)
    db_session.flush()

    run = RuleEvaluationRun(
        inspection_id=inspection_id,
        actor_user_id=officer_id,
        source_extraction_run_id=extraction.id,
        rule_pack_id="fixture-pack",
        rule_pack_version="fixture-v1",
        rule_pack_sha256="b" * 64,
        rule_pack_snapshot={
            "rule_pack_id": "fixture-pack",
            "version": "fixture-v1",
            "rules": [],
        },
        context_snapshot={
            "intended_for_retail_sale": True,
            "industrial_or_institutional_consumer": False,
            "package_exceeds_25kg_or_25l": False,
        },
        result_count=1,
    )
    db_session.add(run)
    db_session.flush()

    result = RuleEvaluationResult(
        evaluation_run_id=run.id,
        rule_id=(
            "LMPC-R6-1-E-MRP-EVIDENCE"
            if declaration_type is DeclarationType.MRP
            else "LMPC-R6-1-C-NET-QUANTITY-EVIDENCE"
        ),
        provision=(
            "Rule 6(1)(e)"
            if declaration_type is DeclarationType.MRP
            else "Rule 6(1)(c)"
        ),
        declaration_type=declaration_type.value,
        status=status,
        evidence_summary_id=summary.id,
        explanation="Fixture preliminary evidence result.",
        details={
            "source_ids": ["fixture-source"],
            "effective_from": "2022-10-01",
        },
    )
    db_session.add(result)
    db_session.commit()
    db_session.refresh(run)
    db_session.refresh(result)
    return run, result, summary, capture


def submit(client, inspection_id, headers):
    response = client.post(
        f"/api/v1/inspections/{inspection_id}/submit",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "pending_review"


def review(client, inspection_id, result_id, headers, payload):
    return client.post(
        f"/api/v1/inspections/{inspection_id}/rule-reviews/{result_id}",
        headers=headers,
        json=payload,
    )


def finalize(client, inspection_id, headers):
    return client.post(
        f"/api/v1/inspections/{inspection_id}/finalization",
        headers=headers,
    )


def test_accepted_pass_finalizes_and_generates_deterministic_pdf(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER, email="finalizer@example.test")
    supervisor = user_factory(UserRole.SUPERVISOR)
    other_officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)
    run, result, summary, capture = seed_rule_result(
        db_session,
        inspection_id=inspection["id"],
        officer_id=officer.id,
    )
    submit(client, inspection["id"], headers)

    reviewed = review(
        client,
        inspection["id"],
        result.id,
        headers,
        {"decision": "accepted", "note": "Evidence checked."},
    )
    assert reviewed.status_code == 200

    response = finalize(client, inspection["id"], headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["rule_evaluation_run_id"] == run.id
    assert payload["rule_pack_id"] == "fixture-pack"
    assert len(payload["snapshot_sha256"]) == 64
    assert len(payload["report_sha256"]) == 64
    assert payload["report_size_bytes"] > 100

    snapshot = payload["snapshot"]
    assert snapshot["inspection"]["id"] == inspection["id"]
    assert snapshot["finalized_by"]["user_id"] == officer.id
    assert snapshot["results"][0]["machine_status"] == "pass"
    assert snapshot["results"][0]["machine_value"] == summary.canonical_value
    assert snapshot["results"][0]["resolved_value"] == summary.canonical_value
    assert snapshot["results"][0]["resolution"] == (
        "officer_accepted_machine_evidence"
    )
    assert snapshot["results"][0]["evidence"] == [
        {
            "capture_id": capture.id,
            "view_type": "front",
            "sha256": "a" * 64,
            "original_filename": "front.jpg",
        }
    ]

    inspection_response = client.get(
        f"/api/v1/inspections/{inspection['id']}",
        headers=headers,
    )
    assert inspection_response.status_code == 200
    assert inspection_response.json()["status"] == "finalized"

    report = client.get(
        f"/api/v1/inspections/{inspection['id']}/finalization/report",
        headers=headers,
    )
    assert report.status_code == 200
    assert report.headers["content-type"].startswith("application/pdf")
    assert report.content.startswith(b"%PDF")
    assert sha256(report.content).hexdigest() == payload["report_sha256"]
    assert b"CODEFLUX Inspection Review Report" in report.content

    regenerated = build_report_pdf(
        snapshot,
        snapshot_sha256=payload["snapshot_sha256"],
    )
    assert regenerated == report.content

    supervisor_read = client.get(
        f"/api/v1/inspections/{inspection['id']}/finalization",
        headers=auth_headers(supervisor),
    )
    assert supervisor_read.status_code == 200

    other_read = client.get(
        f"/api/v1/inspections/{inspection['id']}/finalization",
        headers=auth_headers(other_officer),
    )
    assert other_read.status_code == 404

    edit = client.patch(
        f"/api/v1/inspections/{inspection['id']}",
        headers=headers,
        json={"product_name": "Should Not Change"},
    )
    assert edit.status_code == 409

    events = list(
        db_session.scalars(
            select(AuditEvent).where(
                AuditEvent.inspection_id == inspection["id"],
                AuditEvent.event_type == AuditEventType.INSPECTION_FINALIZED.value,
            )
        ).all()
    )
    assert len(events) == 1
    assert events[0].details["report_sha256"] == payload["report_sha256"]


def test_missing_review_blocks_finalization(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)
    seed_rule_result(
        db_session,
        inspection_id=inspection["id"],
        officer_id=officer.id,
    )
    submit(client, inspection["id"], headers)

    response = finalize(client, inspection["id"], headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "officer_review_required"


def test_recheck_review_blocks_finalization(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)
    _, result, _, _ = seed_rule_result(
        db_session,
        inspection_id=inspection["id"],
        officer_id=officer.id,
    )
    submit(client, inspection["id"], headers)

    reviewed = review(
        client,
        inspection["id"],
        result.id,
        headers,
        {
            "decision": "recheck_required",
            "note": "Capture is not clear enough.",
        },
    )
    assert reviewed.status_code == 200

    response = finalize(client, inspection["id"], headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "officer_recheck_unresolved"


def test_accepting_manual_verification_does_not_resolve_it(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)
    _, result, _, _ = seed_rule_result(
        db_session,
        inspection_id=inspection["id"],
        officer_id=officer.id,
        status=RuleEvaluationStatus.MANUAL_VERIFICATION_REQUIRED,
        canonical_value=None,
    )
    submit(client, inspection["id"], headers)

    reviewed = review(
        client,
        inspection["id"],
        result.id,
        headers,
        {"decision": "accepted"},
    )
    assert reviewed.status_code == 200

    response = finalize(client, inspection["id"], headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "unsupported_officer_resolution"


def test_corrected_manual_verification_can_finalize_without_mutating_machine_result(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)
    _, result, summary, _ = seed_rule_result(
        db_session,
        inspection_id=inspection["id"],
        officer_id=officer.id,
        status=RuleEvaluationStatus.MANUAL_VERIFICATION_REQUIRED,
        canonical_value=None,
    )
    submit(client, inspection["id"], headers)

    reviewed = review(
        client,
        inspection["id"],
        result.id,
        headers,
        {
            "decision": "corrected",
            "corrected_value": {
                "currency": "INR",
                "amount": "75",
            },
            "note": "MRP was manually verified on the package.",
        },
    )
    assert reviewed.status_code == 200

    response = finalize(client, inspection["id"], headers)

    assert response.status_code == 200
    item = response.json()["snapshot"]["results"][0]
    assert item["machine_status"] == "manual_verification_required"
    assert item["machine_value"] is None
    assert item["resolved_value"] == {
        "currency": "INR",
        "amount": "75.00",
    }
    assert item["resolution"] == "officer_corrected_evidence"

    db_session.refresh(result)
    db_session.refresh(summary)
    assert result.status is RuleEvaluationStatus.MANUAL_VERIFICATION_REQUIRED
    assert summary.canonical_value is None


def test_indeterminate_result_cannot_finalize_via_correction(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)
    _, result, _, _ = seed_rule_result(
        db_session,
        inspection_id=inspection["id"],
        officer_id=officer.id,
        status=RuleEvaluationStatus.INDETERMINATE,
        canonical_value=None,
    )
    submit(client, inspection["id"], headers)

    reviewed = review(
        client,
        inspection["id"],
        result.id,
        headers,
        {
            "decision": "corrected",
            "corrected_value": {
                "currency": "INR",
                "amount": "60",
            },
            "note": "Value read manually.",
        },
    )
    assert reviewed.status_code == 200

    response = finalize(client, inspection["id"], headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "unsupported_officer_resolution"


def test_stale_rule_evidence_blocks_finalization(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)
    _, result, _, _ = seed_rule_result(
        db_session,
        inspection_id=inspection["id"],
        officer_id=officer.id,
    )
    submit(client, inspection["id"], headers)

    reviewed = review(
        client,
        inspection["id"],
        result.id,
        headers,
        {"decision": "accepted"},
    )
    assert reviewed.status_code == 200

    db_session.add(
        Capture(
            inspection_id=inspection["id"],
            uploader_user_id=officer.id,
            view_type=CaptureViewType.BACK,
            original_filename="new-back.jpg",
            storage_key=f"tests/finalization/{inspection['id']}/new-back.jpg",
            sha256="c" * 64,
            mime_type="image/jpeg",
            size_bytes=256,
            width_px=320,
            height_px=240,
        )
    )
    db_session.commit()

    response = finalize(client, inspection["id"], headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "current_rule_evaluation_required"


def test_other_officer_cannot_finalize(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    owner = user_factory(UserRole.OFFICER)
    other = user_factory(UserRole.OFFICER)
    owner_headers = auth_headers(owner)
    inspection = create_inspection(client, owner_headers)
    _, result, _, _ = seed_rule_result(
        db_session,
        inspection_id=inspection["id"],
        officer_id=owner.id,
    )
    submit(client, inspection["id"], owner_headers)
    reviewed = review(
        client,
        inspection["id"],
        result.id,
        owner_headers,
        {"decision": "accepted"},
    )
    assert reviewed.status_code == 200

    response = finalize(
        client,
        inspection["id"],
        auth_headers(other),
    )

    assert response.status_code == 404


def test_report_integrity_failure_is_not_served(
    client,
    db_session,
    media_storage,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)
    _, result, _, _ = seed_rule_result(
        db_session,
        inspection_id=inspection["id"],
        officer_id=officer.id,
    )
    submit(client, inspection["id"], headers)
    reviewed = review(
        client,
        inspection["id"],
        result.id,
        headers,
        {"decision": "accepted"},
    )
    assert reviewed.status_code == 200

    finalized = finalize(client, inspection["id"], headers)
    assert finalized.status_code == 200
    payload = finalized.json()

    from app.models.finalization import InspectionFinalization

    record = db_session.get(InspectionFinalization, payload["id"])
    media_storage.path_for(record.report_storage_key).write_bytes(b"tampered")

    response = client.get(
        f"/api/v1/inspections/{inspection['id']}/finalization/report",
        headers=headers,
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "finalized_report_integrity_failed"


def test_snapshot_integrity_failure_is_not_returned_or_reported(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)
    _, result, _, _ = seed_rule_result(
        db_session,
        inspection_id=inspection["id"],
        officer_id=officer.id,
    )
    submit(client, inspection["id"], headers)
    reviewed = review(
        client,
        inspection["id"],
        result.id,
        headers,
        {"decision": "accepted"},
    )
    assert reviewed.status_code == 200

    finalized = finalize(client, inspection["id"], headers)
    assert finalized.status_code == 200
    payload = finalized.json()

    from app.models.finalization import InspectionFinalization

    record = db_session.get(InspectionFinalization, payload["id"])
    record.snapshot = {
        **record.snapshot,
        "inspection": {
            **record.snapshot["inspection"],
            "product_name": "Tampered Product",
        },
    }
    db_session.commit()

    metadata = client.get(
        f"/api/v1/inspections/{inspection['id']}/finalization",
        headers=headers,
    )
    assert metadata.status_code == 503
    assert metadata.json()["error"]["code"] == (
        "finalization_snapshot_integrity_failed"
    )

    report = client.get(
        f"/api/v1/inspections/{inspection['id']}/finalization/report",
        headers=headers,
    )
    assert report.status_code == 503
    assert report.json()["error"]["code"] == (
        "finalization_snapshot_integrity_failed"
    )
