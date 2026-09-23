import "dart:convert";

import "package:crypto/crypto.dart";

import "sync_state.dart";

enum SyncOperationType {
  createInspection("create_inspection"),
  uploadCapture("upload_capture"),
  processCapture("process_capture"),
  analyzeGeometry("analyze_geometry"),
  runOcr("run_ocr"),
  extractDeclarations("extract_declarations"),
  evaluateRules("evaluate_rules"),
  submitInspection("submit_inspection"),
  createOfficerReview("create_officer_review"),
  reopenForRecheck("reopen_for_recheck"),
  finalizeInspection("finalize_inspection");

  const SyncOperationType(this.dbValue);

  final String dbValue;

  static SyncOperationType fromDb(String value) {
    return SyncOperationType.values.firstWhere(
      (type) => type.dbValue == value,
      orElse: () => throw FormatException("Unknown operation type: " + value),
    );
  }
}

Object? _canonicalize(Object? value) {
  if (value is Map) {
    final entries = value.entries.toList()
      ..sort(
        (left, right) =>
            left.key.toString().compareTo(right.key.toString()),
      );
    return <String, Object?>{
      for (final entry in entries)
        entry.key.toString(): _canonicalize(entry.value),
    };
  }
  if (value is List) {
    return value.map(_canonicalize).toList(growable: false);
  }
  return value;
}

String canonicalJsonEncode(Object? value) {
  return jsonEncode(_canonicalize(value));
}

String payloadSha256(Map<String, Object?> payload) {
  return sha256.convert(utf8.encode(canonicalJsonEncode(payload))).toString();
}

class SyncOperation {
  const SyncOperation({
    required this.id,
    required this.inspectionId,
    required this.type,
    required this.resourceId,
    required this.payload,
    required this.payloadSha256,
    required this.dependencyIds,
    required this.state,
    required this.attemptCount,
    required this.createdAt,
    required this.updatedAt,
    this.nextAttemptAt,
    this.lastAttemptAt,
    this.lastErrorKind,
    this.lastErrorCode,
    this.lastErrorMessage,
    this.remoteResourceId,
  });

  factory SyncOperation.queued({
    required String id,
    required String inspectionId,
    required SyncOperationType type,
    required String resourceId,
    required Map<String, Object?> payload,
    List<String> dependencyIds = const <String>[],
    DateTime? now,
  }) {
    final timestamp = (now ?? DateTime.now().toUtc()).toUtc();
    return SyncOperation(
      id: id,
      inspectionId: inspectionId,
      type: type,
      resourceId: resourceId,
      payload: Map<String, Object?>.unmodifiable(payload),
      payloadSha256: payloadSha256(payload),
      dependencyIds: List<String>.unmodifiable(dependencyIds),
      state: SyncState.queued,
      attemptCount: 0,
      createdAt: timestamp,
      updatedAt: timestamp,
    );
  }

  final String id;
  final String inspectionId;
  final SyncOperationType type;
  final String resourceId;
  final Map<String, Object?> payload;
  final String payloadSha256;
  final List<String> dependencyIds;
  final SyncState state;
  final int attemptCount;
  final DateTime? nextAttemptAt;
  final DateTime? lastAttemptAt;
  final String? lastErrorKind;
  final String? lastErrorCode;
  final String? lastErrorMessage;
  final String? remoteResourceId;
  final DateTime createdAt;
  final DateTime updatedAt;
}
