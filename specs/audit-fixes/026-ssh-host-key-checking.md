# SSH Host Key Checking Default

**Audit Reference**: Security Defaults #4 | Severity: 6/10
**Source**: internal audit (2026-01-29)

## Problem

Ansible configuration disables SSH host key checking by default. This is
convenient for local VMs but not a production-safe default and weakens
host authenticity guarantees.

## Requirements

### FR-1: Default to Host Key Checking On
Enable host key checking by default in generated `ansible.cfg`.

### FR-2: Provide an Explicit Opt-Out
Allow users to disable host key checking via a config flag or CLI option.

### FR-3: Document Behavior
Document the security implications and the opt-out mechanism.

### FR-4: Tests
Add tests to verify that the generated ansible config matches the selected setting.

## Affected Files

- `src/clauded/provisioner.py`
- `docs/`
- `tests/`
