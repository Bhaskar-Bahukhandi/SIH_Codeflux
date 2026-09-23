# Phase 7 — Offline-first Operation and Synchronization Hardening

Status: initial implementation in progress

Issue: #36

## Roadmap position

This is the next functional milestone from the approved CODEFLUX roadmap.

The original roadmap called this Offline + Synchronization Hardening. Repository history has already used Phase 6 for Officer review/finalization work, so this milestone is tracked as Repository Phase 7.

## Dependency gate

PR #35 must complete its real execution gate and merge before this phase may depend on finalization/report APIs.

Until then, this branch may contain only work that is independent of unvalidated Phase 6 finalization/report behavior: local persistence design, queue contracts, idempotency design, reconciliation rules, tests/specifications, and backward-compatible server primitives.

## Goal

Allow an Officer to continue inspection work with intermittent or absent connectivity and later synchronize exactly once without losing evidence or duplicating remote state.

Connectivity must never change Legal Metrology semantics.

## Non-negotiable invariants

1. The current online backend remains the last-known-good path.
2. No queued operation may be shown as successfully synced until remote durability is confirmed.
3. Local original evidence is retained until remote storage and metadata are positively reconciled.
4. Retries must be idempotent.
5. Replaying a completed queue must not create duplicate remote records.
6. Dependency ordering must be explicit.
7. Semantic/API rejection is not treated as a transient network retry.
8. Stale evidence remains stale after synchronization; sync must not bypass freshness gates.
9. Officer review history and immutable machine evidence are never silently overwritten to resolve a conflict.
10. Offline state never creates or upgrades a legal finding.

## Planned architecture

### Mobile local store

Planned technology remains Flutter with:

- SQLite for structured local state;
- local file storage for package-image evidence;
- durable locally generated operation IDs;
- explicit mapping between local and remote resource IDs;
- persistent sync status and last error metadata.

The exact Flutter persistence package is intentionally not fixed in this document until the mobile implementation slice begins.

### Durable operation queue

A queued operation should minimally record:

- operation ID;
- inspection/local aggregate ID;
- operation type;
- serialized payload or stable payload reference;
- dependency operation IDs;
- idempotency key;
- attempt count;
- current sync state;
- last attempt timestamp;
- last transport/API error classification;
- remote resource identifier after success;
- payload/evidence checksum when relevant.

### Sync states

The implementation must expose explicit states. The initial proposed state model is:

- local_only
- queued
- syncing
- synced
- retry_required
- conflict
- blocked

These names may be refined, but there must be no implicit success state.

### Failure classification

At minimum distinguish:

- transport unavailable;
- timeout / outcome unknown;
- authentication expired;
- server 5xx / uncertain remote outcome;
- validation failure;
- authorization failure;
- stale-evidence conflict;
- domain lifecycle conflict;
- checksum/integrity conflict.

Timeouts, transport loss, 5xx responses, interrupted in-flight operations and unverifiable success responses are treated as uncertain remote outcomes. They require reconciliation before replay where the API provides enough identifying information.

### Idempotency

Offline-created mutations that may be retried must have stable idempotency semantics.

The first implementation review must cover at least:

- inspection creation;
- capture upload;
- Officer review creation;
- finalization request;
- any report-producing mutation.

Where an existing API cannot be retried safely, add a backward-compatible server primitive rather than relying on client-side guessing.

### Reconciliation

After a successful request or reconnect:

1. confirm remote resource identity;
2. compare stable IDs/checksums where available;
3. persist local-to-remote mapping;
4. mark the operation synced only after confirmation;
5. unblock dependent operations;
6. retain explicit conflict/blocked state for mismatches.

## Implemented slice: stable resource replay safety

The current Phase 7 branch now contains two bounded implementation layers.

### Server replay-safety layer

- client-generated stable UUID for inspection creation;
- client-generated stable UUID for capture upload;
- client-generated stable UUID for Officer review creation;
- exact replay returns the existing resource instead of creating a duplicate;
- mismatched reuse of the same client resource ID is rejected;
- capture replay confirms stored evidence integrity before reporting success;
- focused backend regression tests are present in `test_sync_idempotency.py`.

### Mobile offline foundation

- Flutter package baseline under `apps/mobile`;
- SQLite schema for local inspections, evidence metadata and sync operations;
- explicit local-only / queued / syncing / synced / retry-required / conflict / blocked states;
- durable dependency-aware queue;
- blocked/missing predecessor propagation;
- reconciliation-first recovery after a process restart interrupts an in-flight operation;
- bounded retry/backoff;
- transport/API failure classification;
- generalized uncertain-outcome protection for timeout, transport loss, 5xx, process interruption and unverifiable success responses;
- reconciliation-aware headless sync coordinator;
- replay-aware HTTP executor/reconciler for inspection creation, capture upload and Officer review creation;
- local evidence SHA-256/size validation before capture upload;
- bounded startup queue draining and interrupted-sync recovery;
- atomic projection of queue state onto local inspection/evidence state;
- checksum-preserving local evidence storage;
- evidence deletion gate requiring remote-durability confirmation;
- SQLite FFI tests for queue persistence, ordering, retries, restart recovery and local draft survival;
- HTTP adapter contract tests;
- an offline -> restart -> reconnect scenario test with a simulated response lost after remote capture application;
- a dedicated `Mobile Offline Tests` workflow.

No database migration is introduced in this slice, avoiding a revision collision with PR #35.

The camera/UI integration, authentication/token persistence, remaining mutation adapters, real Flutter-to-FastAPI integration run, and physical-device offline/reconnect validation are still pending.

The committed reconnect scenario is a deterministic sync-mechanics test using mock HTTP server state. It verifies dependency ordering, database restart persistence, response-loss reconciliation, exactly-once mutation counts in the simulated remote state, and local-evidence retention. It must not be described as real backend or field validation.

Execution status remains pending: the repository Actions jobs currently terminate before runner steps are allocated, and the ChatGPT container used for this pass could not resolve GitHub for a local checkout. These limitations are not application-test failures, but they also do not count as passing validation.

## Validation gates

### Queue durability

Prove:

- queued operations survive app/process restart;
- locally stored evidence survives restart;
- operation order/dependencies survive restart;
- failed operations do not disappear.

### Replay / idempotency

For every supported mutation:

- execute once;
- simulate lost response or retry;
- execute again with the same idempotency identity;
- verify exactly one remote resource/change exists.

### Partial failure

Test at least:

- inspection succeeds, capture upload fails;
- one capture succeeds, next fails;
- timeout/transport loss/5xx after server success;
- expired authentication;
- stale evidence after reconnect;
- semantic 409 conflict;
- local file missing/corrupt before upload.

### Minimum offline scenario

The exit test is the scenario documented in Issue #36:

online auth -> connectivity loss -> local inspection + multiple images -> restart -> reconnect -> ordered sync -> forced retry -> reconciliation -> replay -> no duplicates.

## Rollback / fallback

- This branch is isolated from main.
- No existing online API behavior may be removed to support offline sync.
- New server fields/endpoints must be backward compatible until the mobile client has proven them.
- If queue/idempotency behavior is not validated, keep the feature behind the phase branch and retain the online-only workflow.
- Local evidence cleanup is disabled unless successful remote reconciliation is proven.

## Explicitly deferred

- Supervisor web dashboard;
- broader Legal Metrology declaration/rule coverage;
- physical/font-size measurement;
- penalty or statutory notice generation;
- manufacturer/consumer/e-commerce portals;
- blockchain;
- RAG/assistant features.

## Exit decision

Phase 7 may close only when the minimum offline scenario is executed successfully, replay produces no duplicate mutation, the existing online path still works, and validation evidence is recorded.
