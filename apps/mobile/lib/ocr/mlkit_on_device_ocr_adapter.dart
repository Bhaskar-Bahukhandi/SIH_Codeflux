import "dart:io";

import "package:google_mlkit_text_recognition/google_mlkit_text_recognition.dart";

typedef OnDeviceOcrPlatformProbe = bool Function();

class OnDeviceOcrLine {
  const OnDeviceOcrLine({
    required this.text,
    required this.confidence,
    required this.left,
    required this.top,
    required this.right,
    required this.bottom,
  });

  final String text;
  final double? confidence;
  final double left;
  final double top;
  final double right;
  final double bottom;
}

class OnDeviceOcrResult {
  const OnDeviceOcrResult({
    required this.fullText,
    required this.lines,
  });

  final String fullText;
  final List<OnDeviceOcrLine> lines;
}

/// Isolated feasibility adapter for native mobile OCR.
///
/// This adapter is intentionally not wired into the Officer synchronization
/// pipeline. The validated server PP-OCRv5 path remains authoritative until a
/// physical-device comparison establishes an approved mobile OCR role.
class MlKitOnDeviceOcrAdapter {
  MlKitOnDeviceOcrAdapter({
    TextRecognitionScript script = TextRecognitionScript.latin,
    OnDeviceOcrPlatformProbe? platformProbe,
  }) : _script = script,
       _platformProbe = platformProbe ?? _defaultPlatformProbe;

  final TextRecognitionScript _script;
  final OnDeviceOcrPlatformProbe _platformProbe;
  TextRecognizer? _recognizer;

  static bool _defaultPlatformProbe() => Platform.isAndroid || Platform.isIOS;

  bool get isSupportedPlatform => _platformProbe();

  Future<OnDeviceOcrResult> recognizeFilePath(String imagePath) async {
    if (!isSupportedPlatform) {
      throw UnsupportedError(
        "ML Kit on-device OCR is supported only on Android and iOS.",
      );
    }

    final file = File(imagePath);
    if (!await file.exists()) {
      throw FileSystemException(
        "On-device OCR image file does not exist.",
        imagePath,
      );
    }

    final recognizer = _recognizer ??= TextRecognizer(script: _script);
    final recognized = await recognizer.processImage(
      InputImage.fromFilePath(imagePath),
    );

    final lines = <OnDeviceOcrLine>[];
    for (final block in recognized.blocks) {
      for (final line in block.lines) {
        lines.add(
          OnDeviceOcrLine(
            text: line.text,
            confidence: line.confidence,
            left: line.boundingBox.left,
            top: line.boundingBox.top,
            right: line.boundingBox.right,
            bottom: line.boundingBox.bottom,
          ),
        );
      }
    }

    return OnDeviceOcrResult(
      fullText: recognized.text,
      lines: List<OnDeviceOcrLine>.unmodifiable(lines),
    );
  }

  Future<void> close() async {
    final recognizer = _recognizer;
    _recognizer = null;
    if (recognizer != null) {
      await recognizer.close();
    }
  }
}
