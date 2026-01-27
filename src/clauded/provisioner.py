"""Ansible provisioning for clauded VMs."""

import getpass
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

from .config import Config
from .lima import LimaVM


def _find_ansible_playbook() -> str:
    """Find the ansible-playbook executable in the same environment as clauded."""
    # When installed as a uv tool or in a venv, ansible-playbook is in the same
    # bin directory as the Python interpreter
    bin_dir = Path(sys.executable).parent
    ansible_playbook = bin_dir / "ansible-playbook"
    if ansible_playbook.exists():
        return str(ansible_playbook)
    # Fallback to PATH lookup
    return "ansible-playbook"


class Provisioner:
    """Generates and runs Ansible playbooks for VM provisioning."""

    def __init__(self, config: Config, vm: LimaVM, *, debug: bool = False):
        self.config = config
        self.vm = vm
        self.roles_path = Path(__file__).parent / "roles"
        self.debug = debug

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

            cmd = [
                _find_ansible_playbook(),
                "-i",
                str(inventory_path),
                str(playbook_path),
                "--ssh-extra-args",
                f"-F {lima_ssh_config}",
            ]
            if self.debug:
                cmd.append("-vv")

            subprocess.run(cmd, env=env, check=True)

    def _get_roles(self) -> list[str]:
        """Determine which roles to include based on config."""
        roles = ["common", "node"]  # Always include (git is in common, npm in node)

        if self.config.python:
            roles.append("python")
            roles.append("uv")
            roles.append("poetry")
        # node is already included by default for npm
        # Java/Kotlin: install Java first (Kotlin and build tools need it)
        if self.config.java or self.config.kotlin:
            roles.append("java")
        if self.config.kotlin:
            roles.append("kotlin")
        if self.config.java or self.config.kotlin:
            roles.append("maven")
            roles.append("gradle")
        if self.config.rust:
            roles.append("rust")
        if self.config.go:
            roles.append("go")

        # Tools
        if "docker" in self.config.tools:
            roles.append("docker")
        if "aws-cli" in self.config.tools:
            roles.append("aws_cli")
        if "gh" in self.config.tools:
            roles.append("gh")

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
                    "java_version": self.config.java or "21",
                    "kotlin_version": self.config.kotlin or "2.0",
                    "rust_version": self.config.rust or "stable",
                    "go_version": self.config.go or "1.25.6",
                    "claude_dangerously_skip_permissions": (
                        self.config.claude_dangerously_skip_permissions
                    ),
                },
                "roles": self._get_roles(),
            }
        ]

    def _generate_inventory(self) -> str:
        """Generate the Ansible inventory."""
        username = getpass.getuser()
        # Use lima-{name} to match the Host entry in Lima's ssh.config
        lima_host = f"lima-{self.vm.name}"
        host_vars = (
            f"ansible_host={lima_host} "
            f"ansible_connection=ssh "
            f"ansible_user={username} "
            f"ansible_become_password="
        )
        return f"[vm]\n{self.vm.name} {host_vars}\n"

    def _generate_ansible_cfg(self) -> str:
        """Generate ansible.cfg content."""
        return """[defaults]
host_key_checking = False
retry_files_enabled = False
interpreter_python = auto_silent

[privilege_escalation]
become_ask_pass = False

[ssh_connection]
pipelining = True
"""
