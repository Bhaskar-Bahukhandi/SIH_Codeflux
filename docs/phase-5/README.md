# Phase 5 — Versioned Preliminary Rule Engine

Status: Complete

## Goal

Evaluate current structured declaration evidence against a small, source-verified Legal Metrology rule pack without allowing OCR/extraction uncertainty to become an automatic legal accusation.

## First rule pack

`lmpc-retail-evidence@2026.09-v1`

Supported checks:

- Rule 6(1)(c) — net quantity declaration evidence;
- Rule 6(1)(e) — retail sale price / MRP declaration evidence.

See:

- `packages/rulepacks/lmpc-retail-evidence-v1.json`
- `docs/legal/verified-rule-pack-v1.md`

## Supported applicability profile

The Officer supplies three factual context values:

- intended for retail sale;
- industrial/institutional consumer;
- package exceeds 25 kg / 25 L.

The first pack evaluates only the narrow profile:

- retail = yes;
- industrial/institutional = no;
- exceeds 25 kg / 25 L = no.

Incomplete context -> `indeterminate`.

Outside this supported profile -> `not_evaluated`.

## Evidence mapping

For each supported declaration:

- `single_source` or `consistent` -> `pass` for preliminary declaration-evidence presence;
- `conflict` -> `manual_verification_required`;
- `not_detected` -> `manual_verification_required`.

The pack never converts technical non-detection into `potential_non_compliance`.

## Reproducibility

Every evaluation run stores:

- exact source extraction run;
- rule-pack ID/version;
- SHA-256 of the exact rule-pack file;
- parsed rule-pack snapshot;
- per-rule effective-from/applicability metadata;
- Officer-supplied context snapshot;
- per-rule result/evidence link.

## Validation evidence

At Phase 5 close:

- complete current API regression suite: **91 passed**;
- a pre-existing adjacent-block extraction defect was found by full regression and fixed in `declaration-extractor-v2`;
- complete Alembic chain `0001 -> 0010` passed;
- full downgrade to base and re-upgrade to `0010` passed;
- GitHub-hosted Actions still failed before runner allocation, tracked separately as infrastructure issue #30.

## Boundaries preserved

Phase 5 does not provide final legal adjudication, confirmed physical absence, Officer finding approval, PDF reports, penalties/notices, physical font-size measurement or offline synchronization.

Phase 6 adds the separate Officer verification/correction layer without overwriting Phase 5 machine outputs.
