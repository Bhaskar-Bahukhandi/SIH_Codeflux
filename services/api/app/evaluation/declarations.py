from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.models.declaration import DeclarationType
from app.services.declaration_extractor import (
    DECLARATION_EXTRACTOR_VERSION,
    OcrTextEvidence,
    SUPPORTED_DECLARATION_TYPES,
    extract_declarations,
)

DatasetType = Literal["real_package", "synthetic", "other"]
BlockSource = Literal["actual_ocr", "human_transcription", "synthetic"]

_ALLOWED_DATASET_TYPES = {"real_package", "synthetic", "other"}
_ALLOWED_BLOCK_SOURCES = {"actual_ocr", "human_transcription", "synthetic"}


@dataclass(frozen=True, slots=True)
class ExpectedDeclaration:
    declaration_type: DeclarationType
    normalized_value: dict


@dataclass(frozen=True, slots=True)
class DeclarationEvaluationCase:
    case_id: str
    dataset_type: DatasetType
    block_source: BlockSource
    ocr_blocks: list[OcrTextEvidence]
    expected_declarations: list[ExpectedDeclaration]
    notes: str


def _canonical_value(declaration_type: DeclarationType, value: dict) -> str:
    return (
        declaration_type.value
        + ":"
        + json.dumps(value, sort_keys=True, separators=(",", ":"))
    )


def _parse_declaration_type(value: str, *, context: str) -> DeclarationType:
    try:
        declaration_type = DeclarationType(value)
    except ValueError as exc:
        raise ValueError(
            f"{context}: unsupported declaration_type {value!r}."
        ) from exc

    if declaration_type not in SUPPORTED_DECLARATION_TYPES:
        raise ValueError(
            f"{context}: declaration_type {value!r} is not supported "
            "by the current extractor."
        )
    return declaration_type


def load_declaration_evaluation_manifest(
    path: Path,
) -> list[DeclarationEvaluationCase]:
    manifest = path.expanduser().resolve()
    if not manifest.is_file():
        raise FileNotFoundError(f"Manifest not found: {manifest}")

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
        raise ValueError("Manifest must contain a top-level 'cases' list.")

    cases: list[DeclarationEvaluationCase] = []
    seen: set[str] = set()

    for case_index, raw_case in enumerate(payload["cases"]):
        context = f"case index {case_index}"
        if not isinstance(raw_case, dict):
            raise ValueError(f"{context}: case must be an object.")

        case_id = str(raw_case.get("case_id", "")).strip()
        if not case_id:
            raise ValueError(f"{context}: case_id is required.")
        if case_id in seen:
            raise ValueError(f"{context}: duplicate case_id {case_id!r}.")
        seen.add(case_id)

        dataset_type = str(raw_case.get("dataset_type", "")).strip()
        if dataset_type not in _ALLOWED_DATASET_TYPES:
            raise ValueError(
                f"{context}: dataset_type must be one of "
                f"{sorted(_ALLOWED_DATASET_TYPES)}."
            )

        block_source = str(raw_case.get("block_source", "")).strip()
        if block_source not in _ALLOWED_BLOCK_SOURCES:
            raise ValueError(
                f"{context}: block_source must be one of "
                f"{sorted(_ALLOWED_BLOCK_SOURCES)}."
            )

        raw_blocks = raw_case.get("ocr_blocks")
        if not isinstance(raw_blocks, list):
            raise ValueError(f"{context}: ocr_blocks must be a list.")

        blocks: list[OcrTextEvidence] = []
        for block_index, raw_block in enumerate(raw_blocks):
            block_context = f"{context}, block {block_index}"
            if not isinstance(raw_block, dict):
                raise ValueError(f"{block_context}: block must be an object.")

            text = str(raw_block.get("text", ""))
            confidence = raw_block.get("confidence")
            if not isinstance(confidence, (int, float)):
                raise ValueError(
                    f"{block_context}: confidence must be numeric."
                )
            confidence = float(confidence)
            if not 0.0 <= confidence <= 1.0:
                raise ValueError(
                    f"{block_context}: confidence must be between 0 and 1."
                )

            blocks.append(
                OcrTextEvidence(
                    block_id=str(raw_block.get("block_id") or f"b{block_index}"),
                    order_index=block_index,
                    text=text,
                    confidence=confidence,
                )
            )

        raw_expected = raw_case.get("expected_declarations")
        if not isinstance(raw_expected, list):
            raise ValueError(
                f"{context}: expected_declarations must be a list."
            )

        expected: list[ExpectedDeclaration] = []
        for expected_index, raw_item in enumerate(raw_expected):
            item_context = f"{context}, expected {expected_index}"
            if not isinstance(raw_item, dict):
                raise ValueError(
                    f"{item_context}: expected declaration must be an object."
                )
            declaration_type = _parse_declaration_type(
                str(raw_item.get("declaration_type", "")),
                context=item_context,
            )
            normalized_value = raw_item.get("normalized_value")
            if not isinstance(normalized_value, dict):
                raise ValueError(
                    f"{item_context}: normalized_value must be an object."
                )
            expected.append(
                ExpectedDeclaration(
                    declaration_type=declaration_type,
                    normalized_value=normalized_value,
                )
            )

        cases.append(
            DeclarationEvaluationCase(
                case_id=case_id,
                dataset_type=dataset_type,  # type: ignore[arg-type]
                block_source=block_source,  # type: ignore[arg-type]
                ocr_blocks=blocks,
                expected_declarations=expected,
                notes=str(raw_case.get("notes", "")),
            )
        )

    if not cases:
        raise ValueError("Manifest contains no evaluation cases.")
    return cases


def _metric_summary(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None
        and recall is not None
        and precision + recall > 0
        else None
    )
    return {
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "precision": round(precision, 6) if precision is not None else None,
        "recall": round(recall, 6) if recall is not None else None,
        "f1": round(f1, 6) if f1 is not None else None,
    }


def evaluate_declaration_manifest(path: Path) -> dict:
    cases = load_declaration_evaluation_manifest(path)

    case_results: list[dict] = []
    overall_tp = overall_fp = overall_fn = 0
    type_counts = {
        declaration_type: {"tp": 0, "fp": 0, "fn": 0}
        for declaration_type in SUPPORTED_DECLARATION_TYPES
    }

    for case in cases:
        observations = extract_declarations(case.ocr_blocks)

        expected_map = {
            _canonical_value(
                item.declaration_type,
                item.normalized_value,
            ): {
                "declaration_type": item.declaration_type.value,
                "normalized_value": item.normalized_value,
            }
            for item in case.expected_declarations
        }
        predicted_map = {
            _canonical_value(
                item.declaration_type,
                item.normalized_value,
            ): {
                "declaration_type": item.declaration_type.value,
                "normalized_value": item.normalized_value,
                "raw_text": item.raw_text,
                "block_ids": item.block_ids,
                "ocr_confidence_min": item.ocr_confidence_min,
                "ocr_confidence_mean": item.ocr_confidence_mean,
                "extractor_method": item.extractor_method,
            }
            for item in observations
        }

        expected_keys = set(expected_map)
        predicted_keys = set(predicted_map)
        tp_keys = expected_keys & predicted_keys
        fp_keys = predicted_keys - expected_keys
        fn_keys = expected_keys - predicted_keys

        overall_tp += len(tp_keys)
        overall_fp += len(fp_keys)
        overall_fn += len(fn_keys)

        for declaration_type in SUPPORTED_DECLARATION_TYPES:
            prefix = declaration_type.value + ":"
            expected_type = {key for key in expected_keys if key.startswith(prefix)}
            predicted_type = {key for key in predicted_keys if key.startswith(prefix)}
            counts = type_counts[declaration_type]
            counts["tp"] += len(expected_type & predicted_type)
            counts["fp"] += len(predicted_type - expected_type)
            counts["fn"] += len(expected_type - predicted_type)

        case_results.append(
            {
                "case_id": case.case_id,
                "dataset_type": case.dataset_type,
                "block_source": case.block_source,
                "notes": case.notes,
                "exact_match": expected_keys == predicted_keys,
                "expected": [
                    expected_map[key]
                    for key in sorted(expected_map)
                ],
                "predicted": [
                    predicted_map[key]
                    for key in sorted(predicted_map)
                ],
                "false_positives": [
                    predicted_map[key]
                    for key in sorted(fp_keys)
                ],
                "false_negatives": [
                    expected_map[key]
                    for key in sorted(fn_keys)
                ],
            }
        )

    dataset_counts = {
        dataset_type: sum(
            1 for case in case_results
            if case["dataset_type"] == dataset_type
        )
        for dataset_type in sorted(_ALLOWED_DATASET_TYPES)
    }
    block_source_counts = {
        source: sum(
            1 for case in case_results
            if case["block_source"] == source
        )
        for source in sorted(_ALLOWED_BLOCK_SOURCES)
    }

    real_actual = [
        case
        for case in case_results
        if case["dataset_type"] == "real_package"
        and case["block_source"] == "actual_ocr"
    ]
    real_exact_count = sum(1 for case in real_actual if case["exact_match"])

    warnings: list[str] = []
    if not real_actual:
        warnings.append("no_real_package_actual_ocr_cases")

    return {
        "manifest": str(path.expanduser().resolve()),
        "extractor_version": DECLARATION_EXTRACTOR_VERSION,
        "case_count": len(case_results),
        "dataset_counts": dataset_counts,
        "block_source_counts": block_source_counts,
        "real_package_actual_ocr_case_count": len(real_actual),
        "real_package_actual_ocr_exact_match_count": real_exact_count,
        "real_package_actual_ocr_exact_match_rate": (
            round(real_exact_count / len(real_actual), 6)
            if real_actual
            else None
        ),
        "overall": _metric_summary(overall_tp, overall_fp, overall_fn),
        "by_type": {
            declaration_type.value: _metric_summary(
                type_counts[declaration_type]["tp"],
                type_counts[declaration_type]["fp"],
                type_counts[declaration_type]["fn"],
            )
            for declaration_type in SUPPORTED_DECLARATION_TYPES
        },
        "warnings": warnings,
        "cases": case_results,
    }


def declaration_gate_failures(
    report: dict,
    *,
    require_real_actual_ocr: int = 0,
    min_real_exact_match_rate: float | None = None,
    min_overall_precision: float | None = None,
    min_overall_recall: float | None = None,
) -> list[str]:
    failures: list[str] = []
    real_count = int(report["real_package_actual_ocr_case_count"])

    if real_count < require_real_actual_ocr:
        failures.append(
            f"real_actual_ocr_count:{real_count}<{require_real_actual_ocr}"
        )

    real_exact = report["real_package_actual_ocr_exact_match_rate"]
    if min_real_exact_match_rate is not None:
        if real_exact is None:
            failures.append("real_exact_match_rate:unavailable")
        elif real_exact < min_real_exact_match_rate:
            failures.append(
                f"real_exact_match_rate:{real_exact}<{min_real_exact_match_rate}"
            )

    precision = report["overall"]["precision"]
    if min_overall_precision is not None:
        if precision is None:
            failures.append("overall_precision:unavailable")
        elif precision < min_overall_precision:
            failures.append(
                f"overall_precision:{precision}<{min_overall_precision}"
            )

    recall = report["overall"]["recall"]
    if min_overall_recall is not None:
        if recall is None:
            failures.append("overall_recall:unavailable")
        elif recall < min_overall_recall:
            failures.append(
                f"overall_recall:{recall}<{min_overall_recall}"
            )

    return failures
