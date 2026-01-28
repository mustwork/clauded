# Graceful Cleanup on Keyboard Interrupt

**Audit Reference**: Code Health #23 | Severity: 3/10
**Source**: `.claude/audit-reports/spec-2026-01-28.md`

## Problem

When the user presses CTRL+C during provisioning or VM creation, the Ansible/limactl subprocess is killed, but:

- Temporary playbook files in `/tmp` may not be cleaned up
- The spinner thread may leave the terminal in a broken state (partial line, hidden cursor)
- No cleanup message is printed

The `TemporaryDirectory` context manager in `provisioner.py` handles cleanup for provisioning, but `lima.py:47-71` uses `NamedTemporaryFile(delete=False)` with a `finally` block that may not execute if the process is SIGKILLed.

## Requirements

### FR-1: Signal Handling

Register a `SIGINT` handler that:
- Prints "Interrupted. Cleaning up..."
- Allows context managers and `finally` blocks to execute
- Exits with code 130 (standard SIGINT exit code)

### FR-2: Spinner Cleanup

The spinner must restore terminal state (show cursor, clear spinner line) even when interrupted. Use `try/finally` in the spinner context manager to guarantee cleanup.

### FR-3: Temp File Cleanup

Replace `NamedTemporaryFile(delete=False)` + manual cleanup in `lima.py` with `TemporaryDirectory` context manager (matching `provisioner.py` pattern) for more robust cleanup.

## Affected Files

- `src/clauded/cli.py` (signal handler registration)
- `src/clauded/spinner.py` (ensure cleanup in finally)
- `src/clauded/lima.py:47-71` (use TemporaryDirectory)
