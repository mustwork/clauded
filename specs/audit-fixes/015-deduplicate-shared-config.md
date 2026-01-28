# Deduplicate Shared Configuration Constants

**Audit Reference**: Code Health #19, #20 | Severity: 3/10
**Source**: `.claude/audit-reports/spec-2026-01-28.md`

## Problem

Two categories of code duplication exist:

1. **Language version config** (`wizard.py:40-71`, `wizard_integration.py:102-133`): The same language version mappings (Python versions, Node versions, etc.) are defined in two separate files. Changes require updating both, with drift risk.

2. **Confidence display logic** (`cli_integration.py:61-66, 83-88, 97-102`, etc.): Six identical blocks map confidence strings to display markers. Copy-paste maintenance burden.

## Requirements

### FR-1: Shared Language Config

Extract language version configuration to a single shared location (e.g., a constant in `config.py` or a new `constants.py` module). Both `wizard.py` and `wizard_integration.py` must import from this single source.

The shared config should include for each language:
- Available versions
- Default version
- Display name

### FR-2: Confidence Display Helper

Extract the repeated confidence-to-marker mapping into a single function:

```python
def confidence_marker(confidence: str) -> str:
    """Return display marker for a confidence level."""
```

All six call sites in `cli_integration.py` must use this function.

### FR-3: No Behavioral Change

All wizard behavior, display output, and detection integration must remain identical after refactoring. Existing tests must continue passing without modification.

## Affected Files

- `src/clauded/wizard.py:40-71`
- `src/clauded/detect/wizard_integration.py:102-133`
- `src/clauded/detect/cli_integration.py:61-66, 83-88, 97-102`
- New file if needed for shared constants
