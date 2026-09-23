# Mobile Field Application

Technology: Flutter.

## Current status

Repository Phase 7 has started the offline-first persistence and synchronization foundation.

Implemented on the Phase 7 branch:

- SQLite schema for local inspection drafts, evidence metadata and pending sync operations;
- explicit sync states: local-only, queued, syncing, synced, retry-required, conflict and blocked;
- durable dependency-aware operation queue;
- restart recovery for operations interrupted while syncing;
- bounded retry/backoff policy;
- explicit transport, timeout, authentication, authorization, validation, stale-evidence, lifecycle, identity and integrity failure classes;
- uncertain-outcome protection for timeout, transport loss, 5xx, interrupted process state and unverifiable success responses;
- checksum-preserving local evidence storage;
- a deletion gate that requires explicit remote-durability confirmation;
- headless sync coordinator interfaces for execution and reconciliation;
- replay-aware HTTP adapter for inspection creation, capture upload, preprocessing, geometry, OCR runs, declaration extraction, rule evaluation, submission, Officer review creation and recheck reopening;
- Bearer-token injection through an external token provider rather than hard-coded credentials;
- real Officer login client using `POST /auth/login` + `GET /auth/me`;
- secure session persistence only after the server confirms an active Officer account;
- expired network tokens preserve offline Officer identity but pause synchronization until re-authentication;
- app-facing Officer workspace service for listing owned inspections, creating drafts, adding evidence, queueing review and requesting sync;
- field-workflow orchestration that builds the full per-capture upload -> preprocessing -> geometry -> OCR dependency chain without UI-managed UUIDs;
- exact-resource or lifecycle-state reconciliation for every implemented pre-finalization mutation before replaying an uncertain remote outcome;
- local capture checksum/size verification before any upload request;
- bounded startup queue draining that continues past isolated blocked/conflicted work;
- a simulated offline -> app restart -> reconnect scenario with a deliberately lost capture response;
- Flutter unit tests using SQLite FFI and HTTP mock transport;
- a dedicated mobile offline GitHub Actions workflow.

The Phase 7 branch now includes the first functional Officer UI shell: login, local inspection list, inspection detail, camera/gallery package-image acquisition, applicability-context entry, queue-for-review, sync-now, interrupted-capture recovery messaging, and sign-out/re-authentication handling. Native Android/iOS runner projects are still intentionally ungenerated until the guarded Flutter platform bootstrap can execute. Background scheduling and finalization/report synchronization are **not** represented as implemented yet.

The committed scenarios include a two-capture offline/restart/reconnect test and a full queued pre-finalization pipeline through submission. They use in-process mock HTTP server state to validate sync mechanics and are not substitutes for an executed Flutter-to-FastAPI integration test or field-device validation.

The current slice is infrastructure for the Officer field workflow. It must be validated before UI code is allowed to present any operation as synchronized.

## Offline safety rules

- A queued operation is not equivalent to server success.
- Timeout, transport loss, 5xx, interrupted in-flight work and unverifiable success responses are treated as outcome-unknown until reconciled.
- Dependent operations cannot overtake unsynced prerequisites.
- A blocked or conflicted prerequisite explicitly blocks dependent work.
- Local original evidence is retained until remote durability is positively confirmed.
- Connectivity state never changes Legal Metrology decision semantics.
- The existing online backend remains the fallback until the offline path passes its exit scenario.

## Validation

Run from `apps/mobile`:

    flutter pub get
    flutter analyze
    flutter test

The repository workflow `.github/workflows/mobile-offline-tests.yml` runs the same analysis/test gate on Flutter 3.47.5.

GitHub-hosted runner allocation has been restored. Mobile validation now depends on real `flutter pub get`, `flutter analyze`, and `flutter test` results.


## Current UI slice

The current field UI is deliberately small and operational:

- Officer sign in against the real FastAPI authentication endpoints;
- Officer-scoped local inspection list;
- create local inspection;
- inspection detail with persisted package-image evidence;
- backend-supported capture views: front, back, left, right, top, bottom, detail and other;
- camera or gallery acquisition using the official image picker;
- durable Android lost-image recovery intent;
- factual applicability context for the current preliminary rule pack;
- queue-for-review without issuing any final legal verdict;
- sync-now using persisted queue status only;
- expired token -> re-authentication request without deleting local drafts.

The app requires `CODEFLUX_API_URL` at launch. No demo API endpoint is embedded in the source.

Android/iOS project scaffolding must be generated by `scripts/bootstrap_mobile_platforms.ps1` with a real Flutter SDK, then reviewed before commit.
