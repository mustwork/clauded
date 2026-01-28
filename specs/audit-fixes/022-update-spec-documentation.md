# Update Spec to Document Undocumented Roles and Behaviors

**Audit Reference**: Documentation #29 | Severity: 3/10
**Source**: `.claude/audit-reports/spec-2026-01-28.md`

## Problem

The specification (`specs/spec.md`) does not reflect several implemented behaviors:

1. **Missing roles** (lines 210-228): The Ansible roles table omits three implemented roles: `uv`, `poetry`, and `maven`. These are auto-bundled with Python and Java respectively.

2. **Inventory format mismatch** (lines 253-260): Spec shows `[lima]` group but implementation uses `[vm]` group. Spec shows `[all:vars]` section for SSH config but implementation passes SSH config via CLI flag.

3. **Playbook hosts mismatch** (line 233): Spec shows `hosts: all` but implementation uses `hosts: vm`.

4. **Missing --limit flag** (line 264): Spec shows `--limit lima-{vm-name}` in ansible-playbook command but implementation does not use `--limit`.

5. **MCP detection undocumented**: The `detect/mcp.py` module provides MCP configuration scanning that is not mentioned in the spec.

## Requirements

### FR-1: Add Missing Roles to Spec

Add to the Ansible roles table (`specs/spec.md` lines 210-228):

| Role | Purpose | Key Tasks |
|------|---------|-----------|
| `uv` | Python package manager (uv) | pip install uv |
| `poetry` | Python dependency manager | pipx install poetry |
| `maven` | Java/Kotlin build tool | Download and install Maven |

Document that these roles are auto-included when their parent language is selected.

### FR-2: Align Spec Inventory/Playbook Format

Update spec to match implementation:
- Change `[lima]` to `[vm]` in inventory example
- Change `hosts: all` to `hosts: vm` in playbook example
- Remove `[all:vars]` section (SSH config passed via CLI)
- Remove `--limit` from ansible-playbook command

OR update implementation to match spec (see spec 004 for role selection fixes).

Choose one direction and make spec and implementation consistent.

### FR-3: Document MCP Detection

Add MCP detection to the spec's detect module description (lines 103-108):
- MCP configuration scanning from `.mcp.json`, `mcp.json`, `~/.claude.json`
- Runtime requirement extraction from server commands

## Affected Files

- `specs/spec.md` (lines 210-228, 230-265, 103-108)
