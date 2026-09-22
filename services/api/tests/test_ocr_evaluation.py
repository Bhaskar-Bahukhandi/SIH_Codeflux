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
        "case_id,image_path,dataset_type,ground_truth_path,notes\n"
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
            "real-1,real.jpg,real_package,real.txt,real package fixture",
            "synthetic-1,synthetic.jpg,synthetic,,unlabeled regression fixture",
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
    }
    assert report["real_package_labeled_count"] == 1
    assert report["real_package_mean_character_error_rate"] == 0.0
    assert report["real_package_mean_word_error_rate"] == 0.0
    assert report["warnings"] == []

    real_case = report["cases"][0]
    assert real_case["ocr_source_type"] == "normalized"
    assert real_case["recognized_text"] == "MRP Rs. 50\nNet Qty 100 g"
    assert len(real_case["blocks"]) == 2


def test_unlabeled_real_case_does_not_invent_ocr_accuracy(tmp_path):
    image = tmp_path / "real.jpg"
    image_file(image)
    manifest = tmp_path / "manifest.csv"
    write_manifest(
        manifest,
        ["real-1,real.jpg,real_package,,no transcription yet"],
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
        ["synthetic-1,synthetic.jpg,synthetic,,synthetic only"],
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
        max_real_cer=0.2,
        max_real_wer=0.3,
    )

    assert "real_package_count:0<1" in failures
    assert "labeled_real_package_count:0<1" in failures
    assert "real_package_cer:unavailable" in failures
    assert "real_package_wer:unavailable" in failures
