# Acceptance Criteria: Add Codex Framework

Generated: 2026-02-25T12:00:00Z
Source: spec.md

## Criteria

### AC-001: Codex available on PATH after Ubuntu provisioning
- **Description**: After provisioning an Ubuntu VM, `codex` command must be available on PATH (installed via npm global)
- **Verification**: Ansible role completes without error; `which codex` returns a valid path
- **Type**: integration

### AC-002: Codex available on PATH after Alpine provisioning
- **Description**: After provisioning an Alpine VM, `codex` command must be available on PATH (installed via npm global)
- **Verification**: Ansible role completes without error; `which codex` returns a valid path
- **Type**: integration

### AC-003: Codex always included in new wizard configurations
- **Description**: When creating a new config via the wizard, `codex` is always present in `config.frameworks` without user selection
- **Verification**: Unit test: run wizard with any selection, verify "codex" in resulting frameworks list
- **Type**: unit

### AC-004: Codex always included in detection-based configurations
- **Description**: When creating config via project detection, `codex` is always present in frameworks
- **Verification**: Unit test: create_wizard_defaults() always includes "codex" in frameworks
- **Type**: unit

### AC-005: Backward compatibility with existing configs
- **Description**: Existing `.clauded.yaml` files without `codex` in frameworks load without error
- **Verification**: Unit test: load a config YAML without codex in frameworks list, verify no exception
- **Type**: unit

### AC-006: Provisioner includes codex role with Node.js dependency
- **Description**: When `codex` is in config.frameworks, provisioner includes codex role and auto-adds Node.js if not present
- **Verification**: Unit test: _get_base_roles() with codex in frameworks returns codex role; when node not configured, node is auto-added before codex
- **Type**: unit

### AC-007: All existing tests pass
- **Description**: No regressions introduced by the changes
- **Verification**: `make check` passes (lint + typecheck + test)
- **Type**: unit

### AC-008: Ansible roles follow existing patterns
- **Description**: New codex-ubuntu and codex-alpine roles follow the npm-based installation pattern (like playwright)
- **Verification**: Role directories exist with tasks/main.yml; tasks use `npm install -g @openai/codex`
- **Type**: unit

## Verification Plan

1. Run `make check` to verify no regressions and all new tests pass
2. Verify codex role directories exist at `src/clauded/roles/codex-ubuntu/` and `src/clauded/roles/codex-alpine/`
3. Verify provisioner includes codex in roles when framework is configured
4. Verify wizard always includes codex as default framework

## E2E Test Plan

### Scenario 1: New VM provisioning with codex
- Start Docker Compose services for Ubuntu/Alpine test containers
- Run provisioning with default config (codex included by default)
- Verify `codex` command is available on PATH via Playwright browser test or SSH command
- Services: lima VM or docker container with ansible provisioning

### Scenario 2: Reprovision existing VM adds codex
- Start with existing VM config without codex
- Trigger reprovision
- Verify codex is installed after reprovision
