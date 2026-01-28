# Replace Broad Exception Handling with Specific Catches

**Audit Reference**: Important #8 | Severity: 4/10
**Source**: `.claude/audit-reports/spec-2026-01-28.md`

## Problem

`cli_integration.py:130-132` uses a broad `try-except Exception` that silently swallows all exceptions during detection display, including critical errors like `MemoryError`, `SystemExit`, and `KeyboardInterrupt`. This masks real failures that should propagate.

Similar patterns exist in detection modules (`database.py:95,104,112`, `version.py:215,241`) where bare `except Exception` catches prevent type checkers from validating exception handling and hide specific error types.

## Requirements

### FR-1: Specific Exception Types

Replace `except Exception` blocks with specific catches:
- File I/O operations: catch `OSError`, `PermissionError`
- YAML/JSON/TOML parsing: catch `yaml.YAMLError`, `json.JSONDecodeError`, `tomllib.TOMLDecodeError`
- XML parsing: catch `xml.etree.ElementTree.ParseError`

### FR-2: Critical Exception Propagation

Never catch:
- `KeyboardInterrupt` (user wants to exit)
- `SystemExit` (intentional exit)
- `MemoryError` (unrecoverable)

If using `except Exception`, always re-raise `KeyboardInterrupt` and `SystemExit`.

### FR-3: Logging

All caught exceptions must be logged at `DEBUG` level with the exception details, not silently swallowed. This preserves the graceful degradation behavior while making failures diagnosable with `--debug`.

## Affected Files

- `src/clauded/detect/cli_integration.py:130-132`
- `src/clauded/detect/database.py` (multiple except blocks)
- `src/clauded/detect/version.py` (multiple except blocks)
- `src/clauded/detect/framework.py` (multiple except blocks)
