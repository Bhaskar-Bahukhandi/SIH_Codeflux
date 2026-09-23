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
