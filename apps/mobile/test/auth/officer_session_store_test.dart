import "package:flutter_test/flutter_test.dart";

import "package:codeflux_mobile/auth/officer_session_store.dart";

class MemorySecureStore implements SecureKeyValueStore {
  final Map<String, String> values = <String, String>{};

  @override
  Future<void> delete(String key) async {
    values.remove(key);
  }

  @override
  Future<String?> read(String key) async => values[key];

  @override
  Future<void> write(String key, String value) async {
    values[key] = value;
  }
}

void main() {
  test("Officer session round-trips as one secure blob", () async {
    final storage = MemorySecureStore();
    final store = OfficerSessionStore(storage);
    final session = OfficerSessionContext(
      userId: "officer-1",
      fullName: "Officer Test",
      email: "officer@example.test",
      role: "officer",
      accessToken: "secret-token",
      expiresAt: DateTime.utc(2026, 9, 24, 12),
    );

    await store.save(session);
    expect(storage.values.length, 1);

    final restored = await store.read();
    expect(restored, isNotNull);
    expect(restored!.userId, "officer-1");
    expect(restored.fullName, "Officer Test");
    expect(restored.email, "officer@example.test");
    expect(restored.role, "officer");
    expect(restored.accessToken, "secret-token");
    expect(restored.expiresAt, DateTime.utc(2026, 9, 24, 12));
  });

  test("expired session preserves identity but withholds sync token", () async {
    final storage = MemorySecureStore();
    final store = OfficerSessionStore(storage);
    await store.save(
      OfficerSessionContext(
        userId: "officer-1",
        fullName: "Officer Test",
        email: "officer@example.test",
        role: "officer",
        accessToken: "expired-token",
        expiresAt: DateTime.utc(2026, 9, 24, 10),
      ),
    );

    final context = await store.read();
    expect(context, isNotNull);
    expect(
      context!.tokenExpired(now: DateTime.utc(2026, 9, 24, 10)),
      isTrue,
    );
    expect(
      await store.readValidAccessToken(
        now: DateTime.utc(2026, 9, 24, 10),
      ),
      isNull,
    );
  });

  test("token provider supplies only an unexpired secure token", () async {
    final storage = MemorySecureStore();
    final store = OfficerSessionStore(storage);
    await store.save(
      OfficerSessionContext(
        userId: "officer-1",
        fullName: "Officer Test",
        email: "officer@example.test",
        role: "officer",
        accessToken: "valid-token",
        expiresAt: DateTime.utc(2026, 9, 24, 11),
      ),
    );

    final validProvider = OfficerSessionTokenProvider(
      store,
      now: () => DateTime.utc(2026, 9, 24, 10),
    );
    expect(await validProvider(), "valid-token");

    final expiredProvider = OfficerSessionTokenProvider(
      store,
      now: () => DateTime.utc(2026, 9, 24, 12),
    );
    expect(await expiredProvider(), isNull);
  });

  test("clear removes only the CODEFLUX session blob", () async {
    final storage = MemorySecureStore();
    storage.values["other.secret"] = "preserve-me";
    final store = OfficerSessionStore(storage);
    await store.save(
      OfficerSessionContext(
        userId: "officer-1",
        fullName: "Officer Test",
        email: "officer@example.test",
        role: "officer",
        accessToken: "valid-token",
        expiresAt: DateTime.utc(2026, 9, 24, 11),
      ),
    );

    await store.clear();

    expect(await store.read(), isNull);
    expect(storage.values["other.secret"], "preserve-me");
  });
}
