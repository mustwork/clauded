"""Lima VM lifecycle management."""

import getpass
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import click
import yaml

from .config import Config


def destroy_vm_by_name(vm_name: str) -> None:
    """Delete a VM by name without requiring a Config object.

    CONTRACT:
      Inputs:
        - vm_name: string, non-empty VM name to destroy

      Outputs:
        - None (side effect: VM deleted from Lima)

      Invariants:
        - If VM doesn't exist, operation succeeds silently
        - If VM exists, it is forcefully deleted

      Properties:
        - Idempotent: calling multiple times with same name has same effect
        - Exception safety: SystemExit on lima command failure

    Args:
        vm_name: Name of the VM to destroy

    Raises:
        SystemExit: If Lima is not installed or deletion fails
    """
    print(f"\nDestroying VM '{vm_name}'...")
    try:
        subprocess.run(["limactl", "delete", "-f", vm_name], check=True)
    except FileNotFoundError:
        click.echo("Lima is not installed. Install with: brew install lima", err=True)
        raise SystemExit(1) from None
    except subprocess.CalledProcessError:
        click.echo(f"Failed to destroy VM '{vm_name}'.", err=True)
        raise SystemExit(1) from None


class LimaVM:
    """Manages a Lima VM instance."""

    def __init__(self, config: Config):
        self.config = config
        self.name = config.vm_name

    def exists(self) -> bool:
        """Check if the VM exists."""
        result = subprocess.run(
            ["limactl", "list", "-q"],
            capture_output=True,
            text=True,
        )
        return self.name in result.stdout.strip().split("\n")

    def is_running(self) -> bool:
        """Check if the VM is running."""
        result = subprocess.run(
            ["limactl", "list", "--format", "{{.Status}}", self.name],
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() == "Running"

    def create(self, *, debug: bool = False) -> None:
        """Create and start a new VM."""
        lima_config = self._generate_lima_config()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "lima.yaml"
            with open(config_path, "w") as f:
                yaml.dump(lima_config, f, default_flow_style=False)

            try:
                print(f"\nCreating VM '{self.name}'...")
                cmd = ["limactl"]
                if debug:
                    cmd.extend(["--debug", "--log-level", "debug"])
                # --tty=false prevents TUI prompt when stdin is devnull
                # --timeout allows more time for package installation
                cmd.extend(
                    [
                        "start",
                        "--tty=false",
                        "--timeout",
                        "20m",
                        "--name",
                        self.name,
                        str(config_path),
                    ]
                )
                subprocess.run(
                    cmd,
                    check=True,
                    stdin=subprocess.DEVNULL,
                )
            except FileNotFoundError:
                click.echo(
                    "Lima is not installed. Install with: brew install lima", err=True
                )
                raise SystemExit(1) from None
            except subprocess.CalledProcessError as e:
                click.echo(
                    f"VM creation failed (exit code {e.returncode}). "
                    f"Check Lima logs: ~/.lima/{self.name}/ha.stderr.log",
                    err=True,
                )
                raise SystemExit(1) from None

    def start(self, *, debug: bool = False) -> None:
        """Start an existing VM."""
        print(f"\nStarting VM '{self.name}'...")
        cmd = ["limactl"]
        if debug:
            cmd.extend(["--debug", "--log-level", "debug"])
        # --tty=false prevents TUI prompt when stdin is devnull
        cmd.extend(["start", "--tty=false", self.name])
        try:
            subprocess.run(
                cmd,
                check=True,
                stdin=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            click.echo(
                "Lima is not installed. Install with: brew install lima", err=True
            )
            raise SystemExit(1) from None
        except subprocess.CalledProcessError:
            click.echo(
                f"Failed to start VM '{self.name}'. "
                "Is it in a valid state? Try: clauded --destroy",
                err=True,
            )
            raise SystemExit(1) from None

    def stop(self) -> None:
        """Stop the VM."""
        print(f"\nStopping VM '{self.name}'...")
        try:
            subprocess.run(["limactl", "stop", self.name], check=True)
        except FileNotFoundError:
            click.echo(
                "Lima is not installed. Install with: brew install lima", err=True
            )
            raise SystemExit(1) from None
        except subprocess.CalledProcessError:
            click.echo(
                f"Failed to stop VM '{self.name}'. VM may not be running.", err=True
            )
            raise SystemExit(1) from None

    def count_active_sessions(self) -> int:
        """Count active SSH sessions in the VM.

        Counts pseudo-terminal (pts) devices which correspond to SSH sessions.
        The 'who' command doesn't work reliably on Alpine Linux because SSH
        sessions don't always create utmp entries.

        Note: Non-interactive limactl shell commands (with capture_output) don't
        allocate a pts, so this count reflects only interactive sessions.

        Returns:
            Number of active interactive sessions, or 0 if unable to determine.
        """
        try:
            # Count pts devices - each interactive SSH session allocates one
            # Using ls /dev/pts and counting numeric entries (0, 1, 2, ...)
            # ptmx is the master device and should be excluded
            result = subprocess.run(
                ["limactl", "shell", self.name, "--", "ls", "/dev/pts"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return 0
            # Count numeric entries (0, 1, 2, ...) - these are active pts devices
            entries = result.stdout.strip().split()
            pts_count = sum(1 for e in entries if e.isdigit())
            return pts_count
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            # On any error, assume no other sessions (fail-safe to allow stopping)
            return 0

    def destroy(self) -> None:
        """Delete the VM."""
        destroy_vm_by_name(self.name)

    def shell(self, *, reconnect: bool = False) -> None:
        """Open the Claude Code shell in the VM.

        Args:
            reconnect: If True, force a fresh SSH session. Required after
                provisioning to pick up group membership changes (e.g., docker).
                Lima reuses SSH master control sockets by default, which means
                group changes from Ansible don't take effect without reconnecting.
        """
        # Display welcome message with VM metadata
        self._print_welcome()

        claude_cmd = "claude"
        if self.config.claude_dangerously_skip_permissions:
            claude_cmd += " --dangerously-skip-permissions"

        # Set USE_BUILTIN_RIPGREP=0 explicitly for Alpine/musl compatibility.
        # The native binary's bundled ripgrep doesn't work on musl.
        full_cmd = f"USE_BUILTIN_RIPGREP=0 {claude_cmd}"

        cmd = [
            "limactl",
            "shell",
            "--workdir",
            self.config.mount_guest,
        ]
        # Force fresh SSH session to pick up group membership changes
        if reconnect:
            cmd.append("--reconnect")
        cmd.extend(
            [
                self.name,
                "bash",
                "-lic",
                full_cmd,
            ]
        )
        subprocess.run(cmd)

    def _print_welcome(self) -> None:
        """Print welcome message with VM metadata."""
        try:
            result = subprocess.run(
                ["limactl", "shell", self.name, "cat", "/etc/clauded.json"],
                capture_output=True,
                text=True,
                check=True,
            )
            metadata = json.loads(result.stdout)
            print()
            print(
                f"  {metadata['project_name']} | "
                f"clauded v{metadata['version']} ({metadata['commit']})"
            )
            print(f"  Provisioned: {metadata['provisioned']}")
            print()
        except Exception:
            # Metadata not available (VM not provisioned, old version, or test env)
            pass

    def get_ssh_config_path(self) -> Path:
        """Get the path to Lima's SSH config for this VM."""
        return Path.home() / ".lima" / self.name / "ssh.config"

    def get_vm_distro(self) -> str | None:
        """Read the actual distro running in the VM via SSH.

        CONTRACT:
          Inputs:
            - None (reads from /etc/clauded.json in VM)

          Outputs:
            - distro: string distro identifier ("alpine", "ubuntu")
              or None if unavailable

          Invariants:
            - VM must be running
            - /etc/clauded.json must exist (created during provisioning)

          Properties:
            - Returns None if VM not provisioned yet (file doesn't exist)
            - Returns None if SSH command fails

          Algorithm:
            1. Use limactl shell to read /etc/clauded.json via SSH
            2. Parse JSON and extract "distro" field
            3. Return distro value or None on error

        Returns:
            The distro identifier from the VM, or None if unavailable
        """
        if not self.is_running():
            return None

        try:
            result = subprocess.run(
                ["limactl", "shell", self.name, "cat", "/etc/clauded.json"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                # File doesn't exist yet (VM not provisioned) or other error
                return None

            metadata = json.loads(result.stdout)
            distro = metadata.get("distro")
            return str(distro) if distro is not None else None

        except (json.JSONDecodeError, subprocess.SubprocessError):
            return None

    def _get_image_config(self) -> dict[str, str]:
        """Get the Lima image configuration with integrity verification.

        Returns:
            Dict with 'location', 'arch', and 'digest' for Lima image config.
            Uses custom image URL if configured, otherwise selects cloud image
            based on vm_distro field.
        """
        if self.config.vm_image:
            # User-specified image - no checksum verification available
            return {
                "location": self.config.vm_image,
                "arch": "aarch64",
            }

        # Get distro-specific cloud image
        from .distro import get_distro_provider

        provider = get_distro_provider(self.config.vm_distro)
        image_data = provider.get_cloud_image()

        config = {
            "location": image_data["url"],
            "arch": image_data["arch"],
        }
        # Only include digest if sha256 is specified (for future use)
        if "sha256" in image_data:
            config["digest"] = f"sha256:{image_data['sha256']}"
        return config

    def _generate_lima_config(self) -> dict[str, Any]:
        """Generate Lima YAML configuration."""
        mounts = [
            {
                "location": self.config.mount_host,
                "mountPoint": self.config.mount_guest,
                "writable": True,
            }
        ]

        # Mount ~/.claude directory for global and project-local settings
        # Lima requires absolute paths for mountPoint (not tilde-prefixed)
        # Lima maps the host username to the VM, so guest home is /home/<user>.linux/
        home = Path.home()
        guest_home = f"/home/{getpass.getuser()}.linux"

        # Mount Claude settings directory (read-write to allow settings changes)
        # Create on host if it doesn't exist so settings persist across VMs
        claude_dir = home / ".claude"
        claude_dir.mkdir(exist_ok=True)
        mounts.append(
            {
                "location": str(claude_dir),
                "mountPoint": f"{guest_home}/.claude",
                "writable": True,
            }
        )

        # No provision scripts - all configuration handled by Ansible.
        # Lima user provisions fail on Alpine due to home directory permissions
        # not being set up when cloud-init runs. Ansible runs after boot when
        # permissions are correct.

        return {
            "vmType": "vz",
            "os": "Linux",
            "arch": "aarch64",
            "cpus": self.config.cpus,
            "memory": self.config.memory,
            "disk": self.config.disk,
            "images": [self._get_image_config()],
            "containerd": {
                "system": False,
                "user": False,
            },
            "mountType": "virtiofs",
            "mounts": mounts,
            # Disable automatic port forwarding - VM services stay isolated
            "portForwards": [
                {
                    "guestPortRange": [1, 65535],
                    "ignore": True,
                }
            ],
        }
