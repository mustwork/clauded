# Acceptance Criteria: Dart with Flutter

Generated: 2026-03-18T00:00:00Z
Source: spec.md

## Criteria

### AC-001: Flutter installed with Dart
- **Description**: When Dart is provisioned, `flutter` command is available and functional
- **Verification**: `flutter --version` succeeds in the VM after provisioning with Dart
- **Type**: integration

### AC-002: Dart command still available
- **Description**: The `dart` command remains available after Flutter installation
- **Verification**: `dart --version` succeeds in the VM after provisioning with Dart
- **Type**: integration

### AC-003: Flutter on PATH in new shell sessions
- **Description**: Both `dart` and `flutter` are on the PATH for non-interactive shells
- **Verification**: Check `/etc/profile.d/dart.sh` contains Flutter bin path
- **Type**: unit

### AC-004: Wizard label updated
- **Description**: The Dart option in the wizard and CLI displays "Dart + Flutter"
- **Verification**: `LANGUAGE_CONFIG["dart"]["label"]` contains "flutter"
- **Type**: unit

### AC-005: Flutter version matches Dart version
- **Description**: The Flutter SDK version installed corresponds to the selected Dart version per the version mapping table
- **Verification**: Check `downloads.yml` contains flutter entries keyed by dart version (3.7→3.29.2, 3.6→3.27.4, 3.5→3.24.5)
- **Type**: unit

### AC-006: Works on Alpine and Ubuntu
- **Description**: Flutter installation tasks are present in both Alpine and Ubuntu dart role variants
- **Verification**: Both `dart-alpine/tasks/main.yml` and `dart-ubuntu/tasks/main.yml` contain Flutter installation tasks
- **Type**: unit

## Verification Plan

1. Inspect `downloads.yml` for correct Flutter entries (AC-005)
2. Inspect dart role YAML files for Flutter installation tasks (AC-003, AC-006)
3. Run existing provisioner tests to verify no regressions (AC-001, AC-002)
4. Check `constants.py` label (AC-004)
