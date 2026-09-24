# ADR 0003 — Mobile OCR Feasibility for the SIH Prototype

Status: Accepted feasibility decision; runtime/device validation pending  
Date: 2026-09-24

## Context

ADR 0002 intentionally deferred the mobile OCR runtime decision. It required the OCR/extraction boundary to remain compatible with both server-side and possible on-device processing, and required a dedicated technical spike before full offline automated analysis could be considered complete.

The current CODEFLUX mobile application is Flutter. The checked-in mobile package does not yet include committed Android/iOS runner projects; native platform scaffolding remains guarded by the existing bootstrap process.

The validated server baseline is PP-OCRv5 through PaddleOCR 3.7.0 + PaddlePaddle 3.2.2 on CPU.

## Evidence reviewed

Official PaddleOCR documentation now provides an Android deployment example with:

- a reusable Android SDK module;
- AAR integration into third-party Android applications;
- ONNX Runtime inference;
- text detection + recognition;
- support for PP-OCRv5 mobile detection/recognition models;
- Android minSdk 26;
- JDK 17 / Kotlin native integration.

Official sources reviewed for this spike:

- https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/inference_deployment/cross_platform/android_deployment.en.md
- https://github.com/PaddlePaddle/PaddleOCR/blob/main/configs/det/PP-OCRv5/PP-OCRv5_mobile_det.yml
- https://github.com/PaddlePaddle/PaddleOCR/blob/main/configs/rec/PP-OCRv5/PP-OCRv5_mobile_rec.yml

The repository also still contains the older Paddle-Lite mobile deployment path, but the current Android documentation uses ONNX Runtime and an SDK/AAR structure. The current spike therefore prefers the documented Android SDK/ONNX Runtime path rather than introducing a legacy Paddle-Lite integration.

## Decision

### Android feasibility

**FEASIBLE, NOT YET IMPLEMENTED.**

For an Android implementation, the preferred boundary is:

```text
Flutter/Dart
    |
    | MethodChannel / platform plugin boundary
    v
Android Kotlin adapter
    |
    v
PaddleOCR Android SDK (AAR)
    |
    v
ONNX Runtime + PP-OCRv5 mobile det/rec models
```

The native adapter must return the same evidence concepts required by CODEFLUX:

- ordered text blocks;
- recognized text;
- recognition confidence;
- bounding polygon/box coordinates;
- model/runtime version metadata;
- source image identity/checksum.

It must not directly create Legal Metrology findings. Declaration extraction and rule evaluation remain separate responsibilities.

### Current SIH execution path

The existing server OCR path remains the **canonical validated path for the SIH prototype**.

Do not replace it with an unvalidated native adapter before the demo.

On-device OCR may later be used to improve offline assistance, but results must remain traceable and must not silently overwrite canonical server evidence.

### iOS

The current spike does **not** establish iOS feasibility. No iOS-native PaddleOCR integration was executed or validated. Cross-platform Flutter support must therefore not be claimed from the Android evidence.

## Why implementation is deferred

The repository currently has no committed native Android/iOS runner projects. Implementing an Android OCR adapter now would require:

1. generating/reviewing the guarded native Flutter platform scaffolding;
2. integrating the official Android OCR SDK/AAR;
3. packaging PP-OCRv5 mobile ONNX models;
4. defining the Flutter platform-channel contract;
5. measuring APK/model size and memory;
6. validating on at least one physical ARM64 Android device;
7. comparing on-device output against the canonical server OCR evidence.

Those are device-native validation tasks, not necessary to prove the existing server-backed SIH workflow.

## Required future runtime spike

Before CODEFLUX claims offline automated OCR on Android, execute all of:

1. generate Android scaffolding with the guarded repository bootstrap;
2. integrate the official PaddleOCR Android SDK without changing server behavior;
3. run one representative package image through the native adapter;
4. record model load success, inference completion, latency and memory;
5. preserve block text/confidence/geometry provenance;
6. compare the output shape with the server OCR contract;
7. verify airplane-mode execution;
8. verify app restart does not corrupt/download partial model assets;
9. run on a physical ARM64 Android device.

If any of these fail, retain the server OCR fallback.

## Scope consequence

This spike resolves the **architecture feasibility question**:

- Android on-device OCR: feasible via documented native SDK/AAR + ONNX Runtime;
- implementation: deferred;
- physical-device runtime evidence: still required before claiming offline OCR capability;
- server processing: remains the current validated SIH path.

This decision does not expand Legal Metrology coverage, alter OCR accuracy claims, or make physical-device validation pass.
