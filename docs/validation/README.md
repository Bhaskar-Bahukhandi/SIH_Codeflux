# SIH Demo Validation Gates

Issue: #43

This area records evidence for the integrated CODEFLUX SIH prototype without expanding product scope.

## Status vocabulary

Every gate must be classified as one of:

- **PASS** — executed evidence exists and the gate passed.
- **FAIL** — executed evidence exists and the gate failed.
- **BLOCKED** — the gate could not execute because a required runtime/tool/dependency is unavailable.
- **EXTERNAL EVIDENCE REQUIRED** — the repository can provide a harness, but representative real-world evidence must be supplied and reviewed.
- **DEFERRED BY BLUEPRINT** — the approved blueprint explicitly permits the item to remain outside the current blocking scope.

Do not translate BLOCKED or EXTERNAL EVIDENCE REQUIRED into PASS.

## Automated repository gates

The System Validation workflow and scripts/validate_sih_demo.ps1 consolidate the existing automated checks:

| Gate | Evidence |
| --- | --- |
| API migration chain | Alembic upgrade -> downgrade -> upgrade |
| API regression | Full pytest suite |
| Replay/idempotency | Included backend regression tests |
| Dashboard | Component/integration tests + production build |
| Flutter mobile | Dependency resolution + analyzer + existing tests |
| Repository foundation | Existing Phase 0 repository check |

Passing these gates proves code/test health for the covered paths. It does not prove field accuracy.

## Real-evidence gates

The following remain **EXTERNAL EVIDENCE REQUIRED** until representative evidence is supplied and the existing harnesses are executed:

### Image quality and geometry

Harness: python -m app.cli.validate_phase2

Expected local inputs: evaluation/phase2/manifest.csv plus representative real-package images kept outside Git.

### OCR

Harness: python -m app.cli.validate_ocr

Expected local inputs: evaluation/phase3/manifest.csv, real-package images, reviewed ground-truth transcriptions and a configured PaddleOCR runtime.

### Declaration extraction

Harness: python -m app.cli.validate_declarations

Expected local input: evaluation/phase4/manifest.json with reviewed declaration annotations and provenance.

## Runtime/device gates

These cannot be honestly replaced by mocked HTTP or unit tests:

- physical-device offline -> restart -> reconnect -> replay validation;
- production-like Flutter-to-FastAPI run;
- mobile OCR/on-device adapter feasibility spike;
- calibrated physical font-size measurement validation.

The hosting/deployment provider also remains a recorded open decision.

## Claim boundary

A green System Validation workflow means the checked-in automated prototype paths are regression-clean on the tested toolchains.

It does **not** mean real-package OCR/extraction accuracy, physical-device offline behavior, font-size measurement or production readiness has been proven.

## Exit rule

Issue #43 stays open until every SIH-required external/runtime gate has real evidence or an explicit blueprint-approved deferral.
