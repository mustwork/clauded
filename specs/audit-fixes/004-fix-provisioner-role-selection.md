# Fix Provisioner Role Selection Logic

**Audit Reference**: Spec Deviations #4, #5, #6 | Severity: 7/10
**Source**: `.claude/audit-reports/spec-2026-01-28.md`

## Problem

The provisioner role selection in `provisioner.py` deviates from the specification in three ways:

1. **Node.js always included** (`provisioner.py:84`): `roles = ["common", "node"]` unconditionally includes node. Spec line 193 requires node only when `config.environment.node` is set.

2. **Gradle selection wrong** (`provisioner.py:96-98`): gradle is added when Java or Kotlin is selected, not when "gradle" appears in `config.environment.tools`. Spec line 202 requires gradle only when explicitly in tools list.

3. **Extra roles undocumented** (`provisioner.py:88-89, 97`): uv, poetry, and maven are auto-bundled with Python/Java but are not listed in the specification's Ansible roles table (spec lines 210-228).

## Requirements

### FR-1: Conditional Node.js Role

The `node` role must only be included when `config.environment.node` is set (not None). The `common` role is the only always-included role.

**Impact**: Claude Code and Playwright depend on npm. When `node` becomes conditional, the `claude_code` and `playwright` roles must either:
- Declare a dependency on node (include it themselves), OR
- Document that selecting claude-code or playwright requires node

### FR-2: Gradle Tool Selection

The `gradle` role must be selected based on `"gradle" in config.environment.tools`, matching the spec. It must NOT be selected solely based on Java/Kotlin presence.

### FR-3: Document Extra Roles in Spec

Update `specs/spec.md` Ansible roles table (lines 210-228) to include:

| Role | Purpose | Key Tasks |
|------|---------|-----------|
| `uv` | Python package manager | uv installation via pipx |
| `poetry` | Python dependency manager | poetry installation via pipx |
| `maven` | Java/Kotlin build tool | Maven binary installation |

Also clarify the auto-bundling behavior: when Python is selected, uv and poetry are automatically included. When Java or Kotlin is selected, maven is automatically included.

### FR-4: Update Tests

Update provisioner tests to validate against spec requirements, not current behavior. Add tests for:
- Minimal config produces only `["common"]`
- Node-only config produces `["common", "node"]`
- Gradle in tools but no Java/Kotlin produces `["common", "gradle"]`

## Affected Files

- `src/clauded/provisioner.py:82-126`
- `specs/spec.md:210-228`
- `tests/test_provisioner.py`
