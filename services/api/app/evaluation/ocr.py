from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Literal

from app.core.config import Settings
from app.services.image_quality import (
    PREPROCESSING_VERSION,
    assess_quality,
    normalize_capture,
    quality_thresholds_from_settings,
)
from app.services.ocr_engine import OcrEngine, OcrInferenceFailed
from app.services.perspective import (
    GEOMETRY_ALGORITHM_VERSION,
    PERSPECTIVE_PROCESSING_VERSION,
    analyze_perspective,
    geometry_thresholds_from_settings,
)

DatasetType = Literal["real_package", "synthetic", "other"]
_ALLOWED_DATASET_TYPES = {"real_package", "synthetic", "other"}
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class OcrManifestRow:
    case_id: str
    image_path: Path
    dataset_type: DatasetType
    ground_truth_path: Path | None
    notes: str


def normalize_metric_text(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value)
    return _WHITESPACE.sub(" ", normalized).strip()


def _edit_distance(reference: list[str], prediction: list[str]) -> int:
    if not reference:
        return len(prediction)
    if not prediction:
        return len(reference)

    previous = list(range(len(prediction) + 1))
    for ref_index, ref_item in enumerate(reference, start=1):
        current = [ref_index]
        for pred_index, pred_item in enumerate(prediction, start=1):
            substitution_cost = 0 if ref_item == pred_item else 1
            current.append(
                min(
                    current[-1] + 1,
                    previous[pred_index] + 1,
                    previous[pred_index - 1] + substitution_cost,
                )
            )
        previous = current
    return previous[-1]


def character_error_rate(reference: str, prediction: str) -> float:
    ref = normalize_metric_text(reference)
    pred = normalize_metric_text(prediction)
    distance = _edit_distance(list(ref), list(pred))
    return distance / max(1, len(ref))


def word_error_rate(reference: str, prediction: str) -> float:
    ref_words = normalize_metric_text(reference).split()
    pred_words = normalize_metric_text(prediction).split()
    distance = _edit_distance(ref_words, pred_words)
    return distance / max(1, len(ref_words))


def load_ocr_manifest(path: Path) -> list[OcrManifestRow]:
    manifest = path.expanduser().resolve()
    if not manifest.is_file():
        raise FileNotFoundError(f"Manifest not found: {manifest}")

    required = {
        "case_id",
        "image_path",
        "dataset_type",
        "ground_truth_path",
        "notes",
    }
    rows: list[OcrManifestRow] = []
    seen: set[str] = set()

    with manifest.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(
                "Manifest is missing required columns: "
                + ", ".join(sorted(missing))
            )

        for line_number, raw in enumerate(reader, start=2):
            case_id = (raw.get("case_id") or "").strip()
            if not case_id:
                raise ValueError(
                    f"Manifest line {line_number}: case_id is required."
                )
            if case_id in seen:
                raise ValueError(
                    f"Manifest line {line_number}: duplicate case_id {case_id!r}."
                )
            seen.add(case_id)

            image_value = (raw.get("image_path") or "").strip()
            if not image_value:
                raise ValueError(
                    f"Manifest line {line_number}: image_path is required."
                )

            dataset_type = (raw.get("dataset_type") or "").strip()
            if dataset_type not in _ALLOWED_DATASET_TYPES:
                raise ValueError(
                    f"Manifest line {line_number}: dataset_type must be one of "
                    f"{sorted(_ALLOWED_DATASET_TYPES)}."
                )

            truth_value = (raw.get("ground_truth_path") or "").strip()
            rows.append(
                OcrManifestRow(
                    case_id=case_id,
                    image_path=(manifest.parent / image_value).resolve(),
                    dataset_type=dataset_type,  # type: ignore[arg-type]
                    ground_truth_path=(
                        (manifest.parent / truth_value).resolve()
                        if truth_value
                        else None
                    ),
                    notes=(raw.get("notes") or "").strip(),
                )
            )

    if not rows:
        raise ValueError("Manifest contains no OCR evaluation cases.")
    return rows


def _ground_truth(row: OcrManifestRow) -> str | None:
    if row.ground_truth_path is None:
        return None
    if not row.ground_truth_path.is_file():
        raise FileNotFoundError(
            f"Ground truth for case {row.case_id!r} not found: "
            f"{row.ground_truth_path}"
        )
    return row.ground_truth_path.read_text(encoding="utf-8")


def _case_base(row: OcrManifestRow, ground_truth: str | None) -> dict:
    return {
        "case_id": row.case_id,
        "dataset_type": row.dataset_type,
        "image_path": str(row.image_path),
        "ground_truth_path": (
            str(row.ground_truth_path)
            if row.ground_truth_path is not None
            else None
        ),
        "notes": row.notes,
        "ground_truth_text": ground_truth,
        "normalized_ground_truth_text": (
            normalize_metric_text(ground_truth)
            if ground_truth is not None
            else None
        ),
    }


def evaluate_ocr_manifest(
    manifest_path: Path,
    *,
    settings: Settings,
    engine: OcrEngine,
) -> dict:
    rows = load_ocr_manifest(manifest_path)
    quality_thresholds = quality_thresholds_from_settings(settings)
    geometry_thresholds = geometry_thresholds_from_settings(settings)

    cases: list[dict] = []
    for row in rows:
        if not row.image_path.is_file():
            raise FileNotFoundError(
                f"Image for case {row.case_id!r} not found: {row.image_path}"
            )

        ground_truth = _ground_truth(row)
        case = _case_base(row, ground_truth)

        try:
            original = row.image_path.read_bytes()
            normalized = normalize_capture(original)
            quality = assess_quality(
                normalized.data,
                thresholds=quality_thresholds,
            )
            geometry = analyze_perspective(
                normalized.data,
                thresholds=geometry_thresholds,
            )
        except OSError:
            case.update(
                {
                    "status": "pipeline_error",
                    "error_code": "image_preparation_failed",
                    "quality_status": None,
                    "quality_reasons": [],
                    "geometry_status": None,
                    "geometry_reasons": [],
                    "ocr_source_type": None,
                    "ocr_source_processing_version": None,
                    "recognized_text": None,
                    "normalized_recognized_text": None,
                    "character_error_rate": None,
                    "word_error_rate": None,
                    "blocks": [],
                }
            )
            cases.append(case)
            continue

        if geometry.corrected_jpeg is not None:
            source_bytes = geometry.corrected_jpeg
            source_type = "perspective_corrected"
            source_processing_version = PERSPECTIVE_PROCESSING_VERSION
        else:
            source_bytes = normalized.data
            source_type = "normalized"
            source_processing_version = PREPROCESSING_VERSION

        try:
            detections = engine.extract(source_bytes)
        except OcrInferenceFailed:
            case.update(
                {
                    "status": "ocr_error",
                    "error_code": "ocr_inference_failed",
                    "quality_status": quality.status.value,
                    "quality_reasons": quality.reasons,
                    "geometry_status": geometry.status.value,
                    "geometry_reasons": geometry.reasons,
                    "ocr_source_type": source_type,
                    "ocr_source_processing_version": source_processing_version,
                    "recognized_text": None,
                    "normalized_recognized_text": None,
                    "character_error_rate": None,
                    "word_error_rate": None,
                    "blocks": [],
                }
            )
            cases.append(case)
            continue

        recognized_text = "\n".join(
            detection.text for detection in detections
        )
        cer = (
            round(character_error_rate(ground_truth, recognized_text), 6)
            if ground_truth is not None
            else None
        )
        wer = (
            round(word_error_rate(ground_truth, recognized_text), 6)
            if ground_truth is not None
            else None
        )

        case.update(
            {
                "status": "ok",
                "error_code": None,
                "quality_status": quality.status.value,
                "quality_reasons": quality.reasons,
                "geometry_status": geometry.status.value,
                "geometry_reasons": geometry.reasons,
                "ocr_source_type": source_type,
                "ocr_source_processing_version": source_processing_version,
                "recognized_text": recognized_text,
                "normalized_recognized_text": normalize_metric_text(
                    recognized_text
                ),
                "character_error_rate": cer,
                "word_error_rate": wer,
                "blocks": [
                    {
                        "order_index": index,
                        "text": detection.text,
                        "confidence": detection.confidence,
                        "polygon": detection.polygon,
                    }
                    for index, detection in enumerate(detections)
                ],
            }
        )
        cases.append(case)

    dataset_counts = {
        dataset_type: sum(
            1
            for case in cases
            if case["dataset_type"] == dataset_type
        )
        for dataset_type in sorted(_ALLOWED_DATASET_TYPES)
    }
    successful = [case for case in cases if case["status"] == "ok"]
    labeled = [
        case
        for case in successful
        if case["ground_truth_text"] is not None
    ]
    real_cases = [
        case for case in cases
        if case["dataset_type"] == "real_package"
    ]
    labeled_real = [
        case
        for case in real_cases
        if case["ground_truth_text"] is not None
    ]
    scored_real = [
        case
        for case in labeled_real
        if case["status"] == "ok"
    ]

    warnings: list[str] = []
    if not real_cases:
        warnings.append("no_real_package_cases")
    if not labeled_real:
        warnings.append("no_labeled_real_package_cases")
    if labeled_real and not scored_real:
        warnings.append("no_scored_real_package_cases")
    if any(case["status"] != "ok" for case in cases):
        warnings.append("one_or_more_cases_failed")

    return {
        "manifest": str(manifest_path.expanduser().resolve()),
        "case_count": len(cases),
        "successful_case_count": len(successful),
        "failed_case_count": len(cases) - len(successful),
        "dataset_counts": dataset_counts,
        "labeled_case_count": sum(
            1 for case in cases if case["ground_truth_text"] is not None
        ),
        "scored_case_count": len(labeled),
        "real_package_labeled_count": len(labeled_real),
        "real_package_scored_count": len(scored_real),
        "metric_normalization": {
            "unicode": "NFC",
            "whitespace": "collapse_runs",
            "case_sensitive": True,
            "punctuation_preserved": True,
        },
        "preprocessing_version": PREPROCESSING_VERSION,
        "geometry_algorithm_version": GEOMETRY_ALGORITHM_VERSION,
        "perspective_processing_version": PERSPECTIVE_PROCESSING_VERSION,
        "engine": {
            "name": engine.name,
            "version": engine.version,
            "model_version": engine.model_version,
            "language": engine.language,
            "parameters": engine.parameters,
        },
        "quality_thresholds": quality_thresholds.as_dict(),
        "geometry_thresholds": geometry_thresholds.as_dict(),
        "mean_character_error_rate": (
            round(mean(case["character_error_rate"] for case in labeled), 6)
            if labeled
            else None
        ),
        "mean_word_error_rate": (
            round(mean(case["word_error_rate"] for case in labeled), 6)
            if labeled
            else None
        ),
        "real_package_mean_character_error_rate": (
            round(
                mean(
                    case["character_error_rate"]
                    for case in scored_real
                ),
                6,
            )
            if scored_real
            else None
        ),
        "real_package_mean_word_error_rate": (
            round(
                mean(
                    case["word_error_rate"]
                    for case in scored_real
                ),
                6,
            )
            if scored_real
            else None
        ),
        "warnings": warnings,
        "cases": cases,
    }


def ocr_gate_failures(
    report: dict,
    *,
    require_real_package: int = 0,
    require_labeled_real: int = 0,
    require_scored_real: int = 0,
    max_real_cer: float | None = None,
    max_real_wer: float | None = None,
) -> list[str]:
    failures: list[str] = []
    real_count = int(report["dataset_counts"]["real_package"])
    labeled_real = int(report["real_package_labeled_count"])
    scored_real = int(report["real_package_scored_count"])

    if real_count < require_real_package:
        failures.append(
            f"real_package_count:{real_count}<{require_real_package}"
        )
    if labeled_real < require_labeled_real:
        failures.append(
            f"labeled_real_package_count:{labeled_real}<{require_labeled_real}"
        )
    if scored_real < require_scored_real:
        failures.append(
            f"scored_real_package_count:{scored_real}<{require_scored_real}"
        )

    real_cer = report["real_package_mean_character_error_rate"]
    if max_real_cer is not None:
        if real_cer is None:
            failures.append("real_package_cer:unavailable")
        elif real_cer > max_real_cer:
            failures.append(
                f"real_package_cer:{real_cer}>{max_real_cer}"
            )

    real_wer = report["real_package_mean_word_error_rate"]
    if max_real_wer is not None:
        if real_wer is None:
            failures.append("real_package_wer:unavailable")
        elif real_wer > max_real_wer:
            failures.append(
                f"real_package_wer:{real_wer}>{max_real_wer}"
            )

    return failures
