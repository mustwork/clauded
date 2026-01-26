"""Main CLI entry point for clauded."""

from pathlib import Path

import click

from . import wizard
from .config import Config
from .lima import LimaVM
from .provisioner import Provisioner


@click.command()
@click.option(
    "--destroy", is_flag=True, help="Destroy the VM and optionally remove config"
)
@click.option("--reprovision", is_flag=True, help="Re-run provisioning on the VM")
@click.option("--stop", is_flag=True, help="Stop the VM without entering shell")
def main(destroy: bool, reprovision: bool, stop: bool) -> None:
    """clauded - Isolated, per-project Lima VMs.

    Run in any directory to create or connect to a project-specific VM.
    """
    config_path = Path.cwd() / ".clauded.yaml"
    project_path = Path.cwd().resolve()

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

    # No config? Run wizard
    if not config_path.exists():
        try:
            config = wizard.run(project_path)
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
        vm.create()
        provisioner = Provisioner(config, vm)
        provisioner.run()
    elif not vm.is_running():
        # VM exists but stopped? Start it
        vm.start()
    elif reprovision:
        # VM running and --reprovision? Re-run provisioning
        provisioner = Provisioner(config, vm)
        provisioner.run()

    # Enter shell
    click.echo(f"\nEntering VM '{vm.name}' at {config.mount_guest}...")
    vm.shell()


if __name__ == "__main__":
    main()
