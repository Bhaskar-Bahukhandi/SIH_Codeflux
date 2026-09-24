import "package:uuid/uuid.dart";

import "../models/local_records.dart";
import "../models/sync_operation.dart";

class SyncOperationFactory {
  SyncOperationFactory({Uuid? uuid}) : _uuid = uuid ?? Uuid();

  final Uuid _uuid;

  SyncOperation createInspection(
    LocalInspectionDraft draft, {
    String? operationId,
    DateTime? now,
  }) {
    return SyncOperation.queued(
      id: operationId ?? _uuid.v4(),
      inspectionId: draft.id,
      type: SyncOperationType.createInspection,
      resourceId: draft.id,
      payload: <String, Object?>{
        "id": draft.id,
        "product_name": draft.productName,
        "product_identifier": draft.productIdentifier,
      },
      now: now,
    );
  }

  SyncOperation updateInspection({
    required String inspectionId,
    required String productName,
    String? productIdentifier,
    List<String> dependencyIds = const <String>[],
    String? operationId,
    DateTime? now,
  }) {
    return SyncOperation.queued(
      id: operationId ?? _uuid.v4(),
      inspectionId: inspectionId,
      type: SyncOperationType.updateInspection,
      resourceId: inspectionId,
      payload: <String, Object?>{
        "product_name": productName,
        "product_identifier": productIdentifier,
      },
      dependencyIds: dependencyIds,
      now: now,
    );
  }

  SyncOperation discardInspection({
    required String inspectionId,
    List<String> dependencyIds = const <String>[],
    String? operationId,
    DateTime? now,
  }) {
    return SyncOperation.queued(
      id: operationId ?? _uuid.v4(),
      inspectionId: inspectionId,
      type: SyncOperationType.discardInspection,
      resourceId: inspectionId,
      payload: const <String, Object?>{},
      dependencyIds: dependencyIds,
      now: now,
    );
  }

  SyncOperation uploadCapture(
    LocalEvidenceRecord evidence, {
    required String createInspectionOperationId,
    String? operationId,
    DateTime? now,
  }) {
    return SyncOperation.queued(
      id: operationId ?? _uuid.v4(),
      inspectionId: evidence.inspectionId,
      type: SyncOperationType.uploadCapture,
      resourceId: evidence.id,
      payload: <String, Object?>{
        "capture_id": evidence.id,
        "view_type": evidence.viewType,
        "local_path": evidence.localPath,
        "sha256": evidence.sha256,
        "size_bytes": evidence.sizeBytes,
      },
      dependencyIds: <String>[createInspectionOperationId],
      now: now,
    );
  }

  SyncOperation discardCapture({
    required String inspectionId,
    required String captureId,
    List<String> dependencyIds = const <String>[],
    String? operationId,
    DateTime? now,
  }) {
    return SyncOperation.queued(
      id: operationId ?? _uuid.v4(),
      inspectionId: inspectionId,
      type: SyncOperationType.discardCapture,
      resourceId: captureId,
      payload: <String, Object?>{
        "capture_id": captureId,
      },
      dependencyIds: dependencyIds,
      now: now,
    );
  }

  SyncOperation processCapture({
    required String inspectionId,
    required String captureId,
    required String derivativeId,
    required String qualityAssessmentId,
    List<String> dependencyIds = const <String>[],
    String? operationId,
    DateTime? now,
  }) {
    return SyncOperation.queued(
      id: operationId ?? _uuid.v4(),
      inspectionId: inspectionId,
      type: SyncOperationType.processCapture,
      resourceId: qualityAssessmentId,
      payload: <String, Object?>{
        "capture_id": captureId,
        "derivative_id": derivativeId,
        "quality_assessment_id": qualityAssessmentId,
      },
      dependencyIds: dependencyIds,
      now: now,
    );
  }

  SyncOperation analyzeGeometry({
    required String inspectionId,
    required String captureId,
    required String geometryAssessmentId,
    required String correctedDerivativeId,
    List<String> dependencyIds = const <String>[],
    String? operationId,
    DateTime? now,
  }) {
    return SyncOperation.queued(
      id: operationId ?? _uuid.v4(),
      inspectionId: inspectionId,
      type: SyncOperationType.analyzeGeometry,
      resourceId: geometryAssessmentId,
      payload: <String, Object?>{
        "capture_id": captureId,
        "geometry_assessment_id": geometryAssessmentId,
        "corrected_derivative_id": correctedDerivativeId,
      },
      dependencyIds: dependencyIds,
      now: now,
    );
  }

  SyncOperation runOcr({
    required String inspectionId,
    required String captureId,
    required String ocrRunId,
    List<String> dependencyIds = const <String>[],
    String? operationId,
    DateTime? now,
  }) {
    return SyncOperation.queued(
      id: operationId ?? _uuid.v4(),
      inspectionId: inspectionId,
      type: SyncOperationType.runOcr,
      resourceId: ocrRunId,
      payload: <String, Object?>{
        "id": ocrRunId,
        "capture_id": captureId,
      },
      dependencyIds: dependencyIds,
      now: now,
    );
  }

  SyncOperation extractDeclarations({
    required String inspectionId,
    required String extractionRunId,
    List<String> dependencyIds = const <String>[],
    String? operationId,
    DateTime? now,
  }) {
    return SyncOperation.queued(
      id: operationId ?? _uuid.v4(),
      inspectionId: inspectionId,
      type: SyncOperationType.extractDeclarations,
      resourceId: extractionRunId,
      payload: <String, Object?>{
        "id": extractionRunId,
      },
      dependencyIds: dependencyIds,
      now: now,
    );
  }

  SyncOperation evaluateRules({
    required String inspectionId,
    required String evaluationRunId,
    required Map<String, Object?> context,
    List<String> dependencyIds = const <String>[],
    String? operationId,
    DateTime? now,
  }) {
    return SyncOperation.queued(
      id: operationId ?? _uuid.v4(),
      inspectionId: inspectionId,
      type: SyncOperationType.evaluateRules,
      resourceId: evaluationRunId,
      payload: <String, Object?>{
        "id": evaluationRunId,
        "context": Map<String, Object?>.unmodifiable(context),
      },
      dependencyIds: dependencyIds,
      now: now,
    );
  }

  SyncOperation submitInspection({
    required String inspectionId,
    DateTime? reopenedForRecheckAt,
    List<String> dependencyIds = const <String>[],
    String? operationId,
    DateTime? now,
  }) {
    return SyncOperation.queued(
      id: operationId ?? _uuid.v4(),
      inspectionId: inspectionId,
      type: SyncOperationType.submitInspection,
      resourceId: inspectionId,
      payload: <String, Object?>{
        "reopened_for_recheck_at":
            reopenedForRecheckAt?.toUtc().toIso8601String(),
      },
      dependencyIds: dependencyIds,
      now: now,
    );
  }

  SyncOperation reopenForRecheck({
    required String inspectionId,
    DateTime? previousReopenedForRecheckAt,
    List<String> dependencyIds = const <String>[],
    String? operationId,
    DateTime? now,
  }) {
    return SyncOperation.queued(
      id: operationId ?? _uuid.v4(),
      inspectionId: inspectionId,
      type: SyncOperationType.reopenForRecheck,
      resourceId: inspectionId,
      payload: <String, Object?>{
        "previous_reopened_for_recheck_at":
            previousReopenedForRecheckAt?.toUtc().toIso8601String(),
      },
      dependencyIds: dependencyIds,
      now: now,
    );
  }

  SyncOperation createOfficerReview({
    required String inspectionId,
    required String reviewId,
    required String ruleEvaluationResultId,
    required String decision,
    Map<String, Object?>? correctedValue,
    String? note,
    List<String> dependencyIds = const <String>[],
    String? operationId,
    DateTime? now,
  }) {
    final normalizedNote = note?.trim();
    return SyncOperation.queued(
      id: operationId ?? _uuid.v4(),
      inspectionId: inspectionId,
      type: SyncOperationType.createOfficerReview,
      resourceId: reviewId,
      payload: <String, Object?>{
        "id": reviewId,
        "rule_evaluation_result_id": ruleEvaluationResultId,
        "decision": decision,
        if (correctedValue != null) "corrected_value": correctedValue,
        if (normalizedNote != null && normalizedNote.isNotEmpty)
          "note": normalizedNote,
      },
      dependencyIds: dependencyIds,
      now: now,
    );
  }
}
