# Add License Information

**Audit Reference**: Release Hygiene #1 | Severity: 4/10
**Source**: internal audit (2026-01-29)

## Problem

The project does not include a LICENSE file and the README contains a
placeholder. This blocks distribution and makes usage rights unclear.

## Requirements

### FR-1: Add LICENSE File
Add a `LICENSE` file at repository root with the chosen license text.

### FR-2: Update README
Replace the placeholder with the actual license name.

### FR-3: Package Metadata
Ensure `pyproject.toml` includes a license field and/or classifier that matches
the chosen license.

## Affected Files

- `LICENSE`
- `README.md`
- `pyproject.toml`
