# Phase 7 Stable Resource Identity Contract

Status: initial server contract implemented on the Phase 7 branch.

## Purpose

Offline retries must be safe when the client cannot know whether a previous request reached the server.

The first Phase 7 slice uses stable client-generated UUID resource IDs for create-style mutations that already persist UUID primary keys. This provides a migration-free replay primitive while PR #35 still owns the next database migration revision.

## Inspection creation

Endpoint:

- `POST /api/v1/inspections`

Optional request field:

- `id` — UUID generated once by the client and persisted with the local queued operation.

Replay behavior:

- first matching request creates the inspection;
- replay with the same ID, same Officer and same normalized create payload returns the existing inspection;
- replay does not emit another creation audit event;
- reuse of the ID with different data returns `409 client_resource_id_conflict`;
- clients that omit `id` keep the existing server-generated-ID behavior.

## Capture upload

Endpoint:

- `POST /api/v1/inspections/{inspection_id}/captures`

Optional multipart field:

- `capture_id` — UUID generated once by the client and persisted with the local capture operation.

Replay identity includes:

- inspection;
- owning/uploader Officer;
- view type;
- SHA-256 of the exact image bytes;
- verified MIME type;
- byte size;
- verified image dimensions.

Replay behavior:

- an exact replay returns the existing capture;
- before success is returned, the stored evidence file is checked for presence, byte size and SHA-256 integrity;
- missing stored evidence returns `503 capture_storage_unavailable`;
- corrupted stored evidence returns `503 capture_storage_integrity_failed`;
- ID reuse with different evidence returns `409 client_resource_id_conflict`;
- the conflicting retry must not overwrite the previously accepted evidence file;
- clients that omit `capture_id` keep the existing server-generated-ID behavior.

### Concurrency rule

A client-supplied capture ID and the physical storage object name are deliberately decoupled.

Concurrent requests using the same client capture ID write separate candidate storage objects until the database commit decides the winning capture record. A losing retry deletes only its own candidate object. It cannot delete or overwrite the winning evidence file.

## Officer review creation

Endpoint:

- `POST /api/v1/inspections/{inspection_id}/rule-reviews/{rule_evaluation_result_id}`

Optional request field:

- `id` — UUID generated once by the client and persisted with the queued review operation.

Replay behavior:

- an exact replay returns the existing review and original revision;
- replay does not create another revision or audit event;
- corrected values are normalized before replay comparison;
- ID reuse with a different decision, corrected value, note, result, inspection or Officer returns `409 client_resource_id_conflict`;
- an exact replay may confirm an already-created review even if the workflow has advanced since the original response was lost;
- clients that omit `id` keep the existing revision-creation behavior.

## Client queue rule

The local queue must generate the resource UUID once, before the first network attempt, and persist it durably.

It must never generate a fresh UUID merely because:

- the request timed out;
- the app restarted;
- connectivity dropped;
- a 5xx response was received;
- the client is unsure whether the request succeeded.

A new UUID represents a new intended resource, not a retry.

Stable identity makes replay safe, but the client still does not assume that a failed transport means the server did nothing. Timeout, transport loss, 5xx responses, interrupted in-flight work and unverifiable success responses are reconciled first. Automatic retry is scheduled only after reconciliation positively establishes that the prior mutation was not applied.

## Stable append-only processing run IDs

The same stable-resource rule now applies to append-only OCR, declaration extraction and rule-evaluation runs.

Each operation may carry a client-generated UUID for the top-level run record. Exact replay returns that original run and does not create a second audit event or append-only run. A deliberate new processing run must use a new stable UUID.

Exact run-read endpoints are provided for reconciliation so the client never relies on "latest" when confirming whether a specific uncertain request was applied.

## What this slice does not solve yet

This contract does not yet make every state-transition endpoint replay-safe.

Preprocessing/geometry composite records, submission, recheck reopening, and finalization/report behavior still require their own reconciliation/idempotency rules. Finalization work also remains gated on PR #35.

## Validation evidence required before merge

The committed regression tests cover:

- inspection exact replay -> one record / one creation audit event;
- inspection ID reuse with changed payload -> conflict;
- capture exact replay -> one record / one upload audit event;
- capture ID reuse with different bytes -> conflict while original bytes remain unchanged;
- capture replay with missing remote evidence -> explicit 503, not fake success;
- Officer review exact replay -> one review / one revision / one audit event;
- review ID reuse with changed payload -> conflict.

These tests are present but must not be called passing until they execute in a working test environment or CI runner.
