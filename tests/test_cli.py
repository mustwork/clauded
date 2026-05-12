"""Tests for clauded.cli module."""

from importlib.metadata import version
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from clauded.cli import _sigint_handler, main


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
  cpus: 1
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

    def test_help_shows_version_option(self, runner: CliRunner) -> None:
        """Help shows --version option."""
        result = runner.invoke(main, ["--help"])

        assert "--version" in result.output


class TestCliVersion:
    """Tests for CLI --version option."""

    def test_version_shows_package_version(self, runner: CliRunner) -> None:
        """--version shows the package version from metadata."""
        result = runner.invoke(main, ["--version"])

        assert result.exit_code == 0
        expected_version = version("clauded")
        assert f"clauded, version {expected_version}" in result.output

    def test_version_exits_cleanly(self, runner: CliRunner) -> None:
        """--version exits with code 0."""
        result = runner.invoke(main, ["--version"])

        assert result.exit_code == 0


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

    def test_destroy_works_on_legacy_alpine_config(self, runner: CliRunner) -> None:
        """--destroy must operate on a legacy `vm.distro: alpine` config so the
        FR5 migration message (step 1: clauded --destroy) is actually
        executable. Without this bypass, users would be stuck."""
        alpine_yaml = """version: "1"
vm:
  name: clauded-testcli-legacy
  cpus: 1
  memory: 8GiB
  disk: 20GiB
  distro: alpine
mount:
  host: /test/project
  guest: /workspace
environment:
  tools: []
  databases: []
  frameworks:
    - claude-code
"""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(alpine_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                MockVM.return_value = mock_vm

                result = runner.invoke(main, ["--destroy"], input="n\n")

                assert result.exit_code == 0
                assert "Alpine Linux is no longer supported" not in result.output
                mock_vm.destroy.assert_called_once()


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
        """--stop calls vm.stop() when VM is running and no other sessions."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.count_active_sessions.return_value = 0
                MockVM.return_value = mock_vm

                result = runner.invoke(main, ["--stop"])

                assert result.exit_code == 0
                mock_vm.stop.assert_called_once()

    def test_stop_skips_when_other_sessions_active(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """--stop skips stopping when other sessions are active."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.count_active_sessions.return_value = 2
                mock_vm.name = "clauded-testcli1"
                MockVM.return_value = mock_vm

                result = runner.invoke(main, ["--stop"])

                assert result.exit_code == 0
                assert "2 active session(s)" in result.output
                mock_vm.stop.assert_not_called()

    def test_force_stop_ignores_active_sessions(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """--force-stop stops VM even when other sessions are active."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.count_active_sessions.return_value = 2
                MockVM.return_value = mock_vm

                result = runner.invoke(main, ["--force-stop"])

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
            # Bypass TTY check for this test
            with patch("clauded.cli._require_interactive_terminal", return_value=None):
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
                mock_vm.count_active_sessions.return_value = 0
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
                mock_vm.count_active_sessions.return_value = 0
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
                mock_vm.count_active_sessions.return_value = 0
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
                mock_vm.count_active_sessions.return_value = 0
                MockVM.return_value = mock_vm

                with patch("clauded.cli.Provisioner") as MockProvisioner:
                    mock_provisioner = MagicMock()
                    MockProvisioner.return_value = mock_provisioner

                    runner.invoke(main, ["--reprovision"])

                    mock_provisioner.run.assert_called_once()
                    mock_vm.shell.assert_called_once()

    def test_reprovision_starts_stopped_vm_and_provisions(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """--reprovision starts stopped VM then runs provisioner."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = False
                mock_vm.name = "clauded-testcli1"
                mock_vm.count_active_sessions.return_value = 0
                MockVM.return_value = mock_vm

                with patch("clauded.cli.Provisioner") as MockProvisioner:
                    mock_provisioner = MagicMock()
                    MockProvisioner.return_value = mock_provisioner

                    runner.invoke(main, ["--reprovision"])

                    mock_vm.start.assert_called_once()
                    mock_provisioner.run.assert_called_once()
                    mock_vm.shell.assert_called_once()


class TestCliNonInteractiveDetection:
    """Tests for non-interactive terminal detection."""

    def test_wizard_requires_interactive_terminal(self, runner: CliRunner) -> None:
        """Wizard exits with error when stdin is not a TTY.

        CliRunner doesn't provide a TTY by default, so the wizard should fail
        with an informative error message.
        """
        with runner.isolated_filesystem():
            # CliRunner doesn't provide a TTY, so wizard should fail immediately
            result = runner.invoke(main, ["--no-detect"])

            assert result.exit_code == 1
            assert "Interactive terminal required" in result.output

    def test_edit_requires_interactive_terminal(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """--edit exits with error when stdin is not a TTY."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.name = "clauded-testcli1"
                MockVM.return_value = mock_vm

                # CliRunner doesn't provide a TTY, so edit should fail
                result = runner.invoke(main, ["--edit"])

                assert result.exit_code == 1
                assert "Interactive terminal required" in result.output

    def test_keyboard_interrupt_during_wizard_cancels_cleanly(
        self, runner: CliRunner
    ) -> None:
        """KeyboardInterrupt during wizard prints 'Setup cancelled.' and exits 130."""
        with runner.isolated_filesystem():
            # Bypass TTY check, then trigger KeyboardInterrupt in wizard
            with patch("clauded.cli._require_interactive_terminal", return_value=None):
                with patch("clauded.cli.wizard") as mock_wizard:
                    mock_wizard.run.side_effect = KeyboardInterrupt()

                    result = runner.invoke(main, ["--no-detect"])

                    # Exit code 130 = 128 + SIGINT (2), standard convention
                    assert result.exit_code == 130
                    assert "Setup cancelled" in result.output

    def test_keyboard_interrupt_during_edit_cancels_cleanly(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """KeyboardInterrupt during edit prints 'Edit cancelled.' and exits 130."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.name = "clauded-testcli1"
                MockVM.return_value = mock_vm

                # Bypass TTY check, then trigger KeyboardInterrupt in wizard
                with patch(
                    "clauded.cli._require_interactive_terminal", return_value=None
                ):
                    with patch("clauded.cli.run_edit_with_detection") as mock_edit:
                        mock_edit.side_effect = KeyboardInterrupt()

                        result = runner.invoke(main, ["--edit"])

                        # Exit code 130 = 128 + SIGINT (2), standard convention
                        assert result.exit_code == 130
                        assert "Edit cancelled" in result.output

    def test_no_partial_config_file_on_cancel(self, runner: CliRunner) -> None:
        """Config file should not exist if wizard is cancelled."""
        with runner.isolated_filesystem():
            config_path = Path(".clauded.yaml")

            # Bypass TTY check, then trigger KeyboardInterrupt
            with patch("clauded.cli._require_interactive_terminal", return_value=None):
                with patch("clauded.cli.wizard") as mock_wizard:
                    mock_wizard.run.side_effect = KeyboardInterrupt()

                    runner.invoke(main, ["--no-detect"])

                    # Ensure no partial config was left behind
                    assert not config_path.exists()


class TestSigintHandler:
    """Tests for SIGINT signal handler."""

    def test_sigint_handler_raises_keyboard_interrupt(self) -> None:
        """SIGINT handler raises KeyboardInterrupt to allow cleanup."""
        with pytest.raises(KeyboardInterrupt):
            _sigint_handler(2, None)

    def test_sigint_handler_prints_cleanup_message(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """SIGINT handler prints cleanup message to stderr."""
        try:
            _sigint_handler(2, None)
        except KeyboardInterrupt:
            pass

        captured = capsys.readouterr()
        assert "Interrupted. Cleaning up..." in captured.err


class TestCliEditWorkflow:
    """Tests for --edit workflow."""

    def test_edit_without_config_fails(self, runner: CliRunner) -> None:
        """--edit fails when no .clauded.yaml exists."""
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["--edit"])

            assert result.exit_code == 1
            assert "No .clauded.yaml found" in result.output

    def test_edit_without_vm_fails(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """--edit fails when VM doesn't exist."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = False
                mock_vm.name = "clauded-testcli1"
                MockVM.return_value = mock_vm

                result = runner.invoke(main, ["--edit"])

                assert result.exit_code == 1
                assert "does not exist" in result.output

    def test_edit_starts_stopped_vm_before_wizard(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """--edit starts stopped VM before running wizard."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = False
                mock_vm.name = "clauded-testcli1"
                MockVM.return_value = mock_vm

                # Bypass TTY check, but wizard will still fail without real TTY
                with patch(
                    "clauded.cli._require_interactive_terminal", return_value=None
                ):
                    with patch("clauded.cli.run_edit_with_detection") as mock_edit:
                        mock_config = MagicMock()
                        mock_edit.return_value = mock_config

                        with patch("clauded.cli.Provisioner") as MockProv:
                            mock_prov = MagicMock()
                            MockProv.return_value = mock_prov

                            runner.invoke(main, ["--edit"])

                            # VM should be started first
                            mock_vm.start.assert_called_once()

    def test_edit_runs_wizard_saves_and_provisions(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """--edit runs wizard, saves config, and provisions."""
        with runner.isolated_filesystem():
            config_path = Path(".clauded.yaml")
            config_path.write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.name = "clauded-testcli1"
                mock_vm.count_active_sessions.return_value = 0
                MockVM.return_value = mock_vm

                with patch(
                    "clauded.cli._require_interactive_terminal", return_value=None
                ):
                    with patch("clauded.cli.run_edit_with_detection") as mock_edit:
                        mock_config = MagicMock()
                        mock_config.mount_guest = "/workspace"
                        mock_config.vm_name = "clauded-testcli1"
                        # Mock atomic_update to yield None (no old VM name)
                        mock_context = mock_config.atomic_update.return_value
                        mock_context.__enter__.return_value = None
                        mock_edit.return_value = mock_config

                        with patch("clauded.cli.Provisioner") as MockProv:
                            mock_prov = MagicMock()
                            MockProv.return_value = mock_prov

                            result = runner.invoke(main, ["--edit"])

                            # run_edit_with_detection should be called
                            mock_edit.assert_called_once()
                            # atomic_update should be used (saves config internally)
                            mock_config.atomic_update.assert_called_once()
                            # Provisioner should run
                            mock_prov.run.assert_called_once()
                            # Shell should be entered
                            mock_vm.shell.assert_called_once()
                            assert "Updated .clauded.yaml" in result.output


class TestVmCleanupOnExit:
    """Regression tests for VM cleanup on shell exit.

    Bug report: bug-reports/vm-cleanup-on-exit-report.md
    Fixed: 2026-02-02
    Root cause: vm.shell() returns on exit, but VM stays running
    Protection: Ensures VM is stopped when user exits shell normally
    """

    def test_vm_stopped_after_shell_exit_normal_mode(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """VM is stopped after shell exits in normal mode when last session."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.count_active_sessions.return_value = 0
                mock_vm.name = "clauded-testcli1"
                mock_vm.get_vm_metadata.return_value = None
                MockVM.return_value = mock_vm

                # Mock click.confirm to return True (user confirms stop)
                with patch("clauded.cli.click.confirm", return_value=True):
                    runner.invoke(main, [])

                    # Verify shell was entered
                    mock_vm.shell.assert_called_once()
                    # Verify VM was stopped after shell exit
                    mock_vm.stop.assert_called_once()

    def test_vm_stopped_after_shell_exit_edit_mode(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """VM is stopped after shell exits in edit mode when last session."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.count_active_sessions.return_value = 0
                mock_vm.name = "clauded-testcli1"
                MockVM.return_value = mock_vm

                with patch(
                    "clauded.cli._require_interactive_terminal", return_value=None
                ):
                    with patch("clauded.cli.run_edit_with_detection") as mock_edit:
                        mock_config = MagicMock()
                        mock_config.mount_guest = "/workspace"
                        mock_config.vm_name = "clauded-testcli1"
                        mock_context = mock_config.atomic_update.return_value
                        mock_context.__enter__.return_value = None
                        mock_edit.return_value = mock_config

                        with patch("clauded.cli.Provisioner") as MockProv:
                            mock_prov = MagicMock()
                            MockProv.return_value = mock_prov

                            # Mock click.confirm to return True (user confirms stop)
                            with patch("clauded.cli.click.confirm", return_value=True):
                                runner.invoke(main, ["--edit"])

                                # Verify shell was entered
                                mock_vm.shell.assert_called_once()
                                # Verify VM was stopped after shell exit
                                mock_vm.stop.assert_called_once()

    def test_vm_not_stopped_if_already_stopped(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """VM stop is not called if VM is already stopped (defensive)."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                # Simulate VM stopping during shell session
                mock_vm.is_running.side_effect = [True, False]
                mock_vm.name = "clauded-testcli1"
                MockVM.return_value = mock_vm

                runner.invoke(main, [])

                # Verify shell was entered
                mock_vm.shell.assert_called_once()
                # Verify stop was NOT called (VM already stopped)
                mock_vm.stop.assert_not_called()

    def test_vm_not_stopped_if_other_sessions_active(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """VM is not stopped after shell exit when other sessions are active."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.count_active_sessions.return_value = 1  # One other session
                mock_vm.name = "clauded-testcli1"
                MockVM.return_value = mock_vm

                result = runner.invoke(main, [])

                # Verify shell was entered
                mock_vm.shell.assert_called_once()
                # Verify stop was NOT called (other sessions still active)
                mock_vm.stop.assert_not_called()
                # Verify message about other sessions
                assert "other active session(s)" in result.output

    def test_vm_not_stopped_when_user_declines_prompt(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """VM stays running when user answers No to confirmation prompt."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.count_active_sessions.return_value = 0
                mock_vm.name = "clauded-testcli1"
                MockVM.return_value = mock_vm

                # Mock click.confirm to return False (user declines)
                with patch("clauded.cli.click.confirm", return_value=False):
                    runner.invoke(main, [])

                    # Verify shell was entered
                    mock_vm.shell.assert_called_once()
                    # Verify VM was NOT stopped
                    mock_vm.stop.assert_not_called()

    def test_vm_not_stopped_when_user_cancels_with_ctrl_c(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """VM stays running when user cancels prompt with Ctrl+C."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.count_active_sessions.return_value = 0
                mock_vm.name = "clauded-testcli1"
                MockVM.return_value = mock_vm

                # Mock click.confirm to raise KeyboardInterrupt (Ctrl+C)
                with patch(
                    "clauded.cli.click.confirm", side_effect=KeyboardInterrupt()
                ):
                    runner.invoke(main, [])

                    # Verify shell was entered
                    mock_vm.shell.assert_called_once()
                    # Verify VM was NOT stopped (exception caught)
                    mock_vm.stop.assert_not_called()

    def test_vm_stopped_silently_in_non_interactive_mode(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """In non-interactive mode, VM stops silently without prompts or output."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.count_active_sessions.return_value = 0
                mock_vm.name = "clauded-testcli1"
                mock_vm.get_vm_metadata.return_value = None
                MockVM.return_value = mock_vm

                # Mock sys.stdin.isatty() to return False (non-interactive)
                with patch("clauded.cli.sys.stdin.isatty", return_value=False):
                    # click.confirm auto-returns True with default=True in non-TTY
                    with patch("clauded.cli.click.confirm", return_value=True):
                        result = runner.invoke(main, [])

                        # Verify shell was entered
                        mock_vm.shell.assert_called_once()
                        # Verify VM was stopped
                        mock_vm.stop.assert_called_once()
                        # Verify NO output about stopping (silent mode)
                        assert "Stopping VM" not in result.output
                        assert "stopped" not in result.output


class TestCliDetectWorkflow:
    """Tests for --detect workflow."""

    def test_detect_outputs_json(self, runner: CliRunner) -> None:
        """--detect outputs detection results as JSON."""
        with runner.isolated_filesystem():
            # Create a simple Python project
            Path("pyproject.toml").write_text(
                '[project]\nname = "test"\ndependencies = []'
            )

            result = runner.invoke(main, ["--detect"])

            assert result.exit_code == 0
            # Output should be valid JSON
            import json

            data = json.loads(result.output)
            assert "languages" in data
            assert "versions" in data
            assert "frameworks" in data
            assert "tools" in data
            assert "databases" in data
            assert "scan_stats" in data

    def test_detect_exits_without_wizard(self, runner: CliRunner) -> None:
        """--detect exits immediately without running wizard."""
        with runner.isolated_filesystem():
            with patch("clauded.cli.wizard") as mock_wizard:
                with patch("clauded.cli.run_edit_with_detection") as mock_edit:
                    with patch("clauded.cli.LimaVM"):
                        runner.invoke(main, ["--detect"])

                        # Wizard should not be called
                        mock_wizard.run.assert_not_called()
                        mock_edit.assert_not_called()

    def test_detect_does_not_require_config(self, runner: CliRunner) -> None:
        """--detect works without .clauded.yaml."""
        with runner.isolated_filesystem():
            # No config file exists
            result = runner.invoke(main, ["--detect"])

            assert result.exit_code == 0
            # Should still produce JSON output
            import json

            data = json.loads(result.output)
            assert isinstance(data, dict)

    def test_detect_with_debug_flag(self, runner: CliRunner) -> None:
        """--detect with --debug enables verbose logging."""
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["--detect", "--debug"])

            assert result.exit_code == 0
            # Debug output goes to stderr, but JSON should still be on stdout
            import json

            data = json.loads(result.output)
            assert isinstance(data, dict)


class TestReprovisionWithDetect:
    """Tests for --reprovision --detect workflow."""

    def test_reprovision_detect_runs_detection_and_merges(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """--reprovision --detect runs detection and merges with config."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.name = "clauded-testcli1"
                MockVM.return_value = mock_vm

                with patch("clauded.cli.apply_detection_to_config") as mock_apply:
                    # Simulate detection finding new requirements
                    mock_config = MagicMock()
                    mock_config.tools = ["docker", "uv"]  # uv is new
                    mock_config.databases = []
                    mock_config.python = "3.12"
                    mock_config.node = "20"
                    mock_config.java = None
                    mock_config.kotlin = None
                    mock_config.rust = None
                    mock_config.go = None
                    mock_config.dart = None
                    mock_config.c = None
                    mock_apply.return_value = (mock_config, True)

                    with patch("clauded.cli.Provisioner") as MockProv:
                        mock_prov = MagicMock()
                        MockProv.return_value = mock_prov

                        result = runner.invoke(main, ["--reprovision", "--detect"])

                        # Detection should be applied
                        mock_apply.assert_called_once()
                        # Config should be saved
                        mock_config.save.assert_called_once()
                        # Provisioner should run
                        mock_prov.run.assert_called_once()
                        # Output should mention updates
                        assert "Updated .clauded.yaml" in result.output

    def test_reprovision_detect_no_changes(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """--reprovision --detect with no new requirements still provisions."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.name = "clauded-testcli1"
                MockVM.return_value = mock_vm

                with patch("clauded.cli.apply_detection_to_config") as mock_apply:
                    # Simulate no changes
                    mock_config = MagicMock()
                    mock_apply.return_value = (mock_config, False)

                    with patch("clauded.cli.Provisioner") as MockProv:
                        mock_prov = MagicMock()
                        MockProv.return_value = mock_prov

                        result = runner.invoke(main, ["--reprovision", "--detect"])

                        # Detection should be applied
                        mock_apply.assert_called_once()
                        # Config should NOT be saved (no changes)
                        mock_config.save.assert_not_called()
                        # Provisioner should still run
                        mock_prov.run.assert_called_once()
                        # Output should indicate no changes
                        assert "No new requirements" in result.output

    def test_detect_alone_still_outputs_json(self, runner: CliRunner) -> None:
        """--detect alone (without --reprovision) still outputs JSON and exits."""
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["--detect"])

            assert result.exit_code == 0
            import json

            data = json.loads(result.output)
            assert "languages" in data


# --- Story 04 (--harness flag and harness-aware launch) -------------------


@pytest.fixture
def harness_config_yaml() -> str:
    """Config containing opencode in frameworks (AC-012 setup)."""
    return """version: "1"
harness: claude-code
vm:
  name: clauded-h4test
  cpus: 1
  memory: 8GiB
  disk: 20GiB
mount:
  host: /test/project
  guest: /test/project
environment:
  python: "3.12"
  node: "20"
  tools:
    - docker
  databases: []
  frameworks:
    - claude-code
    - codex
    - opencode
"""


@pytest.fixture
def harness_config_yaml_no_opencode() -> str:
    """Config WITHOUT opencode in frameworks (AC-014 setup)."""
    return """version: "1"
harness: claude-code
vm:
  name: clauded-h4test
  cpus: 1
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
    - codex
"""


class TestHarnessFlagOverride:
    """AC-012: --harness <name> overrides Config.harness for one invocation."""

    def test_harness_flag_overrides_config_one_invocation(
        self, runner: CliRunner, harness_config_yaml: str
    ) -> None:
        """--harness opencode launches opencode this run; .clauded.yaml unchanged."""
        with runner.isolated_filesystem():
            config_path = Path(".clauded.yaml")
            config_path.write_text(harness_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.name = "clauded-h4test"
                mock_vm.count_active_sessions.return_value = 0
                MockVM.return_value = mock_vm

                result = runner.invoke(main, ["--harness", "opencode"])

            assert result.exit_code == 0, result.output
            # LimaVM was constructed with harness_override='opencode' at least once.
            override_seen = any(
                call.kwargs.get("harness_override") == "opencode"
                for call in MockVM.call_args_list
            )
            assert override_seen, MockVM.call_args_list

            # Persisted YAML harness key is unchanged.
            import yaml as _yaml

            with open(config_path) as f:
                data = _yaml.safe_load(f)
            assert data["harness"] == "claude-code"


class TestHarnessFlagInvalidValue:
    """AC-013: Click rejects values outside the allowed set with exit 2."""

    def test_harness_flag_invalid_value_exits_2(self, runner: CliRunner) -> None:
        """--harness gemini exits 2 with Click's 'Invalid value' error."""
        result = runner.invoke(main, ["--harness", "gemini"])

        assert result.exit_code == 2
        assert "Invalid value" in result.output


class TestHarnessFlagMissingFramework:
    """AC-014: --harness opencode against a config lacking opencode exits 1."""

    def test_harness_flag_missing_framework_exits_1(
        self, runner: CliRunner, harness_config_yaml_no_opencode: str
    ) -> None:
        """exit_code==1 with 'clauded --edit' in stderr."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(harness_config_yaml_no_opencode)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.name = "clauded-h4test"
                mock_vm.count_active_sessions.return_value = 0
                MockVM.return_value = mock_vm

                result = runner.invoke(main, ["--harness", "opencode"])

        assert result.exit_code == 1, result.output
        assert "clauded --edit" in result.output


class TestHarnessFlagModeFlagInteractions:
    """AC-015: --harness silently ignored with mode flags; warned with --edit."""

    def test_harness_flag_silently_ignored_with_destroy(
        self, runner: CliRunner, harness_config_yaml_no_opencode: str
    ) -> None:
        """--harness <whatever> with --destroy: behaviour matches plain --destroy.

        The validation gate must NOT fire here even though the chosen harness
        is not in frameworks; the mode handler returns early before validation.
        """
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(harness_config_yaml_no_opencode)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                MockVM.return_value = mock_vm

                result = runner.invoke(
                    main, ["--harness", "opencode", "--destroy"], input="n\n"
                )

            assert result.exit_code == 0, result.output
            mock_vm.destroy.assert_called_once()
            assert "clauded --edit" not in result.output

    def test_harness_flag_silently_ignored_with_stop(
        self, runner: CliRunner, harness_config_yaml_no_opencode: str
    ) -> None:
        """--harness with --stop: stop runs, no validation."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(harness_config_yaml_no_opencode)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.count_active_sessions.return_value = 0
                MockVM.return_value = mock_vm

                result = runner.invoke(main, ["--harness", "opencode", "--stop"])

            assert result.exit_code == 0, result.output
            mock_vm.stop.assert_called_once()

    def test_harness_flag_silently_ignored_with_reprovision(
        self, runner: CliRunner, harness_config_yaml_no_opencode: str
    ) -> None:
        """--harness with --reprovision: provisioner runs, no validation."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(harness_config_yaml_no_opencode)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.name = "clauded-h4test"
                mock_vm.count_active_sessions.return_value = 0
                MockVM.return_value = mock_vm

                with patch("clauded.cli.Provisioner") as MockProvisioner:
                    mock_provisioner = MagicMock()
                    MockProvisioner.return_value = mock_provisioner

                    result = runner.invoke(
                        main, ["--harness", "opencode", "--reprovision"]
                    )

            assert result.exit_code == 0, result.output
            assert "clauded --edit" not in result.output

    def test_harness_flag_silently_ignored_with_detect(self, runner: CliRunner) -> None:
        """--harness with --detect (alone): detect-only path returns early."""
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["--harness", "opencode", "--detect"])

            assert result.exit_code == 0
            import json

            data = json.loads(result.output)
            assert "languages" in data

    def test_harness_flag_warns_with_edit(
        self, runner: CliRunner, harness_config_yaml: str
    ) -> None:
        """--harness with --edit: one-line warning + wizard runs normally."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(harness_config_yaml)

            with patch("clauded.cli._require_interactive_terminal", return_value=None):
                with patch("clauded.cli.LimaVM") as MockVM:
                    mock_vm = MagicMock()
                    mock_vm.exists.return_value = True
                    mock_vm.is_running.return_value = True
                    mock_vm.name = "clauded-h4test"
                    mock_vm.count_active_sessions.return_value = 0
                    MockVM.return_value = mock_vm

                    with patch("clauded.cli.run_edit_with_detection") as mock_edit:
                        # Return a passthrough config (no atomic-update churn)
                        mock_edit.side_effect = lambda c, p, **kw: c

                        with patch("clauded.cli.Provisioner") as MockProvisioner:
                            MockProvisioner.return_value = MagicMock()

                            result = runner.invoke(
                                main, ["--harness", "opencode", "--edit"]
                            )

            assert "ignored with --edit" in result.output
            mock_edit.assert_called_once()

    def test_harness_flag_with_edit_drops_override(
        self, runner: CliRunner, harness_config_yaml: str
    ) -> None:
        """AC-015: --harness with --edit must NOT alter the post-edit shell launch.

        Regression for a bug where the warning was emitted but the override was
        still passed to LimaVM, so the launched shell silently ran the override
        harness instead of the persisted one.
        """
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(harness_config_yaml)

            with patch("clauded.cli._require_interactive_terminal", return_value=None):
                with patch("clauded.cli.LimaVM") as MockVM:
                    mock_vm = MagicMock()
                    mock_vm.exists.return_value = True
                    mock_vm.is_running.return_value = True
                    mock_vm.name = "clauded-h4test"
                    mock_vm.count_active_sessions.return_value = 0
                    MockVM.return_value = mock_vm

                    with patch("clauded.cli.run_edit_with_detection") as mock_edit:
                        mock_edit.side_effect = lambda c, p, **kw: c

                        with patch("clauded.cli.Provisioner") as MockProvisioner:
                            MockProvisioner.return_value = MagicMock()

                            runner.invoke(main, ["--harness", "opencode", "--edit"])

            override_values = [
                call.kwargs.get("harness_override") for call in MockVM.call_args_list
            ]
            assert override_values, "LimaVM was never constructed"
            assert all(v is None for v in override_values), (
                f"--harness override leaked into LimaVM construction under --edit; "
                f"expected all None, got {override_values}"
            )

    def test_harness_flag_with_reprovision_drops_override(
        self, runner: CliRunner, harness_config_yaml: str
    ) -> None:
        """AC-015: --harness with --reprovision must NOT alter the launched shell.

        Regression for a bug where the validation gate was correctly skipped,
        but the override was still propagated to LimaVM and the launched shell
        silently used the override harness.
        """
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(harness_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.name = "clauded-h4test"
                mock_vm.count_active_sessions.return_value = 0
                MockVM.return_value = mock_vm

                with patch("clauded.cli.Provisioner") as MockProvisioner:
                    MockProvisioner.return_value = MagicMock()

                    runner.invoke(main, ["--harness", "opencode", "--reprovision"])

            override_values = [
                call.kwargs.get("harness_override") for call in MockVM.call_args_list
            ]
            assert override_values, "LimaVM was never constructed"
            assert all(v is None for v in override_values), (
                f"--harness override leaked into LimaVM construction under "
                f"--reprovision; expected all None, got {override_values}"
            )

    def test_harness_flag_with_reboot_drops_override(
        self, runner: CliRunner, harness_config_yaml: str
    ) -> None:
        """AC-015: --harness with --reboot must NOT alter the launched shell."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(harness_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.name = "clauded-h4test"
                mock_vm.count_active_sessions.return_value = 0
                MockVM.return_value = mock_vm

                runner.invoke(main, ["--harness", "opencode", "--reboot"])

            override_values = [
                call.kwargs.get("harness_override") for call in MockVM.call_args_list
            ]
            assert override_values, "LimaVM was never constructed"
            assert all(v is None for v in override_values), (
                f"--harness override leaked into LimaVM construction under "
                f"--reboot; expected all None, got {override_values}"
            )


class TestHarnessPassthrough:
    """Tests for generic harness argument forwarding via ``clauded -- <args>``."""

    def test_passthrough_forwards_to_shell_on_launch_path(
        self,
        runner: CliRunner,
        sample_config_yaml: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Args after ``--`` reach LimaVM.shell as ``extra_argv``."""
        monkeypatch.setattr("sys.argv", ["clauded", "--", "--resume", "session-xyz"])
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.name = "clauded-testcli1"
                mock_vm.count_active_sessions.return_value = 0
                MockVM.return_value = mock_vm

                result = runner.invoke(main, ["--", "--resume", "session-xyz"])

                assert result.exit_code == 0, result.output
                mock_vm.shell.assert_called_once()
                kwargs = mock_vm.shell.call_args.kwargs
                assert kwargs["extra_argv"] == ("--resume", "session-xyz")

    def test_passthrough_requires_double_dash_separator(
        self,
        runner: CliRunner,
        sample_config_yaml: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Bare unknown flags without ``--`` produce an actionable error."""
        # sys.argv intentionally lacks "--" — the user typed `clauded --resume x`
        monkeypatch.setattr("sys.argv", ["clauded", "--resume", "x"])
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM"):
                result = runner.invoke(main, ["--resume", "x"])

            assert result.exit_code == 2
            assert "`--` separator" in result.output
            assert "--resume" in result.output

    def test_unknown_flag_before_double_dash_errors(
        self,
        runner: CliRunner,
        sample_config_yaml: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A typoed clauded flag before ``--`` must not silently forward."""
        monkeypatch.setattr(
            "sys.argv",
            ["clauded", "--typo", "--", "--resume", "x"],
        )
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM"):
                result = runner.invoke(main, ["--typo", "--", "--resume", "x"])

            assert result.exit_code == 2
            assert "unknown option(s):" in result.output
            assert "--typo" in result.output
            # The legitimate post-`--` payload should NOT appear in the error.
            assert "--resume" not in result.output.split("unknown option(s):")[1]

    def test_known_flag_plus_unknown_before_double_dash_errors(
        self,
        runner: CliRunner,
        sample_config_yaml: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Known clauded flags don't shield a sibling typo from rejection."""
        monkeypatch.setattr(
            "sys.argv",
            ["clauded", "--debug", "--typo", "--", "foo"],
        )
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM"):
                result = runner.invoke(main, ["--debug", "--typo", "--", "foo"])

            assert result.exit_code == 2
            assert "--typo" in result.output

    def test_legit_forward_with_dash_dash_in_value_succeeds(
        self,
        runner: CliRunner,
        sample_config_yaml: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Forwarded args that themselves start with ``--`` are not rejected."""
        monkeypatch.setattr(
            "sys.argv",
            ["clauded", "--", "--resume", "abc"],
        )
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.name = "clauded-testcli1"
                mock_vm.count_active_sessions.return_value = 0
                MockVM.return_value = mock_vm

                result = runner.invoke(main, ["--", "--resume", "abc"])

            assert result.exit_code == 0, result.output
            kwargs = mock_vm.shell.call_args.kwargs
            assert kwargs["extra_argv"] == ("--resume", "abc")

    def test_passthrough_rejected_on_destroy(
        self,
        runner: CliRunner,
        sample_config_yaml: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``--destroy`` never launches the harness, so passthrough is invalid."""
        monkeypatch.setattr("sys.argv", ["clauded", "--destroy", "--", "--resume", "x"])
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                MockVM.return_value = mock_vm

                result = runner.invoke(
                    main, ["--destroy", "--", "--resume", "x"], input="n\n"
                )

            assert result.exit_code == 2
            assert "not valid with --destroy" in result.output

    def test_passthrough_rejected_on_stop(
        self,
        runner: CliRunner,
        sample_config_yaml: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``--stop`` never launches the harness, so passthrough is invalid."""
        monkeypatch.setattr("sys.argv", ["clauded", "--stop", "--", "--resume", "x"])
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM"):
                result = runner.invoke(main, ["--stop", "--", "--resume", "x"])

            assert result.exit_code == 2
            assert "not valid with --stop" in result.output

    def test_no_passthrough_leaves_shell_extra_argv_empty(
        self,
        runner: CliRunner,
        sample_config_yaml: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When the user passes no extras, shell receives an empty tuple."""
        monkeypatch.setattr("sys.argv", ["clauded"])
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.name = "clauded-testcli1"
                mock_vm.count_active_sessions.return_value = 0
                MockVM.return_value = mock_vm

                runner.invoke(main, [])

                kwargs = mock_vm.shell.call_args.kwargs
                assert kwargs["extra_argv"] == ()


class TestNoUpdateFlag:
    """Tests for ``--no-update``: skip clauded-version + library update checks."""

    def test_no_update_skips_version_and_library_checks(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """--no-update bypasses _handle_version_change and _check_library_updates."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with (
                patch("clauded.cli.LimaVM") as MockVM,
                patch("clauded.cli._handle_version_change") as mock_version,
                patch("clauded.cli._check_library_updates") as mock_libraries,
            ):
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.name = "clauded-testcli1"
                mock_vm.count_active_sessions.return_value = 0
                MockVM.return_value = mock_vm

                result = runner.invoke(main, ["--no-update"])

                assert result.exit_code == 0, result.output
                mock_version.assert_not_called()
                mock_libraries.assert_not_called()
                assert "Skipping update checks" in result.output
                mock_vm.shell.assert_called_once()

    def test_default_runs_version_and_library_checks(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """Without --no-update, both checks fire on the running-VM path."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with (
                patch("clauded.cli.LimaVM") as MockVM,
                patch(
                    "clauded.cli._handle_version_change", return_value=False
                ) as mock_version,
                patch("clauded.cli._check_library_updates") as mock_libraries,
            ):
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.name = "clauded-testcli1"
                mock_vm.count_active_sessions.return_value = 0
                MockVM.return_value = mock_vm

                result = runner.invoke(main, [])

                assert result.exit_code == 0, result.output
                mock_version.assert_called_once()
                mock_libraries.assert_called_once()

    def test_reprovision_overrides_no_update(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """--reprovision wins over --no-update: explicit user intent prevails."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with (
                patch("clauded.cli.LimaVM") as MockVM,
                patch("clauded.cli._handle_version_change") as mock_version,
                patch("clauded.cli._check_library_updates") as mock_libraries,
                patch("clauded.cli.Provisioner") as MockProvisioner,
            ):
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.name = "clauded-testcli1"
                mock_vm.count_active_sessions.return_value = 0
                MockVM.return_value = mock_vm
                mock_provisioner = MagicMock()
                MockProvisioner.return_value = mock_provisioner

                result = runner.invoke(main, ["--reprovision", "--no-update"])

                assert result.exit_code == 0, result.output
                # Version/library checks are skipped (reprovision path already
                # bypasses them) but the explicit reprovision still runs.
                mock_version.assert_not_called()
                mock_libraries.assert_not_called()
                mock_provisioner.run.assert_called_once()


class TestQuietFlag:
    """Tests for the ``--quiet`` setup-output suppression flag."""

    def test_quiet_passes_quiet_to_lima_vm(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """LimaVM is constructed with quiet=True under --quiet."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.name = "clauded-testcli1"
                mock_vm.count_active_sessions.return_value = 0
                MockVM.return_value = mock_vm

                result = runner.invoke(main, ["--quiet"])

            assert result.exit_code == 0, result.output
            quiet_values = [call.kwargs.get("quiet") for call in MockVM.call_args_list]
            assert quiet_values and all(v is True for v in quiet_values)

    def test_quiet_suppresses_launch_banner(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """--quiet hides the 'Starting Claude Code in VM...' line."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.name = "clauded-testcli1"
                mock_vm.count_active_sessions.return_value = 0
                MockVM.return_value = mock_vm

                result = runner.invoke(main, ["--quiet"])

            assert result.exit_code == 0, result.output
            assert "Starting Claude Code" not in result.output

    def test_quiet_auto_accepts_last_session_stop_prompt(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """The 'This is the last active session...' prompt is skipped and
        the default action (stop) is taken without printing anything."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with patch("clauded.cli.LimaVM") as MockVM:
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                # is_running flips: True during launch, still True when
                # _stop_vm_if_last_session inspects it.
                mock_vm.is_running.return_value = True
                mock_vm.name = "clauded-testcli1"
                mock_vm.count_active_sessions.return_value = 0
                MockVM.return_value = mock_vm

                result = runner.invoke(main, ["--quiet"])

            assert result.exit_code == 0, result.output
            assert "last active session" not in result.output
            mock_vm.stop.assert_called_once()

    def test_quiet_rejected_with_edit(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """--quiet + --edit must fail fast; the wizard needs to print."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            result = runner.invoke(main, ["--quiet", "--edit"])

            assert result.exit_code == 2
            assert "--quiet cannot be combined with --edit" in result.output

    def test_quiet_rejected_with_detect_alone(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """--quiet + bare --detect must fail; detect's JSON is the output."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            result = runner.invoke(main, ["--quiet", "--detect"])

            assert result.exit_code == 2
            assert "--quiet cannot be combined with --detect" in result.output

    def test_quiet_rejected_when_wizard_would_run(self, runner: CliRunner) -> None:
        """--quiet without an existing .clauded.yaml errors out."""
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["--quiet"])

            assert result.exit_code == 2
            assert "requires an existing .clauded.yaml" in result.output

    def test_quiet_rejects_first_time_provisioning(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """If the VM doesn't exist, --quiet refuses (provisioning is noisy)."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with (
                patch("clauded.cli.LimaVM") as MockVM,
                patch("clauded.cli.Provisioner") as MockProvisioner,
            ):
                mock_vm = MagicMock()
                mock_vm.exists.return_value = False
                mock_vm.name = "clauded-testcli1"
                MockVM.return_value = mock_vm

                result = runner.invoke(main, ["--quiet"])

            assert result.exit_code == 2
            assert "does not exist" in result.output
            mock_vm.create.assert_not_called()
            MockProvisioner.assert_not_called()

    def test_quiet_rejected_with_reprovision(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """--quiet + --reprovision is contradictory and rejected upfront."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            result = runner.invoke(main, ["--quiet", "--reprovision"])

            assert result.exit_code == 2
            assert "--quiet cannot be combined with --reprovision" in result.output

    def test_quiet_implies_no_update(
        self, runner: CliRunner, sample_config_yaml: str
    ) -> None:
        """--quiet alone (no --no-update) still skips the update checks."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(sample_config_yaml)

            with (
                patch("clauded.cli.LimaVM") as MockVM,
                patch("clauded.cli._handle_version_change") as mock_version,
                patch("clauded.cli._check_library_updates") as mock_libraries,
            ):
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.name = "clauded-testcli1"
                mock_vm.count_active_sessions.return_value = 0
                MockVM.return_value = mock_vm

                result = runner.invoke(main, ["--quiet"])

            assert result.exit_code == 0, result.output
            mock_version.assert_not_called()
            mock_libraries.assert_not_called()
