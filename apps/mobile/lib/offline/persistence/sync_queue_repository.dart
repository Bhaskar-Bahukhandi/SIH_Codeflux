import "dart:convert";

import "package:sqflite_common/sqlite_api.dart";

import "../models/sync_operation.dart";
import "../models/sync_state.dart";
import "../sync/failure_classifier.dart";
import "../sync/retry_policy.dart";
import "offline_database.dart";

enum _DependencyDisposition {
  ready,
  waiting,
  blocked,
  missing,
}

class SyncQueueRepository {
  SyncQueueRepository(this.offlineDatabase);

  final OfflineDatabase offlineDatabase;

  Future<SyncOperation> enqueue(SyncOperation operation) async {
    if (operation.state != SyncState.queued) {
      throw StateError("New sync operations must start in queued state.");
    }
    if (operation.dependencyIds.contains(operation.id)) {
      throw StateError("A sync operation cannot depend on itself.");
    }
    if (operation.dependencyIds.toSet().length !=
        operation.dependencyIds.length) {
      throw StateError("Dependency IDs must be unique.");
    }

    final existing = await getById(operation.id);
    if (existing != null) {
      if (_sameImmutableOperation(existing, operation)) {
        return existing;
      }
      throw StateError(
        "Sync operation ID is already associated with different data.",
      );
    }

    final inspectionRows = await offlineDatabase.database.query(
      "local_inspections",
      columns: <String>["id"],
      where: "id = ?",
      whereArgs: <Object?>[operation.inspectionId],
      limit: 1,
    );
    if (inspectionRows.isEmpty) {
      throw StateError("Local inspection must exist before queueing work.");
    }

    for (final dependencyId in operation.dependencyIds) {
      if (await getById(dependencyId) == null) {
        throw StateError(
          "Dependency operation does not exist: " + dependencyId,
        );
      }
    }

    await offlineDatabase.database.insert(
      "sync_operations",
      _toRow(operation),
    );
    return (await getById(operation.id))!;
  }

  Future<SyncOperation?> getById(String id) async {
    final rows = await offlineDatabase.database.query(
      "sync_operations",
      where: "id = ?",
      whereArgs: <Object?>[id],
      limit: 1,
    );
    if (rows.isEmpty) {
      return null;
    }
    return _fromRow(rows.single);
  }

  Future<List<SyncOperation>> listAll() async {
    final rows = await offlineDatabase.database.query(
      "sync_operations",
      orderBy: "created_at ASC, id ASC",
    );
    return rows.map(_fromRow).toList(growable: false);
  }

  Future<SyncOperation?> claimNextReady(DateTime now) {
    final timestamp = now.toUtc();
    return offlineDatabase.database.transaction((txn) async {
      final candidates = await txn.query(
        "sync_operations",
        where:
            "state = ? OR "
            "(state = ? AND next_attempt_at IS NOT NULL "
            "AND next_attempt_at <= ?)",
        whereArgs: <Object?>[
          SyncState.queued.dbValue,
          SyncState.retryRequired.dbValue,
          timestamp.toIso8601String(),
        ],
        orderBy: "created_at ASC, id ASC",
      );

      for (final row in candidates) {
        final operation = _fromRow(row);
        final disposition = await _dependencyDisposition(
          txn,
          operation.dependencyIds,
        );

        if (disposition == _DependencyDisposition.waiting) {
          continue;
        }

        if (disposition == _DependencyDisposition.blocked ||
            disposition == _DependencyDisposition.missing) {
          SyncStateMachine.requireTransition(
            operation.state,
            SyncState.blocked,
          );
          await txn.update(
            "sync_operations",
            <String, Object?>{
              "state": SyncState.blocked.dbValue,
              "last_error_kind": disposition == _DependencyDisposition.missing
                  ? "dependency_missing"
                  : "dependency_blocked",
              "last_error_code": null,
              "last_error_message":
                  "A required predecessor operation is not resolvable.",
              "next_attempt_at": null,
              "updated_at": timestamp.toIso8601String(),
            },
            where: "id = ?",
            whereArgs: <Object?>[operation.id],
          );
          continue;
        }

        SyncStateMachine.requireTransition(
          operation.state,
          SyncState.syncing,
        );
        await txn.update(
          "sync_operations",
          <String, Object?>{
            "state": SyncState.syncing.dbValue,
            "attempt_count": operation.attemptCount + 1,
            "last_attempt_at": timestamp.toIso8601String(),
            "next_attempt_at": null,
            "updated_at": timestamp.toIso8601String(),
          },
          where: "id = ?",
          whereArgs: <Object?>[operation.id],
        );

        final claimed = await txn.query(
          "sync_operations",
          where: "id = ?",
          whereArgs: <Object?>[operation.id],
          limit: 1,
        );
        return _fromRow(claimed.single);
      }

      return null;
    });
  }

  Future<void> markSynced(
    String id, {
    String? remoteResourceId,
    bool reconciledAfterUnknownOutcome = false,
    DateTime? now,
  }) async {
    final operation = await _requireOperation(id);
    if (operation.state == SyncState.retryRequired &&
        !reconciledAfterUnknownOutcome) {
      throw StateError(
        "A retry_required operation may be marked synced only after explicit reconciliation.",
      );
    }
    SyncStateMachine.requireTransition(operation.state, SyncState.synced);

    await offlineDatabase.database.update(
      "sync_operations",
      <String, Object?>{
        "state": SyncState.synced.dbValue,
        "remote_resource_id": remoteResourceId ?? operation.remoteResourceId,
        "next_attempt_at": null,
        "last_error_kind": null,
        "last_error_code": null,
        "last_error_message": null,
        "updated_at": (now ?? DateTime.now().toUtc())
            .toUtc()
            .toIso8601String(),
      },
      where: "id = ?",
      whereArgs: <Object?>[id],
    );
  }

  Future<void> markFailure(
    String id, {
    required SyncFailureDecision decision,
    required SyncRetryPolicy retryPolicy,
    String? apiCode,
    String? message,
    DateTime? now,
  }) async {
    final timestamp = (now ?? DateTime.now().toUtc()).toUtc();
    final operation = await _requireOperation(id);
    if (operation.state != SyncState.syncing) {
      throw StateError("Only an active syncing operation can record a failure.");
    }

    var targetState = decision.targetState;
    DateTime? nextAttemptAt;
    var errorKind = decision.kind.code;

    if (targetState == SyncState.retryRequired) {
      if (!retryPolicy.canRetry(operation.attemptCount)) {
        targetState = SyncState.blocked;
        errorKind = "retry_exhausted";
      } else if (decision.autoRetry) {
        nextAttemptAt = retryPolicy.nextAttemptAt(
          timestamp,
          operation.attemptCount,
        );
      }
    }

    SyncStateMachine.requireTransition(operation.state, targetState);
    await offlineDatabase.database.update(
      "sync_operations",
      <String, Object?>{
        "state": targetState.dbValue,
        "next_attempt_at": nextAttemptAt?.toIso8601String(),
        "last_error_kind": errorKind,
        "last_error_code": apiCode,
        "last_error_message": message,
        "updated_at": timestamp.toIso8601String(),
      },
      where: "id = ?",
      whereArgs: <Object?>[id],
    );
  }

  Future<void> scheduleRetryAfterReconciliation(
    String id, {
    required SyncRetryPolicy retryPolicy,
    DateTime? now,
  }) async {
    final timestamp = (now ?? DateTime.now().toUtc()).toUtc();
    final operation = await _requireOperation(id);
    if (operation.state != SyncState.retryRequired ||
        operation.nextAttemptAt != null) {
      throw StateError(
        "Only a parked reconciliation-required operation can be released for retry.",
      );
    }

    if (!retryPolicy.canRetry(operation.attemptCount)) {
      await offlineDatabase.database.update(
        "sync_operations",
        <String, Object?>{
          "state": SyncState.blocked.dbValue,
          "last_error_kind": "retry_exhausted",
          "last_error_code": null,
          "last_error_message":
              "The operation was reconciled as not applied, but its retry budget is exhausted.",
          "updated_at": timestamp.toIso8601String(),
        },
        where: "id = ?",
        whereArgs: <Object?>[id],
      );
      return;
    }

    await offlineDatabase.database.update(
      "sync_operations",
      <String, Object?>{
        "next_attempt_at": retryPolicy
            .nextAttemptAt(timestamp, operation.attemptCount)
            .toIso8601String(),
        "last_error_kind": "reconciled_not_applied",
        "last_error_code": null,
        "last_error_message":
            "Server reconciliation confirmed the previous request was not applied.",
        "updated_at": timestamp.toIso8601String(),
      },
      where: "id = ?",
      whereArgs: <Object?>[id],
    );
  }

  Future<void> recordReconciliationFailure(
    String id, {
    String? apiCode,
    String? message,
    DateTime? now,
  }) async {
    final operation = await _requireOperation(id);
    if (operation.state != SyncState.retryRequired ||
        operation.nextAttemptAt != null) {
      throw StateError(
        "Reconciliation failure can be recorded only for a parked operation.",
      );
    }
    await offlineDatabase.database.update(
      "sync_operations",
      <String, Object?>{
        "last_error_kind": "reconciliation_unavailable",
        "last_error_code": apiCode,
        "last_error_message": message,
        "updated_at": (now ?? DateTime.now().toUtc())
            .toUtc()
            .toIso8601String(),
      },
      where: "id = ?",
      whereArgs: <Object?>[id],
    );
  }

  Future<int> recoverInterruptedSyncs({DateTime? now}) async {
    final timestamp = (now ?? DateTime.now().toUtc()).toUtc();
    return offlineDatabase.database.update(
      "sync_operations",
      <String, Object?>{
        "state": SyncState.retryRequired.dbValue,
        "next_attempt_at": timestamp.toIso8601String(),
        "last_error_kind": "process_interrupted",
        "last_error_code": null,
        "last_error_message":
            "The previous sync attempt ended before completion was recorded.",
        "updated_at": timestamp.toIso8601String(),
      },
      where: "state = ?",
      whereArgs: <Object?>[SyncState.syncing.dbValue],
    );
  }

  Future<void> requeueAfterResolution(
    String id, {
    DateTime? now,
  }) async {
    final operation = await _requireOperation(id);
    SyncStateMachine.requireTransition(operation.state, SyncState.queued);
    final timestamp = (now ?? DateTime.now().toUtc()).toUtc();

    await offlineDatabase.database.update(
      "sync_operations",
      <String, Object?>{
        "state": SyncState.queued.dbValue,
        "next_attempt_at": null,
        "last_error_kind": null,
        "last_error_code": null,
        "last_error_message": null,
        "updated_at": timestamp.toIso8601String(),
      },
      where: "id = ?",
      whereArgs: <Object?>[id],
    );
  }

  Future<SyncOperation> _requireOperation(String id) async {
    final operation = await getById(id);
    if (operation == null) {
      throw StateError("Sync operation does not exist.");
    }
    return operation;
  }

  Future<_DependencyDisposition> _dependencyDisposition(
    DatabaseExecutor executor,
    List<String> dependencyIds,
  ) async {
    var waiting = false;
    for (final dependencyId in dependencyIds) {
      final rows = await executor.query(
        "sync_operations",
        columns: <String>["state"],
        where: "id = ?",
        whereArgs: <Object?>[dependencyId],
        limit: 1,
      );
      if (rows.isEmpty) {
        return _DependencyDisposition.missing;
      }
      final state = SyncState.fromDb(rows.single["state"]! as String);
      if (state == SyncState.conflict || state == SyncState.blocked) {
        return _DependencyDisposition.blocked;
      }
      if (state != SyncState.synced) {
        waiting = true;
      }
    }
    return waiting
        ? _DependencyDisposition.waiting
        : _DependencyDisposition.ready;
  }

  bool _sameImmutableOperation(
    SyncOperation left,
    SyncOperation right,
  ) {
    if (left.inspectionId != right.inspectionId ||
        left.type != right.type ||
        left.resourceId != right.resourceId ||
        left.payloadSha256 != right.payloadSha256 ||
        left.dependencyIds.length != right.dependencyIds.length) {
      return false;
    }

    for (var index = 0; index < left.dependencyIds.length; index += 1) {
      if (left.dependencyIds[index] != right.dependencyIds[index]) {
        return false;
      }
    }
    return true;
  }

  Map<String, Object?> _toRow(SyncOperation operation) {
    return <String, Object?>{
      "id": operation.id,
      "inspection_id": operation.inspectionId,
      "operation_type": operation.type.dbValue,
      "resource_id": operation.resourceId,
      "payload_json": canonicalJsonEncode(operation.payload),
      "payload_sha256": operation.payloadSha256,
      "dependency_ids_json": jsonEncode(operation.dependencyIds),
      "state": operation.state.dbValue,
      "attempt_count": operation.attemptCount,
      "next_attempt_at": operation.nextAttemptAt?.toIso8601String(),
      "last_attempt_at": operation.lastAttemptAt?.toIso8601String(),
      "last_error_kind": operation.lastErrorKind,
      "last_error_code": operation.lastErrorCode,
      "last_error_message": operation.lastErrorMessage,
      "remote_resource_id": operation.remoteResourceId,
      "created_at": operation.createdAt.toUtc().toIso8601String(),
      "updated_at": operation.updatedAt.toUtc().toIso8601String(),
    };
  }

  SyncOperation _fromRow(Map<String, Object?> row) {
    final payloadDynamic = jsonDecode(row["payload_json"]! as String);
    if (payloadDynamic is! Map) {
      throw const FormatException("Stored sync payload is not a JSON object.");
    }
    final payload = <String, Object?>{
      for (final entry in payloadDynamic.entries)
        entry.key.toString(): entry.value,
    };

    final dependencyDynamic = jsonDecode(
      row["dependency_ids_json"]! as String,
    );
    if (dependencyDynamic is! List) {
      throw const FormatException(
        "Stored dependency IDs are not a JSON array.",
      );
    }

    return SyncOperation(
      id: row["id"]! as String,
      inspectionId: row["inspection_id"]! as String,
      type: SyncOperationType.fromDb(row["operation_type"]! as String),
      resourceId: row["resource_id"]! as String,
      payload: Map<String, Object?>.unmodifiable(payload),
      payloadSha256: row["payload_sha256"]! as String,
      dependencyIds: List<String>.unmodifiable(
        dependencyDynamic.map((value) => value.toString()),
      ),
      state: SyncState.fromDb(row["state"]! as String),
      attemptCount: row["attempt_count"]! as int,
      nextAttemptAt: _parseNullableDate(row["next_attempt_at"]),
      lastAttemptAt: _parseNullableDate(row["last_attempt_at"]),
      lastErrorKind: row["last_error_kind"] as String?,
      lastErrorCode: row["last_error_code"] as String?,
      lastErrorMessage: row["last_error_message"] as String?,
      remoteResourceId: row["remote_resource_id"] as String?,
      createdAt: DateTime.parse(row["created_at"]! as String).toUtc(),
      updatedAt: DateTime.parse(row["updated_at"]! as String).toUtc(),
    );
  }

  DateTime? _parseNullableDate(Object? value) {
    if (value == null) {
      return null;
    }
    return DateTime.parse(value as String).toUtc();
  }
}
