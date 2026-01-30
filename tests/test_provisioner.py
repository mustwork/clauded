"""Tests for clauded.provisioner module."""

import getpass
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from clauded.config import Config
from clauded.lima import LimaVM
from clauded.provisioner import _ENV_ALLOWLIST, Provisioner, _filter_env


@pytest.fixture
def full_config() -> Config:
    """Create a config with all options enabled."""
    return Config(
        vm_name="clauded-full1234",
        cpus=4,
        memory="8GiB",
        disk="20GiB",
        mount_host="/path/to/project",
        mount_guest="/workspace",
        python="3.12",
        node="20",
        java="21",
        kotlin="2.0",
        rust="stable",
        go="1.25.6",
        tools=["docker", "aws-cli", "gh"],
        databases=["postgresql", "redis", "mysql"],
        frameworks=["playwright", "claude-code"],
    )


@pytest.fixture
def minimal_config() -> Config:
    """Create a config with minimal options."""
    return Config(
        vm_name="clauded-min12345",
        cpus=2,
        memory="4GiB",
        disk="10GiB",
        mount_host="/minimal/project",
        mount_guest="/workspace",
        python=None,
        node=None,
        tools=[],
        databases=[],
        frameworks=[],
    )


class TestProvisionerGetRoles:
    """Tests for Provisioner._get_roles()."""

    def test_always_includes_common(self, minimal_config: Config) -> None:
        """Common role is always included."""
        vm = LimaVM(minimal_config)
        provisioner = Provisioner(minimal_config, vm)

        roles = provisioner._get_roles()

        assert "common" in roles
        assert roles[0] == "common"  # First role

    def test_includes_python_when_selected(self, full_config: Config) -> None:
        """Python role included when python version specified."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        roles = provisioner._get_roles()

        assert "python" in roles

    def test_excludes_python_when_none(self, minimal_config: Config) -> None:
        """Python role excluded when python is None."""
        vm = LimaVM(minimal_config)
        provisioner = Provisioner(minimal_config, vm)

        roles = provisioner._get_roles()

        assert "python" not in roles

    def test_includes_node_when_selected(self, full_config: Config) -> None:
        """Node role included when node version specified."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        roles = provisioner._get_roles()

        assert "node" in roles

    def test_excludes_node_when_none(self, minimal_config: Config) -> None:
        """Node role excluded when node is None and no frameworks need it."""
        vm = LimaVM(minimal_config)
        provisioner = Provisioner(minimal_config, vm)

        roles = provisioner._get_roles()

        assert "node" not in roles

    def test_includes_java_when_selected(self, full_config: Config) -> None:
        """Java role included when java version specified."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        roles = provisioner._get_roles()

        assert "java" in roles

    def test_excludes_java_when_none(self, minimal_config: Config) -> None:
        """Java role excluded when java is None."""
        vm = LimaVM(minimal_config)
        provisioner = Provisioner(minimal_config, vm)

        roles = provisioner._get_roles()

        assert "java" not in roles

    def test_includes_kotlin_when_selected(self, full_config: Config) -> None:
        """Kotlin role included when kotlin version specified."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        roles = provisioner._get_roles()

        assert "kotlin" in roles

    def test_excludes_kotlin_when_none(self, minimal_config: Config) -> None:
        """Kotlin role excluded when kotlin is None."""
        vm = LimaVM(minimal_config)
        provisioner = Provisioner(minimal_config, vm)

        roles = provisioner._get_roles()

        assert "kotlin" not in roles

    def test_includes_rust_when_selected(self, full_config: Config) -> None:
        """Rust role included when rust version specified."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        roles = provisioner._get_roles()

        assert "rust" in roles

    def test_excludes_rust_when_none(self, minimal_config: Config) -> None:
        """Rust role excluded when rust is None."""
        vm = LimaVM(minimal_config)
        provisioner = Provisioner(minimal_config, vm)

        roles = provisioner._get_roles()

        assert "rust" not in roles

    def test_includes_go_when_selected(self, full_config: Config) -> None:
        """Go role included when go version specified."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        roles = provisioner._get_roles()

        assert "go" in roles

    def test_excludes_go_when_none(self, minimal_config: Config) -> None:
        """Go role excluded when go is None."""
        vm = LimaVM(minimal_config)
        provisioner = Provisioner(minimal_config, vm)

        roles = provisioner._get_roles()

        assert "go" not in roles

    def test_includes_docker_when_in_tools(self, full_config: Config) -> None:
        """Docker role included when docker in tools."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        roles = provisioner._get_roles()

        assert "docker" in roles

    def test_includes_aws_cli_when_in_tools(self, full_config: Config) -> None:
        """AWS CLI role included when aws-cli in tools."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        roles = provisioner._get_roles()

        assert "aws_cli" in roles

    def test_includes_gh_when_in_tools(self, full_config: Config) -> None:
        """GitHub CLI role included when gh in tools."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        roles = provisioner._get_roles()

        assert "gh" in roles

    def test_includes_gradle_when_java_selected(self, full_config: Config) -> None:
        """Gradle role included when java is selected (auto-bundled)."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        roles = provisioner._get_roles()

        assert "gradle" in roles

    def test_includes_gradle_when_kotlin_selected(self) -> None:
        """Gradle role included when kotlin is selected (auto-bundled)."""
        config = Config(
            vm_name="clauded-kotlin123",
            cpus=2,
            memory="4GiB",
            disk="10GiB",
            mount_host="/path/to/project",
            mount_guest="/workspace",
            kotlin="2.0",
        )
        vm = LimaVM(config)
        provisioner = Provisioner(config, vm)

        roles = provisioner._get_roles()

        assert "gradle" in roles
        assert "maven" in roles

    def test_includes_maven_when_java_selected(self, full_config: Config) -> None:
        """Maven role included when java is selected."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        roles = provisioner._get_roles()

        assert "maven" in roles

    def test_includes_uv_when_python_selected(self, full_config: Config) -> None:
        """UV role included when python is selected."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        roles = provisioner._get_roles()

        assert "uv" in roles

    def test_includes_poetry_when_python_selected(self, full_config: Config) -> None:
        """Poetry role included when python is selected."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        roles = provisioner._get_roles()

        assert "poetry" in roles

    def test_includes_postgresql_when_in_databases(self, full_config: Config) -> None:
        """PostgreSQL role included when postgresql in databases."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        roles = provisioner._get_roles()

        assert "postgresql" in roles

    def test_includes_redis_when_in_databases(self, full_config: Config) -> None:
        """Redis role included when redis in databases."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        roles = provisioner._get_roles()

        assert "redis" in roles

    def test_includes_mysql_when_in_databases(self, full_config: Config) -> None:
        """MySQL role included when mysql in databases."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        roles = provisioner._get_roles()

        assert "mysql" in roles

    def test_includes_playwright_when_in_frameworks(self, full_config: Config) -> None:
        """Playwright role included when playwright in frameworks."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        roles = provisioner._get_roles()

        assert "playwright" in roles

    def test_playwright_auto_includes_node(self) -> None:
        """Playwright framework automatically includes node role (npm required)."""
        config = Config(
            vm_name="clauded-playwright",
            cpus=2,
            memory="4GiB",
            disk="10GiB",
            mount_host="/path/to/project",
            mount_guest="/workspace",
            node=None,  # Node not explicitly configured
            frameworks=["playwright"],
        )
        vm = LimaVM(config)
        provisioner = Provisioner(config, vm)

        roles = provisioner._get_roles()

        assert "node" in roles
        assert "playwright" in roles
        # Node should come before playwright (dependency order)
        assert roles.index("node") < roles.index("playwright")

    def test_includes_claude_code_when_in_frameworks(self, full_config: Config) -> None:
        """Claude code role included when claude-code in frameworks."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        roles = provisioner._get_roles()

        assert "claude_code" in roles

    def test_full_config_has_all_roles(self, full_config: Config) -> None:
        """Full config produces all 19 roles."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        roles = provisioner._get_roles()

        expected_roles = [
            "common",
            "python",
            "uv",  # Auto-bundled with Python
            "poetry",  # Auto-bundled with Python
            "node",  # Explicitly configured
            "java",  # Java before Maven/Gradle (they need JAVA_HOME)
            "kotlin",
            "maven",  # Auto-bundled with Java/Kotlin
            "gradle",  # Auto-bundled with Java/Kotlin
            "rust",
            "go",
            "docker",
            "aws_cli",
            "gh",
            "postgresql",
            "redis",
            "mysql",
            "playwright",
            "claude_code",
        ]
        assert roles == expected_roles

    def test_minimal_config_has_only_common(self, minimal_config: Config) -> None:
        """Minimal config produces only common role."""
        vm = LimaVM(minimal_config)
        provisioner = Provisioner(minimal_config, vm)

        roles = provisioner._get_roles()

        assert roles == ["common"]


class TestProvisionerGeneratePlaybook:
    """Tests for Provisioner._generate_playbook()."""

    def test_returns_list_with_one_play(self, full_config: Config) -> None:
        """Playbook is a list with one play."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        playbook = provisioner._generate_playbook()

        assert isinstance(playbook, list)
        assert len(playbook) == 1

    def test_play_targets_vm_host(self, full_config: Config) -> None:
        """Play targets 'vm' host group."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        playbook = provisioner._generate_playbook()

        assert playbook[0]["hosts"] == "vm"

    def test_play_uses_become(self, full_config: Config) -> None:
        """Play uses become for privilege escalation."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        playbook = provisioner._generate_playbook()

        assert playbook[0]["become"] is True

    def test_play_includes_python_version_var(self, full_config: Config) -> None:
        """Play includes python_version variable."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        playbook = provisioner._generate_playbook()

        assert playbook[0]["vars"]["python_version"] == "3.12"

    def test_play_includes_node_version_var(self, full_config: Config) -> None:
        """Play includes node_version variable."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        playbook = provisioner._generate_playbook()

        assert playbook[0]["vars"]["node_version"] == "20"

    def test_play_defaults_python_version_when_none(
        self, minimal_config: Config
    ) -> None:
        """Python version defaults to 3.12 when None."""
        vm = LimaVM(minimal_config)
        provisioner = Provisioner(minimal_config, vm)

        playbook = provisioner._generate_playbook()

        assert playbook[0]["vars"]["python_version"] == "3.12"

    def test_play_defaults_node_version_when_none(self, minimal_config: Config) -> None:
        """Node version defaults to 20 when None."""
        vm = LimaVM(minimal_config)
        provisioner = Provisioner(minimal_config, vm)

        playbook = provisioner._generate_playbook()

        assert playbook[0]["vars"]["node_version"] == "20"

    def test_play_includes_java_version_var(self, full_config: Config) -> None:
        """Play includes java_version variable."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        playbook = provisioner._generate_playbook()

        assert playbook[0]["vars"]["java_version"] == "21"

    def test_play_defaults_java_version_when_none(self, minimal_config: Config) -> None:
        """Java version defaults to 21 when None."""
        vm = LimaVM(minimal_config)
        provisioner = Provisioner(minimal_config, vm)

        playbook = provisioner._generate_playbook()

        assert playbook[0]["vars"]["java_version"] == "21"

    def test_play_includes_kotlin_version_var(self, full_config: Config) -> None:
        """Play includes kotlin_version variable."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        playbook = provisioner._generate_playbook()

        assert playbook[0]["vars"]["kotlin_version"] == "2.0"

    def test_play_defaults_kotlin_version_when_none(
        self, minimal_config: Config
    ) -> None:
        """Kotlin version defaults to 2.0 when None."""
        vm = LimaVM(minimal_config)
        provisioner = Provisioner(minimal_config, vm)

        playbook = provisioner._generate_playbook()

        assert playbook[0]["vars"]["kotlin_version"] == "2.0"

    def test_play_includes_rust_version_var(self, full_config: Config) -> None:
        """Play includes rust_version variable."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        playbook = provisioner._generate_playbook()

        assert playbook[0]["vars"]["rust_version"] == "stable"

    def test_play_defaults_rust_version_when_none(self, minimal_config: Config) -> None:
        """Rust version defaults to stable when None."""
        vm = LimaVM(minimal_config)
        provisioner = Provisioner(minimal_config, vm)

        playbook = provisioner._generate_playbook()

        assert playbook[0]["vars"]["rust_version"] == "stable"

    def test_play_includes_go_version_var(self, full_config: Config) -> None:
        """Play includes go_version variable."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        playbook = provisioner._generate_playbook()

        assert playbook[0]["vars"]["go_version"] == "1.25.6"

    def test_play_defaults_go_version_when_none(self, minimal_config: Config) -> None:
        """Go version defaults to 1.25.6 when None."""
        vm = LimaVM(minimal_config)
        provisioner = Provisioner(minimal_config, vm)

        playbook = provisioner._generate_playbook()

        assert playbook[0]["vars"]["go_version"] == "1.25.6"

    def test_play_includes_roles(self, full_config: Config) -> None:
        """Play includes roles from _get_roles()."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        playbook = provisioner._generate_playbook()

        assert "roles" in playbook[0]
        assert "common" in playbook[0]["roles"]

    def test_play_includes_gitconfig_content_when_exists(
        self, full_config: Config, tmp_path: Path
    ) -> None:
        """Play includes gitconfig_content when ~/.gitconfig exists."""
        gitconfig = tmp_path / ".gitconfig"
        gitconfig.write_text("[user]\n\tname = Test User\n")

        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        with patch("clauded.provisioner.Path.home", return_value=tmp_path):
            playbook = provisioner._generate_playbook()

        expected = "[user]\n\tname = Test User\n"
        assert playbook[0]["vars"]["gitconfig_content"] == expected

    def test_play_gitconfig_content_empty_when_not_exists(
        self, full_config: Config, tmp_path: Path
    ) -> None:
        """Play has empty gitconfig_content when ~/.gitconfig doesn't exist."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        with patch("clauded.provisioner.Path.home", return_value=tmp_path):
            playbook = provisioner._generate_playbook()

        assert playbook[0]["vars"]["gitconfig_content"] == ""

    def test_play_gitconfig_handles_adversarial_content(
        self, full_config: Config, tmp_path: Path
    ) -> None:
        """Gitconfig with shell-hostile content is passed through safely.

        The Ansible copy module with content parameter avoids shell heredoc
        parsing, so content that would break shell heredocs (like EOF markers,
        backticks, dollar signs) is handled safely.
        """
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        # Content that would break shell heredocs if not properly escaped
        adversarial_content = """[user]
\tname = GITCONFIG_EOF
\temail = $(whoami)@`hostname`.local
[alias]
\tpwn = !echo 'GITCONFIG_EOF'; cat /etc/passwd
\teof = GITCONFIG_EOF
"""
        gitconfig = tmp_path / ".gitconfig"
        gitconfig.write_text(adversarial_content)

        with patch("clauded.provisioner.Path.home", return_value=tmp_path):
            playbook = provisioner._generate_playbook()

        # Content should pass through unchanged - Ansible handles escaping
        assert playbook[0]["vars"]["gitconfig_content"] == adversarial_content


class TestProvisionerGenerateInventory:
    """Tests for Provisioner._generate_inventory()."""

    def test_generates_ini_format(self, full_config: Config) -> None:
        """Inventory is in INI format with [vm] group."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        inventory = provisioner._generate_inventory()

        assert "[vm]" in inventory

    def test_includes_vm_name(self, full_config: Config) -> None:
        """Inventory includes VM name as host."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        inventory = provisioner._generate_inventory()

        assert "clauded-full1234" in inventory

    def test_uses_ssh_connection(self, full_config: Config) -> None:
        """Inventory uses SSH connection."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        inventory = provisioner._generate_inventory()

        assert "ansible_connection=ssh" in inventory

    def test_uses_current_user(self, full_config: Config) -> None:
        """Inventory uses current system user."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        inventory = provisioner._generate_inventory()

        current_user = getpass.getuser()
        assert f"ansible_user={current_user}" in inventory


class TestProvisionerGenerateAnsibleCfg:
    """Tests for Provisioner._generate_ansible_cfg()."""

    def test_disables_host_key_checking(self, full_config: Config) -> None:
        """Ansible config disables host key checking."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        cfg = provisioner._generate_ansible_cfg()

        assert "host_key_checking = False" in cfg

    def test_disables_retry_files(self, full_config: Config) -> None:
        """Ansible config disables retry files."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        cfg = provisioner._generate_ansible_cfg()

        assert "retry_files_enabled = False" in cfg

    def test_enables_pipelining(self, full_config: Config) -> None:
        """Ansible config enables SSH pipelining."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        cfg = provisioner._generate_ansible_cfg()

        assert "pipelining = True" in cfg


class TestProvisionerRolesPath:
    """Tests for Provisioner roles path."""

    def test_roles_path_is_in_package(self, full_config: Config) -> None:
        """Roles path points to package directory."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        assert provisioner.roles_path.name == "roles"
        assert "clauded" in str(provisioner.roles_path)

    def test_roles_directory_exists(self, full_config: Config) -> None:
        """Roles directory exists."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        assert provisioner.roles_path.exists()
        assert provisioner.roles_path.is_dir()

    def test_common_role_exists(self, full_config: Config) -> None:
        """Common role directory exists."""
        vm = LimaVM(full_config)
        provisioner = Provisioner(full_config, vm)

        common_role = provisioner.roles_path / "common"
        assert common_role.exists()
        assert (common_role / "tasks" / "main.yml").exists()


# Backward compatibility tests for SQLite
def test_provisioner_without_sqlite_config() -> None:
    """Provisioner handles configs without SQLite correctly."""
    config = Config(
        vm_name="test-vm",
        cpus=4,
        memory="8GiB",
        disk="20GiB",
        mount_host="/tmp/test",
        mount_guest="/tmp/test",
        python="3.12",
        databases=["postgresql", "redis"],
        frameworks=["claude-code"],
    )

    from unittest.mock import MagicMock

    vm = MagicMock()
    provisioner = Provisioner(config, vm)
    roles = provisioner._get_roles()

    assert "postgresql" in roles
    assert "redis" in roles
    assert "sqlite" not in roles


def test_provisioner_with_sqlite_config() -> None:
    """Provisioner includes SQLite role when configured."""
    config = Config(
        vm_name="test-vm",
        cpus=4,
        memory="8GiB",
        disk="20GiB",
        mount_host="/tmp/test",
        mount_guest="/tmp/test",
        node="20",
        databases=["sqlite"],
        frameworks=["claude-code"],
    )

    vm = MagicMock()
    provisioner = Provisioner(config, vm)
    roles = provisioner._get_roles()

    assert "sqlite" in roles


class TestProvisionerErrorHandling:
    """Tests for Provisioner subprocess error handling."""

    def test_run_handles_ansible_not_found(
        self, full_config: Config, tmp_path: Path
    ) -> None:
        """run() exits with message when ansible-playbook is not found."""
        vm = MagicMock()
        vm.name = "test-vm"
        vm.get_ssh_config_path.return_value = tmp_path / "ssh.config"
        provisioner = Provisioner(full_config, vm)

        with (
            patch("clauded.provisioner.Path.home", return_value=tmp_path),
            patch("subprocess.run", side_effect=FileNotFoundError()),
        ):
            with pytest.raises(SystemExit) as exc_info:
                provisioner.run()

        assert exc_info.value.code == 1

    def test_run_handles_ansible_failure(
        self, full_config: Config, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """run() exits with recovery message when ansible-playbook fails."""
        vm = MagicMock()
        vm.name = "test-vm"
        vm.get_ssh_config_path.return_value = tmp_path / "ssh.config"
        provisioner = Provisioner(full_config, vm)

        with (
            patch("clauded.provisioner.Path.home", return_value=tmp_path),
            patch(
                "subprocess.run",
                side_effect=subprocess.CalledProcessError(42, "ansible-playbook"),
            ),
        ):
            with pytest.raises(SystemExit) as exc_info:
                provisioner.run()

        assert exc_info.value.code == 1

        # Verify error message contains all recovery options
        captured = capsys.readouterr()
        assert "exit code 42" in captured.err
        assert "clauded --reprovision" in captured.err
        assert "limactl shell test-vm" in captured.err
        assert "clauded --destroy && clauded" in captured.err


class TestEnvironmentFiltering:
    """Tests for environment variable filtering."""

    def test_allowlist_includes_path(self) -> None:
        """PATH is in the allowlist."""
        assert "PATH" in _ENV_ALLOWLIST

    def test_allowlist_includes_home(self) -> None:
        """HOME is in the allowlist."""
        assert "HOME" in _ENV_ALLOWLIST

    def test_allowlist_includes_ssh_auth_sock(self) -> None:
        """SSH_AUTH_SOCK is in the allowlist for agent forwarding."""
        assert "SSH_AUTH_SOCK" in _ENV_ALLOWLIST

    def test_allowlist_includes_locale_vars(self) -> None:
        """Locale variables are in the allowlist."""
        for var in ["LANG", "LC_ALL", "LC_CTYPE"]:
            assert var in _ENV_ALLOWLIST

    def test_allowlist_includes_temp_dirs(self) -> None:
        """Temp directory variables are in the allowlist."""
        for var in ["TMPDIR", "TEMP", "TMP"]:
            assert var in _ENV_ALLOWLIST

    def test_filter_env_keeps_allowlisted_vars(self) -> None:
        """_filter_env keeps variables in the allowlist."""
        env = {"PATH": "/usr/bin", "HOME": "/home/user", "AWS_SECRET_KEY": "secret"}
        filtered = _filter_env(env)

        assert "PATH" in filtered
        assert "HOME" in filtered
        assert filtered["PATH"] == "/usr/bin"
        assert filtered["HOME"] == "/home/user"

    def test_filter_env_removes_sensitive_vars(self) -> None:
        """_filter_env removes sensitive environment variables."""
        sensitive_vars = [
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_SESSION_TOKEN",
            "DATABASE_URL",
            "DB_PASSWORD",
            "API_KEY",
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "GITHUB_TOKEN",
            "NPM_TOKEN",
            "PYPI_TOKEN",
            "SECRET_KEY",
            "PRIVATE_KEY",
        ]
        env = {var: "sensitive_value" for var in sensitive_vars}
        env["PATH"] = "/usr/bin"  # Add one allowlisted

        filtered = _filter_env(env)

        for var in sensitive_vars:
            assert var not in filtered
        assert "PATH" in filtered

    def test_filter_env_returns_empty_for_all_sensitive(self) -> None:
        """_filter_env returns empty dict when all vars are sensitive."""
        env = {"AWS_SECRET_KEY": "secret", "DB_PASSWORD": "secret"}
        filtered = _filter_env(env)

        assert filtered == {}

    def test_filter_env_preserves_all_allowlisted(self) -> None:
        """_filter_env preserves all allowlisted variables when present."""
        env = {var: f"value_{var}" for var in _ENV_ALLOWLIST}
        filtered = _filter_env(env)

        assert filtered == env

    def test_provisioner_run_uses_filtered_env(
        self, full_config: Config, tmp_path: Path
    ) -> None:
        """Provisioner.run() passes filtered environment to subprocess."""
        vm = MagicMock()
        vm.name = "test-vm"
        vm.get_ssh_config_path.return_value = tmp_path / "ssh.config"
        provisioner = Provisioner(full_config, vm)

        captured_env = {}

        def mock_subprocess_run(cmd, env=None, check=False):
            nonlocal captured_env
            captured_env = env or {}
            return MagicMock()

        with (
            patch("clauded.provisioner.Path.home", return_value=tmp_path),
            patch("subprocess.run", side_effect=mock_subprocess_run),
            patch.dict(
                "os.environ",
                {
                    "PATH": "/usr/bin",
                    "HOME": "/home/user",
                    "AWS_SECRET_ACCESS_KEY": "secret123",
                    "DATABASE_PASSWORD": "dbpass",
                },
                clear=True,
            ),
        ):
            provisioner.run()

        # Should have PATH, HOME but not sensitive vars
        assert "PATH" in captured_env
        assert "HOME" in captured_env
        assert "AWS_SECRET_ACCESS_KEY" not in captured_env
        assert "DATABASE_PASSWORD" not in captured_env
        # Should have clauded-specific vars
        assert "ANSIBLE_ROLES_PATH" in captured_env
        assert "ANSIBLE_CONFIG" in captured_env
