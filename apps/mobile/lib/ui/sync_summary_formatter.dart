import "../offline/sync/offline_sync_service.dart";

String formatSyncDrainSummary(SyncDrainSummary summary) {
  if (summary.processed == 0) {
    return "Nothing needed syncing.";
  }

  final outstanding =
      summary.retryScheduled +
      summary.reconciliationRequired +
      summary.conflicts +
      summary.blocked;

  if (outstanding == 0 && !summary.limitReached) {
    return "Sync complete: ${summary.synced} ${_taskWord(summary.synced)} synced.";
  }

  final parts = <String>[
    "${summary.synced} synced",
    if (summary.retryScheduled > 0)
      "${summary.retryScheduled} waiting to retry",
    if (summary.reconciliationRequired > 0)
      "${summary.reconciliationRequired} waiting for reconciliation",
    if (summary.conflicts > 0)
      "${summary.conflicts} ${_conflictWord(summary.conflicts)}",
    if (summary.blocked > 0)
      "${summary.blocked} blocked",
  ];

  final moreWork = summary.limitReached
      ? " More queued work remains."
      : "";

  return "Sync incomplete: ${summary.processed} "
      "${_taskWord(summary.processed)} processed — ${parts.join(", ")}."
      "$moreWork";
}

String _taskWord(int count) => count == 1 ? "task" : "tasks";

String _conflictWord(int count) => count == 1 ? "conflict" : "conflicts";
