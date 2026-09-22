# Contributing to SIH Codeflux

This repository follows the approved CODEFLUX Foundation Blueprint and Development Roadmap.

## Working rules

1. Keep `main` stable.
2. Use a phase or feature branch for changes.
3. Do not add optional product features without an explicit scope decision.
4. Do not hard-code compliance verdicts or demo outputs and present them as real processing.
5. Every implemented Legal Metrology rule must have a verified official source and version/effective-date note.
6. Preserve original evidence when transformations, OCR corrections, or officer corrections are introduced.
7. Low-confidence or unsupported cases must fail safely to review/recheck.
8. Add tests with implementation changes once executable modules exist.
9. Prefer small, reversible commits.
10. Document assumptions and known limitations.

## Branch naming

- `phase/<number>-<name>`
- `feature/<short-name>`
- `fix/<short-name>`
- `docs/<short-name>`

## Pull requests

A pull request should state:

- what changed;
- why it belongs in current scope;
- validation performed;
- known limitations;
- rollback/fallback path;
- whether blueprint/roadmap assumptions changed.

No phase is complete until its exit criteria are evidenced.
