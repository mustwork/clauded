# Dart with Flutter

## Overview

When a user selects Dart as their language, Flutter SDK must always be installed alongside it. Flutter is the UI framework built on Dart and is the primary reason most developers choose Dart. Installing both together ensures the environment is immediately useful for Flutter development without additional configuration.

## Background

Dart is already a supported language option in clauded. The existing Dart roles install only the standalone Dart SDK. This feature extends those roles to also install the Flutter SDK, making Dart+Flutter a single, complete development environment.

## Requirements

### Functional Requirements

1. **Flutter always installed with Dart**: Whenever the Dart language is provisioned in a VM, the Flutter SDK must be installed automatically. There is no option to install Dart without Flutter.

2. **Distro support**: Flutter must be installed on both Alpine and Ubuntu VMs. The existing dart roles (dart-alpine, dart-ubuntu) must be extended.

3. **Version alignment**: The Flutter version installed must correspond to the selected Dart version. Each supported Dart version maps to a specific Flutter stable release that ships with that Dart version.

4. **Download integrity**: Flutter SDK downloads must follow the same download metadata pattern as other tools — URLs defined in `downloads.yml`, referenced from the role via Ansible variables.

5. **PATH configuration**: After installation, both `dart` and `flutter` commands must be available in the PATH for all shell sessions.

6. **Label update**: The wizard display label for Dart must reflect that Flutter is included (e.g., "Dart + Flutter (dart, flutter, pub)").

### Non-Functional Requirements

- Flutter installation must not break existing Dart-only tests.
- Downloads use the existing centralized download metadata pattern.
- Roles follow the same structure as existing language roles.

## Version Mapping

The Flutter version to install is determined by the selected Dart version:

| Dart Version | Flutter Version |
|---|---|
| 3.7 | 3.29.2 |
| 3.6 | 3.27.4 |
| 3.5 | 3.24.5 |

## Architecture Notes

- Flutter SDK download is separate from Dart SDK — both are downloaded and installed
- Flutter is installed to `/usr/local/flutter`
- Flutter bin directory added to `/etc/profile.d/dart.sh` (alongside existing Dart PATH)
- The `flutter` command's bundled `dart` takes precedence over the standalone dart via PATH ordering (Flutter SDK bin should come first, or system dart symlink should point to Flutter's dart)
- The provisioner does not need changes — Flutter is always bundled with Dart at the role level

## Acceptance Criteria

1. When a VM is provisioned with Dart, both `dart --version` and `flutter --version` succeed.
2. The `flutter` command is on the PATH in new shell sessions.
3. The wizard displays "Dart + Flutter" label for the Dart language option.
4. Flutter installation works on both Alpine and Ubuntu distros.
5. Flutter version corresponds to the selected Dart version per the version mapping table.
6. Existing Dart provisioner tests continue to pass.
