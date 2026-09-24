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
| `dataset_type` | yes | `real_package`, `web_reference`, `synthetic`, or `other` |
| `ground_truth_path` | no | UTF-8 human transcription relative to the manifest |
| `source_page_url` | required for `web_reference` | Public source page for the official/reference package image |
| `notes` | yes, may be blank | Capture/context notes |

## Dataset classes

- `real_package`: a camera photograph of a physical retail package. It may be locally collected or an openly licensed public camera photograph when source provenance is retained. Only this class contributes to real-package OCR case counts; CER/WER still require reviewed ground truth.
- `web_reference`: a public manufacturer/product reference image with a recorded source page. Useful for testing OCR execution and packaging diversity, but it does not count as field-camera evidence.
- `synthetic`: generated or constructed regression fixture.
- `other`: evidence outside the above classes.

Web-reference cases are reported separately so their observations cannot silently improve the real-package CER/WER metrics.

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

The report also records SHA-256 provenance for the manifest, image bytes and any ground-truth transcription, plus manifest-relative paths rather than developer-specific absolute paths.

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
- Web-reference images are observation/reference evidence only and never satisfy the real-package OCR gate.
- Unlabeled real images cannot support a CER/WER claim.
- The public-physical OCR workflow executes PP-OCRv5 on openly licensed camera photographs of physical packages. A successful run demonstrates real-package runtime robustness only; it cannot produce CER/WER until reviewed transcriptions are supplied.
- Public physical-package photographs do not prove capture through the CODEFLUX mobile app.
- Labeled images that fail OCR are reported as failures, not scored as if they succeeded.
- Real-package OCR validation remains pending until the team runs this harness on representative package photographs and reviews the report.
- Unlabeled web-reference OCR output can demonstrate engine execution/robustness, but it cannot produce CER/WER accuracy claims.


## Validated CPU observation runtime

A reproducible web-reference observation on the CI Linux CPU runner currently uses:

- `paddleocr==3.7.0`;
- `paddlepaddle==3.2.2`;
- `OCR_MODEL_VERSION=PP-OCRv5`;
- `OCR_DEVICE=cpu`;
- `OCR_ENABLE_MKLDNN=false`.

The MKLDNN/oneDNN path is disabled for this baseline because PaddlePaddle 3.3.x CPU inference exposed an upstream PIR/oneDNN conversion regression during validation. Re-enable it only after a dedicated runtime validation proves the configured PaddlePaddle/OCR combination works.

The first successful official-package observation executed 12/12 web-reference cases with no OCR inference failures and returned 145 OCR text blocks in total. Because those 12 cases intentionally have no human ground-truth transcriptions, the run proves runtime execution only; it does not establish CER/WER accuracy.
