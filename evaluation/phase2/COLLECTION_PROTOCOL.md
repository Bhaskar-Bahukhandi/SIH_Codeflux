# Phase 2 Real-Package Collection Protocol

This protocol is for the real-package image-quality and perspective-geometry evidence gate in issue #43.

It does not define a new Legal Metrology rule and does not measure OCR or declaration accuracy.

## 1. What to photograph

Use ordinary retail pre-packaged products consistent with the current SIH demo scope, such as biscuit/chips-style packets.

Prefer several different physical packages rather than many nearly identical photographs of one package.

For each package, intentionally collect a mix of:

- readable, well-lit, approximately front-facing views;
- mild perspective/angle cases;
- strong angle or distorted-package cases;
- mild blur;
- clearly blurred or motion-affected cases;
- low-light cases;
- glare/reflection cases where applicable.

Do not edit a photograph to make it look better or worse after capture.

## 2. Keep the original evidence

Place the original image files under the ignored local directory:

```text
evaluation/phase2/images/
```

Do not overwrite an original after it has been entered in the manifest.

Use stable filenames such as:

```text
package-001-front.jpg
package-001-angle.jpg
package-002-lowlight.jpg
```

The validation report records a SHA-256 digest for each image, so a changed file will produce different provenance.

## 3. Label before seeing CODEFLUX output

Human expected labels must be assigned **before** running the validation harness for that image.

This reduces confirmation bias.

Do not:

1. run CODEFLUX;
2. see its predicted status;
3. choose the expected label to match the prediction.

If a label is genuinely uncertain, leave the expected field blank and explain why in `notes`. An unlabeled real image is still useful for observed metrics but does not count toward agreement.

## 4. Quality labels

Use exactly one of these values when a human label is defensible:

### `pass`

The image is reasonably readable for downstream machine processing. It does not have a clear capture-quality defect that should trigger review or retake.

### `review_recommended`

The image has a noticeable quality concern, but a human reviewer could reasonably decide that it is still usable.

Examples may include moderate glare, borderline lighting or moderate softness.

### `retake_recommended`

The capture has a clear quality problem severe enough that a new photograph should be preferred.

Examples may include severe blur, unusable darkness/overexposure or strong glare obscuring relevant package content.

These are capture-quality labels only. They are not compliance findings.

## 5. Geometry labels

Use exactly one of:

### `not_detected`

No supported correction candidate is defensibly detected.

This includes both approximately front-facing images that do not need correction and difficult/irregular views where the current conservative detector cannot provide a supported correction.

### `review_recommended`

Perspective/shape conditions are ambiguous enough that automatic correction should not be trusted without review.

### `correction_available`

A defensible package-plane correction candidate is visibly present and the supported detector should reasonably be able to offer correction.

These labels evaluate the current conservative geometry heuristic, not physical-package compliance.

## 6. Manifest entry

Copy `manifest.example.csv` to the ignored local `manifest.csv` and add one row per image.

Required columns:

```text
case_id,image_path,dataset_type,expected_quality_status,expected_geometry_status,notes
```

For real evidence use:

```text
dataset_type=real_package
```

Keep `case_id` stable even if filenames are later reorganized before the evidence run. After an evidence report is accepted, do not silently reuse that case ID for a different image.

## 7. First evidence run

Do a non-gating observation run first:

```bash
cd services/api
python -m app.cli.validate_phase2 \
  --manifest ../../evaluation/phase2/manifest.csv \
  --output ../../evaluation/reports/phase2-observation.json
```

Review:

- dataset counts;
- warnings;
- per-image metrics;
- mismatch case IDs;
- manifest SHA-256;
- image SHA-256 values.

Only after the labels and dataset have been reviewed should the team select and document explicit minimum-count/mismatch gates.

Do not copy the example threshold counts from the README and call them project requirements unless the team explicitly adopts them.

## 8. Evidence integrity

A shareable Phase 2 result should retain together:

- the generated JSON report;
- the exact local manifest used;
- the original images;
- the commit SHA of the code used for the run;
- a short note identifying who performed the human labeling and when.

The report intentionally stores manifest-relative image paths rather than a developer's absolute machine path, while SHA-256 digests identify the exact manifest and image bytes.

## 9. What a successful run proves

It can support a statement about agreement of the current image-quality and geometry statuses on the reviewed real-package sample.

It does **not** by itself prove:

- OCR accuracy;
- declaration extraction accuracy;
- Legal Metrology compliance accuracy;
- physical font-size measurement accuracy;
- production readiness.
