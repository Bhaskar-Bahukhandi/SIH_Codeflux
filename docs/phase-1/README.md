# Phase 1 — Data Foundation

Status: In progress

## Goal

Create the first executable foundation for inspections without introducing OCR, compliance judgments, or UI behavior prematurely.

## First vertical slice

The initial backend slice must prove that:

1. the API starts;
2. health status is available;
3. an inspection draft can be created from real request data;
4. the record receives a stable identifier and timestamps;
5. the draft can be retrieved again;
6. multiple saved records can be listed;
7. a missing record fails explicitly with 404;
8. automated tests exercise those behaviors with isolated persistence.

## Not implemented in this slice

- authentication;
- officer/supervisor authorization;
- package images;
- OCR;
- declarations;
- rule evaluation;
- reports;
- offline mobile synchronization.

These remain later Phase 1/roadmap tasks and must not be simulated with placeholder success responses.

## Next Phase 1 steps

1. add proper schema migrations;
2. extend the core data model toward user/role and inspection lifecycle;
3. define API error conventions;
4. add configuration validation and startup checks;
5. create the mobile local-draft model only after backend identifiers/state are stable enough to mirror safely.

## Validation gate

Do not merge this slice based only on code review. Run the API tests in a real Python environment or working CI runner and record the result in the pull request.
