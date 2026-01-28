# Configurable Alpine Linux Image Version

**Audit Reference**: Minor #13 | Severity: 3/10
**Source**: `.claude/audit-reports/spec-2026-01-28.md`

## Problem

The Alpine Linux 3.21 cloud image URL is hardcoded in `lima.py:175`. When Alpine 3.22 is released, updating the base image requires a code change and new clauded release. Users cannot pin a specific Alpine version or use a newer release independently.

## Requirements

### FR-1: Default with Override

Keep Alpine 3.21 as the default but allow the image URL and version to be overridden via:
- A new optional field in `.clauded.yaml`: `vm.image` (URL string)
- When not specified, use the current hardcoded Alpine 3.21 URL

### FR-2: Config Schema Update

Extend the config schema:

```yaml
vm:
  name: clauded-a1b2c3d4
  cpus: 4
  memory: 8GiB
  disk: 20GiB
  image: https://dl-cdn.alpinelinux.org/alpine/v3.21/releases/cloud/...  # optional
```

The `image` field is optional. When absent, the default Alpine 3.21 image is used. The wizard does not need to prompt for this field.

### FR-3: Update Spec

Update `specs/spec.md` config schema (lines 144-175) to document the optional `vm.image` field.

## Affected Files

- `src/clauded/config.py` (add optional image field)
- `src/clauded/lima.py:175` (use config.image or default)
- `specs/spec.md` (update schema)
- `tests/test_config.py`
- `tests/test_lima.py`
