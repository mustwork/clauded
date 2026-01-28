# Add --version Flag to CLI

**Audit Reference**: Minor #11 | Severity: 2/10
**Source**: `.claude/audit-reports/spec-2026-01-28.md`

## Problem

`clauded --version` is not implemented. Users and operations teams cannot determine which version of clauded is installed without inspecting `pyproject.toml` or `pip show`.

## Requirements

### FR-1: Version Option

Add a `--version` flag to the CLI that prints the version and exits:

```
$ clauded --version
clauded 0.1.0
```

The version must be read from the package metadata (via `importlib.metadata.version("clauded")`) to maintain a single source of truth with `pyproject.toml`.

### FR-2: Click Integration

Use Click's built-in `@click.version_option()` decorator for standard behavior:
- `--version` prints version and exits
- `-V` as short alias (optional)

## Affected Files

- `src/clauded/cli.py` (add version option)
- `tests/test_cli.py` (test --version output)
