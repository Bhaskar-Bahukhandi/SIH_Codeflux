import "dart:typed_data";

import "package:uuid/uuid.dart";

import "../../auth/officer_session_store.dart";
import "../models/local_records.dart";
import "../models/sync_operation.dart";
import "../persistence/local_draft_repository.dart";
import "../persistence/sync_queue_repository.dart";
import "../storage/local_evidence_store.dart";
import "../sync/sync_operation_factory.dart";

class LocalInspectionCreation {
  const LocalInspectionCreation({
    required this.inspection,
    required this.createOperation,
  });

  final LocalInspectionDraft inspection;
  final SyncOperation createOperation;
}

class LocalEvidencePipeline {
  const LocalEvidencePipeline({
    required this.evidence,
    required this.uploadOperation,
    required this.processOperation,
    required this.geometryOperation,
    required this.ocrOperation,
  });

  final LocalEvidenceRecord evidence;
  final SyncOperation uploadOperation;
  final SyncOperation processOperation;
  final SyncOperation geometryOperation;
  final SyncOperation ocrOperation;
}

class InspectionSubmissionPipeline {
  const InspectionSubmissionPipeline({
    required this.extractionOperation,
    required this.evaluationOperation,
    required this.submitOperation,
  });

  final SyncOperation extractionOperation;
  final SyncOperation evaluationOperation;
  final SyncOperation submitOperation;
}

class FieldInspectionWorkflowService {
  FieldInspectionWorkflowService({
    required this.drafts,
    required this.queue,
    required this.evidenceStore,
    SyncOperationFactory? operationFactory,
    Uuid? uuid,
  })  : operationFactory = operationFactory ?? SyncOperationFactory(),
        _uuid = uuid ?? Uuid();

  final LocalDraftRepository drafts;
  final SyncQueueRepository queue;
  final LocalEvidenceStore evidenceStore;
  final SyncOperationFactory operationFactory;
  final Uuid _uuid;

  Future<LocalInspectionCreation> createInspection({
    required OfficerSessionContext officer,
    required String productName,
    String? productIdentifier,
    DateTime? now,
  }) async {
    _requireOfficer(officer);
    final timestamp = (now ?? DateTime.now().toUtc()).toUtc();
    final inspectionId = _uuid.v4();

    final draft = await drafts.createInspection(
      id: inspectionId,
      officerUserId: officer.userId,
      productName: productName,
      productIdentifier: productIdentifier,
      now: timestamp,
    );
    final createOperation = operationFactory.createInspection(
      draft,
      now: timestamp,
    );
    final queued = await queue.enqueue(createOperation);

    return LocalInspectionCreation(
      inspection: (await drafts.getInspection(inspectionId))!,
      createOperation: queued,
    );
  }

  Future<void> updateInspectionDetails({
    required OfficerSessionContext officer,
    required String inspectionId,
    required String productName,
    String? productIdentifier,
    DateTime? now,
  }) async {
    _requireOfficer(officer);
    final draft = await _ownedInspection(
      officer: officer,
      inspectionId: inspectionId,
    );
    final existing = await queue.listForInspection(inspectionId);

    if (existing.any(
      (operation) => operation.type == SyncOperationType.discardInspection,
    )) {
      throw StateError("Discarded inspections cannot be edited.");
    }
    if (existing.any(
      (operation) => operation.type == SyncOperationType.submitInspection,
    )) {
      throw StateError(
        "Inspection details can only be edited before preliminary review is queued.",
      );
    }

    final normalizedName = productName.trim();
    final normalizedIdentifier = productIdentifier?.trim();
    final finalIdentifier =
        normalizedIdentifier == null || normalizedIdentifier.isEmpty
            ? null
            : normalizedIdentifier;
    if (draft.productName == normalizedName &&
        draft.productIdentifier == finalIdentifier) {
      return;
    }

    final createOperation = await ensureInspectionQueued(
      officer: officer,
      inspectionId: inspectionId,
      now: now,
    );
    final updates = existing
        .where(
          (operation) => operation.type == SyncOperationType.updateInspection,
        )
        .toList(growable: false);
    final dependencyId =
        updates.isEmpty ? createOperation.id : updates.last.id;

    await drafts.updateInspectionDetails(
      id: inspectionId,
      productName: normalizedName,
      productIdentifier: finalIdentifier,
      now: now,
    );

    try {
      await queue.enqueue(
        operationFactory.updateInspection(
          inspectionId: inspectionId,
          productName: normalizedName,
          productIdentifier: finalIdentifier,
          dependencyIds: <String>[dependencyId],
          now: now,
        ),
      );
    } catch (_) {
      await drafts.updateInspectionDetails(
        id: inspectionId,
        productName: draft.productName,
        productIdentifier: draft.productIdentifier,
        now: now,
      );
      rethrow;
    }
  }

  Future<void> discardInspection({
    required OfficerSessionContext officer,
    required String inspectionId,
    DateTime? now,
  }) async {
    _requireOfficer(officer);
    await _ownedInspection(
      officer: officer,
      inspectionId: inspectionId,
    );
    final existing = await queue.listForInspection(inspectionId);

    if (existing.any(
      (operation) => operation.type == SyncOperationType.submitInspection,
    )) {
      throw StateError(
        "An inspection cannot be discarded after preliminary review has been queued.",
      );
    }

    final existingDiscard = existing.where(
      (operation) => operation.type == SyncOperationType.discardInspection,
    );
    if (existingDiscard.isNotEmpty) {
      await drafts.markInspectionDiscarded(inspectionId, now: now);
      return;
    }

    final createOperation = await ensureInspectionQueued(
      officer: officer,
      inspectionId: inspectionId,
      now: now,
    );
    await queue.cancelPendingWorkForInspectionDiscard(inspectionId);

    await queue.enqueue(
      operationFactory.discardInspection(
        inspectionId: inspectionId,
        dependencyIds: <String>[createOperation.id],
        now: now,
      ),
    );
    await drafts.markInspectionDiscarded(inspectionId, now: now);
  }

  Future<SyncOperation> ensureInspectionQueued({
    required OfficerSessionContext officer,
    required String inspectionId,
    DateTime? now,
  }) async {
    _requireOfficer(officer);
    final draft = await _ownedInspection(
      officer: officer,
      inspectionId: inspectionId,
    );

    final existing = await queue.singleResourceOperation(
      inspectionId: inspectionId,
      type: SyncOperationType.createInspection,
      resourceId: inspectionId,
    );
    if (existing != null) {
      return existing;
    }

    if (draft.remoteId != null) {
      throw StateError(
        "Inspection is already mapped to a remote resource but has no create operation history.",
      );
    }

    return queue.enqueue(
      operationFactory.createInspection(
        draft,
        now: now,
      ),
    );
  }

  Future<LocalEvidencePipeline> addEvidence({
    required OfficerSessionContext officer,
    required String inspectionId,
    required String viewType,
    required Uint8List bytes,
    String? originalFilename,
    DateTime? now,
  }) async {
    _requireOfficer(officer);
    await _ownedInspection(
      officer: officer,
      inspectionId: inspectionId,
    );

    final normalizedView = viewType.trim();
    if (normalizedView.isEmpty) {
      throw ArgumentError.value(viewType, "viewType", "Must not be blank.");
    }
    if (bytes.isEmpty) {
      throw ArgumentError.value(bytes, "bytes", "Evidence must not be empty.");
    }

    final timestamp = (now ?? DateTime.now().toUtc()).toUtc();
    final evidenceId = _uuid.v4();
    final stored = await evidenceStore.persistBytes(
      inspectionId: inspectionId,
      evidenceId: evidenceId,
      bytes: bytes,
      originalFilename: originalFilename,
    );

    final evidence = await drafts.registerEvidence(
      id: evidenceId,
      inspectionId: inspectionId,
      viewType: normalizedView,
      localPath: stored.path,
      sha256: stored.sha256,
      sizeBytes: stored.sizeBytes,
      now: timestamp,
    );

    final createOperation = await ensureInspectionQueued(
      officer: officer,
      inspectionId: inspectionId,
      now: timestamp,
    );

    return _ensureEvidencePipeline(
      evidence: evidence,
      createInspectionOperationId: createOperation.id,
      now: timestamp,
    );
  }

  Future<LocalEvidencePipeline> ensureEvidencePipeline({
    required OfficerSessionContext officer,
    required String evidenceId,
    DateTime? now,
  }) async {
    _requireOfficer(officer);
    final evidence = await drafts.getEvidence(evidenceId);
    if (evidence == null) {
      throw StateError("Local evidence does not exist.");
    }
    if (evidence.discardedAt != null) {
      throw StateError("Removed evidence cannot be processed again.");
    }
    await _ownedInspection(
      officer: officer,
      inspectionId: evidence.inspectionId,
    );
    final createOperation = await ensureInspectionQueued(
      officer: officer,
      inspectionId: evidence.inspectionId,
      now: now,
    );

    return _ensureEvidencePipeline(
      evidence: evidence,
      createInspectionOperationId: createOperation.id,
      now: now,
    );
  }

  Future<void> removeEvidence({
    required OfficerSessionContext officer,
    required String inspectionId,
    required String evidenceId,
    DateTime? now,
  }) async {
    _requireOfficer(officer);
    await _ownedInspection(
      officer: officer,
      inspectionId: inspectionId,
    );

    final evidence = await drafts.getEvidence(evidenceId);
    if (evidence == null || evidence.inspectionId != inspectionId) {
      throw StateError("Local evidence does not exist for this inspection.");
    }
    if (evidence.discardedAt != null) {
      return;
    }

    final existing = await queue.listForInspection(inspectionId);
    if (existing.any(
      (operation) => operation.type == SyncOperationType.submitInspection,
    )) {
      throw StateError(
        "Images can only be removed before preliminary review is queued.",
      );
    }

    final existingDiscard = existing.where(
      (operation) =>
          operation.type == SyncOperationType.discardCapture &&
          operation.resourceId == evidenceId,
    );
    if (existingDiscard.isNotEmpty) {
      await queue.cancelPendingEvidenceWork(
        inspectionId: inspectionId,
        evidenceId: evidenceId,
        keepUpload: true,
      );
      await drafts.markEvidenceDiscarded(evidenceId, now: now);
      return;
    }

    final plan = await queue.evidenceDiscardPlan(
      inspectionId: inspectionId,
      evidenceId: evidenceId,
    );

    if (plan.requiresRemoteDiscard) {
      await queue.enqueue(
        operationFactory.discardCapture(
          inspectionId: inspectionId,
          captureId: evidenceId,
          dependencyIds: <String>[plan.uploadOperationId!],
          now: now,
        ),
      );
    }

    await queue.cancelPendingEvidenceWork(
      inspectionId: inspectionId,
      evidenceId: evidenceId,
      keepUpload: plan.requiresRemoteDiscard,
    );
    await drafts.markEvidenceDiscarded(evidenceId, now: now);
  }

  Future<InspectionSubmissionPipeline> queueForReview({
    required OfficerSessionContext officer,
    required String inspectionId,
    required Map<String, Object?> ruleContext,
    DateTime? now,
  }) async {
    _requireOfficer(officer);
    await _ownedInspection(
      officer: officer,
      inspectionId: inspectionId,
    );
    _validateRuleContext(ruleContext);

    final evidence = await drafts.listEvidenceForInspection(inspectionId);
    if (evidence.isEmpty) {
      throw StateError(
        "At least one local package image is required before submission.",
      );
    }

    final timestamp = (now ?? DateTime.now().toUtc()).toUtc();
    final createOperation = await ensureInspectionQueued(
      officer: officer,
      inspectionId: inspectionId,
      now: timestamp,
    );

    final ocrDependencies = <String>[];
    for (final record in evidence) {
      final pipeline = await _ensureEvidencePipeline(
        evidence: record,
        createInspectionOperationId: createOperation.id,
        now: timestamp,
      );
      ocrDependencies.add(pipeline.ocrOperation.id);
    }

    final existing = await queue.listForInspection(inspectionId);
    final detailUpdates = existing
        .where(
          (operation) => operation.type == SyncOperationType.updateInspection,
        )
        .toList(growable: false);
    if (detailUpdates.isNotEmpty) {
      ocrDependencies.add(detailUpdates.last.id);
    }
    final captureDiscards = existing
        .where(
          (operation) => operation.type == SyncOperationType.discardCapture,
        )
        .toList(growable: false);
    for (final discard in captureDiscards) {
      ocrDependencies.add(discard.id);
    }

    final extractionExisting = _singleType(
      existing,
      SyncOperationType.extractDeclarations,
    );
    final evaluationExisting = _singleType(
      existing,
      SyncOperationType.evaluateRules,
    );
    final submissionExisting = _singleType(
      existing,
      SyncOperationType.submitInspection,
    );

    if (extractionExisting != null ||
        evaluationExisting != null ||
        submissionExisting != null) {
      if (extractionExisting == null ||
          evaluationExisting == null ||
          submissionExisting == null) {
        throw StateError(
          "Inspection has an incomplete existing submission pipeline.",
        );
      }
      if (canonicalJsonEncode(evaluationExisting.payload["context"]) !=
          canonicalJsonEncode(ruleContext)) {
        throw StateError(
          "Inspection already has a queued rule evaluation with different applicability context.",
        );
      }
      return InspectionSubmissionPipeline(
        extractionOperation: extractionExisting,
        evaluationOperation: evaluationExisting,
        submitOperation: submissionExisting,
      );
    }

    final extraction = await queue.enqueue(
      operationFactory.extractDeclarations(
        inspectionId: inspectionId,
        extractionRunId: _uuid.v4(),
        dependencyIds: List<String>.unmodifiable(ocrDependencies),
        now: timestamp,
      ),
    );
    final evaluation = await queue.enqueue(
      operationFactory.evaluateRules(
        inspectionId: inspectionId,
        evaluationRunId: _uuid.v4(),
        context: ruleContext,
        dependencyIds: <String>[extraction.id],
        now: timestamp,
      ),
    );
    final submission = await queue.enqueue(
      operationFactory.submitInspection(
        inspectionId: inspectionId,
        dependencyIds: <String>[evaluation.id],
        now: timestamp,
      ),
    );

    return InspectionSubmissionPipeline(
      extractionOperation: extraction,
      evaluationOperation: evaluation,
      submitOperation: submission,
    );
  }

  Future<LocalEvidencePipeline> _ensureEvidencePipeline({
    required LocalEvidenceRecord evidence,
    required String createInspectionOperationId,
    DateTime? now,
  }) async {
    final existing = await queue.listForInspection(evidence.inspectionId);
    final upload = _singleCaptureType(
      existing,
      SyncOperationType.uploadCapture,
      evidence.id,
    );
    final process = _singleCaptureType(
      existing,
      SyncOperationType.processCapture,
      evidence.id,
    );
    final geometry = _singleCaptureType(
      existing,
      SyncOperationType.analyzeGeometry,
      evidence.id,
    );
    final ocr = _singleCaptureType(
      existing,
      SyncOperationType.runOcr,
      evidence.id,
    );

    if (upload != null || process != null || geometry != null || ocr != null) {
      if (upload == null || process == null || geometry == null || ocr == null) {
        throw StateError(
          "Evidence has an incomplete existing processing pipeline.",
        );
      }
      return LocalEvidencePipeline(
        evidence: evidence,
        uploadOperation: upload,
        processOperation: process,
        geometryOperation: geometry,
        ocrOperation: ocr,
      );
    }

    final timestamp = (now ?? DateTime.now().toUtc()).toUtc();
    final uploadQueued = await queue.enqueue(
      operationFactory.uploadCapture(
        evidence,
        createInspectionOperationId: createInspectionOperationId,
        now: timestamp,
      ),
    );
    final processQueued = await queue.enqueue(
      operationFactory.processCapture(
        inspectionId: evidence.inspectionId,
        captureId: evidence.id,
        derivativeId: _uuid.v4(),
        qualityAssessmentId: _uuid.v4(),
        dependencyIds: <String>[uploadQueued.id],
        now: timestamp,
      ),
    );
    final geometryQueued = await queue.enqueue(
      operationFactory.analyzeGeometry(
        inspectionId: evidence.inspectionId,
        captureId: evidence.id,
        geometryAssessmentId: _uuid.v4(),
        correctedDerivativeId: _uuid.v4(),
        dependencyIds: <String>[processQueued.id],
        now: timestamp,
      ),
    );
    final ocrQueued = await queue.enqueue(
      operationFactory.runOcr(
        inspectionId: evidence.inspectionId,
        captureId: evidence.id,
        ocrRunId: _uuid.v4(),
        dependencyIds: <String>[geometryQueued.id],
        now: timestamp,
      ),
    );

    return LocalEvidencePipeline(
      evidence: (await drafts.getEvidence(evidence.id))!,
      uploadOperation: uploadQueued,
      processOperation: processQueued,
      geometryOperation: geometryQueued,
      ocrOperation: ocrQueued,
    );
  }

  Future<LocalInspectionDraft> _ownedInspection({
    required OfficerSessionContext officer,
    required String inspectionId,
  }) async {
    final draft = await drafts.getInspection(inspectionId);
    if (draft == null) {
      throw StateError("Local inspection does not exist.");
    }
    if (draft.officerUserId == null ||
        draft.officerUserId != officer.userId) {
      throw StateError(
        "Local inspection belongs to a different Officer session.",
      );
    }
    return draft;
  }

  void _requireOfficer(OfficerSessionContext officer) {
    if (officer.userId.trim().isEmpty) {
      throw StateError(
        "Local field work requires a persisted authenticated Officer identity.",
      );
    }
    if (officer.role.toLowerCase() != "officer") {
      throw StateError(
        "Only an Officer session can create or modify field inspections.",
      );
    }
  }

  void _validateRuleContext(Map<String, Object?> context) {
    const requiredBooleanFields = <String>[
      "intended_for_retail_sale",
      "industrial_or_institutional_consumer",
      "package_exceeds_25kg_or_25l",
    ];
    for (final key in requiredBooleanFields) {
      if (context[key] is! bool) {
        throw ArgumentError.value(
          context,
          "ruleContext",
          "Missing required boolean field: " + key,
        );
      }
    }
  }

  SyncOperation? _singleType(
    List<SyncOperation> operations,
    SyncOperationType type,
  ) {
    final matches = operations
        .where((operation) => operation.type == type)
        .toList(growable: false);
    if (matches.isEmpty) {
      return null;
    }
    if (matches.length != 1) {
      throw StateError(
        "Inspection has multiple " + type.dbValue + " operations.",
      );
    }
    return matches.single;
  }

  SyncOperation? _singleCaptureType(
    List<SyncOperation> operations,
    SyncOperationType type,
    String captureId,
  ) {
    final matches = operations.where((operation) {
      if (operation.type != type) {
        return false;
      }
      if (type == SyncOperationType.uploadCapture) {
        return operation.resourceId == captureId;
      }
      return operation.payload["capture_id"] == captureId;
    }).toList(growable: false);

    if (matches.isEmpty) {
      return null;
    }
    if (matches.length != 1) {
      throw StateError(
        "Capture has multiple " + type.dbValue + " operations.",
      );
    }
    return matches.single;
  }
}
