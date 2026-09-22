# ADR 0002 — Phase 0 Scope Freeze

Status: Accepted for SIH prototype foundation  
Date: 2026-09-22

## Context

Foundation Blueprint v1.0 intentionally left several implementation decisions open so that the repository would not invent product requirements that were absent from the submitted SIH proposal.

This ADR freezes the minimum decisions needed to begin Phase 1 while keeping future changes reversible.

## Decisions

### 1. Initial demo commodity category

Use ordinary **retail pre-packaged snack products**, primarily biscuit/chips-style packets, as the first demo/test category.

Reason:
- this matches the packaging examples already used throughout the submitted presentation;
- the packages are common, easy to source and photograph;
- they provide realistic multi-surface declaration text without changing the overall project scope.

This is a demo dataset choice, not a restriction of the product to food or snacks.

### 2. Initial Legal Metrology rule coverage

The first rule pack will focus on **presence/extraction and preliminary verification of common mandatory retail-package declarations under Rule 6, only where applicability has been verified from official sources**.

Candidate fields for the first pack:
- manufacturer / packer / importer name and address;
- common or generic name of the commodity;
- net quantity;
- month/year or relevant date declaration where applicable;
- retail sale price / MRP;
- consumer-care details;
- unit sale price where applicable.

No candidate becomes an implemented compliance rule until the legal-source matrix marks it verified, including applicability and exceptions.

### 3. Physical font-size measurement approach

Use a **configurable printed calibration reference** placed on approximately the same plane as the declaration region.

The prototype may use a high-contrast fiducial/marker for geometric detection, but the physical reference dimension must be configurable and stored with the inspection evidence.

If the reference is missing, distorted beyond the supported tolerance, or not on a defensible plane relative to the text, the system must return an uncertain/not-evaluated result rather than invent a millimetre measurement.

Exact marker artwork and tolerance thresholds remain implementation details for the later measurement phase.

### 4. On-device vs server processing

Do not freeze a single all-or-nothing processing location yet.

Foundation split:
- mobile: capture, local persistence, basic capture-quality checks where practical, offline queue/state;
- backend: canonical API, central persistence, rule-pack/version management and server processing path;
- OCR/extraction interface: must allow an on-device adapter and a server adapter.

A dedicated technical spike will determine the practical mobile OCR runtime before the offline-analysis phase is declared complete.

This defers an implementation mechanism, not the offline requirement.

### 5. Supervisor permissions

For the first prototype, Supervisor is primarily a **read/review/monitoring role**:
- search and open inspections;
- view findings/evidence/status;
- view/export reports;
- view simple monitoring data.

Supervisor does not silently edit or replace an officer's finalized decision in the initial prototype.

Admin remains responsible for user/role configuration.

### 6. Export format

**PDF is the only required report export in the core prototype.**

Editable exports are optional and should not block the SIH build.

### 7. Hosting/deployment target

Hosting provider remains deferred.

The codebase should remain environment-configurable and container-ready so that local development and later deployment do not require application rewrites.

The hosting decision does not block Phase 1.

## Consequences

Phase 1 may now proceed without guessing the basic demo scope.

The following remain gated:
- legal rule encoding until official-source verification;
- physical font-size pass/fail decisions until calibrated measurement exists;
- full offline automated analysis until the mobile OCR/runtime spike is completed.

## Reversal

Any change to these decisions should be recorded in a later ADR with:
- reason;
- blueprint impact;
- schedule impact;
- migration path;
- validation required;
- rollback/fallback plan.
