# Phase 1 — Data Foundation

Status: In progress

## Goal

Build the executable data, lifecycle and access-control foundation for inspections without pulling OCR, Legal Metrology rule evaluation, reporting, or mobile capture forward prematurely.

## Completed slice A — inspection persistence

- FastAPI application foundation;
- health endpoint;
- SQLAlchemy persistence;
- Alembic migration baseline;
- create/list/get inspection endpoints;
- isolated persistence tests.

## Completed slice B — lifecycle and user-role foundation

- persisted Officer / Supervisor / Admin roles;
- optional officer ownership field on inspections;
- `draft -> pending_review` lifecycle transition;
- safe draft editing;
- machine-readable domain 404/409 errors;
- migration revision 0002;
- lifecycle and role tests.

## Current slice C — authentication and access boundary

This slice adds:

- Argon2 password hashing;
- signed time-limited JWT access tokens;
- login and current-user endpoints;
- administrative CLI user bootstrap;
- officer ownership assigned from the authenticated identity;
- officer read scope restricted to owned inspections;
- supervisor/admin read access;
- owner-only officer mutation;
- deployment guard against weak/default JWT secrets;
- migration revision 0003.

### Important boundary

There is no public user registration and no default administrator account.

The inspection API still does not expose finalization. Finalization remains deferred until the officer-review/report phase has the real evidence and decisions needed to make that state meaningful.

## Still not implemented

- package images/captures;
- OCR and declaration extraction;
- Legal Metrology rule execution;
- officer finding review;
- PDF report generation;
- offline mobile synchronization;
- refresh tokens/MFA/SSO;
- organization tenancy.

## Remaining Phase 1 work

1. add database readiness/startup diagnostics;
2. add append-only audit-event persistence for important state changes;
3. run a final Phase 1 regression/migration validation;
4. close Phase 1 before starting the image-capture phase.

## Validation gate

Each merged slice needs executed tests or equivalent evidence. Do not call a phase complete from static code review alone.
