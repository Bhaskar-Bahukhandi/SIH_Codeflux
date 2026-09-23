# Phase 6 — Finalization and Evidence-backed Report

Status: implementation in progress

## Purpose

This slice closes the current Officer-review workflow without inventing new legal conclusions.

Finalization means the current inspection record and its reviewed declaration-evidence checks are locked into an immutable snapshot. It does **not** calculate a penalty or issue a statutory notice.

## Finalization gate

An inspection may finalize only when:

- it is in `pending_review`;
- the latest preliminary rule evaluation still matches current evidence;
- the result set is complete;
- every result has a latest Officer review;
- no latest review is `recheck_required`;
- `accepted` is used only for a supported machine `pass`;
- `corrected` supplies valid structured MRP/net-quantity evidence for a supported `pass` or `manual_verification_required` result;
- unresolved states such as `indeterminate` and `not_evaluated` remain blocked.

## Immutable snapshot

The stored finalization snapshot includes:

- inspection/product identity;
- finalizing Officer identity;
- exact rule-pack provenance;
- source rule-evaluation/extraction run IDs;
- machine status/value;
- latest Officer review/revision;
- corrected/resolved value;
- evidence capture IDs/view types/SHA-256 values;
- finalization/report IDs and timestamp;
- scope disclaimer.

A canonical JSON SHA-256 is stored with the snapshot.

## PDF report

The PDF is generated only after the finalization gate passes.

It is generated deterministically from the immutable snapshot and stored with:

- report ID;
- report version;
- storage key;
- byte size;
- SHA-256 checksum.

The report is intentionally factual and compact. It labels automated outputs as preliminary evidence checks and does not claim to be a penalty or statutory notice.

## Access

- owning Officer can read the finalized record/report;
- Supervisor/Admin can read it using existing inspection visibility;
- another Officer receives the same not-found behavior used for other private inspection resources.

## Deferred

- penalties;
- statutory notice generation;
- Supervisor override;
- digital signing infrastructure;
- physical/font-size measurement;
- broader declaration/rule coverage.
