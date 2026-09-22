# Phase 1 — Data Foundation

Status: Completion candidate; pending final regression validation

## Goal

Build the executable data, lifecycle, access-control and traceability foundation for inspections without pulling OCR, Legal Metrology rule evaluation, reporting, or mobile capture forward prematurely.

## Slice A — inspection persistence

- FastAPI application foundation;
- liveness endpoint;
- SQLAlchemy persistence;
- Alembic migration baseline;
- create/list/get inspection endpoints;
- isolated persistence tests.

## Slice B — lifecycle and user-role foundation

- persisted Officer / Supervisor / Admin roles;
- officer ownership field on inspections;
- `draft -> pending_review` lifecycle transition;
- safe draft editing;
- machine-readable domain errors;
- migration revision 0002;
- lifecycle and role tests.

## Slice C — authentication and access boundary

- Argon2 password hashing;
- signed time-limited JWT access tokens;
- login/current-user endpoints;
- administrative CLI user bootstrap;
- officer ownership from authenticated identity;
- officer read isolation;
- supervisor/admin read access;
- owner-only mutation;
- deployment guard against weak/default JWT secrets;
- migration revision 0003.

## Slice D — audit and readiness foundation

- append-only inspection audit-event records;
- create/update/submit actions recorded in the same transaction;
- no audit entry for failed transitions;
- real database readiness endpoint;
- safe 503 response when the database is unavailable;
- migration revision 0004.

## Important boundaries preserved

Phase 1 still does not implement:

- package image capture;
- OCR/declaration extraction;
- Legal Metrology rule execution;
- officer finding review/finalization;
- PDF reports;
- offline mobile synchronization.

The API deliberately has no inspection-finalize action yet.

## Phase 1 exit

Phase 1 closes only after the complete regression suite and migration chain through revision 0004 pass. See `docs/phase-1/exit-checklist.md`.

After that, the next roadmap phase is image capture / evidence handling.
