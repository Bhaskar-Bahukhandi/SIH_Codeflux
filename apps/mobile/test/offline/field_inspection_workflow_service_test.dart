import "dart:io";
import "dart:typed_data";

import "package:flutter_test/flutter_test.dart";
import "package:path/path.dart" as p;
import "package:sqflite_common_ffi/sqflite_ffi.dart";

import "package:codeflux_mobile/auth/officer_session_store.dart";
import "package:codeflux_mobile/offline/models/sync_operation.dart";
import "package:codeflux_mobile/offline/persistence/local_draft_repository.dart";
import "package:codeflux_mobile/offline/persistence/offline_database.dart";
import "package:codeflux_mobile/offline/persistence/sync_queue_repository.dart";
import "package:codeflux_mobile/offline/storage/local_evidence_store.dart";
import "package:codeflux_mobile/offline/workflow/field_inspection_workflow_service.dart";

void main() {
  setUpAll(() {
    sqfliteFfiInit();
  });

  late Directory root;
  late OfflineDatabase database;
  late LocalDraftRepository drafts;
  late SyncQueueRepository queue;
  late FieldInspectionWorkflowService workflow;

  setUp(() async {
    root = await Directory.systemTemp.createTemp(
      "codeflux_field_workflow_",
    );
    database = await OfflineDatabase.openAt(
      p.join(root.path, "offline.sqlite3"),
      factory: databaseFactoryFfi,
    );
    drafts = LocalDraftRepository(database);
    queue = SyncQueueRepository(database);
    workflow = FieldInspectionWorkflowService(
      drafts: drafts,
      queue: queue,
      evidenceStore: LocalEvidenceStore(
        Directory(p.join(root.path, "evidence")),
      ),
    );
  });

  tearDown(() async {
    await database.close();
    if (await root.exists()) {
      await root.delete(recursive: true);
    }
  });

  OfficerSessionContext officer({
    String userId = "officer-1",
    String role = "officer",
  }) {
    return OfficerSessionContext(
      userId: userId,
      fullName: "Offline Officer",
      email: "officer@example.test",
      role: role,
      accessToken: "expired-token-is-not-used-for-local-edits",
      expiresAt: DateTime.utc(2026, 9, 20),
    );
  }

  test("expired network token does not block authenticated local field work", () async {
    final created = await workflow.createInspection(
      officer: officer(),
      productName: "  Offline Biscuit Pack  ",
      productIdentifier: " PKT-01 ",
      now: DateTime.utc(2026, 9, 23, 12),
    );

    expect(created.inspection.productName, "Offline Biscuit Pack");
    expect(created.inspection.productIdentifier, "PKT-01");
    expect(created.inspection.officerUserId, "officer-1");
    expect(created.createOperation.type, SyncOperationType.createInspection);
    expect((await queue.listForInspection(created.inspection.id)).length, 1);
  });

  test("different Officer cannot modify another local inspection", () async {
    final created = await workflow.createInspection(
      officer: officer(),
      productName: "Owned Product",
    );

    await expectLater(
      workflow.addEvidence(
        officer: officer(userId: "officer-2"),
        inspectionId: created.inspection.id,
        viewType: "front",
        bytes: Uint8List.fromList(<int>[1, 2, 3]),
        originalFilename: "front.jpg",
      ),
      throwsA(isA<StateError>()),
    );
  });

  test("non-Officer role cannot create field inspection", () async {
    await expectLater(
      workflow.createInspection(
        officer: officer(role: "supervisor"),
        productName: "Supervisor Draft",
      ),
      throwsA(isA<StateError>()),
    );
  });

  test("two local images build one deterministic pre-review dependency graph", () async {
    final created = await workflow.createInspection(
      officer: officer(),
      productName: "Two View Product",
      now: DateTime.utc(2026, 9, 23, 13),
    );

    final front = await workflow.addEvidence(
      officer: officer(),
      inspectionId: created.inspection.id,
      viewType: "front",
      bytes: Uint8List.fromList(<int>[10, 20, 30, 40]),
      originalFilename: "front.jpg",
      now: DateTime.utc(2026, 9, 23, 13, 1),
    );
    final back = await workflow.addEvidence(
      officer: officer(),
      inspectionId: created.inspection.id,
      viewType: "back",
      bytes: Uint8List.fromList(<int>[50, 60, 70, 80]),
      originalFilename: "back.jpg",
      now: DateTime.utc(2026, 9, 23, 13, 2),
    );

    expect(
      front.uploadOperation.dependencyIds,
      <String>[created.createOperation.id],
    );
    expect(
      front.processOperation.dependencyIds,
      <String>[front.uploadOperation.id],
    );
    expect(
      front.geometryOperation.dependencyIds,
      <String>[front.processOperation.id],
    );
    expect(
      front.ocrOperation.dependencyIds,
      <String>[front.geometryOperation.id],
    );
    expect(
      back.uploadOperation.dependencyIds,
      <String>[created.createOperation.id],
    );

    final submission = await workflow.queueForReview(
      officer: officer(),
      inspectionId: created.inspection.id,
      ruleContext: const <String, Object?>{
        "intended_for_retail_sale": true,
        "industrial_or_institutional_consumer": false,
        "package_exceeds_25kg_or_25l": false,
      },
      now: DateTime.utc(2026, 9, 23, 13, 3),
    );

    expect(
      submission.extractionOperation.dependencyIds.toSet(),
      <String>{front.ocrOperation.id, back.ocrOperation.id},
    );
    expect(
      submission.evaluationOperation.dependencyIds,
      <String>[submission.extractionOperation.id],
    );
    expect(
      submission.submitOperation.dependencyIds,
      <String>[submission.evaluationOperation.id],
    );

    final operations = await queue.listForInspection(created.inspection.id);
    expect(operations.length, 12);
    expect(
      operations.where(
        (operation) =>
            operation.type == SyncOperationType.extractDeclarations,
      ).length,
      1,
    );
    expect(
      operations.where(
        (operation) => operation.type == SyncOperationType.evaluateRules,
      ).length,
      1,
    );
    expect(
      operations.where(
        (operation) => operation.type == SyncOperationType.submitInspection,
      ).length,
      1,
    );
  });

  test("repeated queue-for-review is idempotent for the same rule context", () async {
    final created = await workflow.createInspection(
      officer: officer(),
      productName: "Idempotent Product",
    );
    await workflow.addEvidence(
      officer: officer(),
      inspectionId: created.inspection.id,
      viewType: "front",
      bytes: Uint8List.fromList(<int>[1, 3, 5, 7]),
      originalFilename: "front.jpg",
    );

    const context = <String, Object?>{
      "intended_for_retail_sale": true,
      "industrial_or_institutional_consumer": false,
      "package_exceeds_25kg_or_25l": false,
    };
    final first = await workflow.queueForReview(
      officer: officer(),
      inspectionId: created.inspection.id,
      ruleContext: context,
    );
    final replay = await workflow.queueForReview(
      officer: officer(),
      inspectionId: created.inspection.id,
      ruleContext: context,
    );

    expect(replay.extractionOperation.id, first.extractionOperation.id);
    expect(replay.evaluationOperation.id, first.evaluationOperation.id);
    expect(replay.submitOperation.id, first.submitOperation.id);
    expect(
      (await queue.listForInspection(created.inspection.id)).length,
      8,
    );
  });

  test("changed rule context cannot silently replace queued evaluation", () async {
    final created = await workflow.createInspection(
      officer: officer(),
      productName: "Context Product",
    );
    await workflow.addEvidence(
      officer: officer(),
      inspectionId: created.inspection.id,
      viewType: "front",
      bytes: Uint8List.fromList(<int>[2, 4, 6, 8]),
      originalFilename: "front.jpg",
    );

    await workflow.queueForReview(
      officer: officer(),
      inspectionId: created.inspection.id,
      ruleContext: const <String, Object?>{
        "intended_for_retail_sale": true,
        "industrial_or_institutional_consumer": false,
        "package_exceeds_25kg_or_25l": false,
      },
    );

    await expectLater(
      workflow.queueForReview(
        officer: officer(),
        inspectionId: created.inspection.id,
        ruleContext: const <String, Object?>{
          "intended_for_retail_sale": false,
          "industrial_or_institutional_consumer": false,
          "package_exceeds_25kg_or_25l": false,
        },
      ),
      throwsA(isA<StateError>()),
    );
  });

  test("editing a draft updates local details and queues ordered remote patch", () async {
    final created = await workflow.createInspection(
      officer: officer(),
      productName: "Typo Product",
      productIdentifier: "OLD-1",
    );

    await workflow.updateInspectionDetails(
      officer: officer(),
      inspectionId: created.inspection.id,
      productName: "Correct Product",
      productIdentifier: "NEW-1",
    );

    final updated = await drafts.getInspection(created.inspection.id);
    expect(updated!.productName, "Correct Product");
    expect(updated.productIdentifier, "NEW-1");

    final operations = await queue.listForInspection(created.inspection.id);
    expect(operations.length, 2);
    final edit = operations.singleWhere(
      (operation) => operation.type == SyncOperationType.updateInspection,
    );
    expect(edit.dependencyIds, <String>[created.createOperation.id]);
    expect(edit.payload["product_name"], "Correct Product");
    expect(edit.payload["product_identifier"], "NEW-1");

    final evidence = await workflow.addEvidence(
      officer: officer(),
      inspectionId: created.inspection.id,
      viewType: "front",
      bytes: Uint8List.fromList(<int>[9, 8, 7, 6]),
      originalFilename: "front.jpg",
    );
    final submission = await workflow.queueForReview(
      officer: officer(),
      inspectionId: created.inspection.id,
      ruleContext: const <String, Object?>{
        "intended_for_retail_sale": true,
        "industrial_or_institutional_consumer": false,
        "package_exceeds_25kg_or_25l": false,
      },
    );

    expect(
      submission.extractionOperation.dependencyIds.toSet(),
      <String>{evidence.ocrOperation.id, edit.id},
    );
  });

  test("discard hides draft locally and cancels obsolete pending work", () async {
    final created = await workflow.createInspection(
      officer: officer(),
      productName: "Accidental Product",
    );
    await workflow.addEvidence(
      officer: officer(),
      inspectionId: created.inspection.id,
      viewType: "front",
      bytes: Uint8List.fromList(<int>[1, 2, 3, 4]),
      originalFilename: "blurry.jpg",
    );

    expect(
      (await queue.listForInspection(created.inspection.id)).length,
      5,
    );

    await workflow.discardInspection(
      officer: officer(),
      inspectionId: created.inspection.id,
    );

    expect(
      await drafts.listInspectionsForOfficer("officer-1"),
      isEmpty,
    );

    final operations = await queue.listForInspection(created.inspection.id);
    expect(operations.length, 2);
    expect(
      operations.map((operation) => operation.type).toSet(),
      <SyncOperationType>{
        SyncOperationType.createInspection,
        SyncOperationType.discardInspection,
      },
    );
    final discard = operations.singleWhere(
      (operation) => operation.type == SyncOperationType.discardInspection,
    );
    expect(discard.dependencyIds, <String>[created.createOperation.id]);
  });

  test("edit and discard are blocked after preliminary review is queued", () async {
    final created = await workflow.createInspection(
      officer: officer(),
      productName: "Submitted Soon",
    );
    await workflow.addEvidence(
      officer: officer(),
      inspectionId: created.inspection.id,
      viewType: "front",
      bytes: Uint8List.fromList(<int>[4, 3, 2, 1]),
      originalFilename: "front.jpg",
    );
    await workflow.queueForReview(
      officer: officer(),
      inspectionId: created.inspection.id,
      ruleContext: const <String, Object?>{
        "intended_for_retail_sale": true,
        "industrial_or_institutional_consumer": false,
        "package_exceeds_25kg_or_25l": false,
      },
    );

    await expectLater(
      workflow.updateInspectionDetails(
        officer: officer(),
        inspectionId: created.inspection.id,
        productName: "Too Late",
      ),
      throwsA(isA<StateError>()),
    );
    await expectLater(
      workflow.discardInspection(
        officer: officer(),
        inspectionId: created.inspection.id,
      ),
      throwsA(isA<StateError>()),
    );
  });


  test("removing never-uploaded evidence cancels its pipeline without remote discard", () async {
    final created = await workflow.createInspection(
      officer: officer(),
      productName: "Local Removal",
    );
    final evidence = await workflow.addEvidence(
      officer: officer(),
      inspectionId: created.inspection.id,
      viewType: "front",
      bytes: Uint8List.fromList(<int>[1, 2, 3, 4]),
      originalFilename: "blurry.jpg",
    );

    await workflow.removeEvidence(
      officer: officer(),
      inspectionId: created.inspection.id,
      evidenceId: evidence.evidence.id,
    );

    expect(
      await drafts.listEvidenceForInspection(created.inspection.id),
      isEmpty,
    );
    final stored = await drafts.getEvidence(evidence.evidence.id);
    expect(stored!.discardedAt, isNotNull);

    final operations = await queue.listForInspection(created.inspection.id);
    expect(operations.length, 1);
    expect(operations.single.type, SyncOperationType.createInspection);
    expect(
      operations.where(
        (operation) => operation.type == SyncOperationType.discardCapture,
      ),
      isEmpty,
    );
  });

  test("removing uploaded evidence queues discard and cancels later processing", () async {
    final created = await workflow.createInspection(
      officer: officer(),
      productName: "Remote Removal",
    );
    final evidence = await workflow.addEvidence(
      officer: officer(),
      inspectionId: created.inspection.id,
      viewType: "front",
      bytes: Uint8List.fromList(<int>[5, 6, 7, 8]),
      originalFilename: "front.jpg",
    );

    final t0 = DateTime.utc(2026, 9, 24, 12);
    final createClaim = await queue.claimNextReady(t0);
    expect(createClaim!.id, created.createOperation.id);
    await queue.markSynced(
      createClaim.id,
      remoteResourceId: created.inspection.id,
      now: t0,
    );

    final uploadClaim = await queue.claimNextReady(
      t0.add(const Duration(seconds: 1)),
    );
    expect(uploadClaim!.id, evidence.uploadOperation.id);
    await queue.markSynced(
      uploadClaim.id,
      remoteResourceId: evidence.evidence.id,
      now: t0.add(const Duration(seconds: 1)),
    );

    await workflow.removeEvidence(
      officer: officer(),
      inspectionId: created.inspection.id,
      evidenceId: evidence.evidence.id,
      now: t0.add(const Duration(seconds: 2)),
    );

    expect(
      await drafts.listEvidenceForInspection(created.inspection.id),
      isEmpty,
    );

    final operations = await queue.listForInspection(created.inspection.id);
    expect(
      operations.map((operation) => operation.type).toSet(),
      <SyncOperationType>{
        SyncOperationType.createInspection,
        SyncOperationType.uploadCapture,
        SyncOperationType.discardCapture,
      },
    );
    final discard = operations.singleWhere(
      (operation) => operation.type == SyncOperationType.discardCapture,
    );
    expect(discard.resourceId, evidence.evidence.id);
    expect(discard.dependencyIds, <String>[evidence.uploadOperation.id]);

    final replacement = await workflow.addEvidence(
      officer: officer(),
      inspectionId: created.inspection.id,
      viewType: "front",
      bytes: Uint8List.fromList(<int>[9, 10, 11, 12]),
      originalFilename: "replacement.jpg",
    );
    final submission = await workflow.queueForReview(
      officer: officer(),
      inspectionId: created.inspection.id,
      ruleContext: const <String, Object?>{
        "intended_for_retail_sale": true,
        "industrial_or_institutional_consumer": false,
        "package_exceeds_25kg_or_25l": false,
      },
    );

    expect(
      submission.extractionOperation.dependencyIds.toSet(),
      <String>{replacement.ocrOperation.id, discard.id},
    );
  });

  test("evidence cannot be removed after preliminary review is queued", () async {
    final created = await workflow.createInspection(
      officer: officer(),
      productName: "Locked Evidence",
    );
    final evidence = await workflow.addEvidence(
      officer: officer(),
      inspectionId: created.inspection.id,
      viewType: "front",
      bytes: Uint8List.fromList(<int>[3, 1, 4, 1]),
      originalFilename: "front.jpg",
    );
    await workflow.queueForReview(
      officer: officer(),
      inspectionId: created.inspection.id,
      ruleContext: const <String, Object?>{
        "intended_for_retail_sale": true,
        "industrial_or_institutional_consumer": false,
        "package_exceeds_25kg_or_25l": false,
      },
    );

    await expectLater(
      workflow.removeEvidence(
        officer: officer(),
        inspectionId: created.inspection.id,
        evidenceId: evidence.evidence.id,
      ),
      throwsA(isA<StateError>()),
    );
  });

}
