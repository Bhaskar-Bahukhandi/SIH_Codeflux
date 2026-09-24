# Mobile On-Device OCR Feasibility

Issue: #43

Status: feasibility spike in progress

## Question

Can CODEFLUX add an optional on-device OCR capability to the Flutter Officer app without replacing or destabilizing the validated server PP-OCRv5 path?

## Candidate

The spike uses `google_mlkit_text_recognition` 0.17.1 as a Flutter bridge to native Google ML Kit Text Recognition.

The candidate is intentionally isolated behind `MlKitOnDeviceOcrAdapter`. It is not injected into `AppDependencies`, the offline queue, declaration extraction, rule evaluation, or any Officer UI.

Therefore adding/removing this feasibility adapter does not change current inspection semantics.

## Why this candidate

Current upstream documentation indicates:

- Android and iOS are supported; desktop/web are not;
- Latin-script recognition is available locally on supported mobile devices;
- Android supports bundled and Google-Play-services-delivered text-recognition models;
- the Flutter wrapper requires a modern Flutter/Dart toolchain compatible with the repository's Flutter 3.47.5 baseline;
- the wrapper documents iOS 15.5+ and modern Android SDK requirements.

CODEFLUX currently needs Latin-script package text for the frozen prototype scope, so the default Latin recognizer is sufficient for the spike. Additional script packages are not being added.

## Validation levels

### Repository/contract validation

A passing ordinary Flutter gate proves:

- dependency resolution succeeds;
- the adapter type-checks;
- unsupported platforms are rejected before invoking native APIs;
- the server OCR path and existing tests remain unchanged.

### Android native build validation

The dedicated feasibility workflow generates an ephemeral Android runner and builds a debug APK.

A green Android build proves the native ML Kit plugin can be linked into the current Flutter application/toolchain. It does not prove recognition accuracy or physical-device runtime behavior.

### Physical-device runtime validation

This remains **EXTERNAL EVIDENCE REQUIRED**.

A real Android/iOS device is needed to measure:

- first-run/model availability behavior;
- recognition latency;
- memory/battery impact;
- OCR output on actual package captures;
- offline behavior with the selected model-installation path;
- comparison with server PP-OCRv5.

## Integration decision rule

Do not make on-device OCR authoritative in this spike.

The server PP-OCRv5 pipeline remains the validated source for persisted OCR evidence. On-device OCR may later be considered for capture-time hints or offline assistance only after physical-device comparison shows acceptable behavior and the evidence/provenance model is explicitly designed.

## Platform bootstrap impact

The existing guarded platform bootstrap is updated to iOS 15.5 because the candidate Flutter ML Kit wrapper does not support the previously documented iOS 13.0 floor.

Android bootstrap keeps minSdk 24, which is above the candidate's minimum requirement. The bootstrap organization is `org.sih.codeflux`; the previous `in.sih.codeflux` value caused Flutter's Kotlin templates to escape `in` and Gradle rejected the resulting namespace before any native platform files had been committed.

## Exit classification

- Flutter dependency/analyzer/tests green: **PASS — adapter/repository compatibility**.
- Ephemeral Android APK build green: **PASS — Android native build feasibility**.
- Actual on-device OCR execution: **EXTERNAL EVIDENCE REQUIRED** until a physical device is available.
