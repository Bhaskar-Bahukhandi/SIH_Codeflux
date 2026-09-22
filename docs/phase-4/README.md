# Phase 4 — Declaration Extraction and Multi-image Fusion

Status: In progress

## Goal

Convert OCR text evidence into structured declaration candidates with full provenance, while remaining separate from Legal Metrology applicability and compliance rules.

## First supported types

The first extractor supports only:

- MRP / retail sale price candidate;
- net quantity candidate.

This limited initial scope is deliberate. It is better to have transparent, testable extraction for two important declarations than broad label guessing presented as reliable.

## Evidence model

Every observation stores:

- extraction run/version;
- declaration type;
- capture ID;
- OCR run ID;
- exact OCR block IDs used;
- raw joined OCR text;
- normalized structured value;
- minimum and mean OCR recognition scores;
- deterministic extractor method.

No separate “AI confidence” or invented extraction probability is produced.

## Adjacent OCR blocks

If a declaration label and its value are split into two consecutive OCR blocks, the extractor may use both blocks and records both block IDs.

It does not search arbitrary distant blocks.

## Multi-image fusion

Each supported declaration receives one technical state:

- `not_detected` — no candidate was extracted from the current OCR sources;
- `single_source` — one normalized value is supported by only one capture;
- `consistent` — the same normalized value is observed across at least two distinct captures;
- `conflict` — more than one normalized value is observed.

A conflict is preserved. The system does not silently select a winner.

## Current-source rule

Extraction uses the latest OCR run per capture only when that OCR run still points to the capture's current OCR source derivative.

If a capture was reprocessed after OCR, the old OCR run is marked `stale_ocr` and excluded until OCR is rerun.

The extraction run records source and skipped capture IDs/reasons.

## Critical legal boundary

`not_detected` means **the current extractor did not detect a candidate**.

It does **not** mean:

- the declaration is legally required;
- the declaration is physically absent;
- the package is non-compliant.

Legal applicability and compliance remain later, source-gated rule-engine work.

## Not included yet

- manufacturer/packer/importer extraction;
- common/generic commodity name;
- date declarations;
- consumer-care extraction;
- unit sale price;
- physical/font measurement;
- Legal Metrology findings;
- officer corrections/approval.

Those should be added as separate validated extractor/rule slices.
