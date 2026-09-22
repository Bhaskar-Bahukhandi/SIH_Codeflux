# Conservative Perspective / Geometry Handling

## Purpose

This layer attempts to identify a clearly planar, dominant quadrilateral in the normalized package image and optionally creates a perspective-corrected derivative.

It is deliberately conservative. Many real packages are curved, flexible, wrinkled or partially visible. In those cases the correct system behavior is to keep the normalized image as the fallback rather than force a geometric transform.

## Inputs

Geometry analysis uses the latest normalized derivative produced by the quality/preprocessing stage.

Before analysis, the derivative bytes are re-hashed and checked against the stored SHA-256 value.

If preprocessing has not been run, geometry analysis returns an explicit `capture_preprocessing_required` conflict.

## v1 detection

The v1 detector uses OpenCV:

1. grayscale conversion;
2. mild Gaussian blur;
3. Canny edges;
4. morphological closing;
5. external contours;
6. four-point polygon approximation;
7. convexity, area, minimum-side and angle checks.

The strongest plausible candidate is scored using:

- quadrilateral area ratio;
- right-angle quality.

The resulting `geometry_score` is an engineering heuristic. It is not a calibrated probability or legal confidence score.

## States

### `not_detected`

No quadrilateral passes the minimum geometric gates.

No perspective-corrected derivative is created.

### `review_recommended`

A plausible quadrilateral exists, but its geometry score does not pass the correction gate or the transform cannot be produced safely.

No automatic correction is created.

### `correction_available`

The candidate passes the correction gate.

A new `perspective_corrected` JPEG derivative is created. The source normalized derivative remains unchanged and continues to be a valid fallback.

## Provenance

Each assessment stores:

- source normalized derivative ID;
- optional corrected derivative ID;
- ordered corner coordinates;
- area ratio;
- angle score;
- geometry score;
- reasons;
- threshold snapshot;
- algorithm version;
- creation timestamp.

Current versions:

- geometry algorithm: `geometry-v1`
- corrected derivative processing: `perspective-v1`

## Configuration

Default thresholds are provisional engineering values, not Legal Metrology requirements.

They are configurable because they must be tuned against real package imagery before field claims are made.

Material behavior changes require a new algorithm version and regression evidence.

## Safety / fallback

- Never overwrite original evidence.
- Never overwrite the normalized derivative.
- Never force a transform when no reliable quadrilateral is found.
- Curved/flexible packages may legitimately remain uncorrected.
- OCR must be able to use the normalized derivative when correction is unavailable.
- A geometry result must never be presented as a compliance finding.

## Not included

This layer does not perform:

- OCR;
- text-region detection;
- declaration extraction;
- physical dimension/font measurement;
- Legal Metrology rule evaluation.