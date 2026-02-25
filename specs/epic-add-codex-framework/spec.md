# Add OpenAI Codex as Default Framework

## Summary

Add [OpenAI Codex CLI](https://github.com/openai/codex) as a non-configurable default framework installed on both Ubuntu and Alpine VM images, following the same pattern as the existing `claude-code` framework.

## Background

Codex is a coding agent CLI from OpenAI that runs locally. Like Claude Code, it should be installed by default in all VMs since the primary use case of clauded is AI-assisted development.

## Requirements

### R1: Ansible Roles

Create distribution-specific Ansible roles following the existing playwright pattern (npm-based installation):

- `codex-ubuntu/tasks/main.yml` — Install Codex on Ubuntu via `npm install -g @openai/codex`
- `codex-alpine/tasks/main.yml` — Install Codex on Alpine via `npm install -g @openai/codex`

Installation approach: Use `npm install -g @openai/codex` on both distributions. This avoids glibc/musl binary compatibility issues on Alpine. The `codex` binary will be available on PATH via npm's global bin directory (not `~/.local/bin`).

The provisioner must ensure Node.js is available before the codex role runs. This follows the same pattern as playwright: if `"codex"` is in `config.frameworks` and `"node"` is not already in the role list, insert the `"node"` role after `"common"`.

### R2: Default Framework (Non-Configurable)

Codex is a non-configurable default framework, identical to how `claude-code` is handled:
- Always hardcoded into `config.frameworks` by the wizard (cannot be deselected)
- Not shown as a selectable option in the wizard UI
- Automatically provisioned on every VM
- If manually removed from `.clauded.yaml`, it gets re-added on next wizard run / config merge

### R3: Provisioner Integration

- Add `"codex"` to `_ROLES_WITH_VARIANTS` in `provisioner.py`
- Add codex role selection in `_get_base_roles()`: when `"codex"` is in `config.frameworks`, append `"codex"` to roles and ensure Node.js is present (same pattern as playwright)

### R4: Config/Wizard Integration

Update all locations where `"claude-code"` is hardcoded as a default framework to also include `"codex"`:
- `wizard.py`: `answers["frameworks"] = ["claude-code", "codex"] + [user_selections]`
- `detect/wizard_integration.py`: All three locations (static defaults, wizard post-processing, merge_detection_with_config)
- `detect/cli_integration.py`: `create_wizard_defaults()` function

**Backward compatibility**: Existing `.clauded.yaml` files without `"codex"` in frameworks continue to load without error. Codex will be added to the frameworks list during the next config merge / wizard re-run (same behavior as claude-code).

### R5: Documentation

- Update README.md frameworks table to include Codex
- Add CHANGELOG.md entry under `[Unreleased]` / `Added`

## Acceptance Criteria

- AC-1: `codex` command is available on PATH after provisioning on both Alpine and Ubuntu (installed via npm global)
- AC-2: `codex` is always included in `config.frameworks` for new configurations created via the wizard
- AC-3: Existing `.clauded.yaml` files without `codex` continue to load without error
- AC-4: All existing tests pass; new tests cover codex role inclusion, Node.js auto-dependency, and default framework behavior
- AC-5: New Ansible roles follow existing npm-based framework patterns (playwright-ubuntu, playwright-alpine)
