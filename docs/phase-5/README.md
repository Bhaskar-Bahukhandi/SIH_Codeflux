# Phase 5 — Versioned Preliminary Rule Engine

Status: foundation implementation in progress

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

The officer supplies three factual context values:

- intended for retail sale;
- industrial/institutional consumer;
- package exceeds 25 kg / 25 L.

The first pack evaluates only the narrow profile:

- retail = yes;
- industrial/institutional = no;
- exceeds 25 kg / 25 L = no.

Incomplete context -> `indeterminate`.

Outside this supported profile -> `not_evaluated`.

That distinction prevents the prototype from pretending it has encoded every exception or package class.

## Evidence mapping

For each supported declaration:

- `single_source` or `consistent` -> `pass` for preliminary declaration-evidence presence;
- `conflict` -> `manual_verification_required`;
- `not_detected` -> `manual_verification_required`.

The first pack never converts `not_detected` into `potential_non_compliance`.

## Reproducibility

Every evaluation run stores:

- exact source extraction run;
- rule-pack ID;
- rule-pack version;
- SHA-256 of the exact rule-pack file;
- officer-supplied context snapshot;
- per-rule result/evidence link.

## Current boundaries

Not included in this first Phase 5 slice:

- confirmed physical absence workflow;
- `potential_non_compliance` generation;
- officer finding approval/override;
- manufacturer/date/consumer-care/unit-sale-price rules;
- physical/font measurement;
- penalty or notice logic;
- final inspection verdict.

These remain later, separately validated slices.
