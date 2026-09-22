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

CER and WER are calculated only for cases that both have ground truth and complete OCR successfully.

Before comparison:

- Unicode is normalized to NFC;
- whitespace runs are collapsed to one space;
- case is preserved;
- punctuation is preserved.

CER/WER can exceed 1.0 when insertions exceed the reference length. The harness does not clamp them.

## Pipeline used by the harness

Each image goes through:

1. EXIF-aware normalization;
2. the same image-quality assessment used by the application, recorded for context only;
3. the same conservative perspective analysis used by the application;
4. perspective-corrected image when the correction gate passes, otherwise normalized fallback;
5. the configured OCR engine.

The report records which source type was actually used.

A quality status such as `retake_recommended` does not block OCR in the evaluation harness and is not a legal result.

## Per-case failure behavior

An unreadable image or OCR inference failure is recorded as a failed case rather than silently disappearing from the report.

The report distinguishes:

- labeled cases: ground truth exists;
- scored cases: ground truth exists and OCR completed;
- failed cases: image preparation or OCR inference did not complete.

This prevents a dataset from appearing stronger by excluding difficult failures from the denominator.

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
  --require-scored-real 20 \
  --max-real-cer 0.20 \
  --max-real-wer 0.35
```

Those values are examples, not project claims or frozen acceptance thresholds.

## Interpretation

- Unit tests with fake OCR engines prove orchestration and metric logic only.
- Synthetic images are regression evidence only.
- Unlabeled real images cannot support a CER/WER claim.
- Labeled images that fail OCR are reported as failures, not scored as if they succeeded.
- Real-package OCR validation remains pending until the team runs this harness on representative package photographs and reviews the report.
