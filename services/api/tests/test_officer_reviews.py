from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.audit import AuditEvent, AuditEventType
from app.models.declaration import DeclarationExtractionRun
from app.models.rule_evaluation import (
    RuleEvaluationResult,
    RuleEvaluationRun,
    RuleEvaluationStatus,
)
from app.models.user import UserRole


def create_inspection(client, headers):
    response = client.post(
        "/api/v1/inspections",
        headers=headers,
        json={"product_name": "Officer Review Test Product"},
    )
    assert response.status_code == 201
    return response.json()


def seed_rule_result(
    db_session,
    *,
    inspection_id,
    officer_id,
    rule_id="LMPC-R6-1-E-MRP-EVIDENCE",
    declaration_type="mrp",
    status=RuleEvaluationStatus.PASS,
    created_at=None,
):
    extraction = DeclarationExtractionRun(
        inspection_id=inspection_id,
        actor_user_id=officer_id,
        extractor_version="fixture-extractor",
        fusion_version="fixture-fusion",
        inspection_capture_count=0,
        source_capture_count=0,
        source_capture_ids=[],
        source_ocr_run_ids=[],
        skipped_sources=[],
        observation_count=0,
        created_at=created_at or datetime.now(timezone.utc),
    )
    db_session.add(extraction)
    db_session.flush()

    run = RuleEvaluationRun(
        inspection_id=inspection_id,
        actor_user_id=officer_id,
        source_extraction_run_id=extraction.id,
        rule_pack_id="fixture-pack",
        rule_pack_version="fixture-v1",
        rule_pack_sha256="0" * 64,
        rule_pack_snapshot={"fixture": True},
        context_snapshot={},
        result_count=1,
        created_at=created_at or datetime.now(timezone.utc),
    )
    db_session.add(run)
    db_session.flush()

    result = RuleEvaluationResult(
        evaluation_run_id=run.id,
        rule_id=rule_id,
        provision="Rule 6",
        declaration_type=declaration_type,
        status=status,
        evidence_summary_id=None,
        explanation="Fixture preliminary result.",
        details={},
    )
    db_session.add(result)
    db_session.commit()
    db_session.refresh(run)
    db_session.refresh(result)
    return run, result


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


def test_review_is_blocked_while_inspection_is_draft(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)
    _, result = seed_rule_result(
        db_session,
        inspection_id=inspection["id"],
        officer_id=officer.id,
    )

    response = review(
        client,
        inspection["id"],
        result.id,
        headers,
        {"decision": "accepted"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "inspection_not_pending_review"


def test_owner_can_accept_latest_rule_result_after_submission(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)
    run, result = seed_rule_result(
        db_session,
        inspection_id=inspection["id"],
        officer_id=officer.id,
    )
    submit(client, inspection["id"], headers)

    response = review(
        client,
        inspection["id"],
        result.id,
        headers,
        {"decision": "accepted"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["inspection_id"] == inspection["id"]
    assert payload["officer_user_id"] == officer.id
    assert payload["rule_evaluation_run_id"] == run.id
    assert payload["rule_evaluation_result_id"] == result.id
    assert payload["revision"] == 1
    assert payload["decision"] == "accepted"
    assert payload["corrected_value"] is None

    events = list(
        db_session.scalars(
            select(AuditEvent).where(
                AuditEvent.inspection_id == inspection["id"],
                AuditEvent.event_type
                == AuditEventType.OFFICER_RULE_REVIEW_RECORDED.value,
            )
        ).all()
    )
    assert len(events) == 1
    assert events[0].details["review_id"] == payload["id"]
    assert events[0].details["decision"] == "accepted"


def test_blank_optional_note_is_normalized_to_null(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)
    _, result = seed_rule_result(
        db_session,
        inspection_id=inspection["id"],
        officer_id=officer.id,
    )
    submit(client, inspection["id"], headers)

    response = review(
        client,
        inspection["id"],
        result.id,
        headers,
        {
            "decision": "accepted",
            "note": "   ",
        },
    )

    assert response.status_code == 200
    assert response.json()["note"] is None


def test_corrected_mrp_is_normalized_and_requires_note(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)
    _, result = seed_rule_result(
        db_session,
        inspection_id=inspection["id"],
        officer_id=officer.id,
    )
    submit(client, inspection["id"], headers)

    missing_note = review(
        client,
        inspection["id"],
        result.id,
        headers,
        {
            "decision": "corrected",
            "corrected_value": {"currency": "INR", "amount": "55"},
        },
    )
    assert missing_note.status_code == 422

    response = review(
        client,
        inspection["id"],
        result.id,
        headers,
        {
            "decision": "corrected",
            "corrected_value": {"currency": "inr", "amount": "55"},
            "note": "Price was readable on the side panel during manual review.",
        },
    )

    assert response.status_code == 200
    assert response.json()["corrected_value"] == {
        "currency": "INR",
        "amount": "55.00",
    }


def test_net_quantity_correction_rejects_unsupported_unit(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)
    _, result = seed_rule_result(
        db_session,
        inspection_id=inspection["id"],
        officer_id=officer.id,
        rule_id="LMPC-R6-1-C-NET-QUANTITY-EVIDENCE",
        declaration_type="net_quantity",
    )
    submit(client, inspection["id"], headers)

    response = review(
        client,
        inspection["id"],
        result.id,
        headers,
        {
            "decision": "corrected",
            "corrected_value": {"value": "100", "unit": "oz"},
            "note": "Manual correction.",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_corrected_value"


def test_recheck_requires_note_and_review_history_is_append_only(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)
    _, result = seed_rule_result(
        db_session,
        inspection_id=inspection["id"],
        officer_id=officer.id,
    )
    submit(client, inspection["id"], headers)

    invalid = review(
        client,
        inspection["id"],
        result.id,
        headers,
        {"decision": "recheck_required"},
    )
    assert invalid.status_code == 422

    first = review(
        client,
        inspection["id"],
        result.id,
        headers,
        {"decision": "accepted"},
    )
    assert first.status_code == 200
    assert first.json()["revision"] == 1

    second = review(
        client,
        inspection["id"],
        result.id,
        headers,
        {
            "decision": "recheck_required",
            "note": "Glare makes the declaration evidence ambiguous.",
        },
    )
    assert second.status_code == 200
    assert second.json()["revision"] == 2

    history = client.get(
        f"/api/v1/inspections/{inspection['id']}/rule-reviews",
        headers=headers,
    )
    assert history.status_code == 200
    payload = history.json()
    assert [item["revision"] for item in payload["reviews"]] == [1, 2]
    assert payload["latest_by_rule_result"][result.id]["revision"] == 2
    assert (
        payload["latest_by_rule_result"][result.id]["decision"]
        == "recheck_required"
    )


def test_review_rejects_result_from_older_rule_evaluation(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)
    base_time = datetime(2026, 9, 23, tzinfo=timezone.utc)

    _, old_result = seed_rule_result(
        db_session,
        inspection_id=inspection["id"],
        officer_id=officer.id,
        created_at=base_time,
    )
    _, latest_result = seed_rule_result(
        db_session,
        inspection_id=inspection["id"],
        officer_id=officer.id,
        rule_id="LMPC-R6-1-C-NET-QUANTITY-EVIDENCE",
        declaration_type="net_quantity",
        created_at=base_time + timedelta(seconds=1),
    )
    submit(client, inspection["id"], headers)

    old_response = review(
        client,
        inspection["id"],
        old_result.id,
        headers,
        {"decision": "accepted"},
    )
    assert old_response.status_code == 404
    assert old_response.json()["error"]["code"] == (
        "rule_evaluation_result_not_found"
    )

    latest_response = review(
        client,
        inspection["id"],
        latest_result.id,
        headers,
        {"decision": "accepted"},
    )
    assert latest_response.status_code == 200


def test_other_officer_cannot_review_and_supervisor_is_read_only(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    owner = user_factory(UserRole.OFFICER)
    other = user_factory(UserRole.OFFICER)
    supervisor = user_factory(UserRole.SUPERVISOR)
    owner_headers = auth_headers(owner)
    inspection = create_inspection(client, owner_headers)
    _, result = seed_rule_result(
        db_session,
        inspection_id=inspection["id"],
        officer_id=owner.id,
    )
    submit(client, inspection["id"], owner_headers)

    created = review(
        client,
        inspection["id"],
        result.id,
        owner_headers,
        {"decision": "accepted"},
    )
    assert created.status_code == 200

    other_response = review(
        client,
        inspection["id"],
        result.id,
        auth_headers(other),
        {"decision": "accepted"},
    )
    assert other_response.status_code == 404

    supervisor_headers = auth_headers(supervisor)
    history = client.get(
        f"/api/v1/inspections/{inspection['id']}/rule-reviews",
        headers=supervisor_headers,
    )
    assert history.status_code == 200
    assert len(history.json()["reviews"]) == 1

    rejected = review(
        client,
        inspection["id"],
        result.id,
        supervisor_headers,
        {"decision": "accepted"},
    )
    assert rejected.status_code == 403


def test_recheck_review_can_reopen_inspection_to_draft(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)
    _, result = seed_rule_result(
        db_session,
        inspection_id=inspection["id"],
        officer_id=officer.id,
    )
    submit(client, inspection["id"], headers)

    review_response = review(
        client,
        inspection["id"],
        result.id,
        headers,
        {
            "decision": "recheck_required",
            "note": "The price panel needs a clearer capture.",
        },
    )
    assert review_response.status_code == 200

    reopened = client.post(
        f"/api/v1/inspections/{inspection['id']}/reopen-for-recheck",
        headers=headers,
    )

    assert reopened.status_code == 200
    assert reopened.json()["status"] == "draft"
    assert reopened.json()["submitted_at"] is None
    assert reopened.json()["reopened_for_recheck_at"] is not None

    resubmit_without_fresh_evaluation = client.post(
        f"/api/v1/inspections/{inspection['id']}/submit",
        headers=headers,
    )
    assert resubmit_without_fresh_evaluation.status_code == 409
    assert resubmit_without_fresh_evaluation.json()["error"]["code"] == (
        "fresh_rule_evaluation_required"
    )

    editable = client.patch(
        f"/api/v1/inspections/{inspection['id']}",
        headers=headers,
        json={"product_name": "Recheck Product"},
    )
    assert editable.status_code == 200

    events = list(
        db_session.scalars(
            select(AuditEvent).where(
                AuditEvent.inspection_id == inspection["id"],
                AuditEvent.event_type
                == AuditEventType.INSPECTION_REOPENED_FOR_RECHECK.value,
            )
        ).all()
    )
    assert len(events) == 1
    assert events[0].details["trigger_review_ids"] == [
        review_response.json()["id"]
    ]


def test_reopen_requires_latest_recheck_review(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)
    _, result = seed_rule_result(
        db_session,
        inspection_id=inspection["id"],
        officer_id=officer.id,
    )
    submit(client, inspection["id"], headers)

    accepted = review(
        client,
        inspection["id"],
        result.id,
        headers,
        {"decision": "accepted"},
    )
    assert accepted.status_code == 200

    rejected = client.post(
        f"/api/v1/inspections/{inspection['id']}/reopen-for-recheck",
        headers=headers,
    )
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "recheck_review_required"

    recheck = review(
        client,
        inspection["id"],
        result.id,
        headers,
        {
            "decision": "recheck_required",
            "note": "Need a new image.",
        },
    )
    assert recheck.status_code == 200

    resolved = review(
        client,
        inspection["id"],
        result.id,
        headers,
        {"decision": "accepted"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["revision"] == 3

    still_rejected = client.post(
        f"/api/v1/inspections/{inspection['id']}/reopen-for-recheck",
        headers=headers,
    )
    assert still_rejected.status_code == 409
    assert still_rejected.json()["error"]["code"] == "recheck_review_required"


def test_fresh_rule_evaluation_allows_resubmit_after_recheck(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)
    _, result = seed_rule_result(
        db_session,
        inspection_id=inspection["id"],
        officer_id=officer.id,
    )
    submit(client, inspection["id"], headers)

    recheck = review(
        client,
        inspection["id"],
        result.id,
        headers,
        {
            "decision": "recheck_required",
            "note": "Need a fresh evidence pass.",
        },
    )
    assert recheck.status_code == 200

    reopened = client.post(
        f"/api/v1/inspections/{inspection['id']}/reopen-for-recheck",
        headers=headers,
    )
    assert reopened.status_code == 200
    reopened_at = datetime.fromisoformat(
        reopened.json()["reopened_for_recheck_at"].replace("Z", "+00:00")
    )

    _, fresh_result = seed_rule_result(
        db_session,
        inspection_id=inspection["id"],
        officer_id=officer.id,
        rule_id="LMPC-R6-1-C-NET-QUANTITY-EVIDENCE",
        declaration_type="net_quantity",
        created_at=reopened_at + timedelta(seconds=1),
    )

    resubmitted = client.post(
        f"/api/v1/inspections/{inspection['id']}/submit",
        headers=headers,
    )
    assert resubmitted.status_code == 200
    assert resubmitted.json()["status"] == "pending_review"

    fresh_review = review(
        client,
        inspection["id"],
        fresh_result.id,
        headers,
        {"decision": "accepted"},
    )
    assert fresh_review.status_code == 200
    assert fresh_review.json()["revision"] == 1


def test_corrected_values_reject_nonfinite_or_extreme_numbers(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers)
    _, result = seed_rule_result(
        db_session,
        inspection_id=inspection["id"],
        officer_id=officer.id,
    )
    submit(client, inspection["id"], headers)

    for amount in ["NaN", "Infinity", "1e1000"]:
        response = review(
            client,
            inspection["id"],
            result.id,
            headers,
            {
                "decision": "corrected",
                "corrected_value": {"currency": "INR", "amount": amount},
                "note": "Manual correction.",
            },
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_corrected_value"
