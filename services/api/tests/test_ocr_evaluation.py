import hashlib
from io import BytesIO
from pathlib import Path

from PIL import Image

from app.core.config import Settings
from app.evaluation.ocr import (
    character_error_rate,
    evaluate_ocr_manifest,
    normalize_metric_text,
    ocr_gate_failures,
    word_error_rate,
)
from app.services.ocr_engine import OcrDetection


class FakeEvaluationEngine:
    name = "fake-eval"
    version = "1"
    model_version = "fixture"
    language = "en"
    parameters = {"mode": "test"}

    def extract(self, _image_bytes):
        return [
            OcrDetection(
                text="MRP Rs. 50",
                confidence=0.95,
                polygon=[[0, 0], [80, 0], [80, 15], [0, 15]],
            ),
            OcrDetection(
                text="Net Qty 100 g",
                confidence=0.90,
                polygon=[[0, 20], [100, 20], [100, 35], [0, 35]],
            ),
        ]


def image_file(path: Path) -> None:
    buffer = BytesIO()
    Image.new("RGB", (320, 240), (120, 120, 120)).save(
        buffer,
        format="JPEG",
        quality=95,
    )
    path.write_bytes(buffer.getvalue())


def write_manifest(path: Path, rows: list[str]) -> None:
    path.write_text(
        "case_id,image_path,dataset_type,ground_truth_path,notes,source_page_url\n"
        + "\n".join(rows)
        + "\n",
        encoding="utf-8",
    )


def test_metric_normalization_preserves_case_and_punctuation():
    assert normalize_metric_text("MRP\n  Rs. 50") == "MRP Rs. 50"
    assert normalize_metric_text("MRP") != normalize_metric_text("mrp")
    assert normalize_metric_text("Rs. 50") != normalize_metric_text("Rs 50")


def test_cer_and_wer_are_zero_for_equivalent_whitespace():
    reference = "MRP Rs. 50\nNet Qty 100 g"
    prediction = "MRP   Rs. 50 Net Qty 100 g"

    assert character_error_rate(reference, prediction) == 0.0
    assert word_error_rate(reference, prediction) == 0.0


def test_ocr_evaluation_separates_real_and_synthetic_and_reports_metrics(tmp_path):
    real_image = tmp_path / "real.jpg"
    synthetic_image = tmp_path / "synthetic.jpg"
    image_file(real_image)
    image_file(synthetic_image)

    real_truth = tmp_path / "real.txt"
    real_truth.write_text("MRP Rs. 50\nNet Qty 100 g", encoding="utf-8")

    manifest = tmp_path / "manifest.csv"
    write_manifest(
        manifest,
        [
            "real-1,real.jpg,real_package,real.txt,real package fixture,",
            "synthetic-1,synthetic.jpg,synthetic,,unlabeled regression fixture,",
        ],
    )

    report = evaluate_ocr_manifest(
        manifest,
        settings=Settings(_env_file=None, app_env="test"),
        engine=FakeEvaluationEngine(),
    )

    assert report["case_count"] == 2
    assert report["dataset_counts"] == {
        "other": 0,
        "real_package": 1,
        "synthetic": 1,
        "web_reference": 0,
    }
    assert report["manifest"] == "manifest.csv"
    assert report["manifest_sha256"] == hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert report["input_provenance_version"] == "ocr-input-sha256-v1"
    assert report["real_package_labeled_count"] == 1
    assert report["real_package_mean_character_error_rate"] == 0.0
    assert report["real_package_mean_word_error_rate"] == 0.0
    assert report["warnings"] == []

    real_case = report["cases"][0]
    assert real_case["image_path"] == "real.jpg"
    assert real_case["image_sha256"] == hashlib.sha256(real_image.read_bytes()).hexdigest()
    assert real_case["ground_truth_path"] == "real.txt"
    assert real_case["ground_truth_sha256"] == hashlib.sha256(real_truth.read_bytes()).hexdigest()
    assert str(tmp_path) not in real_case["image_path"]
    assert real_case["ocr_source_type"] == "normalized"
    assert real_case["recognized_text"] == "MRP Rs. 50\nNet Qty 100 g"
    assert len(real_case["blocks"]) == 2


def test_unlabeled_real_case_does_not_invent_ocr_accuracy(tmp_path):
    image = tmp_path / "real.jpg"
    image_file(image)
    manifest = tmp_path / "manifest.csv"
    write_manifest(
        manifest,
        ["real-1,real.jpg,real_package,,no transcription yet,"],
    )

    report = evaluate_ocr_manifest(
        manifest,
        settings=Settings(_env_file=None, app_env="test"),
        engine=FakeEvaluationEngine(),
    )

    assert report["real_package_labeled_count"] == 0
    assert report["real_package_mean_character_error_rate"] is None
    assert report["real_package_mean_word_error_rate"] is None
    assert "no_labeled_real_package_cases" in report["warnings"]
    assert report["cases"][0]["character_error_rate"] is None
    assert report["cases"][0]["word_error_rate"] is None


def test_ocr_gates_fail_when_required_real_evidence_is_missing(tmp_path):
    image = tmp_path / "synthetic.jpg"
    image_file(image)
    manifest = tmp_path / "manifest.csv"
    write_manifest(
        manifest,
        ["synthetic-1,synthetic.jpg,synthetic,,synthetic only,"],
    )

    report = evaluate_ocr_manifest(
        manifest,
        settings=Settings(_env_file=None, app_env="test"),
        engine=FakeEvaluationEngine(),
    )
    failures = ocr_gate_failures(
        report,
        require_real_package=1,
        require_labeled_real=1,
        require_scored_real=1,
        max_real_cer=0.2,
        max_real_wer=0.3,
    )

    assert "real_package_count:0<1" in failures
    assert "labeled_real_package_count:0<1" in failures
    assert "scored_real_package_count:0<1" in failures
    assert "real_package_cer:unavailable" in failures
    assert "real_package_wer:unavailable" in failures


class FailingEvaluationEngine(FakeEvaluationEngine):
    def extract(self, _image_bytes):
        from app.services.ocr_engine import OcrInferenceFailed

        raise OcrInferenceFailed("synthetic inference failure")


def test_ocr_evaluation_records_inference_failure_instead_of_aborting(tmp_path):
    image = tmp_path / "real.jpg"
    image_file(image)
    truth = tmp_path / "real.txt"
    truth.write_text("MRP Rs. 50", encoding="utf-8")
    manifest = tmp_path / "manifest.csv"
    write_manifest(
        manifest,
        ["real-1,real.jpg,real_package,real.txt,engine failure fixture,"],
    )

    report = evaluate_ocr_manifest(
        manifest,
        settings=Settings(_env_file=None, app_env="test"),
        engine=FailingEvaluationEngine(),
    )

    assert report["failed_case_count"] == 1
    assert report["successful_case_count"] == 0
    assert report["real_package_labeled_count"] == 1
    assert report["real_package_scored_count"] == 0
    assert report["real_package_mean_character_error_rate"] is None
    assert report["cases"][0]["status"] == "ocr_error"
    assert report["cases"][0]["error_code"] == "ocr_inference_failed"
    assert "one_or_more_cases_failed" in report["warnings"]
    assert "no_scored_real_package_cases" in report["warnings"]


def test_web_reference_is_provenanced_and_excluded_from_real_ocr_gates(tmp_path):
    image = tmp_path / "official-pack.jpg"
    image_file(image)
    manifest = tmp_path / "manifest.csv"
    write_manifest(
        manifest,
        [
            (
                "web-1,official-pack.jpg,web_reference,,official product reference,"
                "https://example.com/products/official-pack"
            )
        ],
    )

    report = evaluate_ocr_manifest(
        manifest,
        settings=Settings(_env_file=None, app_env="test"),
        engine=FakeEvaluationEngine(),
    )

    assert report["dataset_counts"]["web_reference"] == 1
    assert report["dataset_counts"]["real_package"] == 0
    assert report["web_reference_count"] == 1
    assert report["web_reference_labeled_count"] == 0
    assert report["web_reference_scored_count"] == 0
    assert report["web_reference_source_domains"] == ["example.com"]
    assert report["cases"][0]["source_page_url"] == (
        "https://example.com/products/official-pack"
    )
    assert report["cases"][0]["source_domain"] == "example.com"
    assert report["cases"][0]["image_sha256"] == hashlib.sha256(image.read_bytes()).hexdigest()

    failures = ocr_gate_failures(report, require_real_package=1)
    assert "real_package_count:0<1" in failures


def test_web_reference_requires_absolute_source_page_url(tmp_path):
    image = tmp_path / "official-pack.jpg"
    image_file(image)
    missing = tmp_path / "missing-source.csv"
    write_manifest(
        missing,
        ["web-1,official-pack.jpg,web_reference,,missing source,"],
    )

    from app.evaluation.ocr import load_ocr_manifest

    try:
        load_ocr_manifest(missing)
    except ValueError as exc:
        assert "source_page_url is required" in str(exc)
    else:
        raise AssertionError("Expected missing web-reference source URL to fail.")

    invalid = tmp_path / "invalid-source.csv"
    write_manifest(
        invalid,
        ["web-1,official-pack.jpg,web_reference,,invalid source,not-a-url"],
    )
    try:
        load_ocr_manifest(invalid)
    except ValueError as exc:
        assert "absolute http(s) URL" in str(exc)
    else:
        raise AssertionError("Expected invalid web-reference source URL to fail.")
