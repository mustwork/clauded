"""Ansible provisioning for clauded VMs."""

import getpass
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click
import yaml

from . import __version__
from .config import Config
from .downloads import get_downloads
from .lima import LimaVM

# Roles that have distro-specific variants (e.g., common-alpine, common-ubuntu).
# Roles NOT in this set use the original name without suffix.
# All roles now have variants after Story 06.
_ROLES_WITH_VARIANTS = frozenset(
    {
        # Core roles (Story 03)
        "common",
        "python",
        "node",
        # Language roles (Story 04)
        "java",
        "kotlin",
        "rust",
        "go",
        "dart",
        "c",
        # Tool roles (Story 05)
        "docker",
        "uv",
        "poetry",
        "maven",
        "gradle",
        "aws_cli",
        "gh",
        # Database roles (Story 06)
        "postgresql",
        "redis",
        "mysql",
        "sqlite",
        "mongodb",
        # Framework roles (Story 06)
        "claude_code",
        "playwright",
    }
)

# Allowlist of safe environment variables to pass to ansible-playbook.
# This prevents leaking sensitive variables (AWS credentials, API keys, etc.)
# into the Ansible subprocess while allowing required functionality.
_ENV_ALLOWLIST = frozenset(
    {
        # System essentials
        "PATH",
        "HOME",
        "USER",
        "LOGNAME",
        # Locale settings
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "LC_MESSAGES",
        "LC_COLLATE",
        # Terminal
        "TERM",
        "COLORTERM",
        # SSH agent forwarding
        "SSH_AUTH_SOCK",
        # Temp directories
        "TMPDIR",
        "TEMP",
        "TMP",
        # XDG directories (used by many tools)
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_CACHE_HOME",
        "XDG_RUNTIME_DIR",
    }
)


def _filter_env(env: dict[str, str]) -> dict[str, str]:
    """Filter environment variables to only include safe allowlisted values."""
    return {k: v for k, v in env.items() if k in _ENV_ALLOWLIST}


try:
    from ._build_info import __commit__
except ImportError:
    # Development mode - read from git
    def _get_git_commit() -> str:
        repo_root = Path(__file__).parent.parent.parent
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return "unknown"

    __commit__ = _get_git_commit()


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

    def _apply_distro_suffix(self, base_roles: list[str]) -> list[str]:
        """Apply distro suffix to roles that have variants.

        Args:
            base_roles: List of base role names (e.g., ["common", "python", "docker"])

        Returns:
            List of role names with distro suffix applied where appropriate.
            Roles in _ROLES_WITH_VARIANTS get f"{role}-{distro}" suffix.
            Other roles keep their original name.
        """
        distro = self.config.vm_distro
        result = []
        for role in base_roles:
            if role in _ROLES_WITH_VARIANTS:
                result.append(f"{role}-{distro}")
            else:
                result.append(role)
        return result

    def _validate_roles_exist(self, role_names: list[str]) -> list[str]:
        """Validate that all required roles exist.

        Args:
            role_names: List of role names (with distro suffix where applicable)

        Returns:
            List of missing role names.
        """
        missing = []
        for role in role_names:
            role_path = self.roles_path / role
            if not role_path.is_dir():
                missing.append(role)
        return missing

    def run(self) -> None:
        """Run the provisioning playbook."""
        # Get base roles and apply distro suffix
        base_roles = self._get_base_roles()
        roles_with_suffix = self._apply_distro_suffix(base_roles)

        # Validate all roles exist before running
        missing_roles = self._validate_roles_exist(roles_with_suffix)
        if missing_roles:
            click.echo(
                f"Error: Missing Ansible roles for distro '{self.config.vm_distro}':\n"
                + "\n".join(f"  - {role}" for role in missing_roles)
                + "\n\nThis may indicate incomplete distro support. "
                "Check that all required role variants exist.",
                err=True,
            )
            raise SystemExit(1)

        playbook = self._generate_playbook(roles_with_suffix)
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
            print(f"Roles: {', '.join(roles_with_suffix)}\n")

            # Display SQLite storage disclaimer (C3)
            if "sqlite" in self.config.databases:
                print("⚠️  SQLite storage location:")
                print("   • Host-mounted paths persist across VM recreations")
                print("   • VM-local paths are ephemeral (lost on VM destroy)")
                print("   • Configure database file location according to your needs\n")

            env = {
                **_filter_env(dict(os.environ)),
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

            try:
                subprocess.run(cmd, env=env, check=True)
            except FileNotFoundError:
                click.echo(
                    "Ansible is not installed. Install with: uv tool install clauded",
                    err=True,
                )
                raise SystemExit(1) from None
            except subprocess.CalledProcessError as e:
                click.echo(
                    f"Provisioning failed (exit code {e.returncode}).\n"
                    f"  • Retry provisioning: clauded --reprovision\n"
                    f"  • Debug in the VM:    limactl shell {self.vm.name}\n"
                    f"  • Start fresh:        clauded --destroy && clauded",
                    err=True,
                )
                raise SystemExit(1) from None

    def _get_base_roles(self) -> list[str]:
        """Determine which base roles to include based on config.

        Returns base role names WITHOUT distro suffix.
        Use _apply_distro_suffix() to add suffixes for roles with variants.
        """
        roles = ["common"]  # Base system packages (git, curl, etc.)

        if self.config.python:
            roles.append("python")
            roles.append("uv")  # Auto-bundled with Python
            roles.append("poetry")  # Auto-bundled with Python
        # Node.js: only include when explicitly configured or required by frameworks
        if self.config.node:
            roles.append("node")
        # Java/Kotlin: install Java first (Kotlin and build tools need it)
        if self.config.java or self.config.kotlin:
            roles.append("java")
        if self.config.kotlin:
            roles.append("kotlin")
        if self.config.java or self.config.kotlin:
            roles.append("maven")  # Auto-bundled with Java/Kotlin
            roles.append("gradle")  # Auto-bundled with Java/Kotlin
        if self.config.rust:
            roles.append("rust")
        if self.config.go:
            roles.append("go")
        if self.config.dart:
            roles.append("dart")
        if self.config.c:
            roles.append("c")

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
        if "sqlite" in self.config.databases:
            roles.append("sqlite")
        if "mongodb" in self.config.databases:
            roles.append("mongodb")

        # Frameworks
        if "playwright" in self.config.frameworks:
            # Playwright requires npm for installation
            if "node" not in roles:
                roles.insert(roles.index("common") + 1, "node")
            roles.append("playwright")
        if "claude-code" in self.config.frameworks:
            roles.append("claude_code")

        return roles

    def _generate_playbook(self, roles: list[str]) -> list[dict[str, Any]]:
        """Generate the Ansible playbook.

        Args:
            roles: List of role names with distro suffix applied where applicable.
        """
        timestamp_fmt = "%Y-%m-%d %H:%M:%S UTC"
        provision_timestamp = datetime.now(UTC).strftime(timestamp_fmt)

        # Read host dotfiles to copy to VM
        home = Path.home()
        gitconfig_content = ""
        gitconfig_path = home / ".gitconfig"
        if gitconfig_path.exists():
            gitconfig_content = gitconfig_path.read_text()

        # Get centralized download metadata for supply chain integrity
        downloads = get_downloads()

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
                    "go_version": self.config.go or "1.23.5",
                    "dart_version": self.config.dart or "3.7",
                    "c_version": self.config.c or "gcc14",
                    "claude_dangerously_skip_permissions": (
                        self.config.claude_dangerously_skip_permissions
                    ),
                    "clauded_version": __version__,
                    "clauded_commit": __commit__,
                    "clauded_provision_timestamp": provision_timestamp,
                    "clauded_project_name": self.config.project_name,
                    "clauded_mount_guest": self.config.mount_guest,
                    "clauded_mount_host": self.config.mount_host,
                    "vm_distro": self.config.vm_distro,
                    "gitconfig_content": gitconfig_content,
                    # Centralized download metadata for integrity verification
                    "downloads": downloads,
                    # Playwright browsers (default all if playwright enabled)
                    "playwright_browsers": self.config.playwright_browsers
                    or (
                        ["chromium", "firefox", "webkit"]
                        if "playwright" in self.config.frameworks
                        else []
                    ),
                },
                "roles": roles,
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
        host_key_checking = "True" if self.config.ssh_host_key_checking else "False"
        return f"""[defaults]
host_key_checking = {host_key_checking}
retry_files_enabled = False
interpreter_python = auto_silent
remote_tmp = /tmp/.ansible-${{USER}}

[privilege_escalation]
become_ask_pass = False

[ssh_connection]
pipelining = True
"""
