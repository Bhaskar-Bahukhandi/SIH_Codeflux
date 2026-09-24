import csv
import hashlib
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from app.core.config import Settings
from app.evaluation.phase2 import (
    evaluate_phase2_manifest,
    load_phase2_manifest,
    phase2_gate_failures,
)


def blank_jpeg(path: Path) -> None:
    buffer = BytesIO()
    Image.new("RGB", (320, 240), (120, 120, 120)).save(
        buffer,
        format="JPEG",
        quality=95,
    )
    path.write_bytes(buffer.getvalue())


def write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "case_id",
        "image_path",
        "dataset_type",
        "expected_quality_status",
        "expected_geometry_status",
        "source_page_url",
        "notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_evaluation_keeps_real_and_synthetic_evidence_separate(tmp_path):
    real_image = tmp_path / "real.jpg"
    synthetic_image = tmp_path / "synthetic.jpg"
    blank_jpeg(real_image)
    blank_jpeg(synthetic_image)

    manifest = tmp_path / "manifest.csv"
    write_manifest(
        manifest,
        [
            {
                "case_id": "real-1",
                "image_path": real_image.name,
                "dataset_type": "real_package",
                "expected_quality_status": "retake_recommended",
                "expected_geometry_status": "not_detected",
                "notes": "Human-labeled real-package placeholder fixture.",
            },
            {
                "case_id": "synthetic-1",
                "image_path": synthetic_image.name,
                "dataset_type": "synthetic",
                "expected_quality_status": "retake_recommended",
                "expected_geometry_status": "not_detected",
                "notes": "Synthetic regression fixture.",
            },
        ],
    )

    report = evaluate_phase2_manifest(
        manifest,
        settings=Settings(_env_file=None, app_env="test"),
    )

    assert report["case_count"] == 2
    assert report["manifest"] == "manifest.csv"
    assert report["manifest_sha256"] == hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert report["input_provenance_version"] == "phase2-input-sha256-v1"
    assert report["cases"][0]["image_path"] == "real.jpg"
    assert report["cases"][0]["image_sha256"] == hashlib.sha256(real_image.read_bytes()).hexdigest()
    assert str(tmp_path) not in report["cases"][0]["image_path"]
    assert report["dataset_counts"] == {
        "other": 0,
        "real_package": 1,
        "synthetic": 1,
    }
    assert report["real_package_labeled_quality_count"] == 1
    assert report["real_package_labeled_geometry_count"] == 1
    assert report["quality_status_agreement"]["agreement_rate"] == 1.0
    assert report["geometry_status_agreement"]["agreement_rate"] == 1.0
    assert report["warnings"] == []


def test_unlabeled_dataset_does_not_invent_agreement(tmp_path):
    image = tmp_path / "package.jpg"
    blank_jpeg(image)
    manifest = tmp_path / "manifest.csv"
    write_manifest(
        manifest,
        [
            {
                "case_id": "case-1",
                "image_path": image.name,
                "dataset_type": "other",
                "expected_quality_status": "",
                "expected_geometry_status": "",
                "notes": "",
            }
        ],
    )

    report = evaluate_phase2_manifest(
        manifest,
        settings=Settings(_env_file=None, app_env="test"),
    )

    assert report["quality_status_agreement"]["labeled_count"] == 0
    assert report["quality_status_agreement"]["agreement_rate"] is None
    assert report["geometry_status_agreement"]["labeled_count"] == 0
    assert report["geometry_status_agreement"]["agreement_rate"] is None
    assert "no_real_package_cases" in report["warnings"]


def test_manifest_rejects_invalid_expected_status(tmp_path):
    image = tmp_path / "package.jpg"
    blank_jpeg(image)
    manifest = tmp_path / "manifest.csv"
    write_manifest(
        manifest,
        [
            {
                "case_id": "case-1",
                "image_path": image.name,
                "dataset_type": "synthetic",
                "expected_quality_status": "perfect",
                "expected_geometry_status": "",
                "notes": "",
            }
        ],
    )

    with pytest.raises(ValueError, match="expected_quality_status"):
        load_phase2_manifest(manifest)


def test_evaluation_fails_when_manifest_image_is_missing(tmp_path):
    manifest = tmp_path / "manifest.csv"
    write_manifest(
        manifest,
        [
            {
                "case_id": "case-1",
                "image_path": "missing.jpg",
                "dataset_type": "real_package",
                "expected_quality_status": "",
                "expected_geometry_status": "",
                "notes": "",
            }
        ],
    )

    with pytest.raises(FileNotFoundError, match="case-1"):
        evaluate_phase2_manifest(
            manifest,
            settings=Settings(_env_file=None, app_env="test"),
        )


def test_validation_gates_fail_without_required_real_evidence(tmp_path):
    image = tmp_path / "synthetic.jpg"
    blank_jpeg(image)
    manifest = tmp_path / "manifest.csv"
    write_manifest(
        manifest,
        [
            {
                "case_id": "synthetic-1",
                "image_path": image.name,
                "dataset_type": "synthetic",
                "expected_quality_status": "retake_recommended",
                "expected_geometry_status": "not_detected",
                "notes": "",
            }
        ],
    )

    report = evaluate_phase2_manifest(
        manifest,
        settings=Settings(_env_file=None, app_env="test"),
    )
    failures = phase2_gate_failures(
        report,
        require_real_package=1,
        require_labeled_real_quality=1,
        require_labeled_real_geometry=1,
        fail_on_mismatch=True,
    )

    assert "real_package_count:0<1" in failures
    assert "labeled_real_quality_count:0<1" in failures
    assert "labeled_real_geometry_count:0<1" in failures
    assert all(not item.startswith("status_mismatches:") for item in failures)


def test_web_reference_requires_source_page_and_stays_out_of_real_gate(tmp_path):
    image = tmp_path / "official-pack.jpg"
    blank_jpeg(image)
    manifest = tmp_path / "manifest.csv"
    write_manifest(
        manifest,
        [
            {
                "case_id": "web-1",
                "image_path": image.name,
                "dataset_type": "web_reference",
                "expected_quality_status": "",
                "expected_geometry_status": "",
                "source_page_url": "https://example.com/products/official-pack",
                "notes": "Official product-page reference image.",
            }
        ],
    )

    report = evaluate_phase2_manifest(
        manifest,
        settings=Settings(_env_file=None, app_env="test"),
    )

    assert report["dataset_counts"]["web_reference"] == 1
    assert report["dataset_counts"]["real_package"] == 0
    assert report["web_reference_count"] == 1
    assert report["web_reference_source_domains"] == ["example.com"]
    assert report["cases"][0]["source_page_url"] == (
        "https://example.com/products/official-pack"
    )
    assert report["cases"][0]["source_domain"] == "example.com"

    failures = phase2_gate_failures(report, require_real_package=1)
    assert "real_package_count:0<1" in failures


def test_web_reference_without_source_page_is_rejected(tmp_path):
    image = tmp_path / "official-pack.jpg"
    blank_jpeg(image)
    manifest = tmp_path / "manifest.csv"
    write_manifest(
        manifest,
        [
            {
                "case_id": "web-1",
                "image_path": image.name,
                "dataset_type": "web_reference",
                "expected_quality_status": "",
                "expected_geometry_status": "",
                "source_page_url": "",
                "notes": "",
            }
        ],
    )

    with pytest.raises(ValueError, match="source_page_url is required"):
        load_phase2_manifest(manifest)


def test_invalid_source_page_url_is_rejected(tmp_path):
    image = tmp_path / "official-pack.jpg"
    blank_jpeg(image)
    manifest = tmp_path / "manifest.csv"
    write_manifest(
        manifest,
        [
            {
                "case_id": "web-1",
                "image_path": image.name,
                "dataset_type": "web_reference",
                "expected_quality_status": "",
                "expected_geometry_status": "",
                "source_page_url": "not-a-url",
                "notes": "",
            }
        ],
    )

    with pytest.raises(ValueError, match=r"absolute http\(s\) URL"):
        load_phase2_manifest(manifest)
