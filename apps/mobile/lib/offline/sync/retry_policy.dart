class SyncRetryPolicy {
  const SyncRetryPolicy({
    this.baseDelay = const Duration(seconds: 5),
    this.maxDelay = const Duration(minutes: 5),
    this.maxAttempts = 8,
  });

  final Duration baseDelay;
  final Duration maxDelay;
  final int maxAttempts;

  bool canRetry(int completedAttempts) => completedAttempts < maxAttempts;

  Duration delayForAttempt(int completedAttempts) {
    if (completedAttempts < 1) {
      return Duration.zero;
    }

    var multiplier = 1;
    for (var i = 1; i < completedAttempts; i += 1) {
      multiplier *= 2;
      if (baseDelay.inMilliseconds * multiplier >= maxDelay.inMilliseconds) {
        return maxDelay;
      }
    }

    final delay = Duration(
      milliseconds: baseDelay.inMilliseconds * multiplier,
    );
    return delay > maxDelay ? maxDelay : delay;
  }

  DateTime nextAttemptAt(DateTime now, int completedAttempts) {
    return now.toUtc().add(delayForAttempt(completedAttempts));
  }
}
