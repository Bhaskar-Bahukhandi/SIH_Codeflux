import "dart:typed_data";

import "../auth/officer_session_store.dart";
import "../offline/models/inspection_sync_summary.dart";
import "../offline/models/local_records.dart";
import "../offline/models/sync_operation.dart";
import "../offline/persistence/local_draft_repository.dart";
import "../offline/persistence/sync_queue_repository.dart";
import "../offline/sync/offline_sync_service.dart";
import "../offline/workflow/field_inspection_workflow_service.dart";
import "../review/officer_review_api_client.dart";
import "../review/officer_review_models.dart";

class OfficerInspectionWorkspaceItem {
  const OfficerInspectionWorkspaceItem({
    required this.inspection,
    required this.syncSummary,
    required this.evidenceCount,
    required this.reviewStageQueued,
  });

  final LocalInspectionDraft inspection;
  final InspectionSyncSummary syncSummary;
  final int evidenceCount;
  final bool reviewStageQueued;
}

class WorkspaceSyncResult {
  const WorkspaceSyncResult._({
    required this.requiresAuthentication,
    this.summary,
  });

  const WorkspaceSyncResult.authenticationRequired()
      : this._(requiresAuthentication: true);

  const WorkspaceSyncResult.completed(SyncDrainSummary summary)
      : this._(
          requiresAuthentication: false,
          summary: summary,
        );

  final bool requiresAuthentication;
  final SyncDrainSummary? summary;
}

class OfficerWorkspaceService {
  const OfficerWorkspaceService({
    required this.sessionStore,
    required this.drafts,
    required this.queue,
    required this.workflow,
    required this.syncService,
    required this.reviewClient,
  });

  final OfficerSessionStore sessionStore;
  final LocalDraftRepository drafts;
  final SyncQueueRepository queue;
  final FieldInspectionWorkflowService workflow;
  final OfflineSyncService syncService;
  final OfficerReviewApiClient reviewClient;

  Future<OfficerSessionContext?> currentOfficerIdentity() async {
    final session = await sessionStore.read();
    if (session == null) {
      return null;
    }
    if (session.role.toLowerCase() != "officer") {
      throw StateError(
        "Persisted mobile session is not an Officer identity.",
      );
    }
    return session;
  }

  Future<List<OfficerInspectionWorkspaceItem>> listInspections() async {
    final officer = await _requireOfficerIdentity();
    final remoteReviewStages = <String, bool>{};

    try {
      final remoteInspections = await reviewClient.listInspections();
      for (final remote in remoteInspections) {
        if (!remote.isReviewStage) {
          continue;
        }
        remoteReviewStages[remote.id] = true;
        if (await drafts.getInspection(remote.id) == null) {
          await drafts.restoreSyncedInspection(
            id: remote.id,
            officerUserId: officer.userId,
            productName: remote.productName,
            productIdentifier: remote.productIdentifier,
            createdAt: remote.createdAt,
            updatedAt: remote.updatedAt,
          );
        }
      }
    } catch (_) {
      // The Officer workspace remains fully usable from local storage
      // when the server cannot be reached.
    }

    final inspections = await drafts.listInspectionsForOfficer(
      officer.userId,
    );

    final items = <OfficerInspectionWorkspaceItem>[];
    for (final inspection in inspections) {
      final evidence = await drafts.listEvidenceForInspection(
        inspection.id,
      );
      final summary = await queue.inspectionSyncSummary(
        inspection.id,
      );
      final operations = await queue.listForInspection(inspection.id);
      items.add(
        OfficerInspectionWorkspaceItem(
          inspection: inspection,
          syncSummary: summary,
          evidenceCount: evidence.length,
          reviewStageQueued:
              remoteReviewStages[inspection.id] == true ||
              operations.any(
                (operation) =>
                    operation.type == SyncOperationType.submitInspection,
              ),
        ),
      );
    }
    return List<OfficerInspectionWorkspaceItem>.unmodifiable(items);
  }

  Future<OfficerInspectionWorkspaceItem> inspection(
    String inspectionId,
  ) async {
    final officer = await _requireOfficerIdentity();
    final inspection = await drafts.getInspection(inspectionId);
    if (inspection == null ||
        inspection.officerUserId != officer.userId) {
      throw StateError(
        "Inspection is unavailable for the current Officer.",
      );
    }
    final evidence = await drafts.listEvidenceForInspection(
      inspectionId,
    );
    final operations = await queue.listForInspection(inspectionId);

    var remoteReviewStage = false;
    try {
      remoteReviewStage =
          (await reviewClient.inspectionSummary(inspectionId)).isReviewStage;
    } catch (_) {
      // Fall back to local queue history when offline.
    }

    return OfficerInspectionWorkspaceItem(
      inspection: inspection,
      syncSummary: await queue.inspectionSyncSummary(inspectionId),
      evidenceCount: evidence.length,
      reviewStageQueued:
          remoteReviewStage ||
          operations.any(
            (operation) =>
                operation.type == SyncOperationType.submitInspection,
          ),
    );
  }

  Future<List<LocalEvidenceRecord>> listEvidence(
    String inspectionId,
  ) async {
    final officer = await _requireOfficerIdentity();
    final inspection = await drafts.getInspection(inspectionId);
    if (inspection == null ||
        inspection.officerUserId != officer.userId) {
      throw StateError(
        "Inspection is unavailable for the current Officer.",
      );
    }
    return drafts.listEvidenceForInspection(inspectionId);
  }

  Future<LocalInspectionCreation> createInspection({
    required String productName,
    String? productIdentifier,
    DateTime? now,
  }) async {
    final officer = await _requireOfficerIdentity();
    return workflow.createInspection(
      officer: officer,
      productName: productName,
      productIdentifier: productIdentifier,
      now: now,
    );
  }

  Future<void> updateInspectionDetails({
    required String inspectionId,
    required String productName,
    String? productIdentifier,
    DateTime? now,
  }) async {
    final officer = await _requireOfficerIdentity();
    await workflow.updateInspectionDetails(
      officer: officer,
      inspectionId: inspectionId,
      productName: productName,
      productIdentifier: productIdentifier,
      now: now,
    );
  }

  Future<void> discardInspection({
    required String inspectionId,
    DateTime? now,
  }) async {
    final officer = await _requireOfficerIdentity();
    await workflow.discardInspection(
      officer: officer,
      inspectionId: inspectionId,
      now: now,
    );
  }

  Future<LocalEvidencePipeline> addEvidence({
    required String inspectionId,
    required String viewType,
    required Uint8List bytes,
    String? originalFilename,
    DateTime? now,
  }) async {
    final officer = await _requireOfficerIdentity();
    return workflow.addEvidence(
      officer: officer,
      inspectionId: inspectionId,
      viewType: viewType,
      bytes: bytes,
      originalFilename: originalFilename,
      now: now,
    );
  }

  Future<void> removeEvidence({
    required String evidenceId,
    DateTime? now,
  }) async {
    final officer = await _requireOfficerIdentity();
    await workflow.removeEvidence(
      officer: officer,
      evidenceId: evidenceId,
      now: now,
    );
  }

  Future<InspectionSubmissionPipeline> queueForReview({
    required String inspectionId,
    required Map<String, Object?> ruleContext,
    DateTime? now,
  }) async {
    final officer = await _requireOfficerIdentity();
    return workflow.queueForReview(
      officer: officer,
      inspectionId: inspectionId,
      ruleContext: ruleContext,
      now: now,
    );
  }

  Future<OfficerReviewState> loadOfficerReviewState(
    String inspectionId,
  ) async {
    await _requireOfficerIdentity();
    return reviewClient.load(inspectionId);
  }

  Future<void> queueOfficerReview({
    required String inspectionId,
    required String ruleEvaluationResultId,
    required String decision,
    Map<String, Object?>? correctedValue,
    String? note,
    DateTime? now,
  }) async {
    final officer = await _requireOfficerIdentity();
    await workflow.queueOfficerReview(
      officer: officer,
      inspectionId: inspectionId,
      ruleEvaluationResultId: ruleEvaluationResultId,
      decision: decision,
      correctedValue: correctedValue,
      note: note,
      now: now,
    );
  }

  Future<void> queueFinalization({
    required String inspectionId,
    DateTime? now,
  }) async {
    final officer = await _requireOfficerIdentity();
    await workflow.queueFinalization(
      officer: officer,
      inspectionId: inspectionId,
      now: now,
    );
  }

  Future<WorkspaceSyncResult> syncNow({DateTime? now}) async {
    await _requireOfficerIdentity();
    final token = await sessionStore.readValidAccessToken(now: now);
    if (token == null || token.trim().isEmpty) {
      return const WorkspaceSyncResult.authenticationRequired();
    }

    final summary = await syncService.recoverAndDrain(now: now);
    return WorkspaceSyncResult.completed(summary);
  }

  Future<void> signOut() => sessionStore.clear();

  Future<OfficerSessionContext> _requireOfficerIdentity() async {
    final session = await currentOfficerIdentity();
    if (session == null) {
      throw StateError(
        "No authenticated Officer identity is available on this device.",
      );
    }
    return session;
  }
}
