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
- replay-aware HTTP adapter for inspection creation, capture upload and Officer review creation;
- Bearer-token injection through an external token provider rather than hard-coded credentials;
- server reconciliation for inspection/capture/review stable IDs before replaying any uncertain remote outcome;
- local capture checksum/size verification before any upload request;
- bounded startup queue draining that continues past isolated blocked/conflicted work;
- a simulated offline -> app restart -> reconnect scenario with a deliberately lost capture response;
- Flutter unit tests using SQLite FFI and HTTP mock transport;
- a dedicated mobile offline GitHub Actions workflow.

The Flutter UI, camera integration, login/token-persistence screens, background scheduling, and sync adapters for preprocessing/OCR/extraction/rule evaluation/submission/recheck/finalization are **not** represented as implemented yet.

The current reconnect scenario uses an in-process mock HTTP server state to validate sync mechanics. It is not a substitute for an executed Flutter-to-FastAPI integration test or field-device validation.

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

The repository workflow `.github/workflows/mobile-offline-tests.yml` runs the same analysis/test gate on Flutter 3.38.0.

At the current repository infrastructure state, GitHub-hosted jobs are still terminating before step allocation. A zero-step Actions failure is not counted as a Flutter test failure or a passing validation result.
