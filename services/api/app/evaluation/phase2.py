from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from app.core.config import Settings
from app.models.geometry import GeometryStatus
from app.models.quality import CaptureQualityStatus
from app.services.image_quality import (
    PREPROCESSING_VERSION,
    QUALITY_ALGORITHM_VERSION,
    assess_quality,
    normalize_capture,
    quality_thresholds_from_settings,
)
from app.services.perspective import (
    GEOMETRY_ALGORITHM_VERSION,
    analyze_perspective,
    geometry_thresholds_from_settings,
)

DatasetType = Literal["real_package", "synthetic", "other"]
_ALLOWED_DATASET_TYPES = {"real_package", "synthetic", "other"}


@dataclass(frozen=True, slots=True)
class Phase2ManifestRow:
    case_id: str
    image_path: Path
    dataset_type: DatasetType
    expected_quality_status: str | None
    expected_geometry_status: str | None
    notes: str


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _validate_expected_quality(value: str | None) -> str | None:
    value = _optional_text(value)
    if value is None:
        return None
    allowed = {status.value for status in CaptureQualityStatus}
    if value not in allowed:
        raise ValueError(
            f"Unsupported expected_quality_status {value!r}; "
            f"expected one of {sorted(allowed)}."
        )
    return value


def _validate_expected_geometry(value: str | None) -> str | None:
    value = _optional_text(value)
    if value is None:
        return None
    allowed = {status.value for status in GeometryStatus}
    if value not in allowed:
        raise ValueError(
            f"Unsupported expected_geometry_status {value!r}; "
            f"expected one of {sorted(allowed)}."
        )
    return value


def load_phase2_manifest(path: Path) -> list[Phase2ManifestRow]:
    manifest_path = path.expanduser().resolve()
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    required_columns = {
        "case_id",
        "image_path",
        "dataset_type",
        "expected_quality_status",
        "expected_geometry_status",
        "notes",
    }

    rows: list[Phase2ManifestRow] = []
    seen_case_ids: set[str] = set()

    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        missing = required_columns - fieldnames
        if missing:
            raise ValueError(
                "Manifest is missing required columns: "
                + ", ".join(sorted(missing))
            )

        for line_number, raw in enumerate(reader, start=2):
            case_id = (raw.get("case_id") or "").strip()
            if not case_id:
                raise ValueError(f"Manifest line {line_number}: case_id is required.")
            if case_id in seen_case_ids:
                raise ValueError(
                    f"Manifest line {line_number}: duplicate case_id {case_id!r}."
                )
            seen_case_ids.add(case_id)

            relative_image = (raw.get("image_path") or "").strip()
            if not relative_image:
                raise ValueError(
                    f"Manifest line {line_number}: image_path is required."
                )
            image_path = (manifest_path.parent / relative_image).resolve()

            dataset_type = (raw.get("dataset_type") or "").strip()
            if dataset_type not in _ALLOWED_DATASET_TYPES:
                raise ValueError(
                    f"Manifest line {line_number}: dataset_type must be one of "
                    f"{sorted(_ALLOWED_DATASET_TYPES)}."
                )

            rows.append(
                Phase2ManifestRow(
                    case_id=case_id,
                    image_path=image_path,
                    dataset_type=dataset_type,  # type: ignore[arg-type]
                    expected_quality_status=_validate_expected_quality(
                        raw.get("expected_quality_status")
                    ),
                    expected_geometry_status=_validate_expected_geometry(
                        raw.get("expected_geometry_status")
                    ),
                    notes=(raw.get("notes") or "").strip(),
                )
            )

    if not rows:
        raise ValueError("Manifest contains no evaluation cases.")

    return rows


def _agreement_summary(
    cases: list[dict],
    *,
    expected_key: str,
    actual_key: str,
) -> dict:
    labeled = [
        case
        for case in cases
        if case[expected_key] is not None
    ]
    matches = [
        case
        for case in labeled
        if case[expected_key] == case[actual_key]
    ]
    mismatches = [
        case["case_id"]
        for case in labeled
        if case[expected_key] != case[actual_key]
    ]

    return {
        "labeled_count": len(labeled),
        "match_count": len(matches),
        "agreement_rate": (
            round(len(matches) / len(labeled), 6)
            if labeled
            else None
        ),
        "mismatch_case_ids": mismatches,
    }


def evaluate_phase2_manifest(
    manifest_path: Path,
    *,
    settings: Settings,
) -> dict:
    rows = load_phase2_manifest(manifest_path)
    quality_thresholds = quality_thresholds_from_settings(settings)
    geometry_thresholds = geometry_thresholds_from_settings(settings)

    cases: list[dict] = []
    for row in rows:
        if not row.image_path.is_file():
            raise FileNotFoundError(
                f"Image for case {row.case_id!r} not found: {row.image_path}"
            )

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

        cases.append(
            {
                "case_id": row.case_id,
                "image_path": str(row.image_path),
                "dataset_type": row.dataset_type,
                "notes": row.notes,
                "expected_quality_status": row.expected_quality_status,
                "quality_status": quality.status.value,
                "quality_match": (
                    quality.status.value == row.expected_quality_status
                    if row.expected_quality_status is not None
                    else None
                ),
                "quality_metrics": {
                    "sharpness_score": quality.sharpness_score,
                    "brightness_mean": quality.brightness_mean,
                    "dark_fraction": quality.dark_fraction,
                    "bright_fraction": quality.bright_fraction,
                    "glare_fraction": quality.glare_fraction,
                    "reasons": quality.reasons,
                },
                "expected_geometry_status": row.expected_geometry_status,
                "geometry_status": geometry.status.value,
                "geometry_match": (
                    geometry.status.value == row.expected_geometry_status
                    if row.expected_geometry_status is not None
                    else None
                ),
                "geometry_metrics": {
                    "area_ratio": geometry.area_ratio,
                    "angle_score": geometry.angle_score,
                    "geometry_score": geometry.geometry_score,
                    "reasons": geometry.reasons,
                    "corners": geometry.corners,
                },
            }
        )

    dataset_counts = {
        dataset_type: sum(
            1 for case in cases if case["dataset_type"] == dataset_type
        )
        for dataset_type in sorted(_ALLOWED_DATASET_TYPES)
    }
    real_cases = [
        case for case in cases if case["dataset_type"] == "real_package"
    ]

    warnings: list[str] = []
    if not real_cases:
        warnings.append("no_real_package_cases")
    if not any(
        case["expected_quality_status"] is not None
        for case in real_cases
    ):
        warnings.append("no_labeled_real_package_quality_cases")
    if not any(
        case["expected_geometry_status"] is not None
        for case in real_cases
    ):
        warnings.append("no_labeled_real_package_geometry_cases")

    quality_summary = _agreement_summary(
        cases,
        expected_key="expected_quality_status",
        actual_key="quality_status",
    )
    geometry_summary = _agreement_summary(
        cases,
        expected_key="expected_geometry_status",
        actual_key="geometry_status",
    )

    return {
        "manifest": str(manifest_path.expanduser().resolve()),
        "case_count": len(cases),
        "dataset_counts": dataset_counts,
        "real_package_labeled_quality_count": sum(
            1
            for case in real_cases
            if case["expected_quality_status"] is not None
        ),
        "real_package_labeled_geometry_count": sum(
            1
            for case in real_cases
            if case["expected_geometry_status"] is not None
        ),
        "preprocessing_version": PREPROCESSING_VERSION,
        "quality_algorithm_version": QUALITY_ALGORITHM_VERSION,
        "geometry_algorithm_version": GEOMETRY_ALGORITHM_VERSION,
        "quality_thresholds": quality_thresholds.as_dict(),
        "geometry_thresholds": geometry_thresholds.as_dict(),
        "quality_status_agreement": quality_summary,
        "geometry_status_agreement": geometry_summary,
        "warnings": warnings,
        "cases": cases,
    }
