import "dart:async";
import "dart:convert";
import "dart:io";

import "package:http/http.dart" as http;

import "officer_session_store.dart";

class MobileAuthFailure implements Exception {
  const MobileAuthFailure({
    required this.code,
    required this.message,
    this.statusCode,
    this.transportUnavailable = false,
    this.timedOut = false,
  });

  final String code;
  final String message;
  final int? statusCode;
  final bool transportUnavailable;
  final bool timedOut;

  @override
  String toString() => message;
}

class CodefluxOfficerAuthClient {
  CodefluxOfficerAuthClient({
    required this.client,
    required this.serverBaseUri,
    required this.sessionStore,
    this.requestTimeout = const Duration(seconds: 20),
    DateTime Function()? now,
  }) : _now = now ?? (() => DateTime.now().toUtc());

  final http.Client client;
  final Uri serverBaseUri;
  final OfficerSessionStore sessionStore;
  final Duration requestTimeout;
  final DateTime Function() _now;

  Future<OfficerSessionContext> login({
    required String email,
    required String password,
  }) async {
    final normalizedEmail = email.trim().toLowerCase();
    if (normalizedEmail.isEmpty) {
      throw const MobileAuthFailure(
        code: "email_required",
        message: "Email is required.",
      );
    }
    if (password.isEmpty) {
      throw const MobileAuthFailure(
        code: "password_required",
        message: "Password is required.",
      );
    }

    final loginResponse = await _send(
      http.Request(
        "POST",
        _endpoint("api/v1/auth/login"),
      )
        ..headers.addAll(const <String, String>{
          "Content-Type": "application/json",
          "Accept": "application/json",
        })
        ..body = jsonEncode(<String, Object?>{
          "email": normalizedEmail,
          "password": password,
        }),
    );
    final loginBody = _requireSuccessObject(loginResponse);

    final token = loginBody["access_token"]?.toString();
    final tokenType = loginBody["token_type"]?.toString().toLowerCase();
    final expiresIn = loginBody["expires_in"];
    if (token == null ||
        token.trim().isEmpty ||
        tokenType != "bearer" ||
        expiresIn is! int ||
        expiresIn <= 0) {
      throw const MobileAuthFailure(
        code: "invalid_auth_response",
        message: "The server returned an invalid authentication response.",
      );
    }

    final meResponse = await _send(
      http.Request(
        "GET",
        _endpoint("api/v1/auth/me"),
      )
        ..headers.addAll(<String, String>{
          "Authorization": "Bearer " + token,
          "Accept": "application/json",
        }),
    );
    final me = _requireSuccessObject(meResponse);

    final userId = _requiredString(me, "id");
    final fullName = _requiredString(me, "full_name");
    final remoteEmail = _requiredString(me, "email").toLowerCase();
    final role = _requiredString(me, "role").toLowerCase();
    if (me["is_active"] != true) {
      throw const MobileAuthFailure(
        code: "inactive_officer",
        message: "This Officer account is not active.",
        statusCode: 403,
      );
    }
    if (role != "officer") {
      throw const MobileAuthFailure(
        code: "officer_role_required",
        message: "The field application is available only to Officer accounts.",
        statusCode: 403,
      );
    }
    if (remoteEmail != normalizedEmail) {
      throw const MobileAuthFailure(
        code: "auth_identity_mismatch",
        message: "Authenticated account identity does not match the login request.",
        statusCode: 409,
      );
    }

    final issuedAt = _now().toUtc();
    final session = OfficerSessionContext(
      userId: userId,
      fullName: fullName,
      email: remoteEmail,
      role: role,
      accessToken: token,
      expiresAt: issuedAt.add(Duration(seconds: expiresIn)),
    );
    await sessionStore.save(session);
    return session;
  }

  Future<OfficerSessionContext?> restoreSession() {
    return sessionStore.read();
  }

  Future<OfficerSessionContext?> restoreNetworkReadySession({
    DateTime? now,
  }) async {
    final session = await sessionStore.read();
    if (session == null || session.tokenExpired(now: now)) {
      return null;
    }
    return session;
  }

  Future<void> logout() => sessionStore.clear();

  Uri _endpoint(String relativePath) {
    final normalizedBase = serverBaseUri.toString().endsWith("/")
        ? serverBaseUri
        : Uri.parse(serverBaseUri.toString() + "/");
    return normalizedBase.resolve(relativePath);
  }

  Future<http.Response> _send(http.BaseRequest request) async {
    try {
      final streamed = await client.send(request).timeout(requestTimeout);
      return await http.Response.fromStream(streamed).timeout(requestTimeout);
    } on TimeoutException {
      throw const MobileAuthFailure(
        code: "auth_timeout",
        message: "Authentication request timed out.",
        timedOut: true,
      );
    } on http.ClientException catch (error) {
      throw MobileAuthFailure(
        code: "auth_transport_unavailable",
        message: error.message,
        transportUnavailable: true,
      );
    } on SocketException catch (error) {
      throw MobileAuthFailure(
        code: "auth_transport_unavailable",
        message: error.message,
        transportUnavailable: true,
      );
    }
  }

  Map<String, dynamic> _requireSuccessObject(http.Response response) {
    Object? decoded;
    try {
      decoded = jsonDecode(response.body);
    } on FormatException {
      decoded = null;
    }

    if (response.statusCode < 200 || response.statusCode >= 300) {
      String? code;
      String? message;
      if (decoded is Map && decoded["error"] is Map) {
        final error = decoded["error"] as Map;
        code = error["code"]?.toString();
        message = error["message"]?.toString();
      }
      throw MobileAuthFailure(
        code: code ?? "authentication_failed",
        message: message ??
            "Authentication failed with HTTP " +
                response.statusCode.toString() +
                ".",
        statusCode: response.statusCode,
      );
    }

    if (decoded is! Map) {
      throw const MobileAuthFailure(
        code: "invalid_auth_response",
        message: "The server returned an invalid authentication response.",
      );
    }
    return <String, dynamic>{
      for (final entry in decoded.entries)
        entry.key.toString(): entry.value,
    };
  }

  String _requiredString(Map<String, dynamic> value, String key) {
    final item = value[key];
    if (item is! String || item.trim().isEmpty) {
      throw MobileAuthFailure(
        code: "invalid_auth_response",
        message: "The authentication response is missing " + key + ".",
      );
    }
    return item.trim();
  }
}
