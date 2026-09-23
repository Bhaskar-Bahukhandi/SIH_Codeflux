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
- timeout/outcome-unknown protection that requires reconciliation before blind replay;
- checksum-preserving local evidence storage;
- a deletion gate that requires explicit remote-durability confirmation;
- headless sync coordinator interfaces for execution and reconciliation;
- Flutter unit tests using SQLite FFI;
- a dedicated mobile offline GitHub Actions workflow.

The Flutter UI, camera integration, authentication screens and HTTP API executor are **not** represented as implemented yet.

The current slice is infrastructure for the Officer field workflow. It must be validated before UI code is allowed to present any operation as synchronized.

## Offline safety rules

- A queued operation is not equivalent to server success.
- A timeout is treated as outcome-unknown until reconciled.
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
