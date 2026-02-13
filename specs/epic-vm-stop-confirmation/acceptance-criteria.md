# Acceptance Criteria: VM Stop Confirmation

Generated: 2026-02-13T00:00:00Z
Source: spec.md

## Overview

These criteria verify that users receive an explicit confirmation prompt before VM shutdown when exiting the last active session with `keep_vm_running: false`, providing users with control over VM lifecycle and preventing unexpected shutdowns.

## Criteria

### AC-001: Prompt displayed for last session
- **Description**: When exiting the last active session with `keep_vm_running: false`, a confirmation prompt is displayed asking if the user wants to stop the VM
- **Verification**: Start VM with `clauded`, exit shell, observe prompt "This is the last active session. Stop VM 'clauded-<name>'? [Y/n]:" appears before VM stops
- **Type**: integration
- **Source**: FR-1 (Confirmation Prompt Display), FR-3 (Prompt Placement)

### AC-002: VM stops when user confirms
- **Description**: Selecting "Yes" (Y/y/Enter) at the confirmation prompt stops the VM as expected
- **Verification**: Start VM, exit shell, answer "Y" or press Enter at prompt, verify VM is stopped with `limactl list` showing VM status as "Stopped"
- **Type**: integration
- **Source**: FR-2 (User Response Handling - Yes case)

### AC-003: VM keeps running when user declines
- **Description**: Selecting "No" (N/n) at the confirmation prompt leaves the VM running and exits cleanly
- **Verification**: Start VM, exit shell, answer "N" at prompt, verify VM remains running with `limactl list` showing VM status as "Running"
- **Type**: integration
- **Source**: FR-2 (User Response Handling - No case)

### AC-004: No prompt when keep_vm_running is true
- **Description**: If `keep_vm_running: true` in config, no prompt is shown and VM stays running per configuration
- **Verification**: Set `vm.keep_running: true` in `.clauded.yaml`, start VM, exit shell, verify no prompt appears and VM remains running
- **Type**: integration
- **Source**: FR-3 (Prompt Placement - Only when keep_vm_running: false)

### AC-005: No prompt when other sessions active
- **Description**: If other SSH sessions are active in the VM, no prompt is shown and VM stays running (existing behavior preserved)
- **Verification**: Connect two terminals with `clauded` to same VM, exit one terminal, verify no prompt appears in either terminal and VM remains running, verify message shown about other active sessions
- **Type**: integration
- **Source**: FR-3 (Prompt Placement - Only when last session)

### AC-006: Non-interactive mode defaults to stop
- **Description**: In non-interactive contexts where stdin is not a TTY (e.g., piped input, CI/CD, scripts), the prompt does not block and VM stops silently without any output
- **Verification**: Run `echo 'exit' | clauded` or equivalent non-TTY invocation, verify VM stops without hanging, verify no output is produced (silent stop), verify process completes successfully
- **Type**: integration
- **Source**: FR-2 (User Response Handling - Non-interactive case), FR-4 (Non-Interactive Behavior)

### AC-007: Prompt message is clear
- **Description**: The confirmation prompt clearly communicates that this is the last active session and asks if the user wants to stop the VM, including the VM name for clarity
- **Verification**: Observe prompt text contains "last active session", "Stop VM", and the VM name (e.g., 'clauded-abcd1234'), verify format matches "This is the last active session. Stop VM 'clauded-<name>'? [Y/n]:"
- **Type**: manual
- **Source**: FR-1 (Confirmation Prompt Display)

## Verification Plan

### Automated Tests

#### Integration Tests
- AC-001: Prompt displayed for last session
- AC-002: VM stops when user confirms
- AC-003: VM keeps running when user declines
- AC-004: No prompt when keep_vm_running is true
- AC-005: No prompt when other sessions active
- AC-006: Non-interactive mode defaults to stop

#### Manual Verification
- AC-007: Prompt message clarity (read prompt text during integration testing)

## Coverage Matrix

| Spec Requirement | Acceptance Criteria |
|------------------|---------------------|
| FR-1: Confirmation Prompt Display | AC-001, AC-007 |
| FR-2: User Response Handling | AC-002, AC-003, AC-006 |
| FR-3: Prompt Placement | AC-001, AC-004, AC-005 |
| FR-4: Non-Interactive Behavior | AC-006 |
