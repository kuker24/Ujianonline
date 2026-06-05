# APK Build Success Report — 2026-06-05

## Status
APK release build is now confirmed working locally after Flutter and Android build toolchain fixes.

This report intentionally excludes secret/local-only material:
- no APK/AAB artifact is committed,
- no keystore or `key.properties` is committed,
- no `local.properties` is committed,
- the full build token is not recorded in Git.

## Relevant GitHub Commits
- `9ae9856` — `fix: resolve Flutter executable in APK builder`
- `7b4a813` — `fix: resolve Flutter APK source compile errors`
- `12466f6` — `fix: update Android build toolchain for Flutter`

## Local Toolchain Result
- Flutter installed and detected from `/home/fahmi/.cache/flutter_sdk/bin/flutter`.
- Flutter version used locally: `3.44.1` stable.
- Dart version used locally: `3.12.1`.
- Android toolchain and licenses were accepted locally.

## Build Fixes Confirmed
The following blockers were resolved:
- Flutter executable was missing from PATH / configured SDK path.
- Flutter source compile mismatches were repaired.
- Gradle wrapper was updated from `8.5` to `8.7`.
- Android Gradle Plugin was updated from `8.3.2` to `8.6.0`.
- Kotlin Gradle Plugin was updated from `1.9.0` to `2.0.0`.

## Validation Commands
The following local checks passed:

```bash
flutter pub get
flutter analyze --no-fatal-infos --no-fatal-warnings
flutter test
cd android && ./gradlew --no-daemon :app:assembleRelease --dry-run
flutter build apk --release
```

Notes:
- `flutter analyze` still reports non-fatal info/warning items only.
- Gradle/AGP/Kotlin warnings remain about future Flutter compatibility, but the current release build succeeds.

## APK Artifact Summary
- APK release build succeeded locally.
- APK artifact was copied outside the repository under the user's Downloads area.
- APK size observed: approximately `67 MB`.
- APK SHA-256 observed: `bfd485870703d93f90defbcb2250165f0592e66e8d31906d3e560c112b5b41fe`.
- Package name: `com.school.examapp`.
- Version: `1.0.0+1`.
- Production server URL: `https://man1rokanhulu.cloud/`.
- Cleartext traffic: disabled.

## Signing Verification
`apksigner verify --verbose --print-certs` passed.

Observed signing details:
- APK Signature Scheme v2: verified.
- Number of signers: `1`.
- Certificate SHA-256 digest: `297ad1bfc6ed358684ad699569daf4a6565847790211ce726bf53da580ef3187`.

## Admin Panel Requirement
Before distributing this APK, the operator must register the latest APK build token and signature hash in the admin settings panel.

- Full build token is intentionally not stored in Git. Use the latest local build log or `flutter_client_code/lib/config.dart` from the local build workspace.
- Signature hash to register: `297ad1bfc6ed358684ad699569daf4a6565847790211ce726bf53da580ef3187`.
- Keep the stable profile enabled during rollout if both stable and new-update APKs are supported.

## Operational Notes
- No VPS deployment/restart/migration/load-test was performed as part of this APK build confirmation.
- No Phase 5 hybrid/queue/runtime-buffer work was started.
- Do not commit generated APK/AAB outputs, keystores, `key.properties`, or full build tokens.
