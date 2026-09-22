from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_officer
from app.db import get_db
from app.errors import conflict, not_found
from app.models.audit import AuditEventType
from app.models.declaration import (
    DeclarationExtractionRun,
    DeclarationObservation,
    DeclarationObservationBlock,
    DeclarationSummary,
)
from app.models.ocr import OcrBlock
from app.models.user import User
from app.schemas.declaration import DeclarationExtractionResultRead
from app.services.audit import record_inspection_event
from app.services.declaration_extractor import (
    DECLARATION_EXTRACTOR_VERSION,
    OcrTextEvidence,
    extract_declarations,
)
from app.services.declaration_fusion import (
    DECLARATION_FUSION_VERSION,
    FusionObservation,
    fuse_declarations,
)
from app.services.declaration_sources import collect_current_ocr_sources
from app.services.inspection_access import get_visible_inspection_or_raise
from app.services.inspection_lifecycle import require_draft

router = APIRouter(
    prefix="/inspections/{inspection_id}/declarations",
    tags=["declarations"],
)


def _result_for_run(
    db: Session,
    run: DeclarationExtractionRun,
) -> dict:
    observations = list(
        db.scalars(
            select(DeclarationObservation)
            .where(DeclarationObservation.extraction_run_id == run.id)
            .order_by(
                DeclarationObservation.declaration_type.asc(),
                DeclarationObservation.capture_id.asc(),
                DeclarationObservation.id.asc(),
            )
        ).all()
    )

    observation_payloads: list[dict] = []
    for observation in observations:
        source_block_ids = list(
            db.scalars(
                select(DeclarationObservationBlock.ocr_block_id)
                .where(
                    DeclarationObservationBlock.observation_id
                    == observation.id
                )
                .order_by(
                    DeclarationObservationBlock.block_order.asc(),
                    DeclarationObservationBlock.id.asc(),
                )
            ).all()
        )
        observation_payloads.append(
            {
                "id": observation.id,
                "extraction_run_id": observation.extraction_run_id,
                "declaration_type": observation.declaration_type,
                "capture_id": observation.capture_id,
                "ocr_run_id": observation.ocr_run_id,
                "raw_text": observation.raw_text,
                "normalized_value": observation.normalized_value,
                "ocr_confidence_min": observation.ocr_confidence_min,
                "ocr_confidence_mean": observation.ocr_confidence_mean,
                "extractor_method": observation.extractor_method,
                "source_block_ids": source_block_ids,
            }
        )

    summaries = list(
        db.scalars(
            select(DeclarationSummary)
            .where(DeclarationSummary.extraction_run_id == run.id)
            .order_by(DeclarationSummary.declaration_type.asc())
        ).all()
    )

    return {
        "run": run,
        "observations": observation_payloads,
        "summaries": summaries,
    }


@router.post("/extract", response_model=DeclarationExtractionResultRead)
def extract_inspection_declarations(
    inspection_id: str,
    db: Session = Depends(get_db),
    officer: User = Depends(require_officer),
) -> dict:
    inspection = get_visible_inspection_or_raise(db, inspection_id, officer)
    require_draft(inspection)

    current = collect_current_ocr_sources(
        db,
        inspection_id=inspection.id,
    )
    source_pairs = current.source_pairs

    if not source_pairs:
        raise conflict(
            "inspection_current_ocr_required",
            "Run current OCR on at least one inspection capture before extraction.",
        )

    run = DeclarationExtractionRun(
        inspection_id=inspection.id,
        actor_user_id=officer.id,
        extractor_version=DECLARATION_EXTRACTOR_VERSION,
        fusion_version=DECLARATION_FUSION_VERSION,
        inspection_capture_count=current.inspection_capture_count,
        source_capture_count=len(source_pairs),
        source_capture_ids=current.source_capture_ids,
        source_ocr_run_ids=current.source_ocr_run_ids,
        skipped_sources=current.skipped_sources,
        observation_count=0,
    )
    db.add(run)
    db.flush()

    persisted_observations: list[DeclarationObservation] = []
    fusion_inputs: list[FusionObservation] = []

    for capture, ocr_run in source_pairs:
        blocks = list(
            db.scalars(
                select(OcrBlock)
                .where(OcrBlock.run_id == ocr_run.id)
                .order_by(OcrBlock.order_index.asc(), OcrBlock.id.asc())
            ).all()
        )

        evidence_blocks = [
            OcrTextEvidence(
                block_id=block.id,
                order_index=block.order_index,
                text=block.text,
                confidence=block.confidence,
            )
            for block in blocks
        ]

        for candidate in extract_declarations(evidence_blocks):
            observation = DeclarationObservation(
                extraction_run_id=run.id,
                declaration_type=candidate.declaration_type,
                capture_id=capture.id,
                ocr_run_id=ocr_run.id,
                raw_text=candidate.raw_text,
                normalized_value=candidate.normalized_value,
                ocr_confidence_min=candidate.ocr_confidence_min,
                ocr_confidence_mean=candidate.ocr_confidence_mean,
                extractor_method=candidate.extractor_method,
            )
            db.add(observation)
            db.flush()

            for block_order, block_id in enumerate(candidate.block_ids):
                db.add(
                    DeclarationObservationBlock(
                        observation_id=observation.id,
                        ocr_block_id=block_id,
                        block_order=block_order,
                    )
                )

            persisted_observations.append(observation)
            fusion_inputs.append(
                FusionObservation(
                    declaration_type=observation.declaration_type,
                    capture_id=observation.capture_id,
                    normalized_value=observation.normalized_value,
                )
            )

    run.observation_count = len(persisted_observations)

    fused = fuse_declarations(fusion_inputs)
    summaries: list[DeclarationSummary] = []
    for result in fused:
        summary = DeclarationSummary(
            extraction_run_id=run.id,
            declaration_type=result.declaration_type,
            status=result.status,
            canonical_value=result.canonical_value,
            candidate_values=result.candidate_values,
            observation_count=result.observation_count,
            capture_count=result.capture_count,
        )
        db.add(summary)
        summaries.append(summary)

    record_inspection_event(
        db,
        inspection_id=inspection.id,
        actor_user_id=officer.id,
        event_type=AuditEventType.DECLARATION_EXTRACTION_COMPLETED,
        details={
            "extraction_run_id": run.id,
            "extractor_version": run.extractor_version,
            "fusion_version": run.fusion_version,
            "source_capture_count": run.source_capture_count,
            "observation_count": run.observation_count,
            "summary_statuses": {
                summary.declaration_type.value: summary.status.value
                for summary in summaries
            },
        },
    )

    db.commit()
    db.refresh(run)
    return _result_for_run(db, run)


@router.get("/latest", response_model=DeclarationExtractionResultRead)
def latest_declaration_extraction(
    inspection_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    inspection = get_visible_inspection_or_raise(db, inspection_id, user)

    run = db.scalar(
        select(DeclarationExtractionRun)
        .where(DeclarationExtractionRun.inspection_id == inspection.id)
        .order_by(
            DeclarationExtractionRun.created_at.desc(),
            DeclarationExtractionRun.id.desc(),
        )
        .limit(1)
    )
    if run is None:
        raise not_found(
            "declaration_extraction_not_found",
            "No declaration extraction exists for this inspection.",
        )

    return _result_for_run(db, run)
