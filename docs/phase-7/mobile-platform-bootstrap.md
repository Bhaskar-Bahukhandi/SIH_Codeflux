# Mobile Platform Bootstrap

The Phase 7 branch now contains the Flutter application code but intentionally does not hand-write generated Android/iOS runner projects.

Generate those projects with the same Flutter SDK that will build the prototype:

    powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_mobile_platforms.ps1

The script:

- requires a clean Git working tree;
- refuses to overwrite existing `android/` or `ios/` directories;
- runs Flutter's platform generation in `apps/mobile`;
- restores the existing hand-written `pubspec.yaml` and `lib/main.dart` after generation;
- sets the Android app minimum SDK to 24 for the current `image_picker` support floor;
- adds the iOS camera and photo-library usage descriptions;
- sets the iOS deployment target to 13.0 when a Podfile is generated;
- runs `flutter pub get`, `flutter analyze`, and `flutter test`;
- does not commit anything.

The default reverse-domain organization is `in.sih.codeflux`. Override it when running the script if the team chooses another application identifier:

    powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_mobile_platforms.ps1 -Organization "in.example.team"

After the script succeeds, review the generated native files before committing them.

## Runtime API configuration

The mobile app deliberately has no fake or hard-coded API address.

Run with:

    flutter run --dart-define=CODEFLUX_API_URL=https://your-api.example/

For local Android-emulator development, use the actual reachable development API address chosen by the team; do not commit a machine-specific address into `lib/main.dart`.

## Current limitation

This repository session cannot execute Flutter locally, and GitHub Actions is still failing before runner-step allocation under Issue #38. Therefore the generated native platform projects should not be committed from this branch until the bootstrap script can run and the analyzer/tests genuinely execute.
