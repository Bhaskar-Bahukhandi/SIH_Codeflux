# Phase 6 Officer Review Slice — Validation Checklist

Status: implementation complete; execution gate pending

## Functional checks

- [ ] owning Officer can review a result from the latest rule-evaluation run after submission;
- [ ] draft inspection rejects Officer rule review;
- [ ] result from an older rule-evaluation run is rejected;
- [ ] latest rule evaluation is rejected if later capture/OCR evidence makes its source extraction stale;
- [ ] other Officer cannot review another Officer's inspection;
- [ ] Supervisor/Admin can read review history but cannot create Officer reviews;
- [ ] accepted review is append-only and auditable;
- [ ] corrected review requires a note and structured corrected value;
- [ ] MRP correction normalizes to INR + two-decimal amount;
- [ ] net-quantity correction accepts only the currently supported normalized units;
- [ ] non-finite/extreme correction numbers fail explicitly rather than causing a server error;
- [ ] recheck_required requires a note;
- [ ] repeated review creates a higher revision without overwriting history;
- [ ] a latest recheck_required review can reopen pending_review -> draft;
- [ ] an accepted review that supersedes recheck_required blocks reopening;
- [ ] reopened inspection cannot be re-submitted against the unchanged old rule evaluation;
- [ ] a fresh rule-evaluation run after reopen allows resubmission;
- [ ] evidence changed after that fresh evaluation blocks resubmission until evaluation is refreshed again;
- [ ] review/reopen actions emit audit events.

## Persistence and migration

- [ ] complete Alembic chain upgrades through revision 0011;
- [ ] downgrade to base succeeds;
- [ ] re-upgrade from base through 0011 succeeds;
- [ ] officer_rule_reviews uniqueness/revision constraint is enforced;
- [ ] reopened_for_recheck_at persists correctly.

## Regression

- [ ] complete API regression suite passes after Phase 6 changes;
- [ ] prior capture/preprocessing/OCR/declaration/rule-engine tests remain green.

## Scope checks

- [x] machine OCR/extraction/rule results are not edited by Officer review;
- [x] no final legal verdict is introduced;
- [x] no penalty/notice logic is introduced;
- [x] no Supervisor override is introduced;
- [x] report/finalization implementation is isolated to follow-up issue #34.

## Infrastructure note

GitHub-hosted Actions currently fails before runner steps execute and is tracked in #30.

A red Actions badge with zero executed steps must not be interpreted as a project-test failure. This checklist remains open until the regression and migration commands actually execute in a working environment.
