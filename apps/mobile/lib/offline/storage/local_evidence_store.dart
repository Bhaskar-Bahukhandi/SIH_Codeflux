import "dart:io";
import "dart:typed_data";

import "package:crypto/crypto.dart";
import "package:path/path.dart" as p;
import "package:uuid/uuid.dart";

class StoredLocalEvidence {
  const StoredLocalEvidence({
    required this.path,
    required this.sha256,
    required this.sizeBytes,
  });

  final String path;
  final String sha256;
  final int sizeBytes;
}

class LocalEvidenceStore {
  LocalEvidenceStore(this.root);

  final Directory root;
  static final RegExp _safeSegment = RegExp(r"^[A-Za-z0-9_-]+$");
  static final RegExp _safeExtension = RegExp(r"^\.[A-Za-z0-9]{1,10}$");

  String _segment(String value, String field) {
    if (!_safeSegment.hasMatch(value)) {
      throw ArgumentError.value(value, field, "Unsafe storage segment.");
    }
    return value;
  }

  String _extension(String? originalFilename) {
    if (originalFilename == null || originalFilename.isEmpty) {
      return ".bin";
    }
    final extension = p.extension(originalFilename);
    return _safeExtension.hasMatch(extension) ? extension.toLowerCase() : ".bin";
  }

  Future<StoredLocalEvidence> persistBytes({
    required String inspectionId,
    required String evidenceId,
    required Uint8List bytes,
    String? originalFilename,
  }) async {
    final safeInspectionId = _segment(inspectionId, "inspectionId");
    final safeEvidenceId = _segment(evidenceId, "evidenceId");
    final directory = Directory(
      p.join(root.path, "inspections", safeInspectionId, "evidence"),
    );
    await directory.create(recursive: true);

    final destination = File(
      p.join(
        directory.path,
        safeEvidenceId + _extension(originalFilename),
      ),
    );
    final digest = sha256.convert(bytes).toString();

    if (await destination.exists()) {
      final existing = await destination.readAsBytes();
      final existingDigest = sha256.convert(existing).toString();
      if (existing.length == bytes.length && existingDigest == digest) {
        return StoredLocalEvidence(
          path: destination.path,
          sha256: digest,
          sizeBytes: bytes.length,
        );
      }
      throw StateError(
        "Evidence ID is already associated with different local bytes.",
      );
    }

    final temporary = File(
      destination.path + "." + const Uuid().v4() + ".tmp",
    );
    try {
      await temporary.writeAsBytes(bytes, flush: true);
      await temporary.rename(destination.path);
    } finally {
      if (await temporary.exists()) {
        await temporary.delete();
      }
    }

    return StoredLocalEvidence(
      path: destination.path,
      sha256: digest,
      sizeBytes: bytes.length,
    );
  }

  Future<bool> verify(StoredLocalEvidence evidence) async {
    final file = File(evidence.path);
    if (!await file.exists()) {
      return false;
    }
    final bytes = await file.readAsBytes();
    return bytes.length == evidence.sizeBytes &&
        sha256.convert(bytes).toString() == evidence.sha256;
  }

  Future<void> deleteAfterRemoteConfirmation(
    StoredLocalEvidence evidence, {
    required bool remoteDurabilityConfirmed,
  }) async {
    if (!remoteDurabilityConfirmed) {
      throw StateError(
        "Local evidence cannot be deleted before remote durability is confirmed.",
      );
    }

    final file = File(evidence.path);
    if (await file.exists()) {
      await file.delete();
    }
  }
}
