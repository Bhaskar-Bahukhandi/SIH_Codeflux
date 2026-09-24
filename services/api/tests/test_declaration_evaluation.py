import hashlib
import json

from app.evaluation.declarations import (
    declaration_gate_failures,
    evaluate_declaration_manifest,
)


def write_manifest(tmp_path, cases):
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps({"cases": cases}),
        encoding="utf-8",
    )
    return path


def test_evaluation_reports_exact_matches_and_real_actual_ocr_count(tmp_path):
    manifest = write_manifest(
        tmp_path,
        [
            {
                "case_id": "real-1",
                "dataset_type": "real_package",
                "block_source": "actual_ocr",
                "ocr_blocks": [
                    {
                        "block_id": "b0",
                        "text": "MRP Rs. 50.00",
                        "confidence": 0.94,
                    },
                    {
                        "block_id": "b1",
                        "text": "Net Qty 100 g",
                        "confidence": 0.90,
                    },
                ],
                "expected_declarations": [
                    {
                        "declaration_type": "mrp",
                        "normalized_value": {
                            "currency": "INR",
                            "amount": "50.00",
                        },
                    },
                    {
                        "declaration_type": "net_quantity",
                        "normalized_value": {
                            "value": "100",
                            "unit": "g",
                        },
                    },
                ],
                "notes": "",
            }
        ],
    )

    report = evaluate_declaration_manifest(manifest)

    assert report["real_package_actual_ocr_case_count"] == 1
    assert report["real_package_actual_ocr_exact_match_rate"] == 1.0
    assert report["real_package_actual_ocr_metrics"]["precision"] == 1.0
    assert report["real_package_actual_ocr_metrics"]["recall"] == 1.0
    assert report["overall"] == {
        "true_positive": 2,
        "false_positive": 0,
        "false_negative": 0,
        "precision": 1.0,
        "recall": 1.0,
        "f1": 1.0,
    }
    assert report["warnings"] == []
    assert report["cases"][0]["exact_match"] is True


def test_false_positive_and_false_negative_are_kept_visible(tmp_path):
    manifest = write_manifest(
        tmp_path,
        [
            {
                "case_id": "synthetic-1",
                "dataset_type": "synthetic",
                "block_source": "synthetic",
                "ocr_blocks": [
                    {
                        "text": "MRP Rs. 50.00",
                        "confidence": 0.95,
                    }
                ],
                "expected_declarations": [
                    {
                        "declaration_type": "net_quantity",
                        "normalized_value": {
                            "value": "100",
                            "unit": "g",
                        },
                    }
                ],
                "notes": "",
            }
        ],
    )

    report = evaluate_declaration_manifest(manifest)

    assert report["overall"]["true_positive"] == 0
    assert report["overall"]["false_positive"] == 1
    assert report["overall"]["false_negative"] == 1
    assert report["overall"]["precision"] == 0.0
    assert report["overall"]["recall"] == 0.0
    assert report["overall"]["f1"] == 0.0
    assert len(report["cases"][0]["false_positives"]) == 1
    assert len(report["cases"][0]["false_negatives"]) == 1
    assert "no_real_package_actual_ocr_cases" in report["warnings"]


def test_human_transcription_real_case_does_not_count_as_actual_ocr(tmp_path):
    manifest = write_manifest(
        tmp_path,
        [
            {
                "case_id": "real-manual-1",
                "dataset_type": "real_package",
                "block_source": "human_transcription",
                "ocr_blocks": [],
                "expected_declarations": [],
                "notes": "",
            }
        ],
    )

    report = evaluate_declaration_manifest(manifest)

    assert report["dataset_counts"]["real_package"] == 1
    assert report["real_package_actual_ocr_case_count"] == 0
    assert report["real_package_actual_ocr_exact_match_rate"] is None


def test_evidence_gate_fails_without_real_actual_ocr_cases(tmp_path):
    manifest = write_manifest(
        tmp_path,
        [
            {
                "case_id": "synthetic-1",
                "dataset_type": "synthetic",
                "block_source": "synthetic",
                "ocr_blocks": [],
                "expected_declarations": [],
                "notes": "",
            }
        ],
    )

    report = evaluate_declaration_manifest(manifest)
    failures = declaration_gate_failures(
        report,
        require_real_actual_ocr=1,
        min_real_exact_match_rate=0.8,
        min_real_precision=0.9,
        min_real_recall=0.9,
    )

    assert "real_actual_ocr_count:0<1" in failures
    assert "real_exact_match_rate:unavailable" in failures
    assert "real_precision:unavailable" in failures
    assert "real_recall:unavailable" in failures


def test_manifest_rejects_out_of_range_ocr_score(tmp_path):
    manifest = write_manifest(
        tmp_path,
        [
            {
                "case_id": "bad-score",
                "dataset_type": "synthetic",
                "block_source": "synthetic",
                "ocr_blocks": [
                    {
                        "text": "MRP Rs. 50",
                        "confidence": 1.5,
                    }
                ],
                "expected_declarations": [],
                "notes": "",
            }
        ],
    )

    try:
        evaluate_declaration_manifest(manifest)
    except ValueError as exc:
        assert "between 0 and 1" in str(exc)
    else:
        raise AssertionError("Expected invalid OCR confidence to be rejected.")


def test_unlabeled_web_reference_is_observed_without_affecting_metrics(tmp_path):
    manifest = write_manifest(
        tmp_path,
        [
            {
                "case_id": "web-1",
                "dataset_type": "web_reference",
                "block_source": "actual_ocr",
                "ocr_blocks": [
                    {
                        "block_id": "b0",
                        "text": "NET QUANTITY: 200 g",
                        "confidence": 0.96,
                    }
                ],
                "expected_declarations": None,
                "source_page_url": "https://example.com/products/package",
                "notes": "Official package reference.",
            }
        ],
    )

    report = evaluate_declaration_manifest(manifest)

    assert report["manifest"] == "manifest.json"
    assert report["manifest_sha256"] == hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert report["input_provenance_version"] == "declaration-input-sha256-v1"
    assert report["dataset_counts"]["web_reference"] == 1
    assert report["dataset_counts"]["real_package"] == 0
    assert report["labeled_case_count"] == 0
    assert report["unlabeled_case_count"] == 1
    assert report["web_reference_actual_ocr_case_count"] == 1
    assert report["web_reference_actual_ocr_labeled_count"] == 0
    assert report["web_reference_source_domains"] == ["example.com"]
    assert report["web_reference_actual_ocr_predicted_declaration_count"] == 1

    case = report["cases"][0]
    assert case["labeled"] is False
    assert case["exact_match"] is None
    assert case["expected"] is None
    assert len(case["predicted"]) == 1
    assert case["false_positives"] == []
    assert case["false_negatives"] == []

    assert report["overall"] == {
        "true_positive": 0,
        "false_positive": 0,
        "false_negative": 0,
        "precision": None,
        "recall": None,
        "f1": None,
    }
    assert declaration_gate_failures(report, require_real_actual_ocr=1) == [
        "real_actual_ocr_count:0<1"
    ]


def test_empty_expected_declarations_remains_a_labeled_negative_case(tmp_path):
    manifest = write_manifest(
        tmp_path,
        [
            {
                "case_id": "negative-1",
                "dataset_type": "synthetic",
                "block_source": "synthetic",
                "ocr_blocks": [
                    {
                        "text": "MRP Rs. 50.00",
                        "confidence": 0.95,
                    }
                ],
                "expected_declarations": [],
                "notes": "Explicit labeled negative.",
            }
        ],
    )

    report = evaluate_declaration_manifest(manifest)

    assert report["labeled_case_count"] == 1
    assert report["unlabeled_case_count"] == 0
    assert report["cases"][0]["labeled"] is True
    assert report["cases"][0]["exact_match"] is False
    assert len(report["cases"][0]["false_positives"]) == 1
    assert report["overall"]["false_positive"] == 1


def test_web_reference_requires_source_page_url(tmp_path):
    manifest = write_manifest(
        tmp_path,
        [
            {
                "case_id": "web-missing-source",
                "dataset_type": "web_reference",
                "block_source": "actual_ocr",
                "ocr_blocks": [],
                "expected_declarations": None,
                "notes": "",
            }
        ],
    )

    try:
        evaluate_declaration_manifest(manifest)
    except ValueError as exc:
        assert "source_page_url is required" in str(exc)
    else:
        raise AssertionError("Expected missing web-reference source URL to fail.")


def test_missing_expected_declarations_must_be_explicitly_null_when_unlabeled(tmp_path):
    manifest = write_manifest(
        tmp_path,
        [
            {
                "case_id": "missing-label-state",
                "dataset_type": "synthetic",
                "block_source": "synthetic",
                "ocr_blocks": [],
                "notes": "",
            }
        ],
    )

    try:
        evaluate_declaration_manifest(manifest)
    except ValueError as exc:
        assert "expected_declarations is required" in str(exc)
    else:
        raise AssertionError("Expected missing label state to fail.")
