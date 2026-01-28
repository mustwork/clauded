# Expand Test Coverage for Untested Modules

**Audit Reference**: Test Infrastructure #26, #27 | Severity: 4/10
**Source**: `.claude/audit-reports/spec-2026-01-28.md`

## Problem

Several modules have zero or minimal test coverage:

| Module | Coverage | LOC | Risk |
|--------|----------|-----|------|
| `spinner.py` | 0% | 41 | Low (UI only) |
| `detect/mcp.py` | 0% | 261 | Medium (untested detection) |
| `detect/cli_integration.py` | ~40% | 349 | Medium (display logic) |
| `detect/wizard_integration.py` | ~60% | 380 | Medium (wizard defaults) |

Additionally, ~100 detection tests are nearly identical and could be parameterized to reduce duplication without losing coverage.

CLI workflow gaps:
- No test for `--edit` workflow
- No test for `--detect` workflow (JSON output)
- No test for `--reprovision` with stopped VM (covered in spec 001)

## Requirements

### FR-1: MCP Detection Tests

Add test file `tests/test_mcp.py` covering:
- Detection from `.mcp.json` file
- Detection from `mcp.json` file
- Detection from `~/.claude.json`
- Server command parsing (uvx, npx, node, python, docker)
- Missing/malformed file handling
- Symlink protection

### FR-2: Spinner Tests

Add test file `tests/test_spinner.py` covering:
- Spinner context manager start/stop
- Thread cleanup on exit
- Cleanup on exception

### FR-3: CLI Workflow Tests

Add to `tests/test_cli.py`:
- `--edit` workflow: loads config, runs wizard, saves, provisions, enters shell
- `--detect` workflow: runs detection, outputs JSON, exits
- `--reprovision` with stopped VM (per spec 001)

### FR-4: Parameterize Redundant Tests

Convert repeated test patterns to `@pytest.mark.parametrize()`:
- Framework detection tests (test_framework.py): parameterize by (manifest_type, framework_name, package_name)
- Version detection tests (test_version_detection.py): parameterize by (runtime, file, content, expected_version)

Target: reduce ~100 near-identical test functions to ~20 parameterized functions with equivalent coverage.

## Affected Files

- `tests/test_mcp.py` (new)
- `tests/test_spinner.py` (new)
- `tests/test_cli.py` (add workflow tests)
- `tests/test_framework.py` (parameterize)
- `tests/test_version_detection.py` (parameterize)
