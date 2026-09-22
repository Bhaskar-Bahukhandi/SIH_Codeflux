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
    assert report["overall"]["f1"] is None
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
    )

    assert "real_actual_ocr_count:0<1" in failures
    assert "real_exact_match_rate:unavailable" in failures


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
