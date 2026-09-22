# Phase 3 — OCR Text Evidence

Status: OCR foundation implemented; real-package OCR validation pending

## Goal

Convert prepared package images into traceable text evidence while keeping OCR separate from declaration extraction and legal compliance logic.

## Slice A — OCR provenance and persistence

Implemented:

- pluggable OCR-engine interface;
- PaddleOCR 3.x adapter;
- explicit source-derivative selection;
- source derivative/checksum provenance;
- append-only OCR runs;
- ordered text blocks with recognition score and polygon;
- protected OCR execution/latest-result endpoints;
- audit tracing;
- fake-engine tests that do not require model downloads.

## Source selection

OCR uses:

1. the latest perspective-corrected derivative only when that correction is based on the latest normalized derivative;
2. otherwise the latest normalized derivative.

This prevents an older perspective correction from silently overriding newer preprocessing.

## Slice B — OCR evaluation harness

Implemented:

- manifest-driven OCR dataset;
- explicit `real_package`, `synthetic`, `other` separation;
- human ground-truth text files;
- the application normalization/perspective preparation chain;
- CER and WER;
- per-case OCR blocks and selected source type;
- engine/model/version/parameter provenance;
- labeled/scored/failed case counts;
- JSON reports;
- optional evidence gates without hard-coded acceptance thresholds.

See `evaluation/phase3/README.md`.

## Important boundaries

OCR output is evidence, not a Legal Metrology verdict.

- Recognition score is the OCR engine's score, not a calibrated legal probability.
- Empty/failed OCR does not prove a declaration is absent.
- Image-quality status is guidance, not a hard legal gate.
- No declaration normalization or field extraction occurs in this phase.
- No rule engine or compliance finding occurs in this phase.

## PaddleOCR runtime

The adapter targets PaddleOCR 3.x `PaddleOCR(...).predict(...)` and reads recognition text, score and polygon output.

The Python package is optional because local inference also depends on a compatible inference engine/runtime. Missing support returns an explicit backend-unavailable error instead of an empty result.

## Phase 3 validation state

The orchestration, persistence and metric paths can be regression-tested without model downloads.

However, **real-package OCR validation is still pending** until representative package photographs are collected, human-transcribed, and run through the configured OCR runtime.

Until then:

- do not claim a CER/WER value for field performance;
- do not tune declaration logic around synthetic-only behavior;
- do not treat zero OCR blocks as proof that text is absent.

## Next work

Once this slice is merged, the next implementation step can prepare declaration extraction/multi-image fusion architecture, but production-quality claims must continue to remain gated on real package OCR evidence.
