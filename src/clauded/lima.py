"""Lima VM lifecycle management."""

import subprocess
import tempfile
from pathlib import Path

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

    def create(self) -> None:
        """Create and start a new VM."""
        lima_config = self._generate_lima_config()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(lima_config, f, default_flow_style=False)
            config_path = f.name

        try:
            print(f"\nCreating VM '{self.name}'...")
            subprocess.run(
                ["limactl", "start", "--name", self.name, config_path],
                check=True,
            )
        finally:
            Path(config_path).unlink(missing_ok=True)

    def start(self) -> None:
        """Start an existing VM."""
        print(f"\nStarting VM '{self.name}'...")
        subprocess.run(["limactl", "start", self.name], check=True)

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
        subprocess.run(
            [
                "limactl",
                "shell",
                "--workdir",
                self.config.mount_guest,
                self.name,
                "claude",
            ]
        )

    def get_ssh_config_path(self) -> Path:
        """Get the path to Lima's SSH config for this VM."""
        return Path.home() / ".lima" / self.name / "ssh.config"

    def _generate_lima_config(self) -> dict:
        """Generate Lima YAML configuration."""
        mounts = [
            {
                "location": self.config.mount_host,
                "mountPoint": self.config.mount_guest,
                "writable": True,
            }
        ]

        # Add read-only mounts for home directory config (if they exist)
        home = Path.home()
        for dirname in [".claude", ".git"]:
            dirpath = home / dirname
            if dirpath.exists():
                mounts.append(
                    {
                        "location": str(dirpath),
                        "mountPoint": f"~/{dirname}",
                        "writable": False,
                    }
                )

        return {
            "vmType": "vz",
            "os": "Linux",
            "arch": "aarch64",
            "cpus": self.config.cpus,
            "memory": self.config.memory,
            "disk": self.config.disk,
            "images": [
                {
                    "location": "https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-arm64.img",
                    "arch": "aarch64",
                }
            ],
            "containerd": {
                "system": False,
                "user": False,
            },
            "mountType": "virtiofs",
            "mounts": mounts,
            "provision": [
                {
                    "mode": "system",
                    "script": (
                        "apt-get update && "
                        "apt-get install -y ca-certificates curl git python3-pip"
                    ),
                }
            ],
        }
