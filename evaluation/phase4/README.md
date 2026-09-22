# Phase 4 Declaration Extraction Evaluation

This harness measures deterministic declaration extraction **given OCR text blocks**.

It is separate from OCR accuracy and separate from Legal Metrology compliance accuracy.

## Case format

A local JSON manifest contains a top-level `cases` list.

Each case records:

- `case_id`;
- `dataset_type`: `real_package`, `synthetic`, or `other`;
- `block_source`: `actual_ocr`, `human_transcription`, or `synthetic`;
- ordered OCR blocks with text and recognition score;
- expected structured declarations;
- notes.

An empty `expected_declarations` list is a valid labeled negative case.

## Why block-source provenance matters

A real package with manually typed text is useful for extractor testing, but it does not show how the extractor behaves on OCR mistakes.

Therefore only:

> `dataset_type = real_package` + `block_source = actual_ocr`

counts toward the report's real end-to-end extraction evidence.

## Metrics

The harness compares exact normalized declaration values and reports:

- true positives;
- false positives;
- false negatives;
- precision;
- recall;
- F1;
- exact case match;
- per-declaration-type metrics;
- real-package actual-OCR exact-match rate.

When a denominator does not exist, a metric is `null` rather than an invented perfect score.

## Run

From `services/api`:

```bash
python -m app.cli.validate_declarations \
  --manifest ../../evaluation/phase4/manifest.json \
  --output ../../evaluation/reports/phase4-declarations.json
```

Optional evidence gates:

```bash
python -m app.cli.validate_declarations \
  --manifest ../../evaluation/phase4/manifest.json \
  --output ../../evaluation/reports/phase4-declarations.json \
  --require-real-actual-ocr 20 \
  --min-real-exact-match-rate 0.80 \
  --min-overall-precision 0.90 \
  --min-overall-recall 0.85
```

Those values are examples only. They are not current project performance claims or frozen acceptance thresholds.

## Current limitation

The current extractor supports only MRP and net quantity.

Real-package extraction validation remains pending until actual OCR outputs from reviewed package photographs are collected and annotated.
