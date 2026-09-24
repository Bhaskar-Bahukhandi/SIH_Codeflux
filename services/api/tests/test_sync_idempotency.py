from datetime import datetime, timezone
from io import BytesIO
from uuid import uuid4

from PIL import Image
from sqlalchemy import func, select

from app.models.audit import AuditEvent, AuditEventType
from app.models.capture import Capture
from app.models.declaration import DeclarationExtractionRun
from app.models.inspection import Inspection
from app.models.officer_review import OfficerRuleReview
from app.models.rule_evaluation import (
    RuleEvaluationResult,
    RuleEvaluationRun,
    RuleEvaluationStatus,
)
from app.models.user import UserRole


def image_bytes(pixel=(120, 90, 60)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (32, 24), pixel).save(buffer, format="JPEG")
    return buffer.getvalue()


def create_inspection(client, headers, *, client_id=None, name="Sync Test Product"):
    payload = {"product_name": name}
    if client_id is not None:
        payload["id"] = client_id
    return client.post(
        "/api/v1/inspections",
        headers=headers,
        json=payload,
    )


def seed_rule_result(db_session, *, inspection_id, officer_id):
    created_at = datetime.now(timezone.utc)
    extraction = DeclarationExtractionRun(
        inspection_id=inspection_id,
        actor_user_id=officer_id,
        extractor_version="sync-test-extractor",
        fusion_version="sync-test-fusion",
        inspection_capture_count=0,
        source_capture_count=0,
        source_capture_ids=[],
        source_ocr_run_ids=[],
        skipped_sources=[],
        observation_count=0,
        created_at=created_at,
    )
    db_session.add(extraction)
    db_session.flush()

    run = RuleEvaluationRun(
        inspection_id=inspection_id,
        actor_user_id=officer_id,
        source_extraction_run_id=extraction.id,
        rule_pack_id="sync-test-pack",
        rule_pack_version="sync-test-v1",
        rule_pack_sha256="0" * 64,
        rule_pack_snapshot={"fixture": True},
        context_snapshot={},
        result_count=1,
        created_at=created_at,
    )
    db_session.add(run)
    db_session.flush()

    result = RuleEvaluationResult(
        evaluation_run_id=run.id,
        rule_id="LMPC-R6-1-E-MRP-EVIDENCE",
        provision="Rule 6",
        declaration_type="mrp",
        status=RuleEvaluationStatus.PASS,
        evidence_summary_id=None,
        explanation="Sync replay fixture.",
        details={},
    )
    db_session.add(result)
    db_session.commit()
    db_session.refresh(result)
    return result


def audit_count(db_session, inspection_id, event_type):
    return db_session.scalar(
        select(func.count(AuditEvent.id)).where(
            AuditEvent.inspection_id == inspection_id,
            AuditEvent.event_type == event_type.value,
        )
    )


def test_client_inspection_id_replay_returns_one_remote_resource(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    client_id = str(uuid4())

    first = create_inspection(
        client,
        headers,
        client_id=client_id,
        name="Offline Biscuit Pack",
    )
    replay = create_inspection(
        client,
        headers,
        client_id=client_id,
        name="Offline Biscuit Pack",
    )

    assert first.status_code == 201
    assert replay.status_code == 201
    assert first.json()["id"] == client_id
    assert replay.json()["id"] == client_id
    assert db_session.scalar(select(func.count(Inspection.id))) == 1
    assert (
        audit_count(
            db_session,
            client_id,
            AuditEventType.INSPECTION_CREATED,
        )
        == 1
    )

    conflict = create_inspection(
        client,
        headers,
        client_id=client_id,
        name="Different Product",
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "client_resource_id_conflict"


def test_client_capture_id_replay_is_exactly_once_and_preserves_original_evidence(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers).json()
    capture_id = str(uuid4())
    original = image_bytes((120, 90, 60))

    def upload(data):
        return client.post(
            f"/api/v1/inspections/{inspection['id']}/captures",
            headers=headers,
            data={
                "view_type": "front",
                "capture_id": capture_id,
            },
            files={
                "file": (
                    "front.jpg",
                    data,
                    "application/octet-stream",
                )
            },
        )

    first = upload(original)
    replay = upload(original)

    assert first.status_code == 201
    assert replay.status_code == 201
    assert first.json()["id"] == capture_id
    assert replay.json()["id"] == capture_id
    assert db_session.scalar(select(func.count(Capture.id))) == 1
    assert (
        audit_count(
            db_session,
            inspection["id"],
            AuditEventType.CAPTURE_UPLOADED,
        )
        == 1
    )

    conflicting_bytes = image_bytes((10, 20, 30))
    conflict = upload(conflicting_bytes)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "client_resource_id_conflict"

    content = client.get(
        f"/api/v1/inspections/{inspection['id']}/captures/{capture_id}/content",
        headers=headers,
    )
    assert content.status_code == 200
    assert content.content == original



def test_capture_exact_replay_remains_safe_after_submission(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers).json()
    capture_id = str(uuid4())
    original = image_bytes((90, 120, 70))

    def upload(data, *, client_capture_id=capture_id):
        return client.post(
            f"/api/v1/inspections/{inspection['id']}/captures",
            headers=headers,
            data={
                "view_type": "front",
                "capture_id": client_capture_id,
            },
            files={
                "file": (
                    "front.jpg",
                    data,
                    "application/octet-stream",
                )
            },
        )

    first = upload(original)
    assert first.status_code == 201

    submitted = client.post(
        f"/api/v1/inspections/{inspection['id']}/submit",
        headers=headers,
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "pending_review"

    replay = upload(original)
    assert replay.status_code == 201
    assert replay.json()["id"] == capture_id
    assert db_session.scalar(select(func.count(Capture.id))) == 1
    assert (
        audit_count(
            db_session,
            inspection["id"],
            AuditEventType.CAPTURE_UPLOADED,
        )
        == 1
    )

    changed_bytes = image_bytes((10, 30, 50))
    conflicting_replay = upload(changed_bytes)
    assert conflicting_replay.status_code == 409
    assert (
        conflicting_replay.json()["error"]["code"]
        == "client_resource_id_conflict"
    )

    new_capture = upload(
        original,
        client_capture_id=str(uuid4()),
    )
    assert new_capture.status_code == 409
    assert new_capture.json()["error"]["code"] == "inspection_not_editable"

def test_capture_replay_does_not_claim_success_when_remote_evidence_is_missing(
    client,
    db_session,
    media_storage,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers).json()
    capture_id = str(uuid4())
    original = image_bytes()

    upload = client.post(
        f"/api/v1/inspections/{inspection['id']}/captures",
        headers=headers,
        data={
            "view_type": "detail",
            "capture_id": capture_id,
        },
        files={
            "file": (
                "detail.jpg",
                original,
                "application/octet-stream",
            )
        },
    )
    assert upload.status_code == 201

    stored = db_session.get(Capture, capture_id)
    media_storage.delete(stored.storage_key)

    replay = client.post(
        f"/api/v1/inspections/{inspection['id']}/captures",
        headers=headers,
        data={
            "view_type": "detail",
            "capture_id": capture_id,
        },
        files={
            "file": (
                "detail.jpg",
                original,
                "application/octet-stream",
            )
        },
    )

    assert replay.status_code == 503
    assert replay.json()["error"]["code"] == "capture_storage_unavailable"


def test_client_review_id_replay_does_not_add_another_revision(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    inspection = create_inspection(client, headers).json()
    result = seed_rule_result(
        db_session,
        inspection_id=inspection["id"],
        officer_id=officer.id,
    )

    submitted = client.post(
        f"/api/v1/inspections/{inspection['id']}/submit",
        headers=headers,
    )
    assert submitted.status_code == 200

    review_id = str(uuid4())
    payload = {
        "id": review_id,
        "decision": "accepted",
        "note": "Verified against the current evidence.",
    }
    endpoint = (
        f"/api/v1/inspections/{inspection['id']}/"
        f"rule-reviews/{result.id}"
    )

    first = client.post(endpoint, headers=headers, json=payload)
    replay = client.post(endpoint, headers=headers, json=payload)

    assert first.status_code == 200
    assert replay.status_code == 200
    assert first.json()["id"] == review_id
    assert replay.json()["id"] == review_id
    assert first.json()["revision"] == 1
    assert replay.json()["revision"] == 1
    assert db_session.scalar(select(func.count(OfficerRuleReview.id))) == 1
    assert (
        audit_count(
            db_session,
            inspection["id"],
            AuditEventType.OFFICER_RULE_REVIEW_RECORDED,
        )
        == 1
    )

    conflict_payload = {
        **payload,
        "note": "Different replay payload.",
    }
    conflict = client.post(
        endpoint,
        headers=headers,
        json=conflict_payload,
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "client_resource_id_conflict"
