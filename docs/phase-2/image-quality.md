# Image Quality and Preprocessing Foundation

## Purpose

This layer decides whether an image is technically suitable for later OCR/extraction work. It does **not** decide Legal Metrology compliance.

## Original evidence vs derivative

The uploaded package image remains immutable evidence.

Processing creates a separate normalized JPEG derivative:

`original capture -> integrity check -> EXIF orientation normalization -> derivative -> quality metrics`

The derivative has its own:

- ID;
- storage key;
- SHA-256 checksum;
- dimensions;
- processing version;
- creation timestamp.

The original storage object and original checksum are never replaced.

## Quality metrics in v1

### Sharpness

Measured using variance of the Laplacian on the normalized grayscale image.

This is useful for obvious blur detection but is not treated as a universal perceptual-quality score.

### Brightness / exposure

The processor records:

- mean grayscale brightness;
- fraction of very dark pixels;
- fraction of very bright pixels.

These metrics are used only to recommend retaking or reviewing an image before OCR.

### Glare risk

A high-intensity, low-saturation mask is split into connected components. Very large white regions are excluded from the glare fraction so a white package background is not automatically treated as glare.

This remains a heuristic and requires validation on the project's real package-image dataset.

## Outcomes

Each run produces one of:

- `pass`
- `review_recommended`
- `retake_recommended`

A result is capture guidance, not a legal finding.

Examples:

- low sharpness -> retake/review;
- severe underexposure -> retake;
- borderline brightness -> review;
- possible local glare -> review/retake.

## Versioning

Current versions:

- preprocessing: `normalize-v1`
- quality algorithm: `quality-v1`

Every assessment stores the threshold snapshot used for that run. This allows later tuning without pretending old results used new thresholds.

## Threshold policy

Default values are configuration, not law.

They are intentionally exposed through environment settings so they can be tuned against a golden image dataset.

Threshold changes should require:

1. validation dataset results;
2. reason for the change;
3. false-retake / missed-bad-image comparison;
4. a new quality algorithm version when behavior materially changes.

## Not implemented in this slice

- automatic perspective correction;
- package/label boundary detection;
- OCR;
- declaration extraction;
- font-size measurement;
- legal rules.

Perspective correction is intentionally deferred until the geometric method and failure conditions are validated.