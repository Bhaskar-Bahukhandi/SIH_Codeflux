# Phase 1 Exit Checklist

Phase 1 establishes the data, lifecycle, authentication and traceability foundation. It does **not** claim image/OCR/rule/report functionality.

## Persistence and migrations

- [x] PostgreSQL remains the central production database target.
- [x] SQLAlchemy models are versioned through Alembic migrations.
- [x] Inspection records have stable identifiers and timestamps.
- [x] User/role records are persisted.
- [x] Migration upgrade/downgrade paths are tested for each Phase 1 revision.

## Inspection lifecycle

- [x] Draft inspection can be created and reopened.
- [x] Draft fields can be edited.
- [x] Draft can be submitted to pending review.
- [x] Submitted inspection cannot be silently edited or re-submitted.
- [x] Finalization is intentionally not exposed yet.

## Authentication and authorization

- [x] Passwords are Argon2 hashed.
- [x] Login returns time-limited signed JWT access tokens.
- [x] Inactive/invalid users are rejected.
- [x] Officers see only their own inspections.
- [x] Supervisors can read/monitor but cannot mutate officer inspections.
- [x] No public registration endpoint exists.
- [x] Default development JWT secret is rejected outside development/test.

## Traceability

- [x] Inspection create/update/submit actions create audit events.
- [x] Audit events store actor, inspection, event type, timestamp and structured details.
- [x] Failed state transitions do not create success audit events.
- [x] No audit update/delete API exists.

## Operational foundation

- [x] Liveness endpoint exists.
- [x] Readiness endpoint performs a real database query.
- [x] Database readiness failure returns a safe 503 without internal SQL details.
- [ ] GitHub-hosted Actions runner issue remains external/unresolved; local executed validation must continue to be recorded honestly until fixed.

## Phase 1 exit decision

Phase 1 may close once the final regression suite and migration chain through revision 0004 pass.

The next roadmap phase is image capture / local evidence handling. OCR and Legal Metrology rules must still remain out until their dedicated phases.
