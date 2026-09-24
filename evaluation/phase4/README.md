# Phase 4 Declaration Extraction Evaluation

This harness measures deterministic declaration extraction **given OCR text blocks**.

It is separate from OCR accuracy and separate from Legal Metrology compliance accuracy.

## Case format

A local JSON manifest contains a top-level `cases` list.

Each case records:

- `case_id`;
- `dataset_type`: `real_package`, `web_reference`, `synthetic`, or `other`;
- `block_source`: `actual_ocr`, `human_transcription`, or `synthetic`;
- ordered OCR blocks with text and recognition score;
- expected structured declarations;
- optional source-page provenance for web references;
- notes.

Label-state semantics are explicit:

- a list in `expected_declarations` means the case is labeled;
- an empty list means a reviewed labeled negative case;
- `expected_declarations: null` means an unlabeled observation case and is excluded from precision/recall/exact-match metrics.

A missing `expected_declarations` field is rejected so an unlabeled observation cannot be mistaken for a negative label.

## Why block-source provenance matters

A real package with manually typed text is useful for extractor testing, but it does not show how the extractor behaves on OCR mistakes.

Therefore only a **labeled**:

> `dataset_type = real_package` + `block_source = actual_ocr`

case contributes to the report's real end-to-end extraction metrics and gates.

`web_reference + actual_ocr` cases may be used for prediction observation when their source page is recorded, but unlabeled web references never affect precision, recall, F1 or real-package evidence gates.

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
- real-package actual-OCR exact-match rate;
- real-package actual-OCR precision/recall;
- labeled and unlabeled case counts;
- web-reference actual-OCR case/prediction counts and source domains.

When a denominator does not exist, a metric is `null` rather than an invented perfect score. Unlabeled cases preserve predictions for review but do not create false positives or false negatives.

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
  --min-real-precision 0.90 \
  --min-real-recall 0.85 \
  --min-overall-precision 0.90 \
  --min-overall-recall 0.85
```

Those values are examples only. They are not current project performance claims or frozen acceptance thresholds.

## Current limitation

The current extractor supports only MRP and net quantity.

Real-package extraction validation remains pending until actual OCR outputs from reviewed package photographs are collected and annotated.

The web-reference observation path is intentionally separate: it can show what the current MRP/net-quantity extractor predicts from real PaddleOCR text on official package imagery, but it cannot establish extraction accuracy until those cases receive human-reviewed declaration labels.
