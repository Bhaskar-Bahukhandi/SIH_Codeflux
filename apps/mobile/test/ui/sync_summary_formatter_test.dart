import "package:flutter_test/flutter_test.dart";

import "package:codeflux_mobile/offline/sync/offline_sync_service.dart";
import "package:codeflux_mobile/ui/sync_summary_formatter.dart";

SyncDrainSummary summary({
  required int processed,
  required int synced,
  int retryScheduled = 0,
  int blocked = 0,
  int conflicts = 0,
  int reconciliationRequired = 0,
  bool limitReached = false,
}) {
  return SyncDrainSummary(
    recoveredInterrupted: 0,
    processed: processed,
    synced: synced,
    retryScheduled: retryScheduled,
    blocked: blocked,
    conflicts: conflicts,
    reconciliationRequired: reconciliationRequired,
    limitReached: limitReached,
  );
}

void main() {
  test("reports retry work instead of hiding it", () {
    expect(
      formatSyncDrainSummary(
        summary(
          processed: 8,
          synced: 5,
          retryScheduled: 3,
        ),
      ),
      "Sync incomplete: 8 tasks processed — 5 synced, 3 waiting to retry.",
    );
  });

  test("reports reconciliation, conflicts, blocked work and drain limit", () {
    expect(
      formatSyncDrainSummary(
        summary(
          processed: 6,
          synced: 2,
          retryScheduled: 1,
          reconciliationRequired: 1,
          conflicts: 1,
          blocked: 1,
          limitReached: true,
        ),
      ),
      "Sync incomplete: 6 tasks processed — 2 synced, 1 waiting to retry, "
      "1 waiting for reconciliation, 1 conflict, 1 blocked. "
      "More queued work remains.",
    );
  });

  test("uses concise complete message when everything synced", () {
    expect(
      formatSyncDrainSummary(summary(processed: 4, synced: 4)),
      "Sync complete: 4 tasks synced.",
    );
  });

  test("reports idle drains without implying work was completed", () {
    expect(
      formatSyncDrainSummary(summary(processed: 0, synced: 0)),
      "Nothing needed syncing.",
    );
  });
}
