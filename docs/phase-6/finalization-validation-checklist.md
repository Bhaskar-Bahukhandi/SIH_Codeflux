# Phase 6 Finalization / Report Validation Checklist

Status: implementation complete; execution gate pending

## Finalization gate

- [ ] inspection must be pending_review;
- [ ] latest preliminary rule evaluation must still match current evidence;
- [ ] every latest result must have a latest Officer review;
- [ ] latest recheck_required review blocks finalization;
- [ ] accepted resolves only a supported machine pass;
- [ ] corrected resolves a supported pass or manual_verification_required result with valid structured evidence;
- [ ] indeterminate / not_evaluated / not_applicable / unsupported states remain blocked;
- [ ] another Officer cannot finalize an inspection they do not own.

## Immutable snapshot

- [ ] inspection/product identity is stored;
- [ ] finalizing Officer identity and timestamp are stored;
- [ ] exact rule-pack ID/version/SHA-256 and logical snapshot are preserved;
- [ ] machine result/value is preserved;
- [ ] latest Officer review ID/revision/decision is preserved;
- [ ] corrected/resolved value is stored separately from machine evidence;
- [ ] evidence capture ID/view/SHA-256 references are stored;
- [ ] canonical snapshot SHA-256 is stable.

## PDF

- [ ] PDF is generated only after the gate passes;
- [ ] PDF begins with a valid PDF header and is retrievable as application/pdf;
- [ ] PDF contains report ID/version and snapshot integrity checksum;
- [ ] PDF labels automated output as preliminary evidence checks;
- [ ] deterministic regeneration from the same snapshot produces byte-identical output;
- [ ] stored report SHA-256 matches retrieved bytes;
- [ ] tampered report bytes are rejected instead of served.

## Lifecycle and access

- [ ] inspection status becomes finalized in the same successful transaction;
- [ ] finalized inspection cannot be edited/reopened through draft/recheck endpoints;
- [ ] owning Officer can retrieve finalization/report;
- [ ] Supervisor/Admin can retrieve finalization/report;
- [ ] another Officer receives not-found behavior;
- [ ] finalization emits an audit event;
- [ ] no update/delete API exists for finalization snapshots.

## Migration / regression

- [ ] migration chain upgrades through 0012;
- [ ] downgrade base succeeds;
- [ ] re-upgrade to 0012 succeeds;
- [ ] complete API regression suite passes;
- [ ] all focused finalization/report tests pass.

## Scope boundaries

- [x] no penalty calculation;
- [x] no statutory notice generation;
- [x] no Supervisor override;
- [x] no invented violation status;
- [x] no physical/font-size measurement;
- [x] report file hash is stored externally while the PDF embeds the immutable snapshot checksum, avoiding a self-referential checksum design.
