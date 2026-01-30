"""Tests for clauded.lima module."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from clauded.config import Config
from clauded.downloads import get_alpine_image
from clauded.lima import LimaVM


@pytest.fixture
def sample_config() -> Config:
    """Create a sample config for testing."""
    return Config(
        vm_name="clauded-test1234",
        cpus=4,
        memory="8GiB",
        disk="20GiB",
        mount_host="/path/to/project",
        mount_guest="/path/to/project",
        python="3.12",
        node="20",
        tools=["docker"],
        databases=["postgresql"],
        frameworks=["claude-code"],
    )


class TestLimaVMInit:
    """Tests for LimaVM initialization."""

    def test_sets_name_from_config(self, sample_config: Config) -> None:
        """VM name is taken from config."""
        vm = LimaVM(sample_config)

        assert vm.name == "clauded-test1234"

    def test_stores_config(self, sample_config: Config) -> None:
        """Config is stored for later use."""
        vm = LimaVM(sample_config)

        assert vm.config is sample_config


class TestLimaVMExists:
    """Tests for LimaVM.exists()."""

    def test_returns_true_when_vm_in_list(self, sample_config: Config) -> None:
        """Returns True when VM name appears in limactl list output."""
        vm = LimaVM(sample_config)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="default\nclauded-test1234\nother-vm"
            )

            assert vm.exists() is True

        mock_run.assert_called_once_with(
            ["limactl", "list", "-q"],
            capture_output=True,
            text=True,
        )

    def test_returns_false_when_vm_not_in_list(self, sample_config: Config) -> None:
        """Returns False when VM name not in limactl list output."""
        vm = LimaVM(sample_config)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="default\nother-vm")

            assert vm.exists() is False


class TestLimaVMIsRunning:
    """Tests for LimaVM.is_running()."""

    def test_returns_true_when_status_is_running(self, sample_config: Config) -> None:
        """Returns True when VM status is 'Running'."""
        vm = LimaVM(sample_config)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="Running")

            assert vm.is_running() is True

        mock_run.assert_called_once_with(
            ["limactl", "list", "--format", "{{.Status}}", "clauded-test1234"],
            capture_output=True,
            text=True,
        )

    def test_returns_false_when_status_is_stopped(self, sample_config: Config) -> None:
        """Returns False when VM status is 'Stopped'."""
        vm = LimaVM(sample_config)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="Stopped")

            assert vm.is_running() is False

    def test_returns_false_when_status_has_whitespace(
        self, sample_config: Config
    ) -> None:
        """Handles status output with trailing whitespace."""
        vm = LimaVM(sample_config)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="Running\n")

            assert vm.is_running() is True


class TestLimaVMGetSshConfigPath:
    """Tests for LimaVM.get_ssh_config_path()."""

    def test_returns_correct_path(self, sample_config: Config) -> None:
        """Returns the expected SSH config path."""
        vm = LimaVM(sample_config)

        expected = Path.home() / ".lima" / "clauded-test1234" / "ssh.config"
        assert vm.get_ssh_config_path() == expected


class TestLimaVMGenerateLimaConfig:
    """Tests for LimaVM._generate_lima_config()."""

    def test_generates_correct_structure(self, sample_config: Config) -> None:
        """Generated config has correct structure."""
        vm = LimaVM(sample_config)

        config = vm._generate_lima_config()

        assert config["vmType"] == "vz"
        assert config["os"] == "Linux"
        assert config["arch"] == "aarch64"

    def test_uses_config_resources(self, sample_config: Config) -> None:
        """Generated config uses resource settings from config."""
        vm = LimaVM(sample_config)

        config = vm._generate_lima_config()

        assert config["cpus"] == 4
        assert config["memory"] == "8GiB"
        assert config["disk"] == "20GiB"

    def test_sets_default_alpine_image(self, sample_config: Config) -> None:
        """Generated config uses default Alpine image without digest verification.

        Alpine rebuilds images in-place for security patches without changing
        the version, which breaks hash verification. We rely on HTTPS transport
        security instead.
        """
        sample_config.vm_image = None
        vm = LimaVM(sample_config)

        config = vm._generate_lima_config()

        alpine = get_alpine_image()
        assert len(config["images"]) == 1
        assert config["images"][0]["location"] == alpine["url"]
        assert config["images"][0]["arch"] == "aarch64"
        # No digest - Alpine images are rebuilt in-place
        assert "digest" not in config["images"][0]

    def test_uses_custom_image_when_set(self, sample_config: Config) -> None:
        """Generated config uses custom image URL when vm_image is set."""
        sample_config.vm_image = "https://example.com/custom-alpine.qcow2"
        vm = LimaVM(sample_config)

        config = vm._generate_lima_config()

        assert len(config["images"]) == 1
        assert (
            config["images"][0]["location"] == "https://example.com/custom-alpine.qcow2"
        )
        assert config["images"][0]["arch"] == "aarch64"
        # Custom images don't have checksum verification (user's responsibility)
        assert "digest" not in config["images"][0]

    def test_configures_virtiofs_mount(
        self, sample_config: Config, tmp_path: Path
    ) -> None:
        """Generated config has virtiofs mount for project directory."""
        vm = LimaVM(sample_config)

        with (
            patch("clauded.lima.Path.home", return_value=tmp_path),
            patch("clauded.lima.getpass.getuser", return_value="testuser"),
        ):
            config = vm._generate_lima_config()

        assert config["mountType"] == "virtiofs"
        # First mount is always the project directory
        assert config["mounts"][0]["location"] == "/path/to/project"
        assert config["mounts"][0]["mountPoint"] == "/path/to/project"
        assert config["mounts"][0]["writable"] is True

    def test_mounts_home_directories_when_exist(
        self, sample_config: Config, tmp_path: Path
    ) -> None:
        """Mounts ~/.claude read-write when it exists."""
        vm = LimaVM(sample_config)

        # Create test directory
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()

        with (
            patch("clauded.lima.Path.home", return_value=tmp_path),
            patch("clauded.lima.getpass.getuser", return_value="testuser"),
        ):
            config = vm._generate_lima_config()

        assert len(config["mounts"]) == 2

        # Check .claude mount
        claude_mount = config["mounts"][1]
        assert claude_mount["location"] == str(claude_dir)
        assert claude_mount["mountPoint"] == "/home/testuser.linux/.claude"
        assert claude_mount["writable"] is True

    def test_creates_claude_dir_when_not_exist(
        self, sample_config: Config, tmp_path: Path
    ) -> None:
        """Creates and mounts ~/.claude even when it doesn't exist on host."""
        vm = LimaVM(sample_config)
        claude_dir = tmp_path / ".claude"

        assert not claude_dir.exists()

        with (
            patch("clauded.lima.Path.home", return_value=tmp_path),
            patch("clauded.lima.getpass.getuser", return_value="testuser"),
        ):
            config = vm._generate_lima_config()

        # Should create the directory
        assert claude_dir.exists()
        # Should mount it
        assert len(config["mounts"]) == 2
        assert config["mounts"][1]["location"] == str(claude_dir)

    def test_mount_points_must_be_absolute_paths(
        self, sample_config: Config, tmp_path: Path
    ) -> None:
        """Lima requires mount points to be absolute paths, not starting with ~."""
        vm = LimaVM(sample_config)

        # Create test directory
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()

        with (
            patch("clauded.lima.Path.home", return_value=tmp_path),
            patch("clauded.lima.getpass.getuser", return_value="testuser"),
        ):
            config = vm._generate_lima_config()

        # All mount points must be absolute paths (not starting with ~)
        for mount in config["mounts"]:
            mount_point = mount["mountPoint"]
            assert not mount_point.startswith("~"), (
                f"mountPoint '{mount_point}' must not start with '~' - "
                "Lima requires absolute paths"
            )
            assert mount_point.startswith(
                "/"
            ), f"mountPoint '{mount_point}' must be an absolute path"

    def test_disables_containerd(self, sample_config: Config) -> None:
        """Generated config disables containerd."""
        vm = LimaVM(sample_config)

        config = vm._generate_lima_config()

        assert config["containerd"]["system"] is False
        assert config["containerd"]["user"] is False

    def test_no_provision_scripts(self, sample_config: Config, tmp_path: Path) -> None:
        """Generated config has no provision scripts (handled by Ansible)."""
        vm = LimaVM(sample_config)

        with (
            patch("clauded.lima.Path.home", return_value=tmp_path),
            patch("clauded.lima.getpass.getuser", return_value="testuser"),
        ):
            config = vm._generate_lima_config()

        # No provision scripts - all configuration handled by Ansible
        # Lima user provisions fail on Alpine due to home directory permissions
        assert "provision" not in config


class TestLimaVMCommands:
    """Tests for LimaVM command methods."""

    def test_start_calls_limactl_start(self, sample_config: Config) -> None:
        """start() calls limactl start with VM name."""
        vm = LimaVM(sample_config)

        with patch("subprocess.run") as mock_run:
            vm.start()

        mock_run.assert_called_once_with(
            ["limactl", "start", "--tty=false", "clauded-test1234"],
            check=True,
            stdin=subprocess.DEVNULL,
        )

    def test_stop_calls_limactl_stop(self, sample_config: Config) -> None:
        """stop() calls limactl stop with VM name."""
        vm = LimaVM(sample_config)

        with patch("subprocess.run") as mock_run:
            vm.stop()

        mock_run.assert_called_once_with(
            ["limactl", "stop", "clauded-test1234"],
            check=True,
        )

    def test_destroy_calls_limactl_delete(self, sample_config: Config) -> None:
        """destroy() calls limactl delete with -f flag."""
        vm = LimaVM(sample_config)

        with patch("subprocess.run") as mock_run:
            vm.destroy()

        mock_run.assert_called_once_with(
            ["limactl", "delete", "-f", "clauded-test1234"],
            check=True,
        )

    def test_shell_calls_limactl_shell_with_claude(self, sample_config: Config) -> None:
        """shell() calls limactl shell with claude command and skip permissions flag."""
        vm = LimaVM(sample_config)

        with patch("subprocess.run") as mock_run:
            vm.shell()

        # Last call should be the actual shell command (first call fetches metadata)
        mock_run.assert_called_with(
            [
                "limactl",
                "shell",
                "--workdir",
                "/path/to/project",
                "clauded-test1234",
                "bash",
                "-lic",
                "USE_BUILTIN_RIPGREP=0 claude --dangerously-skip-permissions",
            ]
        )

    def test_shell_without_skip_permissions(self, sample_config: Config) -> None:
        """shell() omits skip permissions flag when disabled."""
        sample_config.claude_dangerously_skip_permissions = False
        vm = LimaVM(sample_config)

        with patch("subprocess.run") as mock_run:
            vm.shell()

        # Last call should be the actual shell command (first call fetches metadata)
        mock_run.assert_called_with(
            [
                "limactl",
                "shell",
                "--workdir",
                "/path/to/project",
                "clauded-test1234",
                "bash",
                "-lic",
                "USE_BUILTIN_RIPGREP=0 claude",
            ]
        )


class TestLimaVMErrorHandling:
    """Tests for LimaVM subprocess error handling."""

    def test_create_handles_lima_not_installed(
        self, sample_config: Config, tmp_path: Path
    ) -> None:
        """create() exits with message when limactl is not found."""
        vm = LimaVM(sample_config)

        with (
            patch("clauded.lima.Path.home", return_value=tmp_path),
            patch("clauded.lima.getpass.getuser", return_value="testuser"),
            patch("subprocess.run", side_effect=FileNotFoundError()),
        ):
            with pytest.raises(SystemExit) as exc_info:
                vm.create()

        assert exc_info.value.code == 1

    def test_create_handles_subprocess_failure(
        self, sample_config: Config, tmp_path: Path
    ) -> None:
        """create() exits with message when limactl start fails."""
        vm = LimaVM(sample_config)

        with (
            patch("clauded.lima.Path.home", return_value=tmp_path),
            patch("clauded.lima.getpass.getuser", return_value="testuser"),
            patch(
                "subprocess.run",
                side_effect=subprocess.CalledProcessError(1, "limactl"),
            ),
        ):
            with pytest.raises(SystemExit) as exc_info:
                vm.create()

        assert exc_info.value.code == 1

    def test_start_handles_lima_not_installed(self, sample_config: Config) -> None:
        """start() exits with message when limactl is not found."""
        vm = LimaVM(sample_config)

        with patch("subprocess.run", side_effect=FileNotFoundError()):
            with pytest.raises(SystemExit) as exc_info:
                vm.start()

        assert exc_info.value.code == 1

    def test_start_handles_subprocess_failure(self, sample_config: Config) -> None:
        """start() exits with message when limactl start fails."""
        vm = LimaVM(sample_config)

        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "limactl"),
        ):
            with pytest.raises(SystemExit) as exc_info:
                vm.start()

        assert exc_info.value.code == 1

    def test_stop_handles_lima_not_installed(self, sample_config: Config) -> None:
        """stop() exits with message when limactl is not found."""
        vm = LimaVM(sample_config)

        with patch("subprocess.run", side_effect=FileNotFoundError()):
            with pytest.raises(SystemExit) as exc_info:
                vm.stop()

        assert exc_info.value.code == 1

    def test_stop_handles_subprocess_failure(self, sample_config: Config) -> None:
        """stop() exits with message when limactl stop fails."""
        vm = LimaVM(sample_config)

        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "limactl"),
        ):
            with pytest.raises(SystemExit) as exc_info:
                vm.stop()

        assert exc_info.value.code == 1

    def test_destroy_handles_lima_not_installed(self, sample_config: Config) -> None:
        """destroy() exits with message when limactl is not found."""
        vm = LimaVM(sample_config)

        with patch("subprocess.run", side_effect=FileNotFoundError()):
            with pytest.raises(SystemExit) as exc_info:
                vm.destroy()

        assert exc_info.value.code == 1

    def test_destroy_handles_subprocess_failure(self, sample_config: Config) -> None:
        """destroy() exits with message when limactl delete fails."""
        vm = LimaVM(sample_config)

        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "limactl"),
        ):
            with pytest.raises(SystemExit) as exc_info:
                vm.destroy()

        assert exc_info.value.code == 1
