# Fix --reprovision Workflow for Stopped VMs

**Audit Reference**: Critical #1 | Severity: 6/10
**Source**: `.claude/audit-reports/spec-2026-01-28.md`

## Problem

The `--reprovision` flag does not trigger Ansible provisioning when the VM is in a stopped state. The `elif` chain in `cli.py:187-193` causes the reprovision branch to be skipped after the stopped-VM branch starts the VM.

**Current behavior**: Stopped VM + `--reprovision` starts the VM but does NOT reprovision.
**Expected behavior** (per spec lines 290-295): Start the VM first, THEN re-run Ansible provisioning.

## Root Cause

```
if not vm.exists():     # creates and provisions
    ...
elif not vm.is_running():  # starts stopped VM
    vm.start()
elif reprovision:       # SKIPPED because previous elif matched
    provisioner.run()
```

Line 190 uses `elif reprovision` which creates an unintended dependency on the `vm.is_running()` check being false.

## Requirements

### FR-1: Reprovision After Start

When `--reprovision` is used and the VM is stopped, the CLI must:
1. Start the VM
2. Run Ansible provisioning
3. Enter shell

The reprovision check must execute independently of the VM start logic.

### FR-2: Test Coverage

Add test case verifying: `vm.exists()=True`, `vm.is_running()=False`, `--reprovision=True` results in both `vm.start()` AND `provisioner.run()` being called.

## Affected Files

- `src/clauded/cli.py:187-193`
- `tests/test_cli.py` (new test case)
