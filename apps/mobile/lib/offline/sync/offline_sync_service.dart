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

class _SyncDrainCounters {
  int processed = 0;
  int synced = 0;
  int retryScheduled = 0;
  int blocked = 0;
  int conflicts = 0;
  int reconciliationRequired = 0;

  void record(SyncCycleResult result) {
    if (result.status == SyncCycleStatus.idle) {
      throw StateError("Idle results are not counted as processed work.");
    }

    processed += 1;
    if (result.status == SyncCycleStatus.synced) {
      synced += 1;
    } else if (result.status == SyncCycleStatus.retryScheduled) {
      retryScheduled += 1;
    } else if (result.status == SyncCycleStatus.blocked) {
      blocked += 1;
    } else if (result.status == SyncCycleStatus.conflict) {
      conflicts += 1;
    } else if (result.status == SyncCycleStatus.reconciliationRequired) {
      reconciliationRequired += 1;
    }
  }
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
    final counters = _SyncDrainCounters();

    final parked = await coordinator.queue.listReconciliationRequired();
    for (final operation in parked) {
      if (counters.processed >= maxOperationsPerDrain) {
        return _summary(
          recoveredInterrupted: recovered,
          counters: counters,
          limitReached: true,
        );
      }

      final result = await coordinator.reconcilePending(
        operation.id,
        now: timestamp,
      );
      counters.record(result);
    }

    return _drain(
      recoveredInterrupted: recovered,
      counters: counters,
      now: timestamp,
    );
  }

  Future<SyncDrainSummary> drain({DateTime? now}) {
    return _drain(
      recoveredInterrupted: 0,
      counters: _SyncDrainCounters(),
      now: (now ?? DateTime.now().toUtc()).toUtc(),
    );
  }

  Future<SyncDrainSummary> _drain({
    required int recoveredInterrupted,
    required _SyncDrainCounters counters,
    required DateTime now,
  }) async {
    while (counters.processed < maxOperationsPerDrain) {
      final result = await coordinator.runNext(now: now);
      if (result.status == SyncCycleStatus.idle) {
        return _summary(
          recoveredInterrupted: recoveredInterrupted,
          counters: counters,
          limitReached: false,
        );
      }

      counters.record(result);
    }

    return _summary(
      recoveredInterrupted: recoveredInterrupted,
      counters: counters,
      limitReached: true,
    );
  }

  SyncDrainSummary _summary({
    required int recoveredInterrupted,
    required _SyncDrainCounters counters,
    required bool limitReached,
  }) {
    return SyncDrainSummary(
      recoveredInterrupted: recoveredInterrupted,
      processed: counters.processed,
      synced: counters.synced,
      retryScheduled: counters.retryScheduled,
      blocked: counters.blocked,
      conflicts: counters.conflicts,
      reconciliationRequired: counters.reconciliationRequired,
      limitReached: limitReached,
    );
  }
}
