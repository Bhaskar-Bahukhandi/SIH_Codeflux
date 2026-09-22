# Evaluation

Evaluation grows with each implementation phase and must distinguish synthetic regression evidence from real-world validation.

Current evaluation areas include:

- Phase 2 image-quality / geometry validation;
- Phase 3 OCR text-fidelity validation;
- Phase 4 declaration-extraction ground truth;
- rule-level compliant / potential-issue / uncertain cases;
- officer-correction traceability;
- report consistency checks;
- offline disconnect/restart/reconnect scenarios;
- authorization tests;
- regression tests.

## Evidence rule

A module is not considered validated only because its unit tests pass or its UI appears to work.

Synthetic data is useful for deterministic regression tests, but it must not be presented as proof of field performance.

- Phase 2: see `evaluation/phase2/README.md`.
- Phase 3 OCR: see `evaluation/phase3/README.md`.
- Phase 4 declaration extraction: see `evaluation/phase4/README.md`.
