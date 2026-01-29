# Respect Runtime Version Selections

**Audit Reference**: Config/UX #2 | Severity: 8/10
**Source**: internal audit (2026-01-29)

## Problem

The wizard and `.clauded.yaml` allow users to select specific Node and Python
versions, but provisioning ignores those selections:
- Node uses `nodejs-current` from Alpine regardless of requested version.
- Python installs system `python3` without respecting the configured version.

This breaks determinism and violates user expectations.

## Requirements

### FR-1: Enforce Selected Versions
Provisioning must install the version specified in config for all supported runtimes.
If exact patch versions are not available, either:
- Map to the closest supported version and inform the user, OR
- Fail fast with a clear error message.

### FR-2: Align UI With Reality
If version pinning is not possible for a runtime, remove that choice from the
wizard and documentation or label it explicitly as "best effort".

### FR-3: Validation and Feedback
Validate selected versions before provisioning and present a helpful error if
unsupported. The error should include a list of supported versions.

### FR-4: Tests
Add tests to ensure:
- Selected versions are reflected in provisioning logic.
- Unsupported versions yield clear errors.

## Affected Files

- `src/clauded/wizard.py`
- `src/clauded/config.py`
- `src/clauded/provisioner.py`
- `src/clauded/roles/node/tasks/main.yml`
- `src/clauded/roles/python/tasks/main.yml`
- `tests/`
- `README.md`
