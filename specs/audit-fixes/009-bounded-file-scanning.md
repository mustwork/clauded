# Bounded File Scanning for Detection

**Audit Reference**: Important #7 | Severity: 5/10
**Source**: `.claude/audit-reports/spec-2026-01-28.md`

## Problem

The linguist detection module uses `rglob("*")` (`linguist.py:390`) to recursively scan all files in the project directory. For monorepos or projects with large vendored directories that slip past exclusion patterns, this can:

- Consume excessive memory building file path lists
- Take minutes to hours on projects with millions of files
- Appear hung with no progress feedback

The existing SKIP_DIRECTORIES list and vendor exclusion patterns mitigate this, but edge cases remain (e.g., deeply nested generated code, unconventional vendor paths).

## Requirements

### FR-1: File Count Limit

Detection must enforce a maximum file count for scanning. When the limit is reached:
- Stop scanning additional files
- Process files already collected
- Log a warning: "Scanned {limit} files; detection results may be incomplete for large projects"
- Continue with partial results (do not fail)

Suggested limit: 50,000 files (sufficient for most projects).

### FR-2: Scan Statistics

The `ScanStats` dataclass must include:
- `files_scanned: int` - actual files processed
- `files_skipped: int` - files excluded by vendor/skip patterns
- `scan_truncated: bool` - whether the limit was reached

### FR-3: CLI Feedback

When `--detect` or default workflow runs detection on a large project:
- Display scan progress if scanning exceeds 5 seconds (e.g., "Scanning project files...")
- Display truncation warning if limit reached

## Affected Files

- `src/clauded/detect/linguist.py:390` (add file count limit)
- `src/clauded/detect/result.py` (update ScanStats)
- `src/clauded/detect/cli_integration.py` (display truncation warning)
- `tests/test_detect_linguist.py`
