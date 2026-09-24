# CODEFLUX SIH Demo Freeze — 2026-09-24

This document records the validated demo boundary for the CODEFLUX SIH prototype. It is a release/freeze record, not a claim that every research-quality accuracy gate is complete.

## Frozen demo slice

- Mobile application version: `0.1.0+2`
- Flutter toolchain used by the APK workflow: `3.47.5`
- Live API/dashboard: `https://codeflux-demo-production.up.railway.app/`
- Production source baseline before this freeze: `7a077d593ea340672832482d5deeb0d6ada755dc`
- Android package is generated ephemerally in CI; permanent Android/iOS runner scaffolding remains intentionally absent from the repository.
- APK type: debug/demo build connected to the live Railway backend. This is suitable for SIH demonstration and physical-device validation, not Play Store distribution.

## Physical Android evidence

A real Android handset was used against the live Railway deployment.

Observed successfully during the physical-device pass:

- Officer authentication with the live Officer account;
- Officer workspace load and persisted local inspection list;
- creation of real inspections;
- capture and display of real package photographs;
- retry/replay of previously failed queue work;
- live preprocessing, geometry, PP-OCRv5 processing, declaration extraction and rule evaluation;
- final submission to the backend;
- current image correction controls in the updated APK, including Replace image and Remove image;
- the updated APK was reported by the tester as working flawlessly after stabilization.

The physical-device session exposed and led to fixes for four production defects rather than hiding them:

1. Flutter route/controller lifecycle teardown during inspection creation;
2. PP-OCRv5 memory pressure on the 1 GB Railway service;
3. missing checked-in Legal Metrology rule-pack data in the combined runtime image;
4. legacy PostgreSQL `inspections.status` width that could not store `PENDING_REVIEW`.

## Live production evidence

The production service currently uses Railway PostgreSQL, one persistent `/data` volume and public HTTPS.

The final handset submission was accepted by the live service:

- inspection id: `17695ce1-8915-42e3-a70d-e24288c68470`;
- final submit endpoint returned HTTP 200 after migration 0014;
- Railway startup log confirmed migration `0013 -> 0014`;
- `/health/ready` returned HTTP 200 on the deployed revision.

The same inspection survived successive backend deployments while its queued workflow was retried. This is evidence of persisted inspection/database state across redeploys. It is not being stretched into a separate claim that every evidence-file path was independently re-read after a forced restart.

## Runtime stabilization now included

### OCR

The 1 GB deployment uses:

- PaddleOCR 3.7.0;
- PaddlePaddle 3.2.2;
- PP-OCRv5 family;
- `PP-OCRv5_mobile_det` for the constrained detector path;
- `OCR_INPUT_MAX_DIMENSION=1600`;
- detector limit `960`;
- serialized native inference within the API process.

A hard 1 GB container smoke survived real Paddle inference without OOM, and the physical-package observation workflow completed 6/6 package photographs with zero inference failures. This proves runtime execution/stability for the tested set, not CER/WER accuracy.

### Rule evaluation

The combined runtime image now includes the checked-in versioned rule pack at `/app/packages/rulepacks/`. The container smoke loads and validates it from inside the built image.

### Submission lifecycle

Alembic migration 0014 widens persisted inspection status storage to support all current lifecycle values, including `PENDING_REVIEW`.

## Demo path

The intended SIH demonstration path is:

1. sign in as an Officer on Android;
2. create an inspection;
3. capture multiple package views;
4. replace/remove a bad image if needed;
5. queue preliminary review;
6. sync;
7. allow preprocessing -> geometry -> OCR -> declaration extraction -> rule evaluation -> submission;
8. confirm the inspection reaches the backend;
9. use the Supervisor web application for review/visibility.

## Remaining evidence-only gates

These are not implementation blockers for the demo and must not be misreported as PASS:

- reviewed real-package OCR transcriptions for CER/WER;
- reviewed real-package declaration labels for precision/recall;
- an explicitly documented physical handset run of offline -> app restart -> reconnect -> replay;
- physical-device runtime/latency/energy evidence for the optional ML Kit adapter;
- independent evidence-file readback across an intentional Railway restart/redeploy if that stronger persistence claim is required.

Physical font-size measurement remains **DEFERRED BY BLUEPRINT** and is not part of the current prototype compliance claim.

## Freeze rule

After this freeze, do not add unrelated features before the SIH demonstration. Changes should be limited to:

- confirmed demo-blocking defects;
- security fixes;
- evidence/documentation corrections;
- build/distribution fixes that do not alter product scope.

Any broader feature work should start after the demo milestone or on a separate post-demo branch.
