import "sync_coordinator.dart";

class SyncDrainSummary {
  const SyncDrainSummary({
    required this.recoveredInterrupted,
    required this.processed,
    required this.synced,
    required this.retryScheduled,
    required this.blocked,
    required this.conflicts,
    required this.reconciliationRequired,
    required this.limitReached,
  });

  final int recoveredInterrupted;
  final int processed;
  final int synced;
  final int retryScheduled;
  final int blocked;
  final int conflicts;
  final int reconciliationRequired;
  final bool limitReached;
}

class OfflineSyncService {
  const OfflineSyncService({
    required this.coordinator,
    this.maxOperationsPerDrain = 50,
  }) : assert(maxOperationsPerDrain > 0);

  final SyncCoordinator coordinator;
  final int maxOperationsPerDrain;

  Future<SyncDrainSummary> recoverAndDrain({DateTime? now}) async {
    final timestamp = (now ?? DateTime.now().toUtc()).toUtc();
    final recovered = await coordinator.queue.recoverInterruptedSyncs(
      now: timestamp,
    );
    return _drain(
      recoveredInterrupted: recovered,
      now: timestamp,
    );
  }

  Future<SyncDrainSummary> drain({DateTime? now}) {
    return _drain(
      recoveredInterrupted: 0,
      now: (now ?? DateTime.now().toUtc()).toUtc(),
    );
  }

  Future<SyncDrainSummary> _drain({
    required int recoveredInterrupted,
    required DateTime now,
  }) async {
    var processed = 0;
    var synced = 0;
    var retryScheduled = 0;
    var blocked = 0;
    var conflicts = 0;
    var reconciliationRequired = 0;

    while (processed < maxOperationsPerDrain) {
      final result = await coordinator.runNext(now: now);
      if (result.status == SyncCycleStatus.idle) {
        return SyncDrainSummary(
          recoveredInterrupted: recoveredInterrupted,
          processed: processed,
          synced: synced,
          retryScheduled: retryScheduled,
          blocked: blocked,
          conflicts: conflicts,
          reconciliationRequired: reconciliationRequired,
          limitReached: false,
        );
      }

      processed += 1;
      switch (result.status) {
        case SyncCycleStatus.synced:
          synced += 1;
        case SyncCycleStatus.retryScheduled:
          retryScheduled += 1;
        case SyncCycleStatus.blocked:
          blocked += 1;
        case SyncCycleStatus.conflict:
          conflicts += 1;
        case SyncCycleStatus.reconciliationRequired:
          reconciliationRequired += 1;
        case SyncCycleStatus.idle:
          throw StateError("Idle result must be handled before counting.");
      }
    }

    return SyncDrainSummary(
      recoveredInterrupted: recoveredInterrupted,
      processed: processed,
      synced: synced,
      retryScheduled: retryScheduled,
      blocked: blocked,
      conflicts: conflicts,
      reconciliationRequired: reconciliationRequired,
      limitReached: true,
    );
  }
}
