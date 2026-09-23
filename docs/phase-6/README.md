# Phase 6 — Officer Finding Verification

Status: foundation implementation in progress

## Goal

Add the explicit human decision layer after versioned rule evaluation while preserving every machine-produced result unchanged.

The traceability chain is now intended to be:

`Inspection -> Capture -> OCR -> Declaration -> Rule Evaluation -> Officer Review`

Reporting/finalization remains a later phase.

## Officer decisions

For a current, reviewable rule result, the owning Officer may record one of four append-only actions:

- `confirm_present` — the declaration is visually confirmed on package evidence;
- `confirm_absent` — the Officer explicitly confirms physical absence;
- `correct_value` — the declaration is present but the machine-extracted structured value is corrected;
- `request_recheck` — evidence should be captured/processed/OCR'd/evaluated again.

## Preliminary outcomes

Officer actions derive one of these review outcomes:

- `verified_declaration_present`;
- `potential_non_compliance`;
- `recheck_required`.

`potential_non_compliance` is created only from explicit Officer-confirmed absence under a current supported rule evaluation. Machine OCR/extraction `not_detected` remains insufficient by itself.

This is still not a final legal verdict.

## Correction provenance

A corrected value is stored separately from the machine result.

The original:

- OCR blocks;
- declaration observation;
- fusion summary;
- rule result;

remain immutable and queryable.

For the current two declaration types, corrections are normalized only to the existing structured forms:

- MRP: INR + positive amount;
- net quantity: positive value + g/kg/ml/l.

This validation is a data-shape safeguard, not a new Legal Metrology rule.

## Evidence references

Present/absent/correction decisions require at least one capture from the same inspection.

A recheck request may be recorded without selecting a specific capture, but requires an Officer note.

## Freshness

Review is allowed only against the latest rule-evaluation run while its declaration/OCR provenance is still current.

If capture preprocessing or OCR changes, the rule evaluation becomes stale and must be refreshed before more review decisions are added.

Old reviews remain as append-only history.

## Role boundary

- owning Officer: create review records while inspection is draft;
- Supervisor/Admin: read the current review workspace/history;
- Supervisor does not overwrite Officer review decisions.

## Not included yet

- inspection finalization;
- submission completeness gate;
- PDF report generation;
- penalties/notices;
- new Legal Metrology rule coverage;
- physical font-size measurement;
- offline synchronization.
