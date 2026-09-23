import "dart:io";
import "dart:typed_data";

import "package:flutter_test/flutter_test.dart";

import "package:codeflux_mobile/offline/storage/local_evidence_store.dart";

void main() {
  late Directory tempDirectory;
  late LocalEvidenceStore store;

  setUp(() async {
    tempDirectory = await Directory.systemTemp.createTemp(
      "codeflux_evidence_test_",
    );
    store = LocalEvidenceStore(tempDirectory);
  });

  tearDown(() async {
    if (await tempDirectory.exists()) {
      await tempDirectory.delete(recursive: true);
    }
  });

  test("same stable evidence ID accepts only identical bytes", () async {
    final bytes = Uint8List.fromList(<int>[1, 2, 3, 4, 5]);

    final first = await store.persistBytes(
      inspectionId: "inspection_1",
      evidenceId: "evidence_1",
      bytes: bytes,
      originalFilename: "front.jpg",
    );
    final replay = await store.persistBytes(
      inspectionId: "inspection_1",
      evidenceId: "evidence_1",
      bytes: bytes,
      originalFilename: "front.jpg",
    );

    expect(replay.path, first.path);
    expect(replay.sha256, first.sha256);
    expect(await store.verify(first), isTrue);

    expect(
      () => store.persistBytes(
        inspectionId: "inspection_1",
        evidenceId: "evidence_1",
        bytes: Uint8List.fromList(<int>[9, 9, 9]),
        originalFilename: "front.jpg",
      ),
      throwsA(isA<StateError>()),
    );
    expect(await store.verify(first), isTrue);
  });

  test("local evidence cannot be deleted before remote confirmation", () async {
    final evidence = await store.persistBytes(
      inspectionId: "inspection_2",
      evidenceId: "evidence_2",
      bytes: Uint8List.fromList(<int>[10, 20, 30]),
      originalFilename: "detail.png",
    );

    expect(
      () => store.deleteAfterRemoteConfirmation(
        evidence,
        remoteDurabilityConfirmed: false,
      ),
      throwsA(isA<StateError>()),
    );
    expect(await store.verify(evidence), isTrue);

    await store.deleteAfterRemoteConfirmation(
      evidence,
      remoteDurabilityConfirmed: true,
    );
    expect(File(evidence.path).existsSync(), isFalse);
  });
}
