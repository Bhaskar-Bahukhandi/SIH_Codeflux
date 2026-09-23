from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import conflict
from app.models.capture import Capture
from app.models.declaration import (
    DeclarationExtractionRun,
    DeclarationObservation,
    DeclarationSummary,
    DeclarationType,
)
from app.models.inspection import Inspection
from app.models.officer_review import OfficerReviewDecision, OfficerRuleReview
from app.models.rule_evaluation import (
    RuleEvaluationResult,
    RuleEvaluationRun,
    RuleEvaluationStatus,
)
from app.models.user import User
from app.services.officer_review_state import latest_officer_reviews_by_result
from app.services.officer_review_validation import normalize_officer_corrected_value


@dataclass(frozen=True, slots=True)
class ResolvedRule:
    result: RuleEvaluationResult
    review: OfficerRuleReview
    summary: DeclarationSummary | None
    machine_value: dict | None
    resolved_value: dict
    resolution: str
    evidence: list[dict[str, Any]]


def canonical_json_bytes(value: dict) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def snapshot_sha256(snapshot: dict) -> str:
    return hashlib.sha256(canonical_json_bytes(snapshot)).hexdigest()


def _results_for_run(
    db: Session,
    *,
    run_id: str,
) -> list[RuleEvaluationResult]:
    return list(
        db.scalars(
            select(RuleEvaluationResult)
            .where(RuleEvaluationResult.evaluation_run_id == run_id)
            .order_by(
                RuleEvaluationResult.rule_id.asc(),
                RuleEvaluationResult.id.asc(),
            )
        ).all()
    )


def _summary_for_result(
    db: Session,
    *,
    result: RuleEvaluationResult,
) -> DeclarationSummary | None:
    if result.evidence_summary_id is None:
        return None
    return db.get(DeclarationSummary, result.evidence_summary_id)


def _capture_references(
    db: Session,
    *,
    extraction_run: DeclarationExtractionRun,
    declaration_type: str,
) -> list[dict[str, Any]]:
    observed_capture_ids = list(
        dict.fromkeys(
            db.scalars(
                select(DeclarationObservation.capture_id)
                .where(
                    DeclarationObservation.extraction_run_id == extraction_run.id,
                    DeclarationObservation.declaration_type
                    == DeclarationType(declaration_type),
                )
                .order_by(
                    DeclarationObservation.capture_id.asc(),
                    DeclarationObservation.id.asc(),
                )
            ).all()
        )
    )

    capture_ids = observed_capture_ids or list(extraction_run.source_capture_ids)
    if not capture_ids:
        return []

    captures = list(
        db.scalars(
            select(Capture)
            .where(Capture.id.in_(capture_ids))
            .order_by(Capture.id.asc())
        ).all()
    )
    return [
        {
            "capture_id": capture.id,
            "view_type": capture.view_type.value,
            "sha256": capture.sha256,
            "original_filename": capture.original_filename,
        }
        for capture in captures
    ]


def _resolve_rule(
    db: Session,
    *,
    result: RuleEvaluationResult,
    review: OfficerRuleReview,
    extraction_run: DeclarationExtractionRun,
) -> ResolvedRule:
    if review.decision is OfficerReviewDecision.RECHECK_REQUIRED:
        raise conflict(
            "officer_recheck_unresolved",
            "A latest Officer review still requires recheck before finalization.",
        )

    summary = _summary_for_result(db, result=result)
    machine_value = summary.canonical_value if summary is not None else None

    if review.decision is OfficerReviewDecision.CORRECTED:
        if result.status not in {
            RuleEvaluationStatus.PASS,
            RuleEvaluationStatus.MANUAL_VERIFICATION_REQUIRED,
        }:
            raise conflict(
                "unsupported_officer_resolution",
                "This preliminary result state cannot be finalized through a value correction.",
            )

        corrected_value = normalize_officer_corrected_value(
            declaration_type=result.declaration_type,
            value=review.corrected_value or {},
        )
        resolved_value = corrected_value
        resolution = "officer_corrected_evidence"

    elif (
        review.decision is OfficerReviewDecision.ACCEPTED
        and result.status is RuleEvaluationStatus.PASS
    ):
        if machine_value is None:
            raise conflict(
                "machine_evidence_value_required",
                "The accepted preliminary pass has no canonical machine evidence value.",
            )
        resolved_value = machine_value
        resolution = "officer_accepted_machine_evidence"

    else:
        raise conflict(
            "unsupported_officer_resolution",
            "The latest Officer review does not resolve this preliminary result for finalization.",
        )

    return ResolvedRule(
        result=result,
        review=review,
        summary=summary,
        machine_value=machine_value,
        resolved_value=resolved_value,
        resolution=resolution,
        evidence=_capture_references(
            db,
            extraction_run=extraction_run,
            declaration_type=result.declaration_type,
        ),
    )


def build_finalization_snapshot(
    db: Session,
    *,
    inspection: Inspection,
    officer: User,
    run: RuleEvaluationRun,
    finalization_id: str,
    report_id: str,
    report_version: str,
    finalized_at: datetime,
) -> dict:
    extraction_run = db.get(
        DeclarationExtractionRun,
        run.source_extraction_run_id,
    )
    if extraction_run is None or extraction_run.inspection_id != inspection.id:
        raise conflict(
            "rule_evidence_chain_invalid",
            "The preliminary rule evaluation does not have a valid declaration-evidence chain.",
        )

    results = _results_for_run(db, run_id=run.id)
    if not results or len(results) != run.result_count:
        raise conflict(
            "rule_evaluation_incomplete",
            "The latest preliminary rule evaluation does not contain its complete result set.",
        )

    latest_reviews = latest_officer_reviews_by_result(
        db,
        inspection_id=inspection.id,
        rule_evaluation_run_id=run.id,
    )

    missing_reviews = [
        result.id
        for result in results
        if result.id not in latest_reviews
    ]
    if missing_reviews:
        raise conflict(
            "officer_review_required",
            "Every latest preliminary rule result must have an Officer review before finalization.",
        )

    resolved_rules = [
        _resolve_rule(
            db,
            result=result,
            review=latest_reviews[result.id],
            extraction_run=extraction_run,
        )
        for result in results
    ]

    return {
        "schema_version": 1,
        "finalization_id": finalization_id,
        "report_id": report_id,
        "report_version": report_version,
        "finalized_at": finalized_at.isoformat(),
        "inspection": {
            "id": inspection.id,
            "product_name": inspection.product_name,
            "product_identifier": inspection.product_identifier,
            "officer_id": inspection.officer_id,
            "submitted_at": (
                inspection.submitted_at.isoformat()
                if inspection.submitted_at is not None
                else None
            ),
        },
        "finalized_by": {
            "user_id": officer.id,
            "full_name": officer.full_name,
            "email": officer.email,
            "role": officer.role.value,
        },
        "rule_pack": {
            "id": run.rule_pack_id,
            "version": run.rule_pack_version,
            "sha256": run.rule_pack_sha256,
            "snapshot": run.rule_pack_snapshot,
        },
        "rule_evaluation": {
            "run_id": run.id,
            "source_extraction_run_id": run.source_extraction_run_id,
            "context_snapshot": run.context_snapshot,
        },
        "results": [
            {
                "rule_result_id": item.result.id,
                "rule_id": item.result.rule_id,
                "provision": item.result.provision,
                "declaration_type": item.result.declaration_type,
                "machine_status": item.result.status.value,
                "machine_explanation": item.result.explanation,
                "machine_details": item.result.details,
                "machine_value": item.machine_value,
                "candidate_values": (
                    item.summary.candidate_values
                    if item.summary is not None
                    else []
                ),
                "officer_review": {
                    "review_id": item.review.id,
                    "revision": item.review.revision,
                    "decision": item.review.decision.value,
                    "corrected_value": item.review.corrected_value,
                    "note": item.review.note,
                    "created_at": item.review.created_at.isoformat(),
                },
                "resolution": item.resolution,
                "resolved_value": item.resolved_value,
                "evidence": item.evidence,
            }
            for item in resolved_rules
        ],
        "disclaimer": (
            "Automated outputs in this report are preliminary declaration-evidence checks. "
            "This record documents Officer review and does not itself calculate a penalty "
            "or issue a statutory notice."
        ),
    }
