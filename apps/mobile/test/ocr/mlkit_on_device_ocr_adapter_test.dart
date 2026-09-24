import "dart:io";

import "package:flutter_test/flutter_test.dart";

import "package:codeflux_mobile/ocr/mlkit_on_device_ocr_adapter.dart";

void main() {
  test("reports unsupported platform without invoking native ML Kit", () async {
    final adapter = MlKitOnDeviceOcrAdapter(
      platformProbe: () => false,
    );

    expect(adapter.isSupportedPlatform, isFalse);
    await expectLater(
      adapter.recognizeFilePath("/tmp/does-not-matter.jpg"),
      throwsA(isA<UnsupportedError>()),
    );

    await adapter.close();
  });

  test("validates local file before invoking native ML Kit", () async {
    final adapter = MlKitOnDeviceOcrAdapter(
      platformProbe: () => true,
    );

    expect(adapter.isSupportedPlatform, isTrue);
    await expectLater(
      adapter.recognizeFilePath("/tmp/codeflux-missing-ocr-image.jpg"),
      throwsA(isA<FileSystemException>()),
    );

    await adapter.close();
  });
}
