from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.declaration import DeclarationExtractionRun
from app.models.officer_review import OfficerRuleReview
from app.models.rule_evaluation import RuleEvaluationRun
from app.services.declaration_sources import declaration_extraction_is_current


def latest_rule_evaluation_run(
    db: Session,
    *,
    inspection_id: str,
) -> RuleEvaluationRun | None:
    return db.scalar(
        select(RuleEvaluationRun)
        .where(RuleEvaluationRun.inspection_id == inspection_id)
        .order_by(
            RuleEvaluationRun.created_at.desc(),
            RuleEvaluationRun.id.desc(),
        )
        .limit(1)
    )


def latest_officer_reviews_by_result(
    db: Session,
    *,
    inspection_id: str,
    rule_evaluation_run_id: str | None = None,
) -> dict[str, OfficerRuleReview]:
    statement = (
        select(OfficerRuleReview)
        .where(OfficerRuleReview.inspection_id == inspection_id)
        .order_by(
            OfficerRuleReview.rule_evaluation_result_id.asc(),
            OfficerRuleReview.revision.asc(),
            OfficerRuleReview.id.asc(),
        )
    )
    if rule_evaluation_run_id is not None:
        statement = statement.where(
            OfficerRuleReview.rule_evaluation_run_id == rule_evaluation_run_id
        )

    latest: dict[str, OfficerRuleReview] = {}
    for review in db.scalars(statement).all():
        latest[review.rule_evaluation_result_id] = review
    return latest


def rule_evaluation_matches_current_evidence(
    db: Session,
    *,
    inspection_id: str,
    run: RuleEvaluationRun,
) -> bool:
    extraction_run = db.get(
        DeclarationExtractionRun,
        run.source_extraction_run_id,
    )
    if extraction_run is None or extraction_run.inspection_id != inspection_id:
        return False

    return declaration_extraction_is_current(
        db,
        inspection_id=inspection_id,
        extraction_run=extraction_run,
    )


def has_current_rule_evaluation_after(
    db: Session,
    *,
    inspection_id: str,
    after: datetime,
) -> bool:
    run = latest_rule_evaluation_run(
        db,
        inspection_id=inspection_id,
    )
    return (
        run is not None
        and run.created_at > after
        and rule_evaluation_matches_current_evidence(
            db,
            inspection_id=inspection_id,
            run=run,
        )
    )
