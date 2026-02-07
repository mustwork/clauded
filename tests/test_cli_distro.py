"""Tests for CLI --distro flag functionality."""

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
def sample_config_yaml() -> str:
    """Provide sample config YAML for testing."""
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
  tools:
    - docker
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
  tools:
    - docker
  databases: []
  frameworks:
    - claude-code
"""


class TestDistroFlag:
    """Test --distro CLI flag validation and conflicts."""

    def test_distro_flag_unsupported_shows_error(self, runner: CliRunner) -> None:
        """--distro with unsupported value shows error and exits."""
        result = runner.invoke(main, ["--distro", "invalid"])
        assert result.exit_code == 1
        assert "Unsupported distro 'invalid'" in result.output
        assert "alpine" in result.output
        assert "ubuntu" in result.output

    def test_distro_flag_alpine_accepted(self, runner: CliRunner) -> None:
        """--distro alpine is accepted as valid."""
        with runner.isolated_filesystem():
            # Default wizard uses detection, so patch run_with_detection
            with patch("clauded.cli._require_interactive_terminal"):
                with patch("clauded.cli.run_with_detection") as mock_run_with_detection:
                    with patch("clauded.cli.LimaVM") as MockVM:
                        with patch("clauded.cli.Provisioner") as MockProvisioner:
                            mock_vm = MagicMock()
                            mock_vm.exists.return_value = False
                            MockVM.return_value = mock_vm

                            mock_provisioner = MagicMock()
                            MockProvisioner.return_value = mock_provisioner

                            from clauded.config import Config

                            mock_config = Config(
                                vm_name="test-vm",
                                vm_distro="alpine",
                                mount_host="/test",
                                mount_guest="/test",
                            )
                            mock_run_with_detection.return_value = mock_config

                            # Should not error on validation
                            runner.invoke(main, ["--distro", "alpine"])

                            # run_with_detection should be called with distro_override
                            mock_run_with_detection.assert_called_once()
                            call_kwargs = mock_run_with_detection.call_args[1]
                            assert call_kwargs.get("distro_override") == "alpine"

    def test_distro_flag_ubuntu_accepted(self, runner: CliRunner) -> None:
        """--distro ubuntu is accepted as valid."""
        with runner.isolated_filesystem():
            # Default wizard uses detection
            with patch("clauded.cli._require_interactive_terminal"):
                with patch("clauded.cli.run_with_detection") as mock_run_with_detection:
                    with patch("clauded.cli.LimaVM") as MockVM:
                        with patch("clauded.cli.Provisioner") as MockProvisioner:
                            mock_vm = MagicMock()
                            mock_vm.exists.return_value = False
                            MockVM.return_value = mock_vm

                            mock_provisioner = MagicMock()
                            MockProvisioner.return_value = mock_provisioner

                            from clauded.config import Config

                            mock_config = Config(
                                vm_name="test-vm",
                                vm_distro="ubuntu",
                                mount_host="/test",
                                mount_guest="/test",
                            )
                            mock_run_with_detection.return_value = mock_config

                            runner.invoke(main, ["--distro", "ubuntu"])

                            mock_run_with_detection.assert_called_once()
                            call_kwargs = mock_run_with_detection.call_args[1]
                            assert call_kwargs.get("distro_override") == "ubuntu"

    def test_distro_flag_conflicts_with_existing_config_alpine(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """--distro ubuntu conflicts with existing alpine config."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            result = runner.invoke(main, ["--distro", "ubuntu"])
            assert result.exit_code == 1
            assert (
                "Error: --distro ubuntu conflicts with existing config" in result.output
            )
            assert "configured distro: alpine" in result.output

    def test_distro_flag_conflicts_with_existing_config_ubuntu(
        self, runner: CliRunner, ubuntu_config_yaml: str
    ) -> None:
        """--distro alpine conflicts with existing ubuntu config."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(ubuntu_config_yaml)

            result = runner.invoke(main, ["--distro", "alpine"])
            assert result.exit_code == 1
            assert (
                "Error: --distro alpine conflicts with existing config" in result.output
            )
            assert "configured distro: ubuntu" in result.output

    def test_distro_flag_matches_existing_config_no_error(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """--distro alpine with alpine config has no conflict."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.name = "clauded-testcli1-abc123"
                mock_vm.count_active_sessions.return_value = 0
                mock_vm.get_vm_distro.return_value = "alpine"  # Matches config
                MockVM.return_value = mock_vm

                result = runner.invoke(main, ["--distro", "alpine"])

                # Should proceed without conflict error
                assert "Error: --distro alpine conflicts" not in result.output
                mock_vm.shell.assert_called_once()

    def test_distro_flag_with_legacy_config_shows_error(
        self, runner: CliRunner
    ) -> None:
        """--distro flag with legacy config (no vm_distro) shows conflict error."""
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

            result = runner.invoke(main, ["--distro", "ubuntu"])
            assert result.exit_code == 1
            # Legacy configs default to alpine, so ubuntu conflicts
            assert (
                "Error: --distro ubuntu conflicts with existing config" in result.output
            )
            assert "configured distro: alpine" in result.output


class TestDistroFlagWithDetection:
    """Test --distro flag integration with detection."""

    def test_distro_flag_passed_to_run_with_detection(self, runner: CliRunner) -> None:
        """--distro flag is passed to run_with_detection."""
        with runner.isolated_filesystem():
            with patch("clauded.cli._require_interactive_terminal"):
                with patch("clauded.cli.run_with_detection") as mock_run_with_detection:
                    with patch("clauded.cli.LimaVM") as MockVM:
                        with patch("clauded.cli.Provisioner") as MockProvisioner:
                            mock_vm = MagicMock()
                            mock_vm.exists.return_value = False
                            MockVM.return_value = mock_vm

                            mock_provisioner = MagicMock()
                            MockProvisioner.return_value = mock_provisioner

                            from clauded.config import Config

                            mock_config = Config(
                                vm_name="test-vm",
                                vm_distro="ubuntu",
                                mount_host="/test",
                                mount_guest="/test",
                            )
                            mock_run_with_detection.return_value = mock_config

                            runner.invoke(main, ["--distro", "ubuntu"])

                            mock_run_with_detection.assert_called_once()
                            call_kwargs = mock_run_with_detection.call_args[1]
                            assert call_kwargs.get("distro_override") == "ubuntu"

    def test_no_detect_flag_passes_distro_to_wizard(self, runner: CliRunner) -> None:
        """--no-detect with --distro passes distro to wizard.run."""
        with runner.isolated_filesystem():
            with patch("clauded.cli._require_interactive_terminal"):
                with patch("clauded.cli.wizard.run") as mock_wizard:
                    with patch("clauded.cli.LimaVM") as MockVM:
                        with patch("clauded.cli.Provisioner") as MockProvisioner:
                            mock_vm = MagicMock()
                            mock_vm.exists.return_value = False
                            MockVM.return_value = mock_vm

                            mock_provisioner = MagicMock()
                            MockProvisioner.return_value = mock_provisioner

                            from clauded.config import Config

                            mock_config = Config(
                                vm_name="test-vm",
                                vm_distro="ubuntu",
                                mount_host="/test",
                                mount_guest="/test",
                            )
                            mock_wizard.return_value = mock_config

                            runner.invoke(main, ["--no-detect", "--distro", "ubuntu"])

                            mock_wizard.assert_called_once()
                            call_kwargs = mock_wizard.call_args[1]
                            assert call_kwargs.get("distro_override") == "ubuntu"
