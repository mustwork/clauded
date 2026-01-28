"""Lima VM lifecycle management."""

import getpass
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import yaml

from .config import Config


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

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(lima_config, f, default_flow_style=False)
            config_path = f.name

        try:
            print(f"\nCreating VM '{self.name}'...")
            cmd = ["limactl"]
            if debug:
                cmd.extend(["--debug", "--log-level", "debug"])
            # --tty=false prevents TUI prompt when stdin is devnull
            # --timeout allows more time for package installation during provisioning
            cmd.extend(
                [
                    "start",
                    "--tty=false",
                    "--timeout",
                    "20m",
                    "--name",
                    self.name,
                    config_path,
                ]
            )
            subprocess.run(
                cmd,
                check=True,
                stdin=subprocess.DEVNULL,
            )
        finally:
            Path(config_path).unlink(missing_ok=True)

    def start(self, *, debug: bool = False) -> None:
        """Start an existing VM."""
        print(f"\nStarting VM '{self.name}'...")
        cmd = ["limactl"]
        if debug:
            cmd.extend(["--debug", "--log-level", "debug"])
        # --tty=false prevents TUI prompt when stdin is devnull
        cmd.extend(["start", "--tty=false", self.name])
        subprocess.run(
            cmd,
            check=True,
            stdin=subprocess.DEVNULL,
        )

    def stop(self) -> None:
        """Stop the VM."""
        print(f"\nStopping VM '{self.name}'...")
        subprocess.run(["limactl", "stop", self.name], check=True)

    def destroy(self) -> None:
        """Delete the VM."""
        print(f"\nDestroying VM '{self.name}'...")
        subprocess.run(["limactl", "delete", "-f", self.name], check=True)

    def shell(self) -> None:
        """Open the Claude Code shell in the VM."""
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
            self.name,
            "bash",
            "-lic",
            full_cmd,
        ]
        subprocess.run(cmd)

    def get_ssh_config_path(self) -> Path:
        """Get the path to Lima's SSH config for this VM."""
        return Path.home() / ".lima" / self.name / "ssh.config"

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

        # No system provision scripts - all package installation handled by Ansible.
        # This makes Lima boot faster and failures recoverable
        # (VM exists, can re-run Ansible).
        provision = []

        # Copy .gitconfig content to VM if it exists
        # (Lima mounts only support directories, not individual files)
        gitconfig = home / ".gitconfig"
        if gitconfig.exists():
            gitconfig_content = gitconfig.read_text()
            # Use heredoc to write the file content
            script = (
                f"cat > ~/.gitconfig << 'GITCONFIG_EOF'\n"
                f"{gitconfig_content}GITCONFIG_EOF"
            )
            provision.append({"mode": "user", "script": script})

        # Copy .claude.json (OAuth tokens) from host if it exists
        # This allows sharing authentication between host and VM
        claude_json = home / ".claude.json"
        if claude_json.exists():
            claude_json_content = claude_json.read_text()
            script = (
                f"cat > ~/.claude.json << 'CLAUDEJSON_EOF'\n"
                f"{claude_json_content}CLAUDEJSON_EOF\n"
                f"chmod 600 ~/.claude.json"
            )
            provision.append({"mode": "user", "script": script})

        return {
            "vmType": "vz",
            "os": "Linux",
            "arch": "aarch64",
            "cpus": self.config.cpus,
            "memory": self.config.memory,
            "disk": self.config.disk,
            "images": [
                {
                    "location": "https://dl-cdn.alpinelinux.org/alpine/v3.21/releases/cloud/nocloud_alpine-3.21.0-aarch64-uefi-cloudinit-r0.qcow2",
                    "arch": "aarch64",
                }
            ],
            "containerd": {
                "system": False,
                "user": False,
            },
            "mountType": "virtiofs",
            "mounts": mounts,
            "provision": provision,
        }
