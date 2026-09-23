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
    expect(inspection.officerUserId, "officer-1");
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
    expect(reopenedInspection.officerUserId, "officer-1");
    expect(reopenedInspection.syncState, SyncState.localOnly);
    expect(reopenedEvidence, isNotNull);
    expect(reopenedEvidence!.inspectionId, inspectionId);
    expect(
      reopenedEvidence.sha256,
      "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    );
    expect(reopenedEvidence.syncState, SyncState.localOnly);
  });

  test("schema v1 upgrade preserves legacy ownership as unknown", () async {
    final legacyPath = p.join(tempDirectory.path, "legacy.sqlite3");
    final legacy = await databaseFactoryFfi.openDatabase(
      legacyPath,
      options: OpenDatabaseOptions(
        version: 1,
        onCreate: (db, version) async {
          await db.execute("""
            CREATE TABLE local_inspections (
              id TEXT PRIMARY KEY,
              product_name TEXT NOT NULL,
              product_identifier TEXT,
              sync_state TEXT NOT NULL,
              remote_id TEXT,
              last_error_kind TEXT,
              last_error_code TEXT,
              last_error_message TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
          """);
          await db.execute("""
            CREATE TABLE local_evidence (
              id TEXT PRIMARY KEY,
              inspection_id TEXT NOT NULL,
              view_type TEXT NOT NULL,
              local_path TEXT NOT NULL,
              sha256 TEXT NOT NULL,
              size_bytes INTEGER NOT NULL,
              sync_state TEXT NOT NULL,
              remote_id TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
          """);
          await db.execute("""
            CREATE TABLE sync_operations (
              id TEXT PRIMARY KEY,
              inspection_id TEXT NOT NULL,
              operation_type TEXT NOT NULL,
              resource_id TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              payload_sha256 TEXT NOT NULL,
              dependency_ids_json TEXT NOT NULL,
              state TEXT NOT NULL,
              attempt_count INTEGER NOT NULL DEFAULT 0,
              next_attempt_at TEXT,
              last_attempt_at TEXT,
              last_error_kind TEXT,
              last_error_code TEXT,
              last_error_message TEXT,
              remote_resource_id TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
          """);
        },
      ),
    );

    const legacyId = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";
    final timestamp = DateTime.utc(2026, 9, 23, 15).toIso8601String();
    await legacy.insert(
      "local_inspections",
      <String, Object?>{
        "id": legacyId,
        "product_name": "Legacy Product",
        "product_identifier": "LEGACY-1",
        "sync_state": SyncState.localOnly.dbValue,
        "created_at": timestamp,
        "updated_at": timestamp,
      },
    );
    await legacy.close();

    final upgraded = await OfflineDatabase.openAt(
      legacyPath,
      factory: databaseFactoryFfi,
    );
    try {
      final upgradedDrafts = LocalDraftRepository(upgraded);
      final legacyDraft = await upgradedDrafts.getInspection(legacyId);

      expect(legacyDraft, isNotNull);
      expect(legacyDraft!.productName, "Legacy Product");
      expect(legacyDraft.officerUserId, isNull);

      final columns = await upgraded.database.rawQuery(
        "PRAGMA table_info(local_inspections)",
      );
      expect(
        columns.map((row) => row["name"]),
        contains("officer_user_id"),
      );

      await expectLater(
        upgradedDrafts.createInspection(
          id: legacyId,
          officerUserId: "officer-1",
          productName: "Legacy Product",
          productIdentifier: "LEGACY-1",
        ),
        throwsA(isA<StateError>()),
      );

      final newDraft = await upgradedDrafts.createInspection(
        id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
        officerUserId: "officer-1",
        productName: "New Owned Product",
      );
      expect(newDraft.officerUserId, "officer-1");
    } finally {
      await upgraded.close();
    }
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

    await expectLater(
      drafts.createInspection(
        id: inspectionId,
        officerUserId: "officer-2",
        productName: "Product",
      ),
      throwsA(isA<StateError>()),
    );
  });
}
