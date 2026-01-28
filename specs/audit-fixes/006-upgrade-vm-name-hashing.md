# Upgrade VM Name Hashing from MD5 to SHA256

**Audit Reference**: Important #4 | Severity: 4/10
**Source**: `.claude/audit-reports/spec-2026-01-28.md`

## Problem

VM names are generated using `hashlib.md5(path).hexdigest()[:8]` (`config.py:44`). MD5 is cryptographically broken and has a higher collision probability than SHA256 when truncated to 8 characters. While 8-character hex provides 4 billion combinations (unlikely to collide in practice), using a stronger hash is a low-cost improvement.

**Backwards compatibility concern**: Changing the hash algorithm changes VM names for existing projects. Users with running VMs will get a new VM name, orphaning their existing VM.

## Requirements

### FR-1: Use SHA256

Replace `hashlib.md5()` with `hashlib.sha256()` for VM name generation. Continue truncating to 8 hex characters.

### FR-2: Migration Path

When a config is loaded with an existing `vm.name` that was generated with MD5:
- The loaded config already contains the explicit VM name
- No migration is needed because `Config.load()` reads the stored name directly
- Only new configs created via `Config.from_wizard()` will use the new hash

This means existing projects keep their old VM names (from `.clauded.yaml`) and only new projects get SHA256-based names.

### FR-3: Update Spec

Update `specs/spec.md` line 179 to reference SHA256 instead of MD5.

## Affected Files

- `src/clauded/config.py:44`
- `specs/spec.md:179`
- `tests/test_config.py` (update hash expectations)
