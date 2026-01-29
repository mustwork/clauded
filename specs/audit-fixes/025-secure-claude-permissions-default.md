# Secure Default for Claude Code Permissions

**Audit Reference**: Security Defaults #3 | Severity: 8/10
**Source**: internal audit (2026-01-29)

## Problem

The default configuration enables `dangerously_skip_permissions` for Claude Code,
which auto-accepts permission prompts. This is an unsafe default for production
and should require explicit user opt-in.

## Requirements

### FR-1: Default to Safe Behavior
Set `claude.dangerously_skip_permissions` default to `false` in config and wizard.

### FR-2: Explicit Opt-In
Wizard copy should clearly warn about the implications and require explicit
confirmation to enable auto-accept.

### FR-3: Backward Compatibility
If existing `.clauded.yaml` files omit the flag, treat it as `false` for new
versions; consider a one-time migration notice if behavior changes.

### FR-4: Documentation
Update docs to describe the flag, the default, and its security implications.

### FR-5: Tests
Add tests ensuring the default is `false` and that enabling it propagates into
provisioning.

## Affected Files

- `src/clauded/config.py`
- `src/clauded/wizard.py`
- `src/clauded/roles/claude_code/tasks/main.yml`
- `docs/`
- `tests/`
