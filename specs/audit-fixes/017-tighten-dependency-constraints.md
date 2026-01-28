# Tighten Dependency Version Constraints

**Audit Reference**: Code Health #22 | Severity: 2/10
**Source**: `.claude/audit-reports/spec-2026-01-28.md`

## Problem

Minimum dependency version constraints in `pyproject.toml` are 2-4 years old:

| Package | Current Constraint | Release Date | Issue |
|---------|-------------------|--------------|-------|
| click | >=8.1 | Jan 2023 | 3+ years old |
| questionary | >=2.0 | Oct 2019 | 6+ years old |
| ansible | >=13.2 | May 2021 | 4+ years old |
| pyyaml | >=6.0 | Jan 2021 | 5+ years old |

Installing with minimal versions gives outdated packages that may have known bugs or missing features used by clauded.

Additionally, `types-pyyaml` may have incorrect capitalization (should be `types-PyYAML`).

## Requirements

### FR-1: Update Minimum Versions

Tighten minimum version constraints to the oldest version that clauded is actually tested against. If no specific older version compatibility is needed, set minimums to versions from the last 12-18 months.

### FR-2: Fix types-pyyaml

Verify the correct package name for PyYAML type stubs and update if incorrect.

### FR-3: No Upper Bounds

Do not add upper bounds (e.g., `<9.0`) unless there is a known incompatibility. Upper bounds cause unnecessary dependency conflicts.

## Affected Files

- `pyproject.toml` (dependency version constraints)
