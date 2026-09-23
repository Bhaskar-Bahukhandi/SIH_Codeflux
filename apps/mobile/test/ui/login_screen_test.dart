import "dart:convert";

import "package:flutter/material.dart";
import "package:flutter_test/flutter_test.dart";
import "package:http/http.dart" as http;
import "package:http/testing.dart";

import "package:codeflux_mobile/auth/codeflux_officer_auth_client.dart";
import "package:codeflux_mobile/auth/officer_session_store.dart";
import "package:codeflux_mobile/ui/login_screen.dart";

class MemorySecureStore implements SecureKeyValueStore {
  final Map<String, String> values = <String, String>{};

  @override
  Future<void> delete(String key) async => values.remove(key);

  @override
  Future<String?> read(String key) async => values[key];

  @override
  Future<void> write(String key, String value) async {
    values[key] = value;
  }
}

void main() {
  testWidgets("Officer can sign in through the real auth contract", (tester) async {
    final sessionStore = OfficerSessionStore(MemorySecureStore());
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

    var authenticated = false;
    await tester.pumpWidget(
      MaterialApp(
        home: LoginScreen(
          authClient: auth,
          onAuthenticated: () => authenticated = true,
        ),
      ),
    );

    final fields = find.byType(TextField);
    await tester.enterText(fields.at(0), "officer@example.test");
    await tester.enterText(fields.at(1), "secret");
    await tester.tap(find.widgetWithText(FilledButton, "Sign in"));
    await tester.pumpAndSettle();

    expect(authenticated, isTrue);
    expect((await sessionStore.read())!.userId, "officer-1");
  });

  testWidgets("invalid credentials remain visible on the login screen", (tester) async {
    final auth = CodefluxOfficerAuthClient(
      client: MockClient((request) async {
        return http.Response(
          jsonEncode(<String, Object?>{
            "error": <String, Object?>{
              "code": "invalid_credentials",
              "message": "Invalid email or password.",
            },
          }),
          401,
        );
      }),
      serverBaseUri: Uri.parse("https://example.test/"),
      sessionStore: OfficerSessionStore(MemorySecureStore()),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: LoginScreen(
          authClient: auth,
          onAuthenticated: () {},
        ),
      ),
    );

    final fields = find.byType(TextField);
    await tester.enterText(fields.at(0), "officer@example.test");
    await tester.enterText(fields.at(1), "wrong");
    await tester.tap(find.widgetWithText(FilledButton, "Sign in"));
    await tester.pumpAndSettle();

    expect(find.text("Invalid email or password."), findsOneWidget);
    expect(find.text("Officer sign in"), findsOneWidget);
  });
}
