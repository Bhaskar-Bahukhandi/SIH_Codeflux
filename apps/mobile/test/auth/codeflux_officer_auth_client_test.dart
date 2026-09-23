import "dart:convert";

import "package:flutter_test/flutter_test.dart";
import "package:http/http.dart" as http;
import "package:http/testing.dart";

import "package:codeflux_mobile/auth/codeflux_officer_auth_client.dart";
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
  late MemorySecureStore secureStore;
  late OfficerSessionStore sessionStore;

  setUp(() {
    secureStore = MemorySecureStore();
    sessionStore = OfficerSessionStore(secureStore);
  });

  test("login saves only the Officer identity confirmed by auth/me", () async {
    var call = 0;
    final client = MockClient((request) async {
      call += 1;
      if (request.url.path == "/api/v1/auth/login") {
        expect(request.method, "POST");
        final body = jsonDecode(request.body) as Map<String, dynamic>;
        expect(body["email"], "officer@example.test");
        expect(body["password"], "secret");
        return http.Response(
          jsonEncode(<String, Object?>{
            "access_token": "token-123",
            "token_type": "bearer",
            "expires_in": 3600,
          }),
          200,
        );
      }

      expect(request.url.path, "/api/v1/auth/me");
      expect(request.headers["authorization"], "Bearer token-123");
      return http.Response(
        jsonEncode(<String, Object?>{
          "id": "officer-1",
          "full_name": "Field Officer",
          "email": "officer@example.test",
          "role": "officer",
          "is_active": true,
        }),
        200,
      );
    });

    final auth = CodefluxOfficerAuthClient(
      client: client,
      serverBaseUri: Uri.parse("https://example.test/"),
      sessionStore: sessionStore,
      now: () => DateTime.utc(2026, 9, 23, 12),
    );

    final session = await auth.login(
      email: "  OFFICER@example.test ",
      password: "secret",
    );

    expect(call, 2);
    expect(session.userId, "officer-1");
    expect(session.role, "officer");
    expect(session.accessToken, "token-123");
    expect(session.expiresAt, DateTime.utc(2026, 9, 23, 13));

    final restored = await sessionStore.read();
    expect(restored, isNotNull);
    expect(restored!.userId, "officer-1");
    expect(restored.email, "officer@example.test");
  });

  test("invalid credentials do not overwrite an existing secure session", () async {
    final existing = OfficerSessionContext(
      userId: "officer-existing",
      fullName: "Existing Officer",
      email: "existing@example.test",
      role: "officer",
      accessToken: "existing-token",
      expiresAt: DateTime.utc(2026, 9, 24),
    );
    await sessionStore.save(existing);

    final client = MockClient((request) async {
      return http.Response(
        jsonEncode(<String, Object?>{
          "error": <String, Object?>{
            "code": "invalid_credentials",
            "message": "Invalid email or password.",
          },
        }),
        401,
      );
    });

    final auth = CodefluxOfficerAuthClient(
      client: client,
      serverBaseUri: Uri.parse("https://example.test/"),
      sessionStore: sessionStore,
    );

    await expectLater(
      auth.login(
        email: "wrong@example.test",
        password: "wrong",
      ),
      throwsA(
        isA<MobileAuthFailure>().having(
          (failure) => failure.code,
          "code",
          "invalid_credentials",
        ),
      ),
    );

    expect((await sessionStore.read())!.userId, "officer-existing");
  });

  test("non-Officer account is rejected and not persisted", () async {
    final client = MockClient((request) async {
      if (request.url.path == "/api/v1/auth/login") {
        return http.Response(
          jsonEncode(<String, Object?>{
            "access_token": "supervisor-token",
            "token_type": "bearer",
            "expires_in": 3600,
          }),
          200,
        );
      }
      return http.Response(
        jsonEncode(<String, Object?>{
          "id": "supervisor-1",
          "full_name": "Supervisor",
          "email": "supervisor@example.test",
          "role": "supervisor",
          "is_active": true,
        }),
        200,
      );
    });

    final auth = CodefluxOfficerAuthClient(
      client: client,
      serverBaseUri: Uri.parse("https://example.test/"),
      sessionStore: sessionStore,
    );

    await expectLater(
      auth.login(
        email: "supervisor@example.test",
        password: "secret",
      ),
      throwsA(
        isA<MobileAuthFailure>().having(
          (failure) => failure.code,
          "code",
          "officer_role_required",
        ),
      ),
    );
    expect(await sessionStore.read(), isNull);
  });

  test("identity mismatch is rejected instead of saving another account", () async {
    final client = MockClient((request) async {
      if (request.url.path == "/api/v1/auth/login") {
        return http.Response(
          jsonEncode(<String, Object?>{
            "access_token": "token",
            "token_type": "bearer",
            "expires_in": 3600,
          }),
          200,
        );
      }
      return http.Response(
        jsonEncode(<String, Object?>{
          "id": "officer-2",
          "full_name": "Different Officer",
          "email": "different@example.test",
          "role": "officer",
          "is_active": true,
        }),
        200,
      );
    });

    final auth = CodefluxOfficerAuthClient(
      client: client,
      serverBaseUri: Uri.parse("https://example.test/"),
      sessionStore: sessionStore,
    );

    await expectLater(
      auth.login(
        email: "requested@example.test",
        password: "secret",
      ),
      throwsA(
        isA<MobileAuthFailure>().having(
          (failure) => failure.code,
          "code",
          "auth_identity_mismatch",
        ),
      ),
    );
    expect(await sessionStore.read(), isNull);
  });

  test("expired session restores identity offline but not network readiness", () async {
    final expired = OfficerSessionContext(
      userId: "officer-1",
      fullName: "Offline Officer",
      email: "officer@example.test",
      role: "officer",
      accessToken: "expired-token",
      expiresAt: DateTime.utc(2026, 9, 23, 10),
    );
    await sessionStore.save(expired);

    final auth = CodefluxOfficerAuthClient(
      client: MockClient((request) async => http.Response("{}", 500)),
      serverBaseUri: Uri.parse("https://example.test/"),
      sessionStore: sessionStore,
    );

    final offlineIdentity = await auth.restoreSession();
    final networkReady = await auth.restoreNetworkReadySession(
      now: DateTime.utc(2026, 9, 23, 12),
    );

    expect(offlineIdentity, isNotNull);
    expect(offlineIdentity!.userId, "officer-1");
    expect(networkReady, isNull);
  });

  test("logout clears secure Officer session", () async {
    await sessionStore.save(
      OfficerSessionContext(
        userId: "officer-1",
        fullName: "Officer",
        email: "officer@example.test",
        role: "officer",
        accessToken: "token",
        expiresAt: DateTime.utc(2026, 9, 24),
      ),
    );

    final auth = CodefluxOfficerAuthClient(
      client: MockClient((request) async => http.Response("{}", 500)),
      serverBaseUri: Uri.parse("https://example.test/"),
      sessionStore: sessionStore,
    );
    await auth.logout();

    expect(await sessionStore.read(), isNull);
  });
}
