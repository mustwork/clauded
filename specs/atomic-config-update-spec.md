# Atomic Config Update with Rollback - Requirements Specification

## Problem Statement

Currently, when running `clauded` in a project, a YAML config is created or updated with a new Lima container ID. If container creation or update fails, the config still references the new (non-existent) container, leaving the system in an inconsistent state. Users must manually clean up and recreate configs. On successful creation when replacing a container, users are not prompted about the old container, leading to orphaned VMs.

This feature solves the problem by:
1. Ensuring configs always reference a valid, working container (rollback on failure)
2. Prompting users to delete replaced containers (cleanup on success)
3. Handling crash recovery when the system is interrupted mid-operation

## Core Functionality

Provide transactional semantics for config updates tied to VM lifecycle operations. The config should only commit to a new VM name after that VM is successfully created and provisioned. If creation fails, the config should automatically roll back to reference the previous working VM.

## Functional Requirements

### FR-1: Config State Tracking
- Add `previous_vm_name: str | None` field to Config dataclass
- Field is optional/nullable for backwards compatibility
- Schema version remains "1" (backwards-compatible addition)
- Config.save() must persist this field
- Config.load() must read this field (defaulting to None if missing)

### FR-2: Atomic Update Context Manager
- Implement `atomic_update(new_vm_name: str)` context manager method on Config class
- Context manager should:
  - Store current `vm_name` as `previous_vm_name` before update
  - Update `vm_name` to new value
  - Save config with both names
  - Yield the old VM name to caller
  - On success (normal exit): prompt user to delete old container, then clear `previous_vm_name` and save
  - On failure (exception): restore `vm_name = previous_vm_name`, clear `previous_vm_name`, save config, and re-raise

**Acceptance Criteria**:
```python
# Success path
with config.atomic_update(new_vm_name) as old_name:
    vm.create()  # succeeds
    # On exit: prompt "Delete old container 'old_name'?"
    # If yes: destroy old VM
    # Clear previous_vm_name, save config

# Failure path
with config.atomic_update(new_vm_name) as old_name:
    vm.create()  # raises exception
    # On exit: vm_name rolled back to old_name
    # previous_vm_name cleared, config saved
    # exception re-raised
```

### FR-3: CLI Integration
- CLI layer should invoke `atomic_update()` context manager when:
  - Creating a VM from new config (lines cli.py:228-231)
  - Editing config and reprovisioning (lines cli.py:189-194)
- Context manager wraps both config save and VM operations
- No changes needed to Config.save() or Config.load() beyond field support

### FR-4: User Prompts for Cleanup
- Use `questionary.confirm()` for deletion prompt (consistent with wizard.py)
- Prompt text: `"Delete previous VM '{old_name}'?"` with default=False
- If user confirms: call `LimaVM(old_name).destroy()`
- If user declines or interrupts (KeyboardInterrupt): skip deletion, clear state, and proceed

### FR-5: Crash Recovery on Startup
- When Config.load() detects `previous_vm_name` is not None:
  - System was interrupted during an update operation
  - Prompt user: `"Incomplete VM update detected. Previous VM was '{previous_vm_name}'. Delete it?"`
  - Use `questionary.confirm()` with default=False
  - If yes: destroy the previous VM
  - Clear `previous_vm_name` and save config
  - Continue normal startup

## Critical Constraints

### C-1: Exception Safety
- Context manager MUST handle all exceptions (not just subprocess errors)
- Rollback must occur even if provisioning fails after VM creation succeeds
- Config must always be in a valid state after any exception

### C-2: Atomic Config Writes
- Config.save() writes atomically (current behavior via yaml.dump)
- No partial writes should occur during rollback

### C-3: Backwards Compatibility
- Existing .clauded.yaml files without `previous_vm_name` must load correctly
- Schema version remains "1"
- Old configs should behave identically (no crash recovery prompts if field is None)

### C-4: User Interruption Handling
- KeyboardInterrupt during prompts should be handled gracefully
- Should not leave system in inconsistent state
- Should follow existing SIGINT handler pattern (cli.py:21-28)

### C-5: VM Name Uniqueness
- VM names are deterministic (based on project path hash)
- Rollback must restore the exact previous name
- No risk of name collisions during update

## Integration Points

### IP-1: Config Class (config.py:136-176)
- Add `previous_vm_name: str | None = None` field to dataclass
- Implement `atomic_update()` context manager method
- Ensure load() and save() handle the new field

### IP-2: CLI Edit Flow (cli.py:166-203)
- Wrap config save + provision in `atomic_update()` context
- Handle user confirmation for old VM deletion
- Preserve existing error handling (KeyboardInterrupt → SystemExit(130))

### IP-3: CLI VM Creation Flow (cli.py:228-231)
- Wrap VM creation + provision in `atomic_update()` context
- Only applies when config already exists and VM is being recreated
- First-time creation (no previous VM) should pass None as old_name

### IP-4: LimaVM Destroy (lima.py:136-148)
- No changes needed to destroy() method
- Context manager calls this method with old VM name
- Existing error handling is sufficient

### IP-5: Config Load Startup (cli.py:139, 157, 172, 223)
- After Config.load(), check if `previous_vm_name` is not None
- If set, trigger crash recovery flow
- Must occur before any VM operations

## User Preferences

- **Prompt library**: Use questionary.confirm() (matches wizard patterns)
- **Invocation point**: CLI layer orchestrates context manager (keeps Config focused)
- **Crash recovery**: Auto-prompt for cleanup on startup (helpful but not automatic)
- **Schema version**: Keep version "1" (backwards-compatible field addition)

## Codebase Context

See `.claude/exploration/atomic-config-update-context.md` for exploration findings.

**Key patterns to follow**:
- Context managers with try/finally for cleanup (spinner.py:14-54)
- questionary.confirm() for yes/no prompts (wizard.py)
- click.confirm() for CLI confirmations (cli.py:145)
- SIGINT handling with KeyboardInterrupt (cli.py:21-28)
- Config validation and auto-correction patterns (config.py:227-235)

## Related Artifacts

- **Exploration Context**: `.claude/exploration/atomic-config-update-context.md`

## Out of Scope

- Concurrent access to configs (system is single-threaded)
- Migration of old configs with orphaned VMs (only handles future updates)
- Automatic detection of orphaned VMs not in config (manual cleanup required)
- Rollback of provisioning changes (only config and VM name are transactional)
- Support for non-deterministic VM names (names are always based on path hash)
- Multi-step undo/redo (only immediate rollback on failure)

---

**Note**: This is a requirements specification, not an architecture design.
Edge cases, error handling details, and implementation approach will be
determined by the integration-architect during Phase 2.
