# Create CHANGELOG

**Audit Reference**: Documentation #28 | Severity: 2/10
**Source**: `.claude/audit-reports/spec-2026-01-28.md`

## Problem

No CHANGELOG exists for the project. Version history is only available through `git log`. Users and contributors cannot easily determine what changed between releases without reading commit messages.

## Requirements

### FR-1: CHANGELOG Format

Create a `CHANGELOG.md` in the project root following Keep a Changelog format (https://keepachangelog.com/):

```markdown
# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- ...

### Changed
- ...

### Fixed
- ...
```

### FR-2: Initial Content

Populate the changelog with the current state of the project (v0.1.0) based on git history. Document:
- Core features (VM lifecycle, wizard, detection, provisioning)
- All supported languages, tools, databases, frameworks
- CLI commands and flags

### FR-3: Maintenance Process

Document in CLAUDE.md that all feature work and bug fixes must include a CHANGELOG entry.

## Affected Files

- `CHANGELOG.md` (new)
- `CLAUDE.md` (add changelog requirement)
