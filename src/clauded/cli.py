"""Main CLI entry point for clauded."""

import logging
import signal
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import click

from . import wizard
from .config import Config
from .detect import detect
from .detect.cli_integration import display_detection_json
from .detect.wizard_integration import run_with_detection
from .lima import LimaVM, destroy_vm_by_name
from .provisioner import Provisioner


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
def main(
    destroy: bool,
    reprovision: bool,
    reboot: bool,
    stop: bool,
    edit: bool,
    detect_only: bool = False,
    no_detect: bool = False,
    debug: bool = False,
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

    config_path = Path.cwd() / ".clauded.yaml"
    project_path = Path.cwd().resolve()

    # Handle --detect (detection-only mode)
    if detect_only:
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

    # Handle --stop
    if stop:
        if not config_path.exists():
            click.echo("No .clauded.yaml found in current directory.")
            raise SystemExit(1)

        config = Config.load(config_path)
        vm = LimaVM(config)

        if vm.exists() and vm.is_running():
            vm.stop()
        else:
            click.echo(f"VM '{vm.name}' is not running.")
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
            new_config = wizard.run_edit(config, project_path)

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
        # BUG FIX: Ensure VM cleanup on shell exit
        # Root cause: vm.shell() returns on exit, but VM stays running
        # Bug report: bug-reports/vm-cleanup-on-exit-report.md
        # Date: 2026-02-02
        try:
            vm.shell()
        finally:
            if vm.is_running():
                # Ignore Ctrl+C during shutdown to ensure cleanup completes
                original_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
                try:
                    vm.stop()
                finally:
                    signal.signal(signal.SIGINT, original_handler)
        return

    # No config? Run wizard (with or without detection)
    if not config_path.exists():
        # Require interactive terminal for wizard prompts
        _require_interactive_terminal()

        try:
            if no_detect:
                # Skip detection, use default wizard
                config = wizard.run(project_path)
            else:
                # Run wizard with detection-based defaults
                config = run_with_detection(project_path, debug=debug)
            config.save(config_path)
            click.echo("\nCreated .clauded.yaml")
        except KeyboardInterrupt:
            click.echo("\nSetup cancelled.")
            raise SystemExit(130) from None
    else:
        config = Config.load(config_path)
        _handle_crash_recovery(config, config_path)

    vm = LimaVM(config)

    # VM doesn't exist? Create and provision
    if not vm.exists():
        # Use atomic_update for crash recovery during VM creation
        with config.atomic_update(config.vm_name, config_path) as old_vm_name:
            vm.create(debug=debug)
            provisioner = Provisioner(config, vm, debug=debug)
            provisioner.run()

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

        # Re-run provisioning if requested (independent of start)
        if reprovision:
            provisioner = Provisioner(config, vm, debug=debug)
            provisioner.run()

    # Reboot VM if requested (to apply group membership changes, etc.)
    if reboot:
        click.echo(f"\nRebooting VM '{vm.name}'...")
        vm.stop()
        vm.start(debug=debug)

    # Enter Claude Code
    click.echo(f"\nStarting Claude Code in VM '{vm.name}' at {config.mount_guest}...")
    # BUG FIX: Ensure VM cleanup on shell exit
    # Root cause: vm.shell() returns on exit, but VM stays running
    # Bug report: bug-reports/vm-cleanup-on-exit-report.md
    # Date: 2026-02-02
    try:
        vm.shell()
    finally:
        if vm.is_running():
            # Ignore Ctrl+C during shutdown to ensure cleanup completes
            original_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
            try:
                vm.stop()
            finally:
                signal.signal(signal.SIGINT, original_handler)


if __name__ == "__main__":
    main()
