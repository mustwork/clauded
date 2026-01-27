"""Tests for clauded.cli module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from clauded.cli import main


@pytest.fixture
def runner() -> CliRunner:
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def sample_config_yaml() -> str:
    """Sample .clauded.yaml content."""
    return """version: "1"
vm:
  name: clauded-testcli1
  cpus: 4
  memory: 8GiB
  disk: 20GiB
mount:
  host: /test/project
  guest: /workspace
environment:
  python: "3.12"
  node: "20"
  tools:
    - docker
  databases: []
  frameworks:
    - claude-code
"""


class TestCliHelp:
    """Tests for CLI help output."""

    def test_help_shows_description(self, runner: CliRunner) -> None:
        """Help shows tool description."""
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "clauded" in result.output
        assert "Lima VM" in result.output

    def test_help_shows_destroy_option(self, runner: CliRunner) -> None:
        """Help shows --destroy option."""
        result = runner.invoke(main, ["--help"])

        assert "--destroy" in result.output

    def test_help_shows_reprovision_option(self, runner: CliRunner) -> None:
        """Help shows --reprovision option."""
        result = runner.invoke(main, ["--help"])

        assert "--reprovision" in result.output

    def test_help_shows_stop_option(self, runner: CliRunner) -> None:
        """Help shows --stop option."""
        result = runner.invoke(main, ["--help"])

        assert "--stop" in result.output


class TestCliDestroy:
    """Tests for CLI --destroy option."""

    def test_destroy_without_config_fails(self, runner: CliRunner) -> None:
        """--destroy fails when no .clauded.yaml exists."""
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["--destroy"])

            assert result.exit_code == 1
            assert "No .clauded.yaml found" in result.output

    def test_destroy_with_config_calls_vm_destroy(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """--destroy calls vm.destroy() when config exists."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                MockVM.return_value = mock_vm

                # Decline to remove config
                result = runner.invoke(main, ["--destroy"], input="n\n")

                assert result.exit_code == 0
                mock_vm.destroy.assert_called_once()

    def test_destroy_removes_config_when_confirmed(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """--destroy removes .clauded.yaml when user confirms."""
        with runner.isolated_filesystem():
            config_path = Path(".clauded.yaml")
            config_path.write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                MockVM.return_value = mock_vm

                # Confirm removal
                result = runner.invoke(main, ["--destroy"], input="y\n")

                assert result.exit_code == 0
                assert not config_path.exists()
                assert "Removed .clauded.yaml" in result.output

    def test_destroy_keeps_config_when_declined(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """--destroy keeps .clauded.yaml when user declines."""
        with runner.isolated_filesystem():
            config_path = Path(".clauded.yaml")
            config_path.write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                MockVM.return_value = mock_vm

                # Decline removal
                result = runner.invoke(main, ["--destroy"], input="n\n")

                assert result.exit_code == 0
                assert config_path.exists()


class TestCliStop:
    """Tests for CLI --stop option."""

    def test_stop_without_config_fails(self, runner: CliRunner) -> None:
        """--stop fails when no .clauded.yaml exists."""
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["--stop"])

            assert result.exit_code == 1
            assert "No .clauded.yaml found" in result.output

    def test_stop_calls_vm_stop_when_running(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """--stop calls vm.stop() when VM is running."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                MockVM.return_value = mock_vm

                result = runner.invoke(main, ["--stop"])

                assert result.exit_code == 0
                mock_vm.stop.assert_called_once()

    def test_stop_shows_message_when_not_running(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """--stop shows message when VM is not running."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = False
                mock_vm.name = "clauded-testcli1"
                MockVM.return_value = mock_vm

                result = runner.invoke(main, ["--stop"])

                assert result.exit_code == 0
                assert "not running" in result.output
                mock_vm.stop.assert_not_called()


class TestCliNoConfig:
    """Tests for CLI when no config exists."""

    def test_runs_wizard_when_no_config(self, runner: CliRunner) -> None:
        """Runs wizard when no .clauded.yaml exists."""
        with runner.isolated_filesystem():
            with patch("clauded.cli.wizard") as mock_wizard:
                mock_config = MagicMock()
                mock_wizard.run.return_value = mock_config

                with patch("clauded.cli.LimaVM") as MockVM:
                    mock_vm = MagicMock()
                    mock_vm.exists.return_value = False
                    MockVM.return_value = mock_vm

                    with patch("clauded.cli.Provisioner"):
                        # This will try to run the wizard with --no-detect flag
                        runner.invoke(main, ["--no-detect"])

                        mock_wizard.run.assert_called_once()


class TestCliWithConfig:
    """Tests for CLI when config exists."""

    def test_creates_vm_when_not_exists(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """Creates and provisions VM when it doesn't exist."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = False
                mock_vm.name = "clauded-testcli1"
                MockVM.return_value = mock_vm

                with patch("clauded.cli.Provisioner") as MockProvisioner:
                    mock_provisioner = MagicMock()
                    MockProvisioner.return_value = mock_provisioner

                    runner.invoke(main, [])

                    mock_vm.create.assert_called_once()
                    mock_provisioner.run.assert_called_once()
                    mock_vm.shell.assert_called_once()

    def test_starts_vm_when_stopped(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """Starts VM when it exists but is stopped."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = False
                mock_vm.name = "clauded-testcli1"
                MockVM.return_value = mock_vm

                runner.invoke(main, [])

                mock_vm.start.assert_called_once()
                mock_vm.create.assert_not_called()
                mock_vm.shell.assert_called_once()

    def test_shells_directly_when_running(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """Shells directly into VM when it's already running."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.name = "clauded-testcli1"
                MockVM.return_value = mock_vm

                runner.invoke(main, [])

                mock_vm.start.assert_not_called()
                mock_vm.create.assert_not_called()
                mock_vm.shell.assert_called_once()

    def test_reprovision_runs_provisioner(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """--reprovision runs provisioner on running VM."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.name = "clauded-testcli1"
                MockVM.return_value = mock_vm

                with patch("clauded.cli.Provisioner") as MockProvisioner:
                    mock_provisioner = MagicMock()
                    MockProvisioner.return_value = mock_provisioner

                    runner.invoke(main, ["--reprovision"])

                    mock_provisioner.run.assert_called_once()
                    mock_vm.shell.assert_called_once()
