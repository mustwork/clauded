# Subprocess Error Handling for VM and Provisioning Operations

**Audit Reference**: Critical #2, #8 | Severity: 7/10
**Source**: `.claude/audit-reports/spec-2026-01-28.md`

## Problem

All `subprocess.run(..., check=True)` calls in `lima.py` and `provisioner.py` raise unhandled `CalledProcessError` exceptions. When `limactl` or `ansible-playbook` fails, users see raw Python tracebacks instead of actionable error messages.

**Examples of poor UX:**
- Lima not installed: `FileNotFoundError` traceback
- VM creation failure: `CalledProcessError` with return code only
- Ansible role failure: No indication of which role failed

## Affected Locations

- `lima.py:67` - VM creation (`limactl start`)
- `lima.py:83` - VM start (`limactl start`)
- `lima.py:90` - VM stop (`limactl stop`)
- `lima.py:95` - VM destroy (`limactl delete`)
- `provisioner.py:80` - Ansible execution (`ansible-playbook`)

## Requirements

### FR-1: Lima Error Handling

All `limactl` subprocess calls must catch `CalledProcessError` and `FileNotFoundError`, and produce user-friendly messages:

- `FileNotFoundError` -> "Lima is not installed. Install with: brew install lima"
- `CalledProcessError` during create -> "VM creation failed (exit code {N}). Check Lima logs: ~/.lima/{vm-name}/ha.stderr.log"
- `CalledProcessError` during start -> "Failed to start VM '{name}'. Is it in a valid state? Try: clauded --destroy"
- `CalledProcessError` during stop -> "Failed to stop VM '{name}'. VM may not be running."
- `CalledProcessError` during destroy -> "Failed to destroy VM '{name}'."

All error messages must be printed via `click.echo(..., err=True)` and the CLI must exit with code 1.

### FR-2: Provisioning Error Handling

Ansible failures must catch `CalledProcessError` and:
- Report the exit code
- Suggest `clauded --reprovision` for retry
- Suggest SSH access for debugging: `limactl shell {vm-name}`

### FR-3: Test Coverage

Add tests for each subprocess failure scenario using mocked `subprocess.run` that raises `CalledProcessError` and `FileNotFoundError`.

## Affected Files

- `src/clauded/lima.py`
- `src/clauded/provisioner.py`
- `tests/test_lima.py`
- `tests/test_provisioner.py`
