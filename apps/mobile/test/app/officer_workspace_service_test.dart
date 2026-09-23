import "dart:io";
import "dart:typed_data";

import "package:flutter_test/flutter_test.dart";
import "package:path/path.dart" as p;
import "package:sqflite_common_ffi/sqflite_ffi.dart";

import "package:codeflux_mobile/app/officer_workspace_service.dart";
import "package:codeflux_mobile/auth/officer_session_store.dart";
import "package:codeflux_mobile/offline/models/sync_operation.dart";
import "package:codeflux_mobile/offline/models/sync_state.dart";
import "package:codeflux_mobile/offline/persistence/local_draft_repository.dart";
import "package:codeflux_mobile/offline/persistence/offline_database.dart";
import "package:codeflux_mobile/offline/persistence/sync_queue_repository.dart";
import "package:codeflux_mobile/offline/storage/local_evidence_store.dart";
import "package:codeflux_mobile/offline/sync/offline_sync_service.dart";
import "package:codeflux_mobile/offline/sync/sync_coordinator.dart";
import "package:codeflux_mobile/offline/workflow/field_inspection_workflow_service.dart";

class MemorySecureStore implements SecureKeyValueStore {
  final Map<String, String> values = <String, String>{};

  @override
  Future<void> delete(String key) async {
    values.remove(key);
  }

  @override
  Future<String?> read(String key) async => values[key];

  @override
  Future<void> write(String key, String value) async {
    values[key] = value;
  }
}

class RecordingExecutor implements SyncOperationExecutor {
  final List<String> executed = <String>[];

  @override
  Future<SyncExecutionSuccess> execute(SyncOperation operation) async {
    executed.add(operation.id);
    return SyncExecutionSuccess(
      remoteResourceId: operation.resourceId,
    );
  }
}

void main() {
  setUpAll(() {
    sqfliteFfiInit();
  });

  late Directory root;
  late OfflineDatabase database;
  late LocalDraftRepository drafts;
  late SyncQueueRepository queue;
  late OfficerSessionStore sessionStore;
  late RecordingExecutor executor;
  late OfficerWorkspaceService workspace;

  setUp(() async {
    root = await Directory.systemTemp.createTemp(
      "codeflux_workspace_test_",
    );
    database = await OfflineDatabase.openAt(
      p.join(root.path, "offline.sqlite3"),
      factory: databaseFactoryFfi,
    );
    drafts = LocalDraftRepository(database);
    queue = SyncQueueRepository(database);
    sessionStore = OfficerSessionStore(MemorySecureStore());
    executor = RecordingExecutor();

    final workflow = FieldInspectionWorkflowService(
      drafts: drafts,
      queue: queue,
      evidenceStore: LocalEvidenceStore(
        Directory(p.join(root.path, "evidence")),
      ),
    );
    workspace = OfficerWorkspaceService(
      sessionStore: sessionStore,
      drafts: drafts,
      queue: queue,
      workflow: workflow,
      syncService: OfflineSyncService(
        coordinator: SyncCoordinator(
          queue: queue,
          executor: executor,
        ),
      ),
    );
  });

  tearDown(() async {
    await database.close();
    if (await root.exists()) {
      await root.delete(recursive: true);
    }
  });

  OfficerSessionContext session({
    String userId = "officer-1",
    DateTime? expiresAt,
  }) {
    return OfficerSessionContext(
      userId: userId,
      fullName: "Field Officer",
      email: userId + "@example.test",
      role: "officer",
      accessToken: "token-" + userId,
      expiresAt: expiresAt ?? DateTime.utc(2026, 9, 24),
    );
  }

  test("workspace lists only inspections owned by persisted Officer", () async {
    await sessionStore.save(session());

    await workspace.createInspection(
      productName: "Officer One Product",
      now: DateTime.utc(2026, 9, 23, 10),
    );

    final other = session(userId: "officer-2");
    final workflow = workspace.workflow;
    await workflow.createInspection(
      officer: other,
      productName: "Officer Two Product",
      now: DateTime.utc(2026, 9, 23, 11),
    );

    final items = await workspace.listInspections();

    expect(items.length, 1);
    expect(items.single.inspection.officerUserId, "officer-1");
    expect(items.single.inspection.productName, "Officer One Product");
    expect(items.single.evidenceCount, 0);
    expect(items.single.syncSummary.totalOperations, 1);
  });

  test("workspace creates evidence and exposes aggregate sync state", () async {
    await sessionStore.save(session());
    final created = await workspace.createInspection(
      productName: "Evidence Product",
    );

    await workspace.addEvidence(
      inspectionId: created.inspection.id,
      viewType: "front",
      bytes: Uint8List.fromList(<int>[1, 2, 3, 4]),
      originalFilename: "front.jpg",
    );

    final item = (await workspace.listInspections()).single;

    expect(item.evidenceCount, 1);
    expect(item.syncSummary.totalOperations, 5);
    expect(item.syncSummary.overallState, SyncState.queued);
  });

  test("expired token pauses sync without mutating queued operations", () async {
    final now = DateTime.utc(2026, 9, 23, 12);
    await sessionStore.save(
      session(expiresAt: now.subtract(const Duration(minutes: 1))),
    );
    final created = await workspace.createInspection(
      productName: "Offline Product",
      now: now,
    );

    final before = await queue.getById(created.createOperation.id);
    expect(before!.state, SyncState.queued);

    final result = await workspace.syncNow(now: now);

    expect(result.requiresAuthentication, isTrue);
    expect(result.summary, isNull);
    expect(executor.executed, isEmpty);
    expect(
      (await queue.getById(created.createOperation.id))!.state,
      SyncState.queued,
    );
    expect((await workspace.listInspections()).length, 1);
  });

  test("fresh token allows previously queued work to sync", () async {
    final now = DateTime.utc(2026, 9, 23, 13);
    await sessionStore.save(
      session(expiresAt: now.subtract(const Duration(minutes: 1))),
    );
    final created = await workspace.createInspection(
      productName: "Reconnect Product",
      now: now,
    );

    expect((await workspace.syncNow(now: now)).requiresAuthentication, isTrue);

    await sessionStore.save(
      session(expiresAt: now.add(const Duration(hours: 1))),
    );
    final result = await workspace.syncNow(
      now: now.add(const Duration(minutes: 1)),
    );

    expect(result.requiresAuthentication, isFalse);
    expect(result.summary!.synced, 1);
    expect(executor.executed, <String>[created.createOperation.id]);
    expect(
      (await queue.getById(created.createOperation.id))!.state,
      SyncState.synced,
    );
  });

  test("sign out removes identity but preserves local inspection data", () async {
    await sessionStore.save(session());
    final created = await workspace.createInspection(
      productName: "Preserved Draft",
    );

    await workspace.signOut();

    expect(await workspace.currentOfficerIdentity(), isNull);
    expect(await drafts.getInspection(created.inspection.id), isNotNull);
    await expectLater(
      workspace.listInspections(),
      throwsA(isA<StateError>()),
    );
  });
}
