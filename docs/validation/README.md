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

The checked-in CPU observation path has now proven that PaddleOCR 3.7.0 + PaddlePaddle 3.2.2 + PP-OCRv5 can execute the 12 curated official web-reference package images with MKLDNN disabled. That observation produced 145 text blocks with 12/12 cases completing and 0 inference failures.

This is **PASS** for the configured web-reference OCR runtime execution path only.

Real-package OCR accuracy remains **EXTERNAL EVIDENCE REQUIRED** because CER/WER requires representative camera captures and reviewed ground-truth transcriptions.

Expected real-evidence inputs: evaluation/phase3/manifest.csv, real-package images, reviewed ground-truth transcriptions and the configured PaddleOCR runtime.

### Declaration extraction

Harness: python -m app.cli.validate_declarations

Expected local input: evaluation/phase4/manifest.json with reviewed declaration annotations and provenance.

## Runtime/device gates

### Production-like Flutter-to-FastAPI integration

**PASS** for the checked-in Linux CI process/network path.

The dedicated live integration workflow now:

- migrates an isolated backend database;
- starts a real FastAPI/uvicorn process;
- authenticates through the real Flutter Officer auth client;
- creates inspection/evidence/queue state locally;
- closes and reopens the mobile SQLite database before reconnect;
- drains the real HTTP sync adapter through inspection creation, capture upload, preprocessing, geometry, PP-OCRv5, declaration extraction, rule evaluation and submission;
- replays stable inspection/capture IDs and verifies no duplicate remote resources;
- verifies the FastAPI readiness endpoint after the run.

The validation also exposed and fixed a lifecycle replay bug: an exact capture retry after submission had previously been rejected before idempotency reconciliation. Exact replay now returns the existing capture, while changed/new evidence remains blocked according to the inspection lifecycle.

This proves the repository's Flutter HTTP adapter can synchronize against the real FastAPI implementation in CI. It is not physical-device evidence.

### Mobile/on-device OCR feasibility

**PASS** for repository compatibility and Android native build feasibility.

The bounded ML Kit spike demonstrates:

- `google_mlkit_text_recognition` 0.17.1 resolves on the Flutter 3.47.5 toolchain;
- the isolated adapter passes analyzer and mobile regression tests;
- the server PP-OCRv5 path remains unchanged and authoritative;
- an ephemeral native Android project builds a debug APK successfully with the ML Kit plugin linked;
- the guarded platform bootstrap now uses a Kotlin-safe `org.sih.codeflux` organization and iOS 15.5 minimum.

This does **not** prove on-device recognition output, latency, memory/battery impact or real offline model behavior. Those require a physical Android/iOS device.

### Blueprint-deferred physical measurement

**DEFERRED BY BLUEPRINT** for the current SIH prototype:

- physical character/font-size measurement;
- calibration-marker artwork/tolerance implementation required by that measurement.

This is not being reclassified as PASS. The accepted Phase 0 scope freeze defines a calibrated-reference approach for any future physical measurement and forbids pass/fail measurement without defensible calibration. The approved Phase 7 roadmap then lists physical/font-size measurement under **Explicitly deferred**, and the Phase 6 finalization scope also excludes it.

Relevant scope records:

- `docs/decisions/0002-phase0-scope-freeze.md`;
- `docs/phase-7/README.md`;
- `docs/phase-6/finalization-report.md`.

Therefore Issue #43 does not require a calibration-marker implementation to call the current approved SIH prototype scope complete. CODEFLUX must continue to state that it does **not** perform physical font-size compliance measurement.

### Still external/runtime-dependent

These remain **EXTERNAL EVIDENCE REQUIRED**:

- physical-device offline -> restart -> reconnect -> replay validation;
- mobile OCR/on-device physical-runtime validation.

### Demo deployment packaging and provider decision

**PASS** for repository-level deployment packaging and provider selection.

Railway Hobby is the selected initial SIH demo target. The checked-in combined Docker image now:

- builds the React dashboard and FastAPI API into one same-origin service;
- installs PaddleOCR 3.7.0 + PaddlePaddle 3.2.2;
- prefetches PP-OCRv5 model artifacts during image construction;
- applies Alembic migrations on container startup;
- serves the dashboard from `/`;
- preserves `/health` and `/health/ready`;
- passed the dedicated container smoke workflow.

Live Railway provisioning is now partially evidenced:

- app service deployment: **PASS**;
- private Railway PostgreSQL connectivity through application readiness: **PASS**;
- `/data` persistent volume attachment: **PASS**;
- public Railway HTTPS routing: **PASS**;
- public `/health`, `/health/ready` and same-origin dashboard: **PASS**;
- authenticated inspection/evidence persistence after intentional service restart/redeploy: **EXTERNAL EVIDENCE REQUIRED**.

### Current unresolved evidence gates

After the repository-controlled validation work, the remaining non-deferred evidence is:

- representative physical-package camera captures for Phase 2 quality/geometry evaluation;
- reviewed real-package OCR transcriptions for CER/WER;
- reviewed real-package declaration labels for extraction precision/recall;
- a physical handset run of offline -> restart -> reconnect -> replay;
- a physical handset run of the optional ML Kit adapter to measure actual recognition/runtime behavior;
- an authenticated live Railway inspection proving database + evidence-file persistence across an intentional restart/redeploy.

None of these may be reported as PASS based only on synthetic, web-reference, emulator, container or mocked evidence.


## Current physical/live demo freeze

The current validated demo boundary is recorded in [final-demo-freeze-2026-09-24.md](final-demo-freeze-2026-09-24.md).

A real Android handset has successfully exercised the current Officer APK against the live Railway backend through authentication, capture, retry recovery, OCR/rule processing and final submission. The final live submit for inspection `17695ce1-8915-42e3-a70d-e24288c68470` returned HTTP 200 after the production schema/rule-pack/OCR stability fixes. The updated APK was subsequently reported as working flawlessly on the physical handset.

This is **PASS** for current mobile-client/live-backend interoperability on the tested Android device. It does not convert the remaining reviewed-accuracy, explicit offline-restart-reconnect, optional ML Kit physical-runtime or stronger evidence-file persistence gates into PASS.

## Claim boundary

A green System Validation workflow means the checked-in automated prototype paths are regression-clean on the tested toolchains.

It does **not** mean real-package OCR/extraction accuracy, physical-device offline behavior, physical font-size measurement or production readiness has been proven. Physical font-size measurement is outside the approved current prototype scope rather than silently assumed complete. The live Flutter-to-FastAPI CI gate is process/network integration evidence, not a physical handset validation.

## Exit rule

Issue #43 stays open until every SIH-required external/runtime gate has real evidence or an explicit blueprint-approved deferral.
