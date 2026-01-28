# Wizard Timeout and Non-Interactive Fallback

**Audit Reference**: Important #6 | Severity: 4/10
**Source**: `.claude/audit-reports/spec-2026-01-28.md`

## Problem

The wizard uses `questionary` prompts with no timeout (`wizard.py`). If the terminal becomes unresponsive or the tool is invoked in a non-interactive context (piped input, CI/CD environment), the CLI hangs indefinitely with no way to recover except SIGKILL.

## Requirements

### FR-1: Non-Interactive Detection

Before launching the wizard, check if stdin is a TTY. If not interactive:
- Print an error message: "Interactive terminal required. Use an existing .clauded.yaml or create one manually."
- Exit with code 1

### FR-2: Keyboard Interrupt Handling

Ensure `KeyboardInterrupt` (CTRL+C) during wizard prompts:
- Cleanly exits the wizard
- Prints "Setup cancelled."
- Exits with code 1
- Does not leave partial `.clauded.yaml` files

### FR-3: Questionary Error Handling

Handle `questionary` returning `None` (user pressed CTRL+C during a prompt) by treating it as cancellation and exiting cleanly.

## Affected Files

- `src/clauded/wizard.py`
- `src/clauded/cli.py` (TTY check before wizard invocation)
- `tests/test_wizard.py`
