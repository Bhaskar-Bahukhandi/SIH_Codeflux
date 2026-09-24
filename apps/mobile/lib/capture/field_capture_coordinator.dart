import "../app/officer_workspace_service.dart";
import "evidence_acquisition_service.dart";
import "pending_capture_repository.dart";

class EvidenceReplacementResult {
  const EvidenceReplacementResult._({
    required this.savedNewEvidence,
    required this.removedOldEvidence,
    this.removalError,
  });

  const EvidenceReplacementResult.cancelled()
      : this._(
          savedNewEvidence: false,
          removedOldEvidence: false,
        );

  const EvidenceReplacementResult.replaced()
      : this._(
          savedNewEvidence: true,
          removedOldEvidence: true,
        );

  const EvidenceReplacementResult.oldEvidenceRetained(String error)
      : this._(
          savedNewEvidence: true,
          removedOldEvidence: false,
          removalError: error,
        );

  final bool savedNewEvidence;
  final bool removedOldEvidence;
  final String? removalError;
}

enum PendingCaptureRecoveryStatus {
  none,
  recovered,
  pendingWithoutRecoveredData,
}

class PendingCaptureRecoveryResult {
  const PendingCaptureRecoveryResult({
    required this.status,
    this.intent,
  });

  final PendingCaptureRecoveryStatus status;
  final PendingCaptureIntent? intent;
}

class FieldCaptureCoordinator {
  const FieldCaptureCoordinator({
    required this.workspace,
    required this.acquisition,
    required this.pendingCaptures,
  });

  final OfficerWorkspaceService workspace;
  final EvidenceAcquisitionService acquisition;
  final PendingCaptureRepository pendingCaptures;

  Future<bool> acquireAndAttach({
    required String inspectionId,
    required String viewType,
    required EvidenceSource source,
    DateTime? now,
  }) async {
    final intent = await pendingCaptures.begin(
      inspectionId: inspectionId,
      viewType: viewType,
      source: source.name,
      now: now,
    );

    AcquiredEvidence? acquired;
    try {
      acquired = await acquisition.acquire(source);
    } catch (_) {
      await pendingCaptures.discard(intent.id);
      rethrow;
    }

    if (acquired == null) {
      await pendingCaptures.discard(intent.id);
      return false;
    }

    await workspace.addEvidence(
      inspectionId: inspectionId,
      viewType: viewType,
      bytes: acquired.bytes,
      originalFilename: acquired.filename,
      now: now,
    );
    await pendingCaptures.complete(intent.id);
    return true;
  }

  Future<EvidenceReplacementResult> replaceAndAttach({
    required String inspectionId,
    required String evidenceId,
    required String viewType,
    required EvidenceSource source,
    DateTime? now,
  }) async {
    final intent = await pendingCaptures.begin(
      inspectionId: inspectionId,
      viewType: viewType,
      source: source.name,
      now: now,
    );

    AcquiredEvidence? acquired;
    try {
      acquired = await acquisition.acquire(source);
    } catch (_) {
      await pendingCaptures.discard(intent.id);
      rethrow;
    }

    if (acquired == null) {
      await pendingCaptures.discard(intent.id);
      return const EvidenceReplacementResult.cancelled();
    }

    await workspace.addEvidence(
      inspectionId: inspectionId,
      viewType: viewType,
      bytes: acquired.bytes,
      originalFilename: acquired.filename,
      now: now,
    );
    await pendingCaptures.complete(intent.id);

    try {
      await workspace.removeEvidence(
        evidenceId: evidenceId,
        now: now,
      );
      return const EvidenceReplacementResult.replaced();
    } catch (error) {
      return EvidenceReplacementResult.oldEvidenceRetained(
        error.toString(),
      );
    }
  }

  Future<PendingCaptureRecoveryResult> recoverInterruptedCapture({
    DateTime? now,
  }) async {
    final intent = await pendingCaptures.current();
    if (intent == null) {
      return const PendingCaptureRecoveryResult(
        status: PendingCaptureRecoveryStatus.none,
      );
    }

    final recovered = await acquisition.recoverLostEvidence();
    if (recovered.isEmpty) {
      return PendingCaptureRecoveryResult(
        status: PendingCaptureRecoveryStatus.pendingWithoutRecoveredData,
        intent: intent,
      );
    }
    if (recovered.length != 1) {
      throw StateError(
        "Recovered image acquisition is ambiguous; expected exactly one image.",
      );
    }

    final image = recovered.single;
    await workspace.addEvidence(
      inspectionId: intent.inspectionId,
      viewType: intent.viewType,
      bytes: image.bytes,
      originalFilename: image.filename,
      now: now,
    );
    await pendingCaptures.complete(intent.id);

    return PendingCaptureRecoveryResult(
      status: PendingCaptureRecoveryStatus.recovered,
      intent: intent,
    );
  }

  Future<void> discardPendingCapture() async {
    final intent = await pendingCaptures.current();
    if (intent != null) {
      await pendingCaptures.discard(intent.id);
    }
  }
}
