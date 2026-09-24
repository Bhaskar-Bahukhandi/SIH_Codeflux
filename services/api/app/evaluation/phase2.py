from __future__ import annotations

import csv
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

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

DatasetType = Literal["real_package", "web_reference", "synthetic", "other"]
_ALLOWED_DATASET_TYPES = {"real_package", "web_reference", "synthetic", "other"}


@dataclass(frozen=True, slots=True)
class Phase2ManifestRow:
    case_id: str
    image_path: Path
    dataset_type: DatasetType
    expected_quality_status: str | None
    expected_geometry_status: str | None
    source_page_url: str | None
    source_domain: str | None
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


def _validate_source_page_url(
    value: str | None,
    *,
    dataset_type: str,
    line_number: int,
) -> tuple[str | None, str | None]:
    source_page_url = _optional_text(value)
    if source_page_url is None:
        if dataset_type == "web_reference":
            raise ValueError(
                f"Manifest line {line_number}: source_page_url is required "
                "for web_reference cases."
            )
        return None, None

    parsed = urlparse(source_page_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(
            f"Manifest line {line_number}: source_page_url must be an "
            "absolute http(s) URL."
        )
    return source_page_url, parsed.hostname.lower()


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

            source_page_url, source_domain = _validate_source_page_url(
                raw.get("source_page_url"),
                dataset_type=dataset_type,
                line_number=line_number,
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
                    source_page_url=source_page_url,
                    source_domain=source_domain,
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
    resolved_manifest = manifest_path.expanduser().resolve()
    rows = load_phase2_manifest(resolved_manifest)
    manifest_sha256 = hashlib.sha256(resolved_manifest.read_bytes()).hexdigest()
    quality_thresholds = quality_thresholds_from_settings(settings)
    geometry_thresholds = geometry_thresholds_from_settings(settings)

    cases: list[dict] = []
    for row in rows:
        if not row.image_path.is_file():
            raise FileNotFoundError(
                f"Image for case {row.case_id!r} not found: {row.image_path}"
            )

        original = row.image_path.read_bytes()
        image_sha256 = hashlib.sha256(original).hexdigest()
        relative_image_path = Path(
            os.path.relpath(row.image_path, start=resolved_manifest.parent)
        ).as_posix()
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
                "image_path": relative_image_path,
                "image_sha256": image_sha256,
                "dataset_type": row.dataset_type,
                "source_page_url": row.source_page_url,
                "source_domain": row.source_domain,
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
    web_reference_cases = [
        case for case in cases if case["dataset_type"] == "web_reference"
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
    web_reference_quality_summary = _agreement_summary(
        web_reference_cases,
        expected_key="expected_quality_status",
        actual_key="quality_status",
    )
    web_reference_geometry_summary = _agreement_summary(
        web_reference_cases,
        expected_key="expected_geometry_status",
        actual_key="geometry_status",
    )

    return {
        "manifest": resolved_manifest.name,
        "manifest_sha256": manifest_sha256,
        "input_provenance_version": "phase2-input-sha256-v1",
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
        "web_reference_count": len(web_reference_cases),
        "web_reference_source_domains": sorted(
            {
                case["source_domain"]
                for case in web_reference_cases
                if case["source_domain"] is not None
            }
        ),
        "preprocessing_version": PREPROCESSING_VERSION,
        "quality_algorithm_version": QUALITY_ALGORITHM_VERSION,
        "geometry_algorithm_version": GEOMETRY_ALGORITHM_VERSION,
        "quality_thresholds": quality_thresholds.as_dict(),
        "geometry_thresholds": geometry_thresholds.as_dict(),
        "quality_status_agreement": quality_summary,
        "geometry_status_agreement": geometry_summary,
        "web_reference_quality_status_agreement": web_reference_quality_summary,
        "web_reference_geometry_status_agreement": web_reference_geometry_summary,
        "warnings": warnings,
        "cases": cases,
    }


def phase2_gate_failures(
    report: dict,
    *,
    require_real_package: int = 0,
    require_labeled_real_quality: int = 0,
    require_labeled_real_geometry: int = 0,
    fail_on_mismatch: bool = False,
) -> list[str]:
    failures: list[str] = []

    real_count = int(report["dataset_counts"]["real_package"])
    if real_count < require_real_package:
        failures.append(
            f"real_package_count:{real_count}<{require_real_package}"
        )

    quality_real = int(report["real_package_labeled_quality_count"])
    if quality_real < require_labeled_real_quality:
        failures.append(
            "labeled_real_quality_count:"
            f"{quality_real}<{require_labeled_real_quality}"
        )

    geometry_real = int(report["real_package_labeled_geometry_count"])
    if geometry_real < require_labeled_real_geometry:
        failures.append(
            "labeled_real_geometry_count:"
            f"{geometry_real}<{require_labeled_real_geometry}"
        )

    if fail_on_mismatch:
        mismatch_ids = sorted(
            set(
                report["quality_status_agreement"]["mismatch_case_ids"]
                + report["geometry_status_agreement"]["mismatch_case_ids"]
            )
        )
        if mismatch_ids:
            failures.append(
                "status_mismatches:" + ",".join(mismatch_ids)
            )

    return failures
