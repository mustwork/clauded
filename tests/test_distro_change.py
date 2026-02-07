"""Tests for distro change detection and VM recreation flow."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from clauded.cli import main


@pytest.fixture
def runner() -> CliRunner:
    """Provide Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def alpine_config_yaml() -> str:
    """Provide Alpine config YAML for testing."""
    return """version: "1"
vm:
  name: clauded-testcli1-abc123
  distro: alpine
  cpus: 4
  memory: 8GiB
  disk: 20GiB
mount:
  host: /test/project
  guest: /test/project
environment:
  python: "3.12"
  tools: []
  databases: []
  frameworks:
    - claude-code
"""


@pytest.fixture
def ubuntu_config_yaml() -> str:
    """Provide Ubuntu config YAML for testing."""
    return """version: "1"
vm:
  name: clauded-testcli1-abc123
  distro: ubuntu
  cpus: 4
  memory: 8GiB
  disk: 20GiB
mount:
  host: /test/project
  guest: /test/project
environment:
  python: "3.12"
  tools: []
  databases: []
  frameworks:
    - claude-code
"""


class TestDistroChangeDetection:
    """Test distro change detection via SSH."""

    def test_distro_match_no_warning(
        self, runner: CliRunner, alpine_config_yaml: str
    ) -> None:
        """No warning when VM distro matches config."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(alpine_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.name = "clauded-testcli1-abc123"
                mock_vm.get_vm_distro.return_value = "alpine"  # Matches config
                mock_vm.count_active_sessions.return_value = 0
                MockVM.return_value = mock_vm

                result = runner.invoke(main, [])

                # Should proceed normally without warning
                assert "Distribution mismatch" not in result.output
                mock_vm.shell.assert_called_once()
                mock_vm.destroy.assert_not_called()

    def test_distro_mismatch_shows_warning(
        self, runner: CliRunner, ubuntu_config_yaml: str
    ) -> None:
        """Warning shown when VM distro mismatches config."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(ubuntu_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.name = "clauded-testcli1-abc123"
                mock_vm.get_vm_distro.return_value = (
                    "alpine"  # Mismatches config (ubuntu)
                )
                mock_vm.count_active_sessions.return_value = 0
                MockVM.return_value = mock_vm

                # Simulate user declining recreation
                result = runner.invoke(main, [], input="n\n")

                # Should show mismatch warning
                assert "Distribution mismatch detected" in result.output
                assert "Current VM distro: alpine" in result.output
                assert "Config distro:     ubuntu" in result.output
                assert (
                    "Changing distribution requires recreating the VM" in result.output
                )
                assert "This will destroy all data in the VM" in result.output

    def test_distro_change_user_cancels(
        self, runner: CliRunner, ubuntu_config_yaml: str
    ) -> None:
        """User can cancel distro change."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(ubuntu_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.get_vm_distro.return_value = "alpine"  # Mismatch
                MockVM.return_value = mock_vm

                result = runner.invoke(main, [], input="n\n")

                # Should exit without destroying
                assert "Distro change cancelled" in result.output
                assert result.exit_code == 0
                mock_vm.destroy.assert_not_called()

    def test_distro_change_user_confirms_recreates_vm(
        self, runner: CliRunner, ubuntu_config_yaml: str
    ) -> None:
        """User confirming distro change destroys and recreates VM."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(ubuntu_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                with patch("clauded.cli.Provisioner") as MockProvisioner:
                    mock_vm = MagicMock()
                    mock_vm.exists.return_value = True
                    mock_vm.is_running.return_value = True
                    mock_vm.get_vm_distro.return_value = "alpine"  # Mismatch
                    mock_vm.name = "clauded-testcli1-abc123"
                    mock_vm.count_active_sessions.return_value = 0
                    MockVM.return_value = mock_vm

                    mock_provisioner = MagicMock()
                    MockProvisioner.return_value = mock_provisioner

                    runner.invoke(main, [], input="y\n")

                    # Should destroy old VM
                    mock_vm.destroy.assert_called_once()

                    # Should create new VM
                    mock_vm.create.assert_called_once()

                    # Should provision new VM
                    mock_provisioner.run.assert_called_once()

    def test_distro_change_not_checked_if_vm_stopped(
        self, runner: CliRunner, ubuntu_config_yaml: str
    ) -> None:
        """Distro change not checked if VM is stopped."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(ubuntu_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = False  # VM stopped
                mock_vm.name = "clauded-testcli1-abc123"
                mock_vm.count_active_sessions.return_value = 0
                MockVM.return_value = mock_vm

                runner.invoke(main, [])

                # get_vm_distro should not be called
                mock_vm.get_vm_distro.assert_not_called()

    def test_distro_change_not_checked_if_no_metadata(
        self, runner: CliRunner, alpine_config_yaml: str
    ) -> None:
        """Distro change not checked if VM has no metadata yet."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(alpine_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.get_vm_distro.return_value = None  # No metadata
                mock_vm.name = "clauded-testcli1-abc123"
                mock_vm.count_active_sessions.return_value = 0
                MockVM.return_value = mock_vm

                result = runner.invoke(main, [])

                # Should proceed normally without warning
                assert "Distribution mismatch" not in result.output
                mock_vm.shell.assert_called_once()

    def test_legacy_config_defaults_to_alpine_detection(
        self, runner: CliRunner
    ) -> None:
        """Legacy config (no vm_distro) defaults to alpine for detection."""
        # Legacy config without vm.distro field - defaults to alpine
        legacy_config = """version: "1"
vm:
  name: clauded-testcli1-abc123
  cpus: 4
  memory: 8GiB
  disk: 20GiB
mount:
  host: /test/project
  guest: /test/project
environment:
  python: "3.12"
"""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(legacy_config)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.get_vm_distro.return_value = "alpine"  # Matches default
                mock_vm.name = "clauded-testcli1-abc123"
                mock_vm.count_active_sessions.return_value = 0
                MockVM.return_value = mock_vm

                result = runner.invoke(main, [])

                # Should proceed normally without warning
                assert "Distribution mismatch" not in result.output
                mock_vm.shell.assert_called_once()


class TestLimaVMDistroRead:
    """Test LimaVM.get_vm_distro() method."""

    def test_get_vm_distro_reads_from_ssh(self) -> None:
        """get_vm_distro reads /etc/clauded.json via SSH."""
        from clauded.config import Config
        from clauded.lima import LimaVM

        config = Config(
            vm_name="test-vm",
            vm_distro="alpine",
            mount_host="/test",
            mount_guest="/test",
        )
        vm = LimaVM(config)

        with patch("clauded.lima.subprocess.run") as mock_run:
            # is_running() calls limactl list --format first
            list_result = MagicMock()
            list_result.returncode = 0
            list_result.stdout = "Running"

            # Then cat /etc/clauded.json via limactl shell
            cat_result = MagicMock()
            cat_result.returncode = 0
            cat_result.stdout = '{"distro": "alpine", "version": "1"}'

            mock_run.side_effect = [list_result, cat_result]

            distro = vm.get_vm_distro()

            # Should call limactl list (is_running) then limactl shell (cat)
            assert mock_run.call_count == 2  # One for is_running, one for cat
            cat_call_args = mock_run.call_args_list[1][0][0]
            assert cat_call_args == [
                "limactl",
                "shell",
                "test-vm",
                "cat",
                "/etc/clauded.json",
            ]

            assert distro == "alpine"

    def test_get_vm_distro_returns_none_if_file_not_found(self) -> None:
        """get_vm_distro returns None if /etc/clauded.json doesn't exist."""
        from clauded.config import Config
        from clauded.lima import LimaVM

        config = Config(
            vm_name="test-vm",
            vm_distro="alpine",
            mount_host="/test",
            mount_guest="/test",
        )
        vm = LimaVM(config)

        with patch("clauded.lima.subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 1  # File not found
            mock_run.return_value = mock_result

            distro = vm.get_vm_distro()

            assert distro is None

    def test_get_vm_distro_returns_none_if_vm_not_running(self) -> None:
        """get_vm_distro returns None if VM is not running."""
        from clauded.config import Config
        from clauded.lima import LimaVM

        config = Config(
            vm_name="test-vm",
            vm_distro="alpine",
            mount_host="/test",
            mount_guest="/test",
        )
        vm = LimaVM(config)

        with patch("clauded.lima.subprocess.run") as mock_run:
            # Mock is_running to return False
            with patch.object(vm, "is_running", return_value=False):
                distro = vm.get_vm_distro()

                # subprocess should not be called
                mock_run.assert_not_called()
                assert distro is None

    def test_get_vm_distro_handles_json_parse_error(self) -> None:
        """get_vm_distro returns None on JSON parse error."""
        from clauded.config import Config
        from clauded.lima import LimaVM

        config = Config(
            vm_name="test-vm",
            vm_distro="alpine",
            mount_host="/test",
            mount_guest="/test",
        )
        vm = LimaVM(config)

        with patch("clauded.lima.subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "invalid json"
            mock_run.return_value = mock_result

            distro = vm.get_vm_distro()

            assert distro is None


class TestDistroChangeE2E:
    """End-to-end tests for distro change workflow."""

    def test_alpine_to_ubuntu_change_flow(
        self, runner: CliRunner, alpine_config_yaml: str
    ) -> None:
        """Alpine config with Ubuntu VM triggers recreation on confirmation."""
        with runner.isolated_filesystem():
            # Start with Alpine config
            Path(".clauded.yaml").write_text(alpine_config_yaml)

            # Manually change config to Ubuntu (simulating user edit)
            ubuntu_config = alpine_config_yaml.replace(
                "distro: alpine", "distro: ubuntu"
            )
            Path(".clauded.yaml").write_text(ubuntu_config)

            with patch("clauded.cli.LimaVM") as MockVM:
                with patch("clauded.cli.Provisioner") as MockProvisioner:
                    mock_vm = MagicMock()
                    mock_vm.exists.return_value = True
                    mock_vm.is_running.return_value = True
                    mock_vm.get_vm_distro.return_value = "alpine"  # Still Alpine in VM
                    mock_vm.name = "clauded-testcli1-abc123"
                    mock_vm.count_active_sessions.return_value = 0
                    MockVM.return_value = mock_vm

                    mock_provisioner = MagicMock()
                    MockProvisioner.return_value = mock_provisioner

                    # User confirms recreation
                    result = runner.invoke(main, [], input="y\n")

                    # Verify full recreation flow
                    assert "Distribution mismatch detected" in result.output
                    assert "Current VM distro: alpine" in result.output
                    assert "Config distro:     ubuntu" in result.output

                    mock_vm.destroy.assert_called_once()
                    mock_vm.create.assert_called_once()
                    mock_provisioner.run.assert_called_once()

    def test_ubuntu_to_alpine_change_flow(
        self, runner: CliRunner, ubuntu_config_yaml: str
    ) -> None:
        """Ubuntu config with Alpine VM triggers recreation on confirmation."""
        with runner.isolated_filesystem():
            # Start with Ubuntu config
            Path(".clauded.yaml").write_text(ubuntu_config_yaml)

            # Change config to Alpine
            alpine_config = ubuntu_config_yaml.replace(
                "distro: ubuntu", "distro: alpine"
            )
            Path(".clauded.yaml").write_text(alpine_config)

            with patch("clauded.cli.LimaVM") as MockVM:
                with patch("clauded.cli.Provisioner") as MockProvisioner:
                    mock_vm = MagicMock()
                    mock_vm.exists.return_value = True
                    mock_vm.is_running.return_value = True
                    mock_vm.get_vm_distro.return_value = "ubuntu"  # Still Ubuntu in VM
                    mock_vm.name = "clauded-testcli1-abc123"
                    mock_vm.count_active_sessions.return_value = 0
                    MockVM.return_value = mock_vm

                    mock_provisioner = MagicMock()
                    MockProvisioner.return_value = mock_provisioner

                    result = runner.invoke(main, [], input="y\n")

                    assert "Current VM distro: ubuntu" in result.output
                    assert "Config distro:     alpine" in result.output

                    mock_vm.destroy.assert_called_once()
                    mock_vm.create.assert_called_once()
