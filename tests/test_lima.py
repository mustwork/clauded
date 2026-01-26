"""Tests for clauded.lima module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from clauded.config import Config
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
        mount_guest="/workspace",
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

    def test_sets_ubuntu_image(self, sample_config: Config) -> None:
        """Generated config uses Ubuntu Jammy cloud image."""
        vm = LimaVM(sample_config)

        config = vm._generate_lima_config()

        assert len(config["images"]) == 1
        assert "ubuntu" in config["images"][0]["location"]
        assert "jammy" in config["images"][0]["location"]
        assert config["images"][0]["arch"] == "aarch64"

    def test_configures_virtiofs_mount(self, sample_config: Config) -> None:
        """Generated config has virtiofs mount for project directory."""
        vm = LimaVM(sample_config)

        config = vm._generate_lima_config()

        assert config["mountType"] == "virtiofs"
        assert len(config["mounts"]) == 1
        assert config["mounts"][0]["location"] == "/path/to/project"
        assert config["mounts"][0]["mountPoint"] == "/workspace"
        assert config["mounts"][0]["writable"] is True

    def test_disables_containerd(self, sample_config: Config) -> None:
        """Generated config disables containerd."""
        vm = LimaVM(sample_config)

        config = vm._generate_lima_config()

        assert config["containerd"]["system"] is False
        assert config["containerd"]["user"] is False

    def test_includes_provision_script(self, sample_config: Config) -> None:
        """Generated config includes basic provisioning script."""
        vm = LimaVM(sample_config)

        config = vm._generate_lima_config()

        assert len(config["provision"]) == 1
        assert config["provision"][0]["mode"] == "system"
        assert "apt-get update" in config["provision"][0]["script"]
        assert "ca-certificates" in config["provision"][0]["script"]


class TestLimaVMCommands:
    """Tests for LimaVM command methods."""

    def test_start_calls_limactl_start(self, sample_config: Config) -> None:
        """start() calls limactl start with VM name."""
        vm = LimaVM(sample_config)

        with patch("subprocess.run") as mock_run:
            vm.start()

        mock_run.assert_called_once_with(
            ["limactl", "start", "clauded-test1234"],
            check=True,
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

    def test_shell_calls_limactl_shell_with_workdir(
        self, sample_config: Config
    ) -> None:
        """shell() calls limactl shell with workdir option."""
        vm = LimaVM(sample_config)

        with patch("subprocess.run") as mock_run:
            vm.shell()

        mock_run.assert_called_once_with(
            ["limactl", "shell", "clauded-test1234", "--workdir", "/workspace"],
        )
