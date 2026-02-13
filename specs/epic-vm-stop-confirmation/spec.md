# VM Stop Confirmation Prompt

## Overview

Add a confirmation prompt when closing the last active session that would trigger automatic VM shutdown. This gives users explicit control over VM lifecycle and prevents unexpected shutdowns.

## Problem Statement

Currently, when a user exits the last active `clauded` session and `keep_vm_running: false`, the VM stops silently without user confirmation. This can be surprising, especially if:

- The user has background processes running in the VM
- The user intended to reconnect quickly and doesn't want to wait for boot
- The user is unsure if other sessions are active

## Solution

Modify `_stop_vm_if_last_session()` in `cli.py` to prompt the user with `click.confirm()` before stopping the VM. The prompt should:

1. Clearly state this is the last active session
2. Explain the VM will be stopped
3. Allow the user to decline, leaving the VM running
4. Default to stopping in non-interactive contexts (current behavior)

## Functional Requirements

### FR-1: Confirmation Prompt Display

When all conditions for automatic shutdown are met (last session + `keep_vm_running: false`), display a confirmation prompt:

```
This is the last active session. Stop VM 'clauded-abcd1234'? [Y/n]:
```

(Note: `[Y/n]` suffix is added automatically by `click.confirm()`, VM name included for clarity)

### FR-2: User Response Handling

- **Yes (Y/y/Enter)**: Stop the VM (default)
- **No (N/n)**: Leave the VM running and exit without stopping
- **Ctrl+C during prompt**: Treat as "No" (leave VM running)
- **EOF (Ctrl+D) or closed stdin**: Default to stopping the VM (safe fallback)
- **Non-interactive context** (stdin is not a TTY): Default to Yes (stop the VM), silently without echo messages

### FR-3: Prompt Placement

The prompt should appear:
- **After** the user exits the VM shell
- **Before** the VM stop operation begins
- **Only** when this is the last active session and `keep_vm_running: false`

### FR-4: Non-Interactive Behavior

When `stdin` is not a TTY (e.g., piped input, CI/CD, scripts), the prompt should not block. Default behavior: stop the VM **silently with no output** (preserve current behavior exactly).

Use `click.confirm()` with `default=True` — this automatically handles TTY detection. Suppress all echo messages in non-interactive mode.

## Acceptance Criteria

1. **AC-1: Prompt displayed for last session**
   - **Description**: When exiting the last active session with `keep_vm_running: false`, a confirmation prompt is displayed
   - **Verification**: Start VM, exit shell, observe prompt before VM stops
   - **Type**: manual / integration

2. **AC-2: VM stops when user confirms**
   - **Description**: Selecting "Yes" or pressing Enter stops the VM
   - **Verification**: Answer "Y" to prompt, verify VM is stopped with `limactl list`
   - **Type**: integration

3. **AC-3: VM keeps running when user declines**
   - **Description**: Selecting "No" leaves the VM running
   - **Verification**: Answer "N" to prompt, verify VM is still running with `limactl list`
   - **Type**: integration

4. **AC-4: No prompt when keep_vm_running is true**
   - **Description**: If `keep_vm_running: true`, no prompt is shown (VM stays running per config)
   - **Verification**: Set `keep_vm_running: true`, exit shell, verify no prompt appears
   - **Type**: integration

5. **AC-5: No prompt when other sessions active**
   - **Description**: If other sessions are active, no prompt is shown (VM stays running)
   - **Verification**: Connect two terminals, exit one, verify no prompt and VM remains running
   - **Type**: integration

6. **AC-6: Non-interactive mode defaults to stop**
   - **Description**: In non-interactive contexts (no TTY), VM stops without blocking on prompt
   - **Verification**: Run `echo 'exit' | clauded` or similar, verify VM stops without hanging
   - **Type**: integration

7. **AC-7: Prompt message is clear**
   - **Description**: The prompt clearly states this is the last session and asks if user wants to stop
   - **Verification**: Read prompt text, confirm it includes "last active session" and "stop VM"
   - **Type**: manual

## Implementation Details

### Location

File: `src/clauded/cli.py`
Function: `_stop_vm_if_last_session(vm: LimaVM, config_path: Path) -> None`

### Current Code (lines 78-110)

```python
def _stop_vm_if_last_session(vm: LimaVM, config_path: Path) -> None:
    """Stop the VM only if this was the last active session."""
    if not vm.is_running():
        return

    # Reload config to respect changes made while VM was running
    current_config = Config.load(config_path)
    if current_config.keep_vm_running:
        return

    # Check if other sessions are still active
    active_sessions = vm.count_active_sessions()
    if active_sessions > 0:
        click.echo(
            f"\nVM '{vm.name}' has {active_sessions} other active session(s), "
            "leaving it running."
        )
        return

    # Last session - stop the VM silently
    # Ignore Ctrl+C during shutdown to ensure cleanup completes
    original_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        vm.stop()  # No echo messages - silent stop
    finally:
        signal.signal(signal.SIGINT, original_handler)
```

### Proposed Changes

Replace the "Last session - stop the VM" section with:

```python
    # Last session - prompt before stopping
    # Allow Ctrl+C to cancel (treated as "No")
    try:
        # Prompt with default=True (auto-confirms in non-interactive contexts)
        # click.confirm() returns True in non-TTY contexts without blocking
        should_stop = click.confirm(
            f"\nThis is the last active session. Stop VM '{vm.name}'?",
            default=True
        )
    except (click.Abort, EOFError, KeyboardInterrupt):
        # Ctrl+C, Ctrl+D, or EOF: treat as "No" (leave VM running)
        should_stop = False

    # Only echo in interactive mode (when stdin is a TTY)
    is_interactive = sys.stdin.isatty()

    if should_stop:
        if is_interactive:
            click.echo(f"Stopping VM '{vm.name}'...")
        # Ignore Ctrl+C during actual stop to ensure cleanup completes
        original_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            vm.stop()
            if is_interactive:
                click.echo(f"VM '{vm.name}' stopped.")
        finally:
            signal.signal(signal.SIGINT, original_handler)
    else:
        if is_interactive:
            click.echo(f"VM '{vm.name}' will continue running.")
```

### Key Implementation Notes

1. **click.confirm()** with `default=True`:
   - Returns `True` in non-interactive contexts (no blocking)
   - Allows user to press Enter for default (stop)
   - Prompts with `[Y/n]` format (capital Y indicates default)

2. **Error handling**:
   - Catch `click.Abort` (Ctrl+C), `EOFError` (Ctrl+D), and `KeyboardInterrupt`
   - Treat all as "No" (leave VM running) for safe fallback
   - User can manually stop later with `clauded --stop`

3. **SIGINT handling**:
   - Allow Ctrl+C during prompt (treat as "No")
   - Ignore SIGINT only during actual `vm.stop()` call
   - Ensures cleanup completes once stop begins

4. **Interactive vs. non-interactive**:
   - Check `sys.stdin.isatty()` to detect interactive mode
   - Echo messages only in interactive mode (preserve silent behavior for scripts)
   - Non-interactive mode auto-confirms with no output

5. **Prompt timing**:
   - After session counting (`active_sessions == 0` confirmed)
   - Before VM stop operation
   - No prompt if `keep_vm_running: true` or other sessions active

6. **Message clarity**:
   - "This is the last active session" (explicit)
   - "Stop VM '{vm.name}'?" (clear action, includes VM name)
   - Always include VM name for clarity in multi-VM setups

## Testing Strategy

### Unit Tests

**Not applicable** — `click.confirm()` requires TTY interaction, difficult to unit test. Use integration tests instead.

### Integration Tests

1. **Interactive prompt - confirm stop**:
   - Start VM with `clauded`
   - Exit shell
   - When prompted, answer "Y"
   - Verify VM is stopped with `limactl list`

2. **Interactive prompt - decline stop**:
   - Start VM with `clauded`
   - Exit shell
   - When prompted, answer "N"
   - Verify VM is still running with `limactl list`

3. **Non-interactive mode**:
   - Run `echo 'exit' | clauded` (or similar non-TTY invocation)
   - Verify VM stops without blocking (default behavior)

4. **No prompt when keep_vm_running is true**:
   - Set `vm.keep_running: true` in `.clauded.yaml`
   - Exit shell
   - Verify no prompt appears and VM stays running

5. **No prompt with multiple sessions**:
   - Connect two terminals to same VM
   - Exit one terminal
   - Verify no prompt and VM remains running

## Non-Goals

- **Not supported**: Configuration option to disable the prompt (users who want silent shutdown can use `keep_vm_running: true` and manually stop with `clauded --stop`)
- **Not supported**: Custom prompt messages (use default message for consistency)
- **Not supported**: Timeout on prompt (prompt waits indefinitely for user input in interactive mode)

## Migration Notes

- **Existing behavior**: Users who expect silent shutdown will now see a prompt **in interactive mode only**
- **Non-interactive mode**: Completely silent (current behavior preserved)
- **Interactive mode change**: Brief pause for prompt before VM stops, even if pressing Enter (default)
- **Workaround**: Press Enter to confirm (default action), or Ctrl+C to cancel, or set `keep_vm_running: true` + use `clauded --stop` for explicit control
- **Breaking change**: No — default action (Enter/non-interactive) preserves current stop behavior, only interaction timing changes slightly

## Dependencies

- `click` library (already used for CLI)
- No new dependencies

## Future Enhancements

- Add `--no-confirm` flag to `clauded` to skip prompt (for scripting)
- Remember user preference (e.g., "don't ask again for this VM")
- Show estimated boot time in prompt ("Next boot will take ~10 seconds")
