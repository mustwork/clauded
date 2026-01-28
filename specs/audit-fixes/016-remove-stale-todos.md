# Remove Stale TODO Comments

**Audit Reference**: Code Health #21 | Severity: 2/10
**Source**: `.claude/audit-reports/spec-2026-01-28.md`

## Problem

Production code contains stale TODO comments that suggest incomplete implementation when the features are actually complete:

- `cli_integration.py:160` - "TODO: Implement JSON output" (JSON output exists)
- `wizard_integration.py:379` - "TODO: Trivial implementation..." (unclear what remains)

Stale TODOs create confusion for developers and auditors about project completeness.

## Requirements

### FR-1: Remove or Resolve TODOs

For each TODO in production code:
- If the referenced work is complete: remove the TODO comment
- If the referenced work is genuinely incomplete: create a feature spec for it and update the TODO to reference the spec
- If the TODO is unclear: remove it

### FR-2: Scan for All TODOs

Audit all source files under `src/clauded/` for TODO, FIXME, HACK, and XXX comments. Address each one.

## Affected Files

- `src/clauded/detect/cli_integration.py:160`
- `src/clauded/detect/wizard_integration.py:379`
- Any other files with stale markers
