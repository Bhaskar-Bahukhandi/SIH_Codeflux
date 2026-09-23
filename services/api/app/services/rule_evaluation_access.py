from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import conflict, not_found
from app.models.declaration import DeclarationExtractionRun
from app.models.rule_evaluation import RuleEvaluationRun
from app.services.declaration_sources import collect_current_ocr_sources


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


def get_rule_evaluation_run_or_raise(
    db: Session,
    *,
    inspection_id: str,
    evaluation_run_id: str,
) -> RuleEvaluationRun:
    run = db.get(RuleEvaluationRun, evaluation_run_id)
    if run is None or run.inspection_id != inspection_id:
        raise not_found(
            "rule_evaluation_not_found",
            "Rule evaluation not found.",
        )
    return run


def assert_rule_evaluation_is_latest_and_current(
    db: Session,
    *,
    inspection_id: str,
    evaluation_run: RuleEvaluationRun,
) -> None:
    latest = latest_rule_evaluation_run(
        db,
        inspection_id=inspection_id,
    )
    if latest is None or latest.id != evaluation_run.id:
        raise conflict(
            "current_rule_evaluation_required",
            "A newer rule evaluation exists. Review the current evaluation instead.",
        )

    extraction_run = db.get(
        DeclarationExtractionRun,
        evaluation_run.source_extraction_run_id,
    )
    if extraction_run is None or extraction_run.inspection_id != inspection_id:
        raise conflict(
            "current_rule_evaluation_required",
            "The rule evaluation no longer has valid declaration provenance.",
        )

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
            "current_rule_evaluation_required",
            "The rule evaluation is stale. Refresh extraction and rule evaluation before officer review.",
        )
