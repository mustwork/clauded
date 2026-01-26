"""Ansible provisioning for clauded VMs."""

import getpass
import os
import subprocess
import tempfile
from pathlib import Path

import yaml

from .config import Config
from .lima import LimaVM


class Provisioner:
    """Generates and runs Ansible playbooks for VM provisioning."""

    def __init__(self, config: Config, vm: LimaVM):
        self.config = config
        self.vm = vm
        self.roles_path = Path(__file__).parent / "roles"

    def run(self) -> None:
        """Run the provisioning playbook."""
        playbook = self._generate_playbook()
        inventory = self._generate_inventory()

        with tempfile.TemporaryDirectory() as tmpdir:
            playbook_path = Path(tmpdir) / "playbook.yml"
            inventory_path = Path(tmpdir) / "inventory.ini"
            ansible_cfg_path = Path(tmpdir) / "ansible.cfg"

            # Write playbook
            with open(playbook_path, "w") as f:
                yaml.dump(playbook, f, default_flow_style=False)

            # Write inventory
            inventory_path.write_text(inventory)

            # Write ansible.cfg
            ansible_cfg_path.write_text(self._generate_ansible_cfg())

            lima_ssh_config = self.vm.get_ssh_config_path()

            print(f"\nProvisioning VM '{self.vm.name}'...")
            print(f"Roles: {', '.join(self._get_roles())}\n")

            env = {
                **os.environ,
                "ANSIBLE_ROLES_PATH": str(self.roles_path),
                "ANSIBLE_CONFIG": str(ansible_cfg_path),
            }

            subprocess.run(
                [
                    "uv",
                    "run",
                    "ansible-playbook",
                    "-i",
                    str(inventory_path),
                    str(playbook_path),
                    "--ssh-extra-args",
                    f"-F {lima_ssh_config}",
                ],
                env=env,
                check=True,
            )

    def _get_roles(self) -> list[str]:
        """Determine which roles to include based on config."""
        roles = ["common"]  # Always include

        if self.config.python:
            roles.append("python")
        if self.config.node:
            roles.append("node")

        # Tools
        if "docker" in self.config.tools:
            roles.append("docker")
        if "aws-cli" in self.config.tools:
            roles.append("aws_cli")
        if "gh" in self.config.tools:
            roles.append("gh")
        # git is included in common

        # Databases
        if "postgresql" in self.config.databases:
            roles.append("postgresql")
        if "redis" in self.config.databases:
            roles.append("redis")
        if "mysql" in self.config.databases:
            roles.append("mysql")

        # Frameworks
        if "playwright" in self.config.frameworks:
            roles.append("playwright")
        if "claude-code" in self.config.frameworks:
            roles.append("claude_code")

        return roles

    def _generate_playbook(self) -> list:
        """Generate the Ansible playbook."""
        return [
            {
                "name": "Provision clauded VM",
                "hosts": "vm",
                "become": True,
                "vars": {
                    "python_version": self.config.python or "3.12",
                    "node_version": self.config.node or "20",
                },
                "roles": self._get_roles(),
            }
        ]

    def _generate_inventory(self) -> str:
        """Generate the Ansible inventory."""
        username = getpass.getuser()
        return f"""[vm]
{self.vm.name} ansible_host=localhost ansible_connection=ssh ansible_user={username}
"""

    def _generate_ansible_cfg(self) -> str:
        """Generate ansible.cfg content."""
        return """[defaults]
host_key_checking = False
retry_files_enabled = False
interpreter_python = auto_silent

[ssh_connection]
pipelining = True
"""
