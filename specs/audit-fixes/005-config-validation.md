# Config Load Validation and Schema Versioning

**Audit Reference**: Spec Deviation #7, Minor #12 | Severity: 5/10
**Source**: `.claude/audit-reports/spec-2026-01-28.md`

## Problem

Two config validation gaps exist:

1. **Mount path validation missing** (`config.py:68-94`): `Config.load()` does not enforce the spec constraint (line 154) that `mount_guest` must equal `mount_host`. Users can manually edit `.clauded.yaml` to set divergent paths, which may cause unexpected behavior (project files at wrong location in VM).

2. **Schema version unchecked** (`config.py:76`): The `version: "1"` field is loaded but never validated. Future schema changes could silently misparse old configs, and config downgrades produce undefined behavior.

## Requirements

### FR-1: Mount Path Validation

`Config.load()` must validate that `mount_guest == mount_host`. If they differ:
- Log a warning
- Auto-correct `mount_guest` to match `mount_host`
- Continue loading (don't fail)

This preserves backwards compatibility while enforcing the constraint.

### FR-2: Schema Version Validation

`Config.load()` must check the `version` field:
- If `version` is `"1"` (current): proceed normally
- If `version` is missing: treat as `"1"`, add warning
- If `version` is higher than supported: exit with error message indicating the config requires a newer clauded version
- If `version` is unrecognized: exit with error message

### FR-3: Migration Foundation

Add a `_migrate_config(data: dict) -> dict` function that can transform older config formats to current. For v1, this is a no-op but establishes the pattern for future upgrades.

## Affected Files

- `src/clauded/config.py:68-94`
- `tests/test_config.py`
