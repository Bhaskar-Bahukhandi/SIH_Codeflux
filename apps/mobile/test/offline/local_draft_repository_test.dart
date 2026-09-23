import "dart:io";

import "package:flutter_test/flutter_test.dart";
import "package:path/path.dart" as p;
import "package:sqflite_common_ffi/sqflite_ffi.dart";

import "package:codeflux_mobile/offline/models/sync_state.dart";
import "package:codeflux_mobile/offline/persistence/local_draft_repository.dart";
import "package:codeflux_mobile/offline/persistence/offline_database.dart";

void main() {
  late Directory tempDirectory;
  late String databasePath;
  late OfflineDatabase offlineDatabase;
  late LocalDraftRepository drafts;

  setUpAll(() {
    sqfliteFfiInit();
  });

  setUp(() async {
    tempDirectory = await Directory.systemTemp.createTemp(
      "codeflux_draft_test_",
    );
    databasePath = p.join(tempDirectory.path, "offline.sqlite3");
    offlineDatabase = await OfflineDatabase.openAt(
      databasePath,
      factory: databaseFactoryFfi,
    );
    drafts = LocalDraftRepository(offlineDatabase);
  });

  tearDown(() async {
    await offlineDatabase.close();
    if (await tempDirectory.exists()) {
      await tempDirectory.delete(recursive: true);
    }
  });

  test("inspection and evidence metadata survive database reopen", () async {
    const inspectionId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
    const evidenceId = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
    final createdAt = DateTime.utc(2026, 9, 23, 16);

    final inspection = await drafts.createInspection(
      id: inspectionId,
      officerUserId: "officer-1",
      productName: "  Local Product  ",
      productIdentifier: " LOCAL-001 ",
      now: createdAt,
    );
    expect(inspection.productName, "Local Product");
    expect(inspection.productIdentifier, "LOCAL-001");
    expect(inspection.syncState, SyncState.localOnly);

    await drafts.registerEvidence(
      id: evidenceId,
      inspectionId: inspectionId,
      viewType: "front",
      localPath: "/local/evidence/front.jpg",
      sha256: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      sizeBytes: 123,
      now: createdAt.add(const Duration(seconds: 1)),
    );

    await offlineDatabase.close();
    offlineDatabase = await OfflineDatabase.openAt(
      databasePath,
      factory: databaseFactoryFfi,
    );
    drafts = LocalDraftRepository(offlineDatabase);

    final reopenedInspection = await drafts.getInspection(inspectionId);
    final reopenedEvidence = await drafts.getEvidence(evidenceId);

    expect(reopenedInspection, isNotNull);
    expect(reopenedInspection!.productName, "Local Product");
    expect(reopenedInspection.syncState, SyncState.localOnly);
    expect(reopenedEvidence, isNotNull);
    expect(reopenedEvidence!.inspectionId, inspectionId);
    expect(
      reopenedEvidence.sha256,
      "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    );
    expect(reopenedEvidence.syncState, SyncState.localOnly);
  });

  test("stable local IDs are idempotent but reject changed data", () async {
    const inspectionId = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";

    final first = await drafts.createInspection(
      id: inspectionId,
      officerUserId: "officer-1",
      productName: "Product",
    );
    final replay = await drafts.createInspection(
      id: inspectionId,
      officerUserId: "officer-1",
      productName: "Product",
    );
    expect(replay.id, first.id);

    await expectLater(
      drafts.createInspection(
        id: inspectionId,
        officerUserId: "officer-1",
        productName: "Different Product",
      ),
      throwsA(isA<StateError>()),
    );
  });
}
