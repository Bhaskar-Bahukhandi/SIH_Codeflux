import "dart:io";
import "dart:typed_data";

import "package:flutter_test/flutter_test.dart";
import "package:path/path.dart" as p;
import "package:sqflite_common_ffi/sqflite_ffi.dart";

import "package:codeflux_mobile/app/officer_workspace_service.dart";
import "package:codeflux_mobile/auth/officer_session_store.dart";
import "package:codeflux_mobile/capture/evidence_acquisition_service.dart";
import "package:codeflux_mobile/capture/field_capture_coordinator.dart";
import "package:codeflux_mobile/capture/pending_capture_repository.dart";
import "package:codeflux_mobile/offline/models/sync_operation.dart";
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
  Future<void> delete(String key) async => values.remove(key);

  @override
  Future<String?> read(String key) async => values[key];

  @override
  Future<void> write(String key, String value) async {
    values[key] = value;
  }
}

class NoopExecutor implements SyncOperationExecutor {
  @override
  Future<SyncExecutionSuccess> execute(SyncOperation operation) async {
    return SyncExecutionSuccess(remoteResourceId: operation.resourceId);
  }
}

class FakeAcquisition implements EvidenceAcquisitionService {
  AcquiredEvidence? next;
  List<AcquiredEvidence> recovered = const <AcquiredEvidence>[];
  EvidenceSource? lastSource;

  @override
  Future<AcquiredEvidence?> acquire(EvidenceSource source) async {
    lastSource = source;
    return next;
  }

  @override
  Future<List<AcquiredEvidence>> recoverLostEvidence() async => recovered;
}

void main() {
  setUpAll(sqfliteFfiInit);

  late Directory root;
  late OfflineDatabase database;
  late LocalDraftRepository drafts;
  late OfficerWorkspaceService workspace;
  late PendingCaptureRepository pending;
  late FakeAcquisition acquisition;
  late FieldCaptureCoordinator coordinator;

  setUp(() async {
    root = await Directory.systemTemp.createTemp("codeflux_capture_flow_");
    database = await OfflineDatabase.openAt(
      p.join(root.path, "offline.sqlite3"),
      factory: databaseFactoryFfi,
    );
    drafts = LocalDraftRepository(database);
    final queue = SyncQueueRepository(database);
    final sessionStore = OfficerSessionStore(MemorySecureStore());
    await sessionStore.save(
      OfficerSessionContext(
        userId: "officer-1",
        fullName: "Officer",
        email: "officer@example.test",
        role: "officer",
        accessToken: "token",
        expiresAt: DateTime.utc(2026, 9, 24),
      ),
    );

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
          executor: NoopExecutor(),
        ),
      ),
    );
    pending = PendingCaptureRepository(database);
    acquisition = FakeAcquisition();
    coordinator = FieldCaptureCoordinator(
      workspace: workspace,
      acquisition: acquisition,
      pendingCaptures: pending,
    );
  });

  tearDown(() async {
    await database.close();
    if (await root.exists()) {
      await root.delete(recursive: true);
    }
  });

  Future<String> createInspection() async {
    final created = await workspace.createInspection(
      productName: "Capture Product",
    );
    return created.inspection.id;
  }

  test("camera image is persisted before pending intent is cleared", () async {
    final inspectionId = await createInspection();
    acquisition.next = AcquiredEvidence(
      bytes: Uint8List.fromList(<int>[1, 2, 3, 4]),
      filename: "front.jpg",
    );

    final saved = await coordinator.acquireAndAttach(
      inspectionId: inspectionId,
      viewType: "front",
      source: EvidenceSource.camera,
    );

    expect(saved, isTrue);
    expect(acquisition.lastSource, EvidenceSource.camera);
    expect(await pending.current(), isNull);

    final evidence = await drafts.listEvidenceForInspection(inspectionId);
    expect(evidence.length, 1);
    expect(evidence.single.viewType, "front");
    expect(File(evidence.single.localPath).existsSync(), isTrue);
  });

  test("cancelled picker clears pending intent without creating evidence", () async {
    final inspectionId = await createInspection();
    acquisition.next = null;

    final saved = await coordinator.acquireAndAttach(
      inspectionId: inspectionId,
      viewType: "back",
      source: EvidenceSource.gallery,
    );

    expect(saved, isFalse);
    expect(await pending.current(), isNull);
    expect(
      await drafts.listEvidenceForInspection(inspectionId),
      isEmpty,
    );
  });

  test("recovered lost image attaches to original inspection and view", () async {
    final inspectionId = await createInspection();
    final intent = await pending.begin(
      inspectionId: inspectionId,
      viewType: "detail",
      source: "camera",
    );
    acquisition.recovered = <AcquiredEvidence>[
      AcquiredEvidence(
        bytes: Uint8List.fromList(<int>[8, 7, 6, 5]),
        filename: "recovered.jpg",
      ),
    ];

    final result = await coordinator.recoverInterruptedCapture();

    expect(result.status, PendingCaptureRecoveryStatus.recovered);
    expect(result.intent!.id, intent.id);
    expect(await pending.current(), isNull);

    final evidence = await drafts.listEvidenceForInspection(inspectionId);
    expect(evidence.length, 1);
    expect(evidence.single.viewType, "detail");
    expect(File(evidence.single.localPath).existsSync(), isTrue);
  });

  test("missing lost data keeps marker visible until Officer discards it", () async {
    final inspectionId = await createInspection();
    final intent = await pending.begin(
      inspectionId: inspectionId,
      viewType: "right",
      source: "camera",
    );
    acquisition.recovered = const <AcquiredEvidence>[];

    final result = await coordinator.recoverInterruptedCapture();

    expect(
      result.status,
      PendingCaptureRecoveryStatus.pendingWithoutRecoveredData,
    );
    expect((await pending.current())!.id, intent.id);

    await coordinator.discardPendingCapture();
    expect(await pending.current(), isNull);
  });
}
