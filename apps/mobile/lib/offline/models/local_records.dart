import "sync_state.dart";

class LocalInspectionDraft {
  const LocalInspectionDraft({
    required this.id,
    required this.productName,
    required this.officerUserId,
    required this.syncState,
    required this.createdAt,
    required this.updatedAt,
    this.productIdentifier,
    this.remoteId,
    this.lastErrorKind,
    this.lastErrorCode,
    this.lastErrorMessage,
  });

  final String id;
  final String productName;
  final String? productIdentifier;
  final String? officerUserId;
  final SyncState syncState;
  final String? remoteId;
  final String? lastErrorKind;
  final String? lastErrorCode;
  final String? lastErrorMessage;
  final DateTime createdAt;
  final DateTime updatedAt;
}

class LocalEvidenceRecord {
  const LocalEvidenceRecord({
    required this.id,
    required this.inspectionId,
    required this.viewType,
    required this.localPath,
    required this.sha256,
    required this.sizeBytes,
    required this.syncState,
    required this.createdAt,
    required this.updatedAt,
    this.remoteId,
    this.discardedAt,
  });

  final String id;
  final String inspectionId;
  final String viewType;
  final String localPath;
  final String sha256;
  final int sizeBytes;
  final SyncState syncState;
  final String? remoteId;
  final DateTime? discardedAt;
  final DateTime createdAt;
  final DateTime updatedAt;
}
