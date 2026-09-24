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
import "package:codeflux_mobile/ui/inspection_screen.dart";
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

class FieldUiHarness {
  FieldUiHarness({
    required this.root,
    required this.database,
    required this.drafts,
    required this.queue,
    required this.workspace,
    required this.acquisition,
    required this.captureCoordinator,
    required this.officer,
  });

  final Directory root;
  final OfflineDatabase database;
  final LocalDraftRepository drafts;
  final SyncQueueRepository queue;
  final OfficerWorkspaceService workspace;
  final FakeAcquisition acquisition;
  final FieldCaptureCoordinator captureCoordinator;
  final OfficerSessionContext officer;

  static Future<FieldUiHarness> create() async {
    final root = await Directory.systemTemp.createTemp(
      "codeflux_widget_flow_",
    );
    final database = await OfflineDatabase.openAt(
      p.join(root.path, "offline.sqlite3"),
      factory: databaseFactoryFfi,
    );
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

    return FieldUiHarness(
      root: root,
      database: database,
      drafts: drafts,
      queue: queue,
      workspace: workspace,
      acquisition: acquisition,
      captureCoordinator: captureCoordinator,
      officer: officer,
    );
  }

  Future<void> dispose() async {
    await database.close();
    if (await root.exists()) {
      await root.delete(recursive: true);
    }
  }
}

Future<void> pumpUntilFound(
  WidgetTester tester,
  Finder finder, {
  int maxPumps = 180,
}) async {
  for (var index = 0; index < maxPumps; index += 1) {
    await tester.pump(const Duration(milliseconds: 100));
    if (finder.evaluate().isNotEmpty) {
      return;
    }
    // SQLite/FFI work completes on real asynchronous time rather than the
    // widget test's fake clock. Give it a bounded wall-clock opportunity to
    // progress when the full CI suite is running several test files at once.
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 20)),
    );
  }
  throw TestFailure(
    "Timed out waiting for expected widget after bounded async polling.",
  );
}

Future<void> unmountApp(WidgetTester tester) async {
  await tester.pumpWidget(const SizedBox.shrink());
  await tester.pump();
}

void main() {
  setUpAll(sqfliteFfiInit);

  testWidgets("Officer creates an inspection and opens its detail screen", (
    tester,
  ) async {
    final harness = (await tester.runAsync(FieldUiHarness.create))!;
    addTearDown(() async {
      await tester.runAsync(harness.dispose);
    });

    debugPrint("field-ui:create:01-harness-ready");
    await tester.pumpWidget(
      MaterialApp(
        home: WorkspaceScreen(
          officer: harness.officer,
          workspace: harness.workspace,
          captureCoordinator: harness.captureCoordinator,
          onSignedOut: () {},
        ),
      ),
    );
    debugPrint("field-ui:create:02-widget-mounted");
    await pumpUntilFound(tester, find.text("Widget Officer"));
    debugPrint("field-ui:create:03-workspace-ready");

    final emptyState = find.text(
      "No inspections on this device yet.\n"
      "Create one to start capturing package evidence.",
    );
    await pumpUntilFound(tester, emptyState);
    expect(emptyState, findsOneWidget);

    await tester.tap(find.text("New inspection"));
    debugPrint("field-ui:create:04-new-inspection-tapped");
    await pumpUntilFound(tester, find.text("New inspection"));
    debugPrint("field-ui:create:05-dialog-ready");

    final formFields = find.byType(TextFormField);
    await tester.enterText(formFields.at(0), "Widget Product");
    await tester.enterText(formFields.at(1), "SKU-WIDGET");
    debugPrint("field-ui:create:06-form-filled");
    await tester.tap(find.widgetWithText(FilledButton, "Create"));
    debugPrint("field-ui:create:07-create-tapped");

    await pumpUntilFound(tester, find.text("Add image"));
    debugPrint("field-ui:create:08-detail-ready");
    expect(find.text("Widget Product"), findsWidgets);

    await tester.pageBack();
    debugPrint("field-ui:create:09-back-requested");
    await pumpUntilFound(tester, find.text("My inspections"));
    await tester.pump(const Duration(milliseconds: 500));
    debugPrint("field-ui:create:10-workspace-returned");
    expect(
      find.widgetWithText(ListTile, "Widget Product"),
      findsOneWidget,
    );

    final inspections = (await tester.runAsync(
      harness.workspace.listInspections,
    ))!;
    debugPrint("field-ui:create:11-storage-verified");
    expect(inspections.length, 1);
    expect(inspections.single.inspection.productIdentifier, "SKU-WIDGET");

    await unmountApp(tester);
    debugPrint("field-ui:create:12-unmounted");
  });

  testWidgets("Officer captures package evidence and queues review", (
    tester,
  ) async {
    final harness = (await tester.runAsync(FieldUiHarness.create))!;
    addTearDown(() async {
      await tester.runAsync(harness.dispose);
    });

    final created = (await tester.runAsync(
      () => harness.workspace.createInspection(
        productName: "Widget Product",
        productIdentifier: "SKU-WIDGET",
      ),
    ))!;
    final inspectionId = created.inspection.id;

    await tester.pumpWidget(
      MaterialApp(
        home: InspectionScreen(
          inspectionId: inspectionId,
          workspace: harness.workspace,
          captureCoordinator: harness.captureCoordinator,
        ),
      ),
    );
    await pumpUntilFound(tester, find.text("Add image"));

    harness.acquisition.next = AcquiredEvidence(
      bytes: base64Decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwC"
        "AAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
      ),
      filename: "front.png",
    );

    final addImageButton = find.widgetWithText(
      TextButton,
      "Add",
    );
    expect(addImageButton, findsOneWidget);
    await tester.tap(addImageButton);
    await pumpUntilFound(tester, find.text("Which side are you capturing?"));
    final frontOption = find.widgetWithText(ListTile, "Front");
    await tester.ensureVisible(frontOption);
    await tester.pump(const Duration(milliseconds: 200));
    await tester.tap(frontOption);

    await pumpUntilFound(tester, find.text("Take photo"));
    final cameraOption = find.widgetWithText(ListTile, "Take photo");
    await tester.ensureVisible(cameraOption);
    await tester.pump(const Duration(milliseconds: 200));
    await tester.tap(cameraOption);
    await pumpUntilFound(
      tester,
      find.textContaining("image saved locally and queued"),
    );

    expect(find.text("Front"), findsOneWidget);
    expect(
      find.textContaining("image saved locally and queued"),
      findsOneWidget,
    );

    final queueReviewButton = find.widgetWithText(
      FilledButton,
      "Queue preliminary review",
    );
    await tester.ensureVisible(queueReviewButton);
    await tester.pump(const Duration(milliseconds: 300));
    await tester.tap(queueReviewButton);
    await pumpUntilFound(tester, find.text("Applicability context"));
    await tester.tap(
      find.widgetWithText(FilledButton, "Queue for review"),
    );
    await pumpUntilFound(
      tester,
      find.textContaining("have been queued"),
    );

    final evidence = (await tester.runAsync(
      () => harness.workspace.listEvidence(inspectionId),
    ))!;
    final operations = (await tester.runAsync(
      () => harness.queue.listForInspection(inspectionId),
    ))!;
    expect(evidence.length, 1);
    expect(operations.length, 8);
    expect(
      find.textContaining("have been queued"),
      findsOneWidget,
    );

    await unmountApp(tester);
  });

  testWidgets("new inspection dialog survives repeated route teardown", (
    tester,
  ) async {
    final harness = (await tester.runAsync(FieldUiHarness.create))!;
    addTearDown(() async {
      await tester.runAsync(harness.dispose);
    });

    await tester.pumpWidget(
      MaterialApp(
        home: WorkspaceScreen(
          officer: harness.officer,
          workspace: harness.workspace,
          captureCoordinator: harness.captureCoordinator,
          onSignedOut: () {},
        ),
      ),
    );
    await pumpUntilFound(tester, find.text("Widget Officer"));

    for (var attempt = 0; attempt < 2; attempt += 1) {
      await tester.tap(find.text("New inspection"));
      await pumpUntilFound(tester, find.byType(TextFormField));
      final fields = find.byType(TextFormField);
      await tester.enterText(fields.at(0), "Cancelled Product $attempt");
      await tester.enterText(fields.at(1), "CANCEL-$attempt");
      await tester.tap(find.widgetWithText(TextButton, "Cancel"));
      await tester.pump(const Duration(milliseconds: 500));
      expect(tester.takeException(), isNull);
      expect(find.byType(TextFormField), findsNothing);
    }

    await tester.tap(find.text("New inspection"));
    await pumpUntilFound(tester, find.byType(TextFormField));
    final fields = find.byType(TextFormField);
    await tester.enterText(fields.at(0), "Lifecycle Product");
    await tester.enterText(fields.at(1), "LIFE-001");
    await tester.tap(find.widgetWithText(FilledButton, "Create"));
    await pumpUntilFound(tester, find.text("Add image"));
    await tester.pump(const Duration(milliseconds: 500));
    expect(tester.takeException(), isNull);

    await tester.pageBack();
    await pumpUntilFound(tester, find.text("My inspections"));
    await tester.pump(const Duration(milliseconds: 500));
    expect(tester.takeException(), isNull);
    expect(find.text("Lifecycle Product"), findsOneWidget);

    await unmountApp(tester);
  });


  testWidgets("Officer can replace then remove a draft package image", (
    tester,
  ) async {
    final harness = (await tester.runAsync(FieldUiHarness.create))!;
    addTearDown(() async {
      await tester.runAsync(harness.dispose);
    });

    final created = (await tester.runAsync(
      () => harness.workspace.createInspection(
        productName: "Replaceable Product",
        productIdentifier: "REP-001",
      ),
    ))!;
    final inspectionId = created.inspection.id;

    await tester.pumpWidget(
      MaterialApp(
        home: InspectionScreen(
          inspectionId: inspectionId,
          workspace: harness.workspace,
          captureCoordinator: harness.captureCoordinator,
        ),
      ),
    );
    await pumpUntilFound(tester, find.text("Add image"));

    final firstBytes = base64Decode(
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwC"
      "AAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
    );
    harness.acquisition.next = AcquiredEvidence(
      bytes: firstBytes,
      filename: "front-first.png",
    );

    await tester.tap(find.widgetWithText(TextButton, "Add"));
    await pumpUntilFound(tester, find.text("Which side are you capturing?"));
    final frontOption = find.widgetWithText(ListTile, "Front");
    await tester.ensureVisible(frontOption);
    await tester.pump(const Duration(milliseconds: 200));
    await tester.tap(frontOption);
    await pumpUntilFound(tester, find.text("Take photo"));
    final firstCameraOption = find.widgetWithText(ListTile, "Take photo");
    await tester.ensureVisible(firstCameraOption);
    await tester.pump(const Duration(milliseconds: 200));
    await tester.tap(firstCameraOption);
    await pumpUntilFound(
      tester,
      find.textContaining("image saved locally and queued"),
    );

    final originalEvidence = (await tester.runAsync(
      () => harness.workspace.listEvidence(inspectionId),
    ))!;
    expect(originalEvidence.length, 1);
    final originalId = originalEvidence.single.id;

    harness.acquisition.next = AcquiredEvidence(
      bytes: firstBytes,
      filename: "front-replacement.png",
    );

    final firstImageActions = find.byTooltip("Image actions");
    await tester.ensureVisible(firstImageActions);
    await tester.pump(const Duration(milliseconds: 200));
    await tester.tap(firstImageActions);
    final replaceMenuItem =
        find.widgetWithText(PopupMenuItem<String>, "Replace image");
    await pumpUntilFound(tester, replaceMenuItem);
    await tester.ensureVisible(replaceMenuItem);
    await tester.pump(const Duration(milliseconds: 100));
    await tester.tap(replaceMenuItem);
    await pumpUntilFound(tester, find.text("Take photo"));
    final replacementCameraOption =
        find.widgetWithText(ListTile, "Take photo");
    await tester.ensureVisible(replacementCameraOption);
    await tester.pump(const Duration(milliseconds: 200));
    await tester.tap(replacementCameraOption);
    await pumpUntilFound(
      tester,
      find.textContaining("image replaced successfully"),
    );

    final replacedEvidence = (await tester.runAsync(
      () => harness.workspace.listEvidence(inspectionId),
    ))!;
    expect(replacedEvidence.length, 1);
    expect(replacedEvidence.single.id, isNot(originalId));

    final replacementImageActions = find.byTooltip("Image actions");
    await tester.ensureVisible(replacementImageActions);
    await tester.pump(const Duration(milliseconds: 200));
    await tester.tap(replacementImageActions);
    final removeMenuItem =
        find.widgetWithText(PopupMenuItem<String>, "Remove image");
    await pumpUntilFound(tester, removeMenuItem);
    await tester.ensureVisible(removeMenuItem);
    await tester.pump(const Duration(milliseconds: 100));
    await tester.tap(removeMenuItem);
    await pumpUntilFound(tester, find.text("Remove package image?"));
    await tester.tap(find.widgetWithText(FilledButton, "Remove"));
    await pumpUntilFound(
      tester,
      find.text(
        "No package images saved yet. Capture multiple views "
        "so declarations can be checked against the available evidence.",
      ),
    );

    expect(
      await tester.runAsync(
        () => harness.workspace.listEvidence(inspectionId),
      ),
      isEmpty,
    );
    expect(tester.takeException(), isNull);

    await unmountApp(tester);
  });

}
