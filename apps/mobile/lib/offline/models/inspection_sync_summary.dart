import "sync_state.dart";

class InspectionSyncSummary {
  const InspectionSyncSummary({
    required this.inspectionId,
    required this.overallState,
    required this.localResourceState,
    required this.operationCounts,
  });

  final String inspectionId;

  /// Aggregate state for the inspection's complete local synchronization graph.
  ///
  /// UI/workflow code should use this value rather than treating the
  /// local inspection record's own sync state as whole-inspection completion.
  final SyncState overallState;

  /// Sync state of the inspection resource itself (the create mutation).
  final SyncState localResourceState;

  final Map<SyncState, int> operationCounts;

  int get totalOperations =>
      operationCounts.values.fold(0, (sum, count) => sum + count);

  bool get isFullySynced => overallState == SyncState.synced;

  int count(SyncState state) => operationCounts[state] ?? 0;
}
