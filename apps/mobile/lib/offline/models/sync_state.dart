enum SyncState {
  localOnly("local_only"),
  queued("queued"),
  syncing("syncing"),
  synced("synced"),
  retryRequired("retry_required"),
  conflict("conflict"),
  blocked("blocked");

  const SyncState(this.dbValue);

  final String dbValue;

  static SyncState fromDb(String value) {
    return SyncState.values.firstWhere(
      (state) => state.dbValue == value,
      orElse: () => throw FormatException("Unknown sync state: " + value),
    );
  }
}

class SyncStateMachine {
  const SyncStateMachine._();

  static bool canTransition(SyncState from, SyncState to) {
    if (from == to) {
      return true;
    }

    return switch (from) {
      SyncState.localOnly =>
        to == SyncState.queued || to == SyncState.blocked,
      SyncState.queued =>
        to == SyncState.syncing ||
            to == SyncState.blocked ||
            to == SyncState.conflict,
      SyncState.syncing =>
        to == SyncState.synced ||
            to == SyncState.retryRequired ||
            to == SyncState.blocked ||
            to == SyncState.conflict,
      SyncState.retryRequired =>
        to == SyncState.syncing ||
            to == SyncState.synced ||
            to == SyncState.blocked ||
            to == SyncState.conflict,
      SyncState.conflict =>
        to == SyncState.queued || to == SyncState.blocked,
      SyncState.blocked =>
        to == SyncState.queued || to == SyncState.conflict,
      SyncState.synced => false,
    };
  }

  static void requireTransition(SyncState from, SyncState to) {
    if (!canTransition(from, to)) {
      throw StateError(
        "Invalid sync-state transition: " +
            from.dbValue +
            " -> " +
            to.dbValue,
      );
    }
  }
}
