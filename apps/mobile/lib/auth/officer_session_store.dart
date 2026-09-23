import "dart:convert";

import "package:flutter_secure_storage/flutter_secure_storage.dart";

abstract interface class SecureKeyValueStore {
  Future<String?> read(String key);
  Future<void> write(String key, String value);
  Future<void> delete(String key);
}

class FlutterSecureKeyValueStore implements SecureKeyValueStore {
  FlutterSecureKeyValueStore({
    FlutterSecureStorage? storage,
  }) : _storage = storage ?? const FlutterSecureStorage();

  final FlutterSecureStorage _storage;

  @override
  Future<String?> read(String key) => _storage.read(key: key);

  @override
  Future<void> write(String key, String value) {
    return _storage.write(key: key, value: value);
  }

  @override
  Future<void> delete(String key) => _storage.delete(key: key);
}

class OfficerSessionContext {
  const OfficerSessionContext({
    required this.userId,
    required this.fullName,
    required this.email,
    required this.role,
    required this.accessToken,
    required this.expiresAt,
  });

  final String userId;
  final String fullName;
  final String email;
  final String role;
  final String accessToken;
  final DateTime expiresAt;

  bool tokenExpired({DateTime? now}) {
    final timestamp = (now ?? DateTime.now().toUtc()).toUtc();
    return !expiresAt.toUtc().isAfter(timestamp);
  }

  Map<String, Object?> toJson() {
    return <String, Object?>{
      "user_id": userId,
      "full_name": fullName,
      "email": email,
      "role": role,
      "access_token": accessToken,
      "expires_at": expiresAt.toUtc().toIso8601String(),
    };
  }

  static OfficerSessionContext fromJson(Map<String, Object?> value) {
    String requiredString(String key) {
      final item = value[key];
      if (item is! String || item.trim().isEmpty) {
        throw FormatException("Invalid secure session field: " + key);
      }
      return item;
    }

    final expiresAt = DateTime.tryParse(requiredString("expires_at"));
    if (expiresAt == null) {
      throw const FormatException(
        "Invalid secure session expiration timestamp.",
      );
    }

    return OfficerSessionContext(
      userId: requiredString("user_id"),
      fullName: requiredString("full_name"),
      email: requiredString("email"),
      role: requiredString("role"),
      accessToken: requiredString("access_token"),
      expiresAt: expiresAt.toUtc(),
    );
  }
}

class OfficerSessionStore {
  OfficerSessionStore(this.secureStore);

  static const String _sessionKey = "codeflux.officer_session.v1";

  final SecureKeyValueStore secureStore;

  Future<void> save(OfficerSessionContext session) {
    return secureStore.write(
      _sessionKey,
      jsonEncode(session.toJson()),
    );
  }

  Future<OfficerSessionContext?> read() async {
    final encoded = await secureStore.read(_sessionKey);
    if (encoded == null) {
      return null;
    }

    final decoded = jsonDecode(encoded);
    if (decoded is! Map) {
      throw const FormatException(
        "Secure Officer session is not a JSON object.",
      );
    }
    return OfficerSessionContext.fromJson(
      <String, Object?>{
        for (final entry in decoded.entries)
          entry.key.toString(): entry.value,
      },
    );
  }

  Future<String?> readValidAccessToken({DateTime? now}) async {
    final session = await read();
    if (session == null || session.tokenExpired(now: now)) {
      return null;
    }
    return session.accessToken;
  }

  Future<void> clear() => secureStore.delete(_sessionKey);
}

class OfficerSessionTokenProvider {
  OfficerSessionTokenProvider(
    this.sessionStore, {
    DateTime Function()? now,
  }) : _now = now ?? (() => DateTime.now().toUtc());

  final OfficerSessionStore sessionStore;
  final DateTime Function() _now;

  Future<String?> call() {
    return sessionStore.readValidAccessToken(now: _now());
  }
}
