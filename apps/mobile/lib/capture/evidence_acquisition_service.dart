import "dart:typed_data";

import "package:image_picker/image_picker.dart";

enum EvidenceSource {
  camera,
  gallery,
}

class AcquiredEvidence {
  const AcquiredEvidence({
    required this.bytes,
    required this.filename,
  });

  final Uint8List bytes;
  final String filename;
}

abstract interface class EvidenceAcquisitionService {
  Future<AcquiredEvidence?> acquire(EvidenceSource source);
  Future<List<AcquiredEvidence>> recoverLostEvidence();
}

class ImagePickerEvidenceAcquisitionService
    implements EvidenceAcquisitionService {
  ImagePickerEvidenceAcquisitionService({
    ImagePicker? picker,
  }) : _picker = picker ?? ImagePicker();

  final ImagePicker _picker;

  @override
  Future<AcquiredEvidence?> acquire(EvidenceSource source) async {
    final imageSource = source == EvidenceSource.camera
        ? ImageSource.camera
        : ImageSource.gallery;

    final file = await _picker.pickImage(
      source: imageSource,
      preferredCameraDevice: CameraDevice.rear,
      requestFullMetadata: false,
    );
    if (file == null) {
      return null;
    }
    return _read(file);
  }

  @override
  Future<List<AcquiredEvidence>> recoverLostEvidence() async {
    final response = await _picker.retrieveLostData();
    if (response.isEmpty) {
      return const <AcquiredEvidence>[];
    }
    if (response.exception != null) {
      throw StateError(
        "Image acquisition recovery failed: " +
            response.exception!.code,
      );
    }

    final files = response.files;
    if (files == null || files.isEmpty) {
      return const <AcquiredEvidence>[];
    }

    final recovered = <AcquiredEvidence>[];
    for (final file in files) {
      recovered.add(await _read(file));
    }
    return List<AcquiredEvidence>.unmodifiable(recovered);
  }

  Future<AcquiredEvidence> _read(XFile file) async {
    final bytes = await file.readAsBytes();
    if (bytes.isEmpty) {
      throw StateError("Selected image is empty.");
    }

    final rawName = file.name.trim();
    final filename = rawName.isEmpty ? "package-image.jpg" : rawName;
    return AcquiredEvidence(
      bytes: bytes,
      filename: filename,
    );
  }
}
