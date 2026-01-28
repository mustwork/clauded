# Sanitize Environment Variables for Ansible Execution

**Audit Reference**: Important #9 | Severity: 5/10
**Source**: `.claude/audit-reports/spec-2026-01-28.md`

## Problem

The provisioner passes the entire host environment (`**os.environ`) to `ansible-playbook` (`provisioner.py:63-64`). This leaks sensitive environment variables (AWS credentials, API keys, database passwords, tokens) into the Ansible subprocess, which could:

- Expose secrets in Ansible logs if `-vvv` verbose mode is used
- Pass secrets into the VM if roles reference environment variables
- Create security audit concerns

## Requirements

### FR-1: Environment Variable Allowlist

Replace `**os.environ` with a curated allowlist of safe variables:

**Required variables:**
- `PATH` - command resolution
- `HOME` - home directory
- `USER` - current user
- `LANG`, `LC_ALL`, `LC_CTYPE` - locale settings
- `TERM` - terminal type
- `SSH_AUTH_SOCK` - SSH agent forwarding
- `TMPDIR`, `TEMP`, `TMP` - temp directory

**clauded-specific variables:**
- `ANSIBLE_ROLES_PATH` - set by provisioner
- `ANSIBLE_CONFIG` - set by provisioner

### FR-2: No Behavioral Change

The allowlist must include all variables required for `limactl` and `ansible-playbook` to function correctly. Test that provisioning still works after the change.

## Affected Files

- `src/clauded/provisioner.py:63-64`
- `tests/test_provisioner.py`
