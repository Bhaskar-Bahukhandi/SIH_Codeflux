# Phase 3 OCR Evaluation

This dataset format evaluates OCR text fidelity separately from later declaration extraction and Legal Metrology rules.

## Local layout

Keep real package images and raw ground-truth transcriptions outside Git unless the team intentionally approves a sanitized dataset:

```text
evaluation/phase3/
  manifest.csv
  images/
    package-001.jpg
  ground_truth/
    package-001.txt
```

## Manifest

Columns:

| Column | Required | Meaning |
| --- | --- | --- |
| `case_id` | yes | Stable unique ID |
| `image_path` | yes | Image path relative to the manifest |
| `dataset_type` | yes | `real_package`, `synthetic`, or `other` |
| `ground_truth_path` | no | UTF-8 human transcription relative to the manifest |
| `notes` | yes, may be blank | Capture/context notes |

## Metric policy

CER and WER are calculated only for cases with ground truth.

Before comparison:

- Unicode is normalized to NFC;
- whitespace runs are collapsed to one space;
- case is preserved;
- punctuation is preserved.

The report may therefore show CER/WER greater than 1.0 when insertions exceed the reference length. This is valid edit-distance behavior and must not be clamped.

## Pipeline used by the harness

Each image goes through:

1. EXIF-aware normalization;
2. the same conservative perspective analysis used by the application;
3. perspective-corrected image when the correction gate passes, otherwise normalized fallback;
4. configured OCR engine.

The report stores which source type was actually used.

Quality status is recorded for context but is not a hard OCR gate and is not a legal result.

## Run

From `services/api` after installing/configuring the OCR runtime:

```bash
python -m app.cli.validate_ocr \
  --manifest ../../evaluation/phase3/manifest.csv \
  --output ../../evaluation/reports/phase3-ocr.json
```

Optional evidence gates can be selected for a validation run:

```bash
python -m app.cli.validate_ocr \
  --manifest ../../evaluation/phase3/manifest.csv \
  --output ../../evaluation/reports/phase3-ocr.json \
  --require-real-package 20 \
  --require-labeled-real 20 \
  --max-real-cer 0.20 \
  --max-real-wer 0.35
```

Those values are examples, not project claims or frozen acceptance thresholds.

## Interpretation

- Unit tests with fake OCR engines prove orchestration and metric logic only.
- Synthetic images are regression evidence only.
- Unlabeled real images cannot support a CER/WER claim.
- Real-package OCR validation remains pending until the team runs this harness on representative package photographs and reviews the report.
