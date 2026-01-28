# Provisioning Failure Recovery

**Audit Reference**: Important #10 | Severity: 5/10
**Source**: `.claude/audit-reports/spec-2026-01-28.md`

## Problem

When Ansible provisioning fails partway through (e.g., package download fails, role has a bug), the VM is left in a partially-provisioned state. Users must `clauded --destroy` and recreate the entire VM from scratch, losing any manually-installed tools or data.

The spec already states Ansible playbooks should be idempotent (line 467), but there is no verification or guidance for users on recovery.

## Requirements

### FR-1: Provisioning Failure Message

When `ansible-playbook` exits with non-zero status, print a clear recovery message:

```
Provisioning failed (exit code {N}).

To retry provisioning:  clauded --reprovision
To debug in the VM:     limactl shell {vm-name}
To start fresh:         clauded --destroy && clauded
```

### FR-2: Partial Provisioning State

After a provisioning failure:
- The VM must remain running (do not stop or destroy)
- The `.clauded.yaml` must be preserved
- The user must be able to `clauded --reprovision` to retry
- The user must be able to `limactl shell {vm-name}` to debug manually

### FR-3: Idempotency Verification

All Ansible roles must be verified as idempotent:
- Running provisioning twice in a row must succeed
- No role should fail because a previous run partially completed
- Document any roles that are NOT idempotent and require manual intervention

## Affected Files

- `src/clauded/provisioner.py` (error handling and messaging)
- `src/clauded/cli.py` (don't destroy VM on provision failure)
- `src/clauded/roles/*/tasks/main.yml` (verify idempotency)
