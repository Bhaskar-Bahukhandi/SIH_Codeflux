import "dart:convert";
import "dart:io";

import "package:flutter/material.dart";
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
import "package:codeflux_mobile/ui/workspace_screen.dart";

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

  @override
  Future<AcquiredEvidence?> acquire(EvidenceSource source) async => next;

  @override
  Future<List<AcquiredEvidence>> recoverLostEvidence() async =>
      const <AcquiredEvidence>[];
}

Future<void> pumpUntilFound(
  WidgetTester tester,
  Finder finder, {
  int maxPumps = 60,
}) async {
  for (var index = 0; index < maxPumps; index += 1) {
    await tester.pump(const Duration(milliseconds: 100));
    if (finder.evaluate().isNotEmpty) {
      return;
    }
  }
  throw TestFailure("Timed out waiting for expected widget.");
}

void main() {
  setUpAll(sqfliteFfiInit);

  testWidgets(
    "Officer creates inspection, captures front image and queues review",
    (tester) async {
      final root = await Directory.systemTemp.createTemp(
        "codeflux_widget_flow_",
      );
      final database = await OfflineDatabase.openAt(
        p.join(root.path, "offline.sqlite3"),
        factory: databaseFactoryFfi,
      );
      addTearDown(() async {
        await database.close();
        if (await root.exists()) {
          await root.delete(recursive: true);
        }
      });

      final drafts = LocalDraftRepository(database);
      final queue = SyncQueueRepository(database);
      final sessionStore = OfficerSessionStore(MemorySecureStore());
      final officer = OfficerSessionContext(
        userId: "officer-1",
        fullName: "Widget Officer",
        email: "officer@example.test",
        role: "officer",
        accessToken: "token",
        expiresAt: DateTime.utc(2026, 9, 24),
      );
      await sessionStore.save(officer);

      final workflow = FieldInspectionWorkflowService(
        drafts: drafts,
        queue: queue,
        evidenceStore: LocalEvidenceStore(
          Directory(p.join(root.path, "evidence")),
        ),
      );
      final workspace = OfficerWorkspaceService(
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
      final acquisition = FakeAcquisition();
      final captureCoordinator = FieldCaptureCoordinator(
        workspace: workspace,
        acquisition: acquisition,
        pendingCaptures: PendingCaptureRepository(database),
      );

      await tester.pumpWidget(
        MaterialApp(
          home: WorkspaceScreen(
            officer: officer,
            workspace: workspace,
            captureCoordinator: captureCoordinator,
            onSignedOut: () {},
          ),
        ),
      );
      await pumpUntilFound(tester, find.text("Widget Officer"));

      expect(find.text("Widget Officer"), findsOneWidget);
      expect(find.text("No inspections on this device yet.\n"
          "Create one to start capturing package evidence."), findsOneWidget);

      await tester.tap(find.text("New inspection"));
      await pumpUntilFound(tester, find.text("New inspection"));

      final formFields = find.byType(TextFormField);
      await tester.enterText(formFields.at(0), "Widget Product");
      await tester.enterText(formFields.at(1), "SKU-WIDGET");
      await tester.tap(find.widgetWithText(FilledButton, "Create"));
      await pumpUntilFound(tester, find.text("Add image"));

      expect(find.text("Widget Product"), findsWidgets);
      expect(find.text("No package images saved yet. Capture multiple views "
          "so declarations can be checked against the available evidence."),
          findsOneWidget);

      acquisition.next = AcquiredEvidence(
        bytes: base64Decode(
          "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwC"
          "AAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
        ),
        filename: "front.png",
      );

      await tester.tap(find.text("Add image"));
      await pumpUntilFound(tester, find.text("Which side are you capturing?"));
      await tester.tap(find.text("Front"));
      await pumpUntilFound(tester, find.text("Take photo"));
      await tester.tap(find.text("Take photo"));
      await pumpUntilFound(
        tester,
        find.textContaining("image saved locally and queued"),
      );

      expect(find.text("Front"), findsOneWidget);
      expect(
        find.textContaining("image saved locally and queued"),
        findsOneWidget,
      );

      await tester.tap(find.text("Queue preliminary review"));
      await pumpUntilFound(tester, find.text("Applicability context"));
      expect(find.text("Applicability context"), findsOneWidget);
      await tester.tap(
        find.widgetWithText(FilledButton, "Queue for review"),
      );
      await pumpUntilFound(
        tester,
        find.textContaining("have been queued"),
      );

      final inspections = await workspace.listInspections();
      expect(inspections.length, 1);
      final inspectionId = inspections.single.inspection.id;

      expect(
        (await workspace.listEvidence(inspectionId)).length,
        1,
      );
      expect(
        (await queue.listForInspection(inspectionId)).length,
        8,
      );
      expect(
        find.textContaining("have been queued"),
        findsOneWidget,
      );

      await tester.pageBack();
      await pumpUntilFound(tester, find.text("My inspections"));
      expect(find.text("Widget Product"), findsOneWidget);
    },
  );
}
