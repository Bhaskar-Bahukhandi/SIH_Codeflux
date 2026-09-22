from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_officer
from app.db import get_db
from app.errors import conflict, not_found
from app.models.audit import AuditEventType
from app.models.declaration import DeclarationExtractionRun, DeclarationSummary
from app.models.rule_evaluation import RuleEvaluationResult, RuleEvaluationRun
from app.models.user import User
from app.schemas.rule_evaluation import (
    RuleEvaluationRequest,
    RuleEvaluationResponse,
)
from app.services.audit import record_inspection_event
from app.services.declaration_sources import collect_current_ocr_sources
from app.services.inspection_access import get_visible_inspection_or_raise
from app.services.inspection_lifecycle import require_draft
from app.services.rule_engine import evaluate_rules
from app.services.rule_pack import load_rule_pack

router = APIRouter(
    prefix="/inspections/{inspection_id}/rule-evaluations",
    tags=["rule-evaluations"],
)


def _latest_extraction_run(
    db: Session,
    *,
    inspection_id: str,
) -> DeclarationExtractionRun | None:
    return db.scalar(
        select(DeclarationExtractionRun)
        .where(DeclarationExtractionRun.inspection_id == inspection_id)
        .order_by(
            DeclarationExtractionRun.created_at.desc(),
            DeclarationExtractionRun.id.desc(),
        )
        .limit(1)
    )


def _assert_extraction_is_current(
    db: Session,
    *,
    inspection_id: str,
    extraction_run: DeclarationExtractionRun,
) -> None:
    current = collect_current_ocr_sources(
        db,
        inspection_id=inspection_id,
    )

    if (
        extraction_run.inspection_capture_count
        != current.inspection_capture_count
        or extraction_run.source_capture_ids != current.source_capture_ids
        or extraction_run.source_ocr_run_ids != current.source_ocr_run_ids
        or extraction_run.skipped_sources != current.skipped_sources
    ):
        raise conflict(
            "current_declaration_extraction_required",
            "Declaration evidence is stale. Run declaration extraction again before rule evaluation.",
        )


def _response_for_run(
    db: Session,
    run: RuleEvaluationRun,
) -> dict:
    results = list(
        db.scalars(
            select(RuleEvaluationResult)
            .where(RuleEvaluationResult.evaluation_run_id == run.id)
            .order_by(
                RuleEvaluationResult.rule_id.asc(),
                RuleEvaluationResult.id.asc(),
            )
        ).all()
    )
    return {
        "run": run,
        "results": results,
    }


@router.post("/evaluate", response_model=RuleEvaluationResponse)
def evaluate_current_declarations(
    inspection_id: str,
    payload: RuleEvaluationRequest,
    db: Session = Depends(get_db),
    officer: User = Depends(require_officer),
) -> dict:
    inspection = get_visible_inspection_or_raise(db, inspection_id, officer)
    require_draft(inspection)

    extraction_run = _latest_extraction_run(
        db,
        inspection_id=inspection.id,
    )
    if extraction_run is None:
        raise conflict(
            "current_declaration_extraction_required",
            "Run declaration extraction before rule evaluation.",
        )

    _assert_extraction_is_current(
        db,
        inspection_id=inspection.id,
        extraction_run=extraction_run,
    )

    summaries = list(
        db.scalars(
            select(DeclarationSummary)
            .where(
                DeclarationSummary.extraction_run_id
                == extraction_run.id
            )
            .order_by(DeclarationSummary.declaration_type.asc())
        ).all()
    )
    summaries_by_type = {
        summary.declaration_type.value: summary
        for summary in summaries
    }

    loaded_pack = load_rule_pack()
    evaluated = evaluate_rules(
        rule_pack=loaded_pack,
        context=payload.context,
        summaries=summaries_by_type,
    )

    run = RuleEvaluationRun(
        inspection_id=inspection.id,
        actor_user_id=officer.id,
        source_extraction_run_id=extraction_run.id,
        rule_pack_id=loaded_pack.definition.rule_pack_id,
        rule_pack_version=loaded_pack.definition.version,
        rule_pack_sha256=loaded_pack.sha256,
        context_snapshot=payload.context.model_dump(),
        result_count=len(evaluated),
    )
    db.add(run)
    db.flush()

    persisted_results: list[RuleEvaluationResult] = []
    for item in evaluated:
        result = RuleEvaluationResult(
            evaluation_run_id=run.id,
            rule_id=item.rule.rule_id,
            provision=item.rule.provision,
            declaration_type=item.rule.declaration_type.value,
            status=item.status,
            evidence_summary_id=item.evidence_summary_id,
            explanation=item.explanation,
            details={
                **item.details,
                "source_ids": item.rule.source_ids,
                "check_type": item.rule.check_type,
                "effective_from": item.rule.effective_from.isoformat(),
                "applicability_note": item.rule.applicability_note,
            },
        )
        db.add(result)
        persisted_results.append(result)

    record_inspection_event(
        db,
        inspection_id=inspection.id,
        actor_user_id=officer.id,
        event_type=AuditEventType.RULE_EVALUATION_COMPLETED,
        details={
            "evaluation_run_id": run.id,
            "source_extraction_run_id": extraction_run.id,
            "rule_pack_id": run.rule_pack_id,
            "rule_pack_version": run.rule_pack_version,
            "rule_pack_sha256": run.rule_pack_sha256,
            "statuses": {
                result.rule_id: result.status.value
                for result in persisted_results
            },
        },
    )

    db.commit()
    db.refresh(run)
    return _response_for_run(db, run)


@router.get("/latest", response_model=RuleEvaluationResponse)
def latest_rule_evaluation(
    inspection_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    inspection = get_visible_inspection_or_raise(db, inspection_id, user)

    run = db.scalar(
        select(RuleEvaluationRun)
        .where(RuleEvaluationRun.inspection_id == inspection.id)
        .order_by(
            RuleEvaluationRun.created_at.desc(),
            RuleEvaluationRun.id.desc(),
        )
        .limit(1)
    )
    if run is None:
        raise not_found(
            "rule_evaluation_not_found",
            "No rule evaluation exists for this inspection.",
        )

    return _response_for_run(db, run)
