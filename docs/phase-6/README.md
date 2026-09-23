# Phase 6 — Officer Verification Layer

Status: initial implementation in progress

## Goal

Add a human verification layer over preliminary automated rule results without mutating machine evidence or prematurely producing a final legal verdict.

## First slice

The first Phase 6 slice adds append-only Officer review records for the latest preliminary rule-evaluation results.

Decisions:

- `accepted`
- `corrected`
- `recheck_required`

## Meaning of decisions

### accepted

The officer has reviewed the current preliminary rule result and its supporting evidence and accepts it for the current workflow stage.

This is **not** final legal approval of the inspection.

### corrected

The officer records a separate structured corrected value and a required explanatory note.

The OCR text, declaration observation, fused summary and rule result remain unchanged.

### recheck_required

The officer explicitly records that evidence must be recaptured, reprocessed or re-evaluated before later finalization.

A note is required so the reason is auditable.

## Lifecycle boundary

Rule review is permitted only after an inspection reaches `pending_review`.

The owning Officer creates review records.

Supervisor/Admin may read review history through the existing inspection visibility rules but cannot mutate Officer review decisions in this slice.

## Append-only rule

Reviews are revisioned rather than overwritten.

A later review of the same rule result creates revision 2, revision 3, and so on. History remains visible.

## Current boundaries

This slice does not:

- finalize an inspection;
- create a final violation finding;
- calculate a penalty;
- issue a notice;
- let a Supervisor replace an Officer decision;
- alter OCR/extraction/rule-engine records.

A later finalization/report phase may require every relevant latest rule result to have an acceptable resolved review state.
