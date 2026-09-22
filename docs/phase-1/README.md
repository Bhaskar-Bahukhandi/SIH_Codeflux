# Phase 1 — Data Foundation

Status: In progress

## Goal

Build the executable data and API foundation for inspections without pulling OCR, Legal Metrology rule evaluation, reporting, or mobile capture forward prematurely.

## Completed slice A — inspection persistence

- FastAPI application foundation;
- health endpoint;
- SQLAlchemy persistence;
- Alembic migration baseline;
- create/list/get inspection endpoints;
- isolated persistence tests.

## Current slice B — lifecycle and user-role foundation

This slice adds:

- persisted Officer / Supervisor / Admin role model;
- optional officer ownership field on inspections;
- explicit draft -> pending-review lifecycle transition;
- safe draft editing;
- machine-readable domain 404/409 errors;
- migration revision 0002;
- tests for lifecycle safety and role persistence.

### Important boundary

The user model is a data foundation only. There is no password/login flow and no unauthenticated user-management API in this slice.

The inspection API does not expose a finalize action yet. Finalization is intentionally deferred until the officer-review/report phase can support it honestly.

## Still not implemented

- authentication and authorization;
- package images/captures;
- OCR and declaration extraction;
- Legal Metrology rule execution;
- officer finding review;
- PDF report generation;
- offline mobile synchronization.

## Next Phase 1 work

1. configuration/startup validation and database readiness;
2. authentication skeleton tied to the persisted user/role model;
3. inspection audit-event foundation for state-changing actions;
4. then close Phase 1 before starting image capture work.

## Validation gate

Each merged slice needs executed tests or equivalent evidence. Do not call a phase complete from static code review alone.
