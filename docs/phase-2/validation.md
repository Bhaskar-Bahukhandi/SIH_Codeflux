# Phase 2 Validation Record

## Automated / reconstructed branch validation

For the current Phase 2 geometry slice:

- complete reconstructed API regression suite: **43 passed**;
- application/test/migration source: Python `compileall` passed;
- migration chain: `0001 -> 0002 -> 0003 -> 0004 -> 0005 -> 0006 -> 0007` passed on a clean SQLite validation database;
- migration `0007 -> 0006 -> 0007` downgrade/re-upgrade passed.

## Geometry cases validated

Synthetic integration coverage verifies:

- clear large planar quadrilateral -> `correction_available`;
- plausible but below correction gate -> `review_recommended`;
- no reliable quadrilateral -> `not_detected`;
- source normalized derivative remains unchanged after correction;
- perspective derivative checksum matches retrieved bytes;
- preprocessing is required before geometry analysis;
- tampered normalized derivative is blocked by SHA-256 integrity check;
- supervisors can read but cannot perform geometry processing;
- another officer cannot access/process an inspection they do not own;
- geometry processing is blocked after inspection submission;
- geometry analysis is audit-traced.

## Important limitation

The quality and geometry thresholds have **not yet been calibrated on a representative real package-image dataset**.

Synthetic tests prove implementation mechanics, fallback behavior and deterministic gates. They do not establish field accuracy.

Before making accuracy claims, the project still needs a small labelled set containing examples such as:

- flat cartons/labels;
- flexible packets;
- curved bottles/containers;
- partial package views;
- glare and shadows;
- severe perspective;
- low-light and motion blur;
- packages where no correction should be attempted.

Threshold tuning must preserve the safe fallback principle: an ambiguous image should remain normalized/reviewable rather than receive a forced perspective correction.

## Hosted CI note

The repository's GitHub-hosted Actions job continues to fail before a runner is assigned (empty step list / runner ID 0). Until that external runner issue is resolved, executed local/reconstructed validation is recorded explicitly instead of being described as passing hosted CI.
