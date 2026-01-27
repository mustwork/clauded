"""Main CLI entry point for clauded."""

import logging
import subprocess
import sys
from pathlib import Path

import click

from . import wizard
from .config import Config
from .detect import detect
from .detect.cli_integration import display_detection_json
from .detect.wizard_integration import run_with_detection
from .lima import LimaVM
from .provisioner import Provisioner


def _reset_terminal() -> None:
    """Reset terminal to a sane state after subprocess calls.

    This ensures the terminal is in the correct mode for interactive
    questionary prompts after running limactl commands that may output
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


@click.command()
@click.option(
    "--destroy", is_flag=True, help="Destroy the VM and optionally remove config"
)
@click.option("--reprovision", is_flag=True, help="Re-run provisioning on the VM")
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
    stop: bool,
    edit: bool,
    detect_only: bool = False,
    no_detect: bool = False,
    debug: bool = False,
) -> None:
    """clauded - Isolated, per-project Lima VMs.

    Run in any directory to create or connect to a project-specific VM.
    """
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
        vm = LimaVM(config)

        if not vm.exists():
            click.echo(f"VM '{vm.name}' does not exist. Run 'clauded' to create it.")
            raise SystemExit(1)

        if not vm.is_running():
            vm.start(debug=debug)

        # Always reset terminal state before running wizard - limactl operations
        # may output escape sequences that interfere with questionary's prompts
        _reset_terminal()

        try:
            new_config = wizard.run_edit(config, project_path)
            new_config.save(config_path)
            click.echo("\nUpdated .clauded.yaml")
            provisioner = Provisioner(new_config, vm, debug=debug)
            provisioner.run()
        except KeyboardInterrupt:
            click.echo("\nEdit cancelled.")
            raise SystemExit(1) from None

        click.echo(
            f"\nStarting Claude Code in VM '{vm.name}' at {new_config.mount_guest}..."
        )
        vm.shell()
        return

    # No config? Run wizard (with or without detection)
    if not config_path.exists():
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
            raise SystemExit(1) from None
    else:
        config = Config.load(config_path)

    vm = LimaVM(config)

    # VM doesn't exist? Create and provision
    if not vm.exists():
        vm.create(debug=debug)
        provisioner = Provisioner(config, vm, debug=debug)
        provisioner.run()
    elif not vm.is_running():
        # VM exists but stopped? Start it
        vm.start(debug=debug)
    elif reprovision:
        # VM running and --reprovision? Re-run provisioning
        provisioner = Provisioner(config, vm, debug=debug)
        provisioner.run()

    # Enter Claude Code
    click.echo(f"\nStarting Claude Code in VM '{vm.name}' at {config.mount_guest}...")
    vm.shell()


if __name__ == "__main__":
    main()
