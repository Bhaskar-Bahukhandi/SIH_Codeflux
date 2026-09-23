from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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
from app.services.declaration_sources import declaration_extraction_is_current
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
    if not declaration_extraction_is_current(
        db,
        inspection_id=inspection_id,
        extraction_run=extraction_run,
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


def _matches_evaluation_replay(
    run: RuleEvaluationRun,
    *,
    inspection_id: str,
    actor_user_id: str,
    context_snapshot: dict,
) -> bool:
    return (
        run.inspection_id == inspection_id
        and run.actor_user_id == actor_user_id
        and run.context_snapshot == context_snapshot
    )


def _raise_client_evaluation_id_conflict() -> None:
    raise conflict(
        "client_resource_id_conflict",
        "The supplied client rule-evaluation ID is already associated with different evaluation data.",
    )


@router.post("/evaluate", response_model=RuleEvaluationResponse)
def evaluate_current_declarations(
    inspection_id: str,
    payload: RuleEvaluationRequest,
    db: Session = Depends(get_db),
    officer: User = Depends(require_officer),
) -> dict:
    inspection = get_visible_inspection_or_raise(db, inspection_id, officer)

    context_snapshot = payload.context.model_dump()
    client_run_id = str(payload.id) if payload.id is not None else None
    if client_run_id is not None:
        existing = db.get(RuleEvaluationRun, client_run_id)
        if existing is not None:
            if _matches_evaluation_replay(
                existing,
                inspection_id=inspection.id,
                actor_user_id=officer.id,
                context_snapshot=context_snapshot,
            ):
                return _response_for_run(db, existing)
            _raise_client_evaluation_id_conflict()

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

    run_kwargs = {
        "inspection_id": inspection.id,
        "actor_user_id": officer.id,
        "source_extraction_run_id": extraction_run.id,
        "rule_pack_id": loaded_pack.definition.rule_pack_id,
        "rule_pack_version": loaded_pack.definition.version,
        "rule_pack_sha256": loaded_pack.sha256,
        "rule_pack_snapshot": loaded_pack.definition.model_dump(mode="json"),
        "context_snapshot": context_snapshot,
        "result_count": len(evaluated),
    }
    if client_run_id is not None:
        run_kwargs["id"] = client_run_id

    run = RuleEvaluationRun(**run_kwargs)
    db.add(run)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        if client_run_id is not None:
            existing = db.get(RuleEvaluationRun, client_run_id)
            if existing is not None:
                if _matches_evaluation_replay(
                    existing,
                    inspection_id=inspection.id,
                    actor_user_id=officer.id,
                    context_snapshot=context_snapshot,
                ):
                    return _response_for_run(db, existing)
                _raise_client_evaluation_id_conflict()
        raise

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


@router.get(
    "/runs/{run_id}",
    response_model=RuleEvaluationResponse,
)
def get_rule_evaluation_run(
    inspection_id: str,
    run_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    inspection = get_visible_inspection_or_raise(db, inspection_id, user)
    run = db.get(RuleEvaluationRun, run_id)
    if run is None or run.inspection_id != inspection.id:
        raise not_found(
            "rule_evaluation_not_found",
            "Rule evaluation not found for this inspection.",
        )
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
