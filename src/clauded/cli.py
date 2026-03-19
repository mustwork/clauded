"""Main CLI entry point for clauded."""

import logging
import re
import signal
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import click

from . import __version__, wizard
from .config import Config
from .detect import detect
from .detect.cli_integration import display_detection_json
from .detect.wizard_integration import (
    apply_detection_to_config,
    run_edit_with_detection,
    run_with_detection,
)
from .downloads import get_downloads
from .lima import LimaVM, destroy_vm_by_name
from .provisioner import Provisioner, __commit__


def _sigint_handler(signum: int, frame: object) -> None:
    """Handle SIGINT (CTRL+C) gracefully.

    Prints a cleanup message and raises KeyboardInterrupt to allow
    context managers and finally blocks to execute properly.
    """
    click.echo("\nInterrupted. Cleaning up...", err=True)
    raise KeyboardInterrupt


def _require_interactive_terminal() -> None:
    """Check that stdin is an interactive terminal.

    The wizard requires an interactive terminal for menu prompts.
    This prevents hangs when running in CI/CD, piped input, or other
    non-interactive contexts.

    Raises:
        SystemExit: If stdin is not a TTY.
    """
    if not sys.stdin.isatty():
        click.echo(
            "Interactive terminal required. "
            "Use an existing .clauded.yaml or create one manually.",
            err=True,
        )
        raise SystemExit(1)


def _reset_terminal() -> None:
    """Reset terminal to a sane state after subprocess calls.

    This ensures the terminal is in the correct mode for interactive
    prompts after running limactl commands that may output
    escape sequences or modify terminal settings.
    """
    if sys.stdin.isatty():
        # Use stty sane for comprehensive terminal reset
        try:
            subprocess.run(["stty", "sane"], check=False, capture_output=True)
        except FileNotFoundError:
            pass

        # Also flush any pending input
        try:
            import termios

            fd = sys.stdin.fileno()
            termios.tcflush(fd, termios.TCIFLUSH)
        except (ImportError, OSError):
            pass


def _stop_vm_if_last_session(vm: LimaVM, config_path: Path) -> None:
    """Stop the VM only if this was the last active session.

    Checks for other active SSH sessions in the VM. If other sessions
    exist, skips stopping to avoid disrupting other users.

    Args:
        vm: The LimaVM instance to potentially stop
        config_path: Path to .clauded.yaml for reloading config
    """
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

    # Last session - prompt before stopping
    # Allow Ctrl+C to cancel (treated as "No")
    try:
        # Prompt with default=True (auto-confirms in non-interactive contexts)
        # click.confirm() returns True in non-TTY contexts without blocking
        should_stop = click.confirm(
            f"\nThis is the last active session. Stop VM '{vm.name}'?", default=True
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


def _prompt_vm_deletion(vm_name: str) -> bool:
    """Prompt user to delete a VM and return their decision.

    Args:
        vm_name: Name of VM to delete

    Returns:
        True if user confirmed deletion, False otherwise

    """
    should_delete = click.confirm(f"Delete previous VM '{vm_name}'?", default=False)

    if should_delete:
        destroy_vm_by_name(vm_name)
        return True

    return False


def _get_vm_tool_version(vm: LimaVM, command: str) -> str | None:
    """Run a version command in the VM and extract a semver string.

    Args:
        vm: LimaVM instance
        command: Command to run (e.g. "claude --version")

    Returns:
        Extracted version string (e.g. "2.1.62") or None on failure.
    """
    try:
        result = subprocess.run(
            ["limactl", "shell", vm.name, "--", "bash", "-lc", command],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None
        match = re.search(r"\d+\.\d+\.\d+", result.stdout)
        return match.group(0) if match else None
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        return None


def _get_npm_latest_version(vm: LimaVM, package: str) -> str | None:
    """Query npm registry from inside VM for latest package version.

    Args:
        vm: LimaVM instance
        package: npm package name (e.g. "@anthropic-ai/claude-code")

    Returns:
        Latest version string or None on failure.
    """
    try:
        result = subprocess.run(
            [
                "limactl",
                "shell",
                vm.name,
                "--",
                "bash",
                "-lc",
                f"npm view {package} version",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None
        match = re.search(r"\d+\.\d+\.\d+", result.stdout)
        return match.group(0) if match else None
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        return None


def _update_claude_code(vm: LimaVM, config: Config, version_str: str) -> bool:
    """Download Claude Code binary for the specific version.

    Downloads to a temporary file first, validates the download succeeded,
    then atomically moves into place. This prevents corrupting the existing
    binary on network failures or bad URLs.

    Args:
        vm: LimaVM instance
        config: Config with distro info
        version_str: Version to download (e.g. "2.3.0")

    Returns:
        True if update succeeded, False on failure.
    """
    downloads = get_downloads()
    gcs_bucket = downloads["claude_code"]["gcs_bucket"]
    platform = "linux-arm64-musl" if config.vm_distro == "alpine" else "linux-arm64"
    url = f"{gcs_bucket}/{version_str}/{platform}/claude"
    # Download to temp file, validate, then atomically move into place
    cmd = (
        "set -e && "
        "tmpfile=$(mktemp ~/.local/bin/.claude-update.XXXXXX) && "
        'trap "rm -f $tmpfile" EXIT && '
        f'curl -fsSL "{url}" -o "$tmpfile" && '
        '[ -s "$tmpfile" ] && '
        'chmod +x "$tmpfile" && '
        'mv -f "$tmpfile" ~/.local/bin/claude && '
        "trap - EXIT"
    )
    result = subprocess.run(
        ["limactl", "shell", vm.name, "--", "bash", "-lc", cmd],
        check=False,
    )
    return result.returncode == 0


def _update_codex(vm: LimaVM, version_str: str) -> bool:
    """Run npm install -g @openai/codex@version in VM.

    Args:
        vm: LimaVM instance
        version_str: Version to install (e.g. "1.2.0")

    Returns:
        True if update succeeded, False on failure.
    """
    result = subprocess.run(
        [
            "limactl",
            "shell",
            vm.name,
            "--",
            "bash",
            "-lc",
            f"sudo npm install -g @openai/codex@{version_str}",
        ],
        check=False,
    )
    return result.returncode == 0


def _handle_version_change(vm: LimaVM) -> bool:
    """Check if clauded has been updated since the VM was provisioned.

    Compares the commit recorded in the VM's /etc/clauded.json with the
    currently running clauded's commit. Prompts the user to reprovision
    if they differ.

    Args:
        vm: LimaVM instance to check

    Returns:
        True if user chose to reprovision, False otherwise.
    """
    metadata = vm.get_vm_metadata()
    if metadata is None:
        return False

    vm_commit = metadata.get("commit")
    vm_version = metadata.get("version", "unknown")
    if not vm_commit or vm_commit == "unknown" or __commit__ == "unknown":
        return False

    if vm_commit == __commit__:
        return False

    click.echo(
        f"\nclauded has been updated since this VM was provisioned.\n\n"
        f"  Provisioned with: v{vm_version} ({vm_commit})\n"
        f"  Installed:        v{__version__} ({__commit__})\n\n"
        f"Reprovisioning updates all VM packages and tools."
    )

    try:
        should_reprovision = click.confirm("Reprovision now?", default=False)
    except (click.Abort, EOFError, KeyboardInterrupt):
        should_reprovision = False

    return should_reprovision


def _get_latest_claude_code_version() -> str | None:
    """Resolve the latest Claude Code version from GCS on the host.

    Returns:
        Latest version string (e.g. "2.3.0") or None on failure.
    """
    downloads = get_downloads()
    gcs_bucket = downloads["claude_code"]["gcs_bucket"]
    try:
        result = subprocess.run(
            ["curl", "-fsSL", f"{gcs_bucket}/latest"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None
        match = re.search(r"\d+\.\d+\.\d+", result.stdout)
        return match.group(0) if match else None
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        return None


def _resolve_framework_versions(config: Config, vm: LimaVM) -> dict[str, str | None]:
    """Resolve desired versions for each framework.

    For each framework in config.frameworks:
    - If the user pinned a version in .clauded.yaml → use it
    - Otherwise resolve "latest" (GCS for claude-code, npm for codex)

    Args:
        config: Config with frameworks and version pins
        vm: LimaVM instance (needed for npm queries inside VM)

    Returns:
        Dict mapping framework name to resolved version string (or None on failure).
    """
    resolved: dict[str, str | None] = {}

    if "claude-code" in config.frameworks:
        if config.claude_code_version:
            resolved["claude-code"] = config.claude_code_version
        else:
            resolved["claude-code"] = _get_latest_claude_code_version()

    if "codex" in config.frameworks:
        if config.codex_version:
            resolved["codex"] = config.codex_version
        else:
            resolved["codex"] = _get_npm_latest_version(vm, "@openai/codex")

    return resolved


def _check_library_updates(vm: LimaVM, config: Config) -> None:
    """Check for framework version mismatches and prompt user to apply changes.

    Performs bidirectional version comparison (upgrades AND downgrades).
    Version sources are determined by _resolve_framework_versions():
    - User-pinned versions from .clauded.yaml take precedence
    - Otherwise resolves "latest" (GCS for Claude Code, npm for Codex)

    Args:
        vm: LimaVM instance
        config: Config with frameworks and version pins
    """
    desired = _resolve_framework_versions(config, vm)
    # (name, installed, target, kind)
    changes: list[tuple[str, str, str, str]] = []

    if "claude-code" in desired and desired["claude-code"]:
        installed = _get_vm_tool_version(vm, "claude --version")
        target = desired["claude-code"]
        if installed and target and installed != target:
            changes.append(("Claude Code", installed, target, "claude-code"))

    if "codex" in desired and desired["codex"]:
        installed = _get_vm_tool_version(vm, "codex --version")
        target = desired["codex"]
        if installed and target and installed != target:
            changes.append(("Codex", installed, target, "codex"))

    if not changes:
        return

    click.echo("\nFramework version changes available:\n")
    for name, installed, target, _ in changes:
        click.echo(f"  {name:<13s}{installed} → {target}")
    click.echo()

    try:
        should_update = click.confirm("Apply version changes?", default=False)
    except (click.Abort, EOFError, KeyboardInterrupt):
        should_update = False

    if not should_update:
        return

    for name, _, target, kind in changes:
        click.echo(f"Updating {name} to {target}...")
        if kind == "claude-code":
            ok = _update_claude_code(vm, config, target)
        elif kind == "codex":
            ok = _update_codex(vm, target)
        else:
            ok = False
        if ok:
            click.echo(f"  {name} updated successfully.")
        else:
            click.echo(f"  {name} update failed. Existing version preserved.", err=True)


def _handle_distro_change(config: Config, vm: LimaVM, config_path: Path) -> bool:
    """Detect and handle VM distro changes requiring recreation.

    CONTRACT:
      Inputs:
        - config: Config with vm_distro field
        - vm: LimaVM instance to check
        - config_path: Path to .clauded.yaml

      Outputs:
        - bool: True if VM was recreated, False if no action taken

      Invariants:
        - Only checks if VM is running
        - Only prompts if distro mismatch detected
        - VM is destroyed and recreated on user confirmation

      Properties:
        - User controlled: requires explicit y/N confirmation
        - Safe: defaults to no action (default=False)

      Algorithm:
        1. Check if VM is running (skip if not)
        2. Read actual distro from VM via SSH
        3. Compare with config.vm_distro
        4. If mismatch: prompt user with clear warning
        5. If user confirms: destroy and recreate VM
        6. If user cancels: exit without changes

    Args:
        config: Current configuration
        vm: VM instance to check
        config_path: Path to config file

    Returns:
        True if VM was recreated, False otherwise

    Raises:
        SystemExit: If user cancels the distro change
    """
    if not vm.is_running():
        return False

    vm_distro = vm.get_vm_distro()

    # No distro metadata yet (VM not provisioned or method returns non-string)
    if not isinstance(vm_distro, str):
        return False

    # Distros match - no action needed
    if vm_distro == config.vm_distro:
        return False

    # Distro mismatch detected - warn user
    click.echo(
        f"\n⚠️  Distribution mismatch detected!\n\n"
        f"  Current VM distro: {vm_distro}\n"
        f"  Config distro:     {config.vm_distro}\n\n"
        f"Changing distribution requires recreating the VM.\n"
        f"This will destroy all data in the VM.\n",
        err=True,
    )

    should_recreate = click.confirm(
        f"Destroy VM and recreate with {config.vm_distro}?",
        default=False,
    )

    if not should_recreate:
        click.echo("\nDistro change cancelled. Exiting without changes.")
        raise SystemExit(0)

    # User confirmed - destroy and recreate
    click.echo(f"\nDestroying VM '{vm.name}'...")
    vm.destroy()
    return True


def _handle_crash_recovery(config: Config, config_path: Path) -> None:
    """Handle incomplete VM update detected on startup.

    CONTRACT:
      Inputs:
        - config: Config object with previous_vm_name potentially set
        - config_path: Path to .clauded.yaml file

      Outputs:
        - None (side effect: may destroy VM, updates config file)

      Invariants:
        - previous_vm_name is always cleared after this function
        - config is saved after any cleanup

      Properties:
        - Idempotent: safe to call multiple times
        - User controlled: respects user decision (prompt with default=False)
        - Exception safe: KeyboardInterrupt handled gracefully

      Algorithm:
        1. If previous_vm_name is None, return immediately
        2. Check if current VM exists
        3. If current VM doesn't exist: rollback vm_name to previous_vm_name
        4. If current VM exists: prompt user to delete previous VM
        5. Clear previous_vm_name and save config
    """
    if config.previous_vm_name is None:
        return

    # Check if current VM exists (the one we tried to create/update to)
    current_vm_exists = subprocess.run(
        ["limactl", "list", "-q"],
        capture_output=True,
        text=True,
    ).returncode == 0 and config.vm_name in subprocess.run(
        ["limactl", "list", "-q"],
        capture_output=True,
        text=True,
    ).stdout.strip().split("\n")

    if not current_vm_exists:
        # Rollback: new VM was never created, restore to previous
        click.echo(
            f"\n⚠️  Incomplete VM update detected. "
            f"Current VM '{config.vm_name}' does not exist. "
            f"Rolling back to '{config.previous_vm_name}'."
        )
        config.vm_name = config.previous_vm_name
        config.previous_vm_name = None
        config.save(config_path)
        return

    # Current VM exists, prompt to delete previous VM
    click.echo(
        f"\n⚠️  Incomplete VM update detected. "
        f"Previous VM was '{config.previous_vm_name}'."
    )

    try:
        _prompt_vm_deletion(config.previous_vm_name)
    except KeyboardInterrupt:
        click.echo("\nSkipping cleanup.")

    # Always clear previous_vm_name after handling
    config.previous_vm_name = None
    config.save(config_path)


@click.command()
@click.version_option(
    version=version("clauded"),
    prog_name="clauded",
)
@click.option(
    "--destroy", is_flag=True, help="Destroy the VM and optionally remove config"
)
@click.option("--reprovision", is_flag=True, help="Re-run provisioning on the VM")
@click.option("--reboot", is_flag=True, help="Reboot VM after provisioning")
@click.option("--stop", is_flag=True, help="Stop the VM without entering shell")
@click.option(
    "--force-stop",
    is_flag=True,
    help="Force stop the VM even if other sessions are active",
)
@click.option("--edit", is_flag=True, help="Edit VM configuration and reprovision")
@click.option(
    "--detect",
    "detect_only",
    is_flag=True,
    help="Run detection only and output results without starting wizard",
)
@click.option(
    "--no-detect",
    is_flag=True,
    help="Skip auto-detection and use default wizard values",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable verbose output for detection, VM creation, and provisioning",
)
@click.option(
    "--distro",
    type=str,
    default=None,
    help="Linux distribution to use (alpine or ubuntu)",
)
def main(
    destroy: bool,
    reprovision: bool,
    reboot: bool,
    stop: bool,
    force_stop: bool,
    edit: bool,
    detect_only: bool = False,
    no_detect: bool = False,
    debug: bool = False,
    distro: str | None = None,
) -> None:
    """clauded - Isolated, per-project Lima VMs.

    Run in any directory to create or connect to a project-specific VM.
    """
    # Register SIGINT handler for graceful cleanup
    signal.signal(signal.SIGINT, _sigint_handler)

    # Configure debug logging for detection
    if debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format="[DEBUG] %(name)s: %(message)s",
        )

    # Validate --distro flag if provided
    if distro is not None:
        from .distro import SUPPORTED_DISTROS

        if distro not in SUPPORTED_DISTROS:
            click.echo(
                f"Error: Unsupported distro '{distro}'. "
                f"Supported distros: {', '.join(SUPPORTED_DISTROS)}",
                err=True,
            )
            raise SystemExit(1)

    config_path = Path.cwd() / ".clauded.yaml"
    project_path = Path.cwd().resolve()

    # Check for --distro conflicts with existing config
    if distro is not None and config_path.exists():
        config = Config.load(config_path)
        if config.vm_distro != distro:
            click.echo(
                f"Error: --distro {distro} conflicts with existing config "
                f"(configured distro: {config.vm_distro}).\n"
                f"To change distro, either:\n"
                f"  1. Delete the VM and config with: clauded --destroy\n"
                f"  2. Remove --distro flag to use existing config",
                err=True,
            )
            raise SystemExit(1)

    # Handle --detect alone (detection-only mode, outputs JSON)
    # Note: --detect with --reprovision is handled separately below
    if detect_only and not reprovision:
        detection_result = detect(project_path, debug=debug)
        display_detection_json(detection_result)
        return

    # Handle --destroy
    if destroy:
        if not config_path.exists():
            click.echo("No .clauded.yaml found in current directory.")
            raise SystemExit(1)

        config = Config.load(config_path)
        vm = LimaVM(config)

        if vm.exists():
            vm.destroy()

        if click.confirm("Remove .clauded.yaml?", default=False):
            config_path.unlink()
            click.echo("Removed .clauded.yaml")

        return

    # Handle --stop and --force-stop
    if stop or force_stop:
        if not config_path.exists():
            click.echo("No .clauded.yaml found in current directory.")
            raise SystemExit(1)

        config = Config.load(config_path)
        vm = LimaVM(config)

        if not vm.exists() or not vm.is_running():
            click.echo(f"VM '{vm.name}' is not running.")
            return

        # Check for other active sessions unless --force-stop
        if not force_stop:
            active_sessions = vm.count_active_sessions()
            if active_sessions > 0:
                click.echo(
                    f"VM '{vm.name}' has {active_sessions} active session(s). "
                    "Use --force-stop to stop anyway."
                )
                return

        vm.stop()
        return

    # Handle --edit
    if edit:
        if not config_path.exists():
            click.echo("No .clauded.yaml found. Run 'clauded' to create one.")
            raise SystemExit(1)

        config = Config.load(config_path)
        _handle_crash_recovery(config, config_path)
        vm = LimaVM(config)

        if not vm.exists():
            click.echo(f"VM '{vm.name}' does not exist. Run 'clauded' to create it.")
            raise SystemExit(1)

        if not vm.is_running():
            vm.start(debug=debug)

        # Always reset terminal state before running wizard - limactl operations
        # may output escape sequences that interfere with menu prompts
        _reset_terminal()

        # Require interactive terminal for wizard prompts
        _require_interactive_terminal()

        try:
            new_config = run_edit_with_detection(config, project_path, debug=debug)

            # Use atomic_update for transactional config save + provisioning
            with new_config.atomic_update(
                new_config.vm_name, config_path
            ) as old_vm_name:
                click.echo("\nUpdated .clauded.yaml")
                # Re-create LimaVM with new config (name might have changed)
                vm = LimaVM(new_config)
                provisioner = Provisioner(new_config, vm, debug=debug)
                provisioner.run()

                # On success: prompt to delete old VM if name changed
                if old_vm_name and old_vm_name != new_config.vm_name:
                    _require_interactive_terminal()
                    _prompt_vm_deletion(old_vm_name)

        except KeyboardInterrupt:
            click.echo("\nEdit cancelled.")
            raise SystemExit(130) from None

        click.echo(
            f"\nStarting Claude Code in VM '{vm.name}' at {new_config.mount_guest}..."
        )
        try:
            # Reconnect to pick up group membership changes from provisioning
            # BUT: skip reconnect if other sessions are active to avoid disrupting them
            # (--reconnect kills the SSH ControlMaster which other sessions share)
            other_sessions = vm.count_active_sessions()
            if other_sessions > 0:
                click.echo(
                    f"Note: {other_sessions} other session(s) active. "
                    "Skipping SSH reconnect to avoid disruption. "
                    "New group memberships (e.g., docker) may require 'newgrp docker' "
                    "or a new terminal."
                )
            vm.shell(reconnect=(other_sessions == 0))
        finally:
            _stop_vm_if_last_session(vm, config_path)
        return

    # No config? Run wizard (with or without detection)
    if not config_path.exists():
        # Require interactive terminal for wizard prompts
        _require_interactive_terminal()

        try:
            if no_detect:
                # Skip detection, use default wizard
                config = wizard.run(project_path, distro_override=distro)
            else:
                # Run wizard with detection-based defaults
                config = run_with_detection(
                    project_path, debug=debug, distro_override=distro
                )
            config.save(config_path)
            click.echo("\nCreated .clauded.yaml")
        except KeyboardInterrupt:
            click.echo("\nSetup cancelled.")
            raise SystemExit(130) from None
    else:
        config = Config.load(config_path)
        _handle_crash_recovery(config, config_path)

    vm = LimaVM(config)
    provisioned = False  # Track if provisioning ran (need SSH reconnect for groups)

    # VM doesn't exist? Create and provision
    if not vm.exists():
        # Use atomic_update for crash recovery during VM creation
        with config.atomic_update(config.vm_name, config_path) as old_vm_name:
            vm.create(debug=debug)
            provisioner = Provisioner(config, vm, debug=debug)
            provisioner.run()
            provisioned = True

            # Prompt to delete old VM if name changed (unlikely in this flow)
            if old_vm_name and old_vm_name != config.vm_name:
                try:
                    _prompt_vm_deletion(old_vm_name)
                except KeyboardInterrupt:
                    click.echo("\nSkipping VM cleanup.")

    else:
        # VM exists but stopped? Start it
        if not vm.is_running():
            vm.start(debug=debug)

        # Check for distro changes (requires VM recreation)
        vm_recreated = _handle_distro_change(config, vm, config_path)
        if vm_recreated:
            # VM was destroyed and needs recreation
            # Treat like first-time creation
            with config.atomic_update(config.vm_name, config_path) as old_vm_name:
                vm.create(debug=debug)
                provisioner = Provisioner(config, vm, debug=debug)
                provisioner.run()
                provisioned = True

                if old_vm_name and old_vm_name != config.vm_name:
                    try:
                        _prompt_vm_deletion(old_vm_name)
                    except KeyboardInterrupt:
                        click.echo("\nSkipping VM cleanup.")

        # Check for clauded version change and library updates
        if not vm_recreated and not reprovision:
            if _handle_version_change(vm):
                provisioner = Provisioner(config, vm, debug=debug)
                provisioner.run()
                provisioned = True
            else:
                _check_library_updates(vm, config)

        # Re-run provisioning if requested (independent of start)
        if reprovision and not vm_recreated:
            # If --detect flag also provided, run detection and merge with config
            if detect_only:
                updated_config, changes_made = apply_detection_to_config(
                    config, project_path, debug=debug
                )
                if changes_made:
                    click.echo("\nDetection found new requirements:")
                    # Show what changed
                    for runtime in (
                        "python",
                        "node",
                        "java",
                        "kotlin",
                        "rust",
                        "go",
                        "dart",
                        "c",
                    ):
                        old_val = getattr(config, runtime, None)
                        new_val = getattr(updated_config, runtime, None)
                        if old_val != new_val and new_val is not None:
                            click.echo(f"  + {runtime}: {new_val}")
                    for tool in updated_config.tools:
                        if tool not in (config.tools or []):
                            click.echo(f"  + tool: {tool}")
                    for db in updated_config.databases:
                        if db not in (config.databases or []):
                            click.echo(f"  + database: {db}")

                    # Save updated config
                    updated_config.save(config_path)
                    click.echo("\nUpdated .clauded.yaml")
                    config = updated_config
                else:
                    click.echo("\nNo new requirements detected.")

            provisioner = Provisioner(config, vm, debug=debug)
            provisioner.run()
            provisioned = True

    # Reboot VM if requested (to apply group membership changes, etc.)
    if reboot:
        # Check for other active sessions before rebooting
        other_sessions = vm.count_active_sessions()
        if other_sessions > 0:
            click.echo(
                f"Cannot reboot: {other_sessions} other session(s) active. "
                "Use --force-stop first or close other sessions."
            )
        else:
            click.echo(f"\nRebooting VM '{vm.name}'...")
            vm.stop()
            vm.start(debug=debug)

    # Enter Claude Code
    click.echo(f"\nStarting Claude Code in VM '{vm.name}' at {config.mount_guest}...")
    try:
        # Reconnect if provisioning ran (picks up group membership changes)
        # Reboot already creates a fresh session, so no reconnect needed
        # BUT: skip reconnect if other sessions are active to avoid disrupting them
        # (--reconnect kills the SSH ControlMaster which other sessions share)
        needs_reconnect = provisioned and not reboot
        if needs_reconnect:
            other_sessions = vm.count_active_sessions()
            if other_sessions > 0:
                click.echo(
                    f"Note: {other_sessions} other session(s) active. "
                    "Skipping SSH reconnect to avoid disruption. "
                    "New group memberships (e.g., docker) may require 'newgrp docker' "
                    "or a new terminal."
                )
                needs_reconnect = False
        vm.shell(reconnect=needs_reconnect)
    finally:
        _stop_vm_if_last_session(vm, config_path)


if __name__ == "__main__":
    main()
