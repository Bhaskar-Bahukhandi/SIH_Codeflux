from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.capture import Capture
from app.models.declaration import DeclarationExtractionRun
from app.models.ocr import OcrRun
from app.services.ocr_source import select_ocr_source_derivative


@dataclass(frozen=True, slots=True)
class CurrentOcrSourceSnapshot:
    inspection_capture_count: int
    source_pairs: list[tuple[Capture, OcrRun]]
    skipped_sources: list[dict]

    @property
    def source_capture_ids(self) -> list[str]:
        return [capture.id for capture, _ in self.source_pairs]

    @property
    def source_ocr_run_ids(self) -> list[str]:
        return [run.id for _, run in self.source_pairs]


def _latest_ocr_run(
    db: Session,
    *,
    capture_id: str,
) -> OcrRun | None:
    return db.scalar(
        select(OcrRun)
        .where(OcrRun.capture_id == capture_id)
        .order_by(OcrRun.created_at.desc(), OcrRun.id.desc())
        .limit(1)
    )


def collect_current_ocr_sources(
    db: Session,
    *,
    inspection_id: str,
) -> CurrentOcrSourceSnapshot:
    captures = list(
        db.scalars(
            select(Capture)
            .where(Capture.inspection_id == inspection_id)
            .order_by(Capture.created_at.asc(), Capture.id.asc())
        ).all()
    )

    source_pairs: list[tuple[Capture, OcrRun]] = []
    skipped_sources: list[dict] = []

    for capture in captures:
        latest_ocr = _latest_ocr_run(db, capture_id=capture.id)
        if latest_ocr is None:
            skipped_sources.append(
                {
                    "capture_id": capture.id,
                    "reason": "no_ocr",
                }
            )
            continue

        current_source = select_ocr_source_derivative(
            db,
            capture_id=capture.id,
        )
        if latest_ocr.source_derivative_id != current_source.id:
            skipped_sources.append(
                {
                    "capture_id": capture.id,
                    "reason": "stale_ocr",
                    "ocr_run_id": latest_ocr.id,
                }
            )
            continue

        source_pairs.append((capture, latest_ocr))

    return CurrentOcrSourceSnapshot(
        inspection_capture_count=len(captures),
        source_pairs=source_pairs,
        skipped_sources=skipped_sources,
    )


def declaration_extraction_is_current(
    db: Session,
    *,
    inspection_id: str,
    extraction_run: DeclarationExtractionRun,
) -> bool:
    if extraction_run.inspection_id != inspection_id:
        return False

    current = collect_current_ocr_sources(
        db,
        inspection_id=inspection_id,
    )
    return (
        extraction_run.inspection_capture_count
        == current.inspection_capture_count
        and extraction_run.source_capture_ids == current.source_capture_ids
        and extraction_run.source_ocr_run_ids == current.source_ocr_run_ids
        and extraction_run.skipped_sources == current.skipped_sources
    )
