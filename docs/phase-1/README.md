# Phase 1 — Data Foundation

Status: Complete

## Goal

Build the executable data, lifecycle, access-control and traceability foundation for inspections without pulling OCR, Legal Metrology rule evaluation, reporting, or mobile capture forward prematurely.

## Completed scope

### Inspection persistence

- FastAPI application foundation;
- liveness and database-readiness endpoints;
- SQLAlchemy persistence;
- Alembic migration baseline;
- create/list/get inspection endpoints.

### Lifecycle and user roles

- persisted Officer / Supervisor / Admin roles;
- officer ownership field on inspections;
- `draft -> pending_review` lifecycle transition;
- safe draft editing;
- machine-readable domain errors.

### Authentication and access boundary

- Argon2 password hashing;
- signed time-limited JWT access tokens;
- login/current-user endpoints;
- administrative CLI user bootstrap;
- officer read isolation;
- supervisor/admin read access;
- owner-only mutation;
- deployment guard against weak/default JWT secrets.

### Audit and readiness

- append-only inspection audit-event records;
- create/update/submit actions recorded in the same transaction;
- no audit entry for failed transitions;
- real database readiness query;
- safe 503 response when the database is unavailable.

## Validation evidence

At Phase 1 close:

- complete API regression suite: **19 passed**;
- migration chain `0001 -> 0002 -> 0003 -> 0004` passed;
- revision 0004 downgrade/re-upgrade passed;
- GitHub-hosted Actions runner remained unavailable, so executed local validation was recorded explicitly rather than represented as passing hosted CI.

See `docs/phase-1/exit-checklist.md`.

## Boundaries preserved

Phase 1 does not implement package image capture, OCR, declaration extraction, Legal Metrology rule execution, officer finding finalization, reports, or offline synchronization.

Those remain later roadmap phases.
