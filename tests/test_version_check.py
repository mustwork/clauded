"""Tests for clauded version check and library update features."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from clauded.cli import main
from clauded.config import Config
from clauded.lima import LimaVM


@pytest.fixture
def runner() -> CliRunner:
    """Provide Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def config_yaml() -> str:
    """Provide config YAML for testing."""
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
    - codex
"""


# ---------------------------------------------------------------------------
# LimaVM.get_vm_metadata() tests
# ---------------------------------------------------------------------------


class TestGetVmMetadata:
    """Tests for LimaVM.get_vm_metadata()."""

    def test_returns_dict_on_success(self) -> None:
        """Valid JSON from VM returns parsed dict."""
        config = Config(
            vm_name="test-vm",
            vm_distro="alpine",
            mount_host="/test",
            mount_guest="/test",
        )
        vm = LimaVM(config)

        with patch("clauded.lima.subprocess.run") as mock_run:
            # is_running check
            list_result = MagicMock()
            list_result.stdout = "Running"
            # cat /etc/clauded.json
            cat_result = MagicMock()
            cat_result.returncode = 0
            cat_result.stdout = (
                '{"version": "0.1.0", "commit": "abc1234", "distro": "alpine"}'
            )
            mock_run.side_effect = [list_result, cat_result]

            result = vm.get_vm_metadata()

        assert result == {
            "version": "0.1.0",
            "commit": "abc1234",
            "distro": "alpine",
        }

    def test_returns_none_vm_not_running(self) -> None:
        """Returns None without subprocess call when VM not running."""
        config = Config(
            vm_name="test-vm",
            vm_distro="alpine",
            mount_host="/test",
            mount_guest="/test",
        )
        vm = LimaVM(config)

        with patch("clauded.lima.subprocess.run") as mock_run:
            with patch.object(vm, "is_running", return_value=False):
                result = vm.get_vm_metadata()

        mock_run.assert_not_called()
        assert result is None

    def test_returns_none_file_missing(self) -> None:
        """Returns None when /etc/clauded.json doesn't exist (returncode=1)."""
        config = Config(
            vm_name="test-vm",
            vm_distro="alpine",
            mount_host="/test",
            mount_guest="/test",
        )
        vm = LimaVM(config)

        with patch("clauded.lima.subprocess.run") as mock_run:
            # is_running
            list_result = MagicMock()
            list_result.stdout = "Running"
            # cat fails
            cat_result = MagicMock()
            cat_result.returncode = 1
            mock_run.side_effect = [list_result, cat_result]

            result = vm.get_vm_metadata()

        assert result is None

    def test_returns_none_json_error(self) -> None:
        """Returns None on invalid JSON."""
        config = Config(
            vm_name="test-vm",
            vm_distro="alpine",
            mount_host="/test",
            mount_guest="/test",
        )
        vm = LimaVM(config)

        with patch("clauded.lima.subprocess.run") as mock_run:
            list_result = MagicMock()
            list_result.stdout = "Running"
            cat_result = MagicMock()
            cat_result.returncode = 0
            cat_result.stdout = "not valid json"
            mock_run.side_effect = [list_result, cat_result]

            result = vm.get_vm_metadata()

        assert result is None


# ---------------------------------------------------------------------------
# clauded version check tests
# ---------------------------------------------------------------------------


class TestVersionCheck:
    """Tests for _handle_version_change() via CLI integration."""

    def test_version_match_no_prompt(self, runner: CliRunner, config_yaml: str) -> None:
        """Same commit means no prompt, shell entered directly."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(config_yaml)

            with (
                patch("clauded.cli.LimaVM") as MockVM,
                patch("clauded.cli.__commit__", "abc1234"),
                patch("clauded.cli.__version__", "0.1.0"),
                patch("clauded.cli._check_library_updates"),
            ):
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.name = "clauded-testcli1-abc123"
                mock_vm.get_vm_distro.return_value = "alpine"
                mock_vm.get_vm_metadata.return_value = {
                    "version": "0.1.0",
                    "commit": "abc1234",
                }
                mock_vm.count_active_sessions.return_value = 0
                MockVM.return_value = mock_vm

                result = runner.invoke(main, [])

                assert "clauded has been updated" not in result.output
                mock_vm.shell.assert_called_once()

    def test_version_mismatch_user_declines(
        self, runner: CliRunner, config_yaml: str
    ) -> None:
        """User declining reprovision → no provisioning, shell entered."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(config_yaml)

            with (
                patch("clauded.cli.LimaVM") as MockVM,
                patch("clauded.cli.Provisioner") as MockProv,
                patch("clauded.cli.__commit__", "def5678"),
                patch("clauded.cli.__version__", "0.2.0"),
                patch("clauded.cli._check_library_updates"),
            ):
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.name = "clauded-testcli1-abc123"
                mock_vm.get_vm_distro.return_value = "alpine"
                mock_vm.get_vm_metadata.return_value = {
                    "version": "0.1.0",
                    "commit": "abc1234",
                }
                mock_vm.count_active_sessions.return_value = 0
                MockVM.return_value = mock_vm

                # "n" for reprovision, "y" for stop
                result = runner.invoke(main, [], input="n\ny\n")

                assert "clauded has been updated" in result.output
                assert "Provisioned with: v0.1.0 (abc1234)" in result.output
                assert "Installed:        v0.2.0 (def5678)" in result.output
                MockProv.return_value.run.assert_not_called()
                mock_vm.shell.assert_called_once()

    def test_version_mismatch_user_confirms(
        self, runner: CliRunner, config_yaml: str
    ) -> None:
        """User confirming reprovision → Provisioner.run() called."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(config_yaml)

            with (
                patch("clauded.cli.LimaVM") as MockVM,
                patch("clauded.cli.Provisioner") as MockProv,
                patch("clauded.cli.__commit__", "def5678"),
                patch("clauded.cli.__version__", "0.2.0"),
            ):
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.name = "clauded-testcli1-abc123"
                mock_vm.get_vm_distro.return_value = "alpine"
                mock_vm.get_vm_metadata.return_value = {
                    "version": "0.1.0",
                    "commit": "abc1234",
                }
                mock_vm.count_active_sessions.return_value = 0
                MockVM.return_value = mock_vm

                mock_provisioner = MagicMock()
                MockProv.return_value = mock_provisioner

                runner.invoke(main, [], input="y\n")

                mock_provisioner.run.assert_called_once()

    def test_skipped_when_vm_created(self, runner: CliRunner) -> None:
        """New VM creation flow does not trigger version check."""
        with runner.isolated_filesystem():
            # No config → wizard flow → VM created from scratch
            with (
                patch("clauded.cli.LimaVM") as MockVM,
                patch("clauded.cli.Provisioner") as MockProv,
                patch("clauded.cli.run_with_detection") as mock_detect,
            ):
                mock_config = MagicMock(spec=Config)
                mock_config.vm_name = "clauded-new-abc123"
                mock_config.mount_guest = "/test"
                mock_config.frameworks = ["claude-code"]
                mock_detect.return_value = mock_config

                mock_vm = MagicMock()
                mock_vm.exists.return_value = False
                mock_vm.name = "clauded-new-abc123"
                mock_vm.count_active_sessions.return_value = 0
                MockVM.return_value = mock_vm

                mock_provisioner = MagicMock()
                MockProv.return_value = mock_provisioner

                runner.invoke(main, [], input="\n")

                # get_vm_metadata should not be called for new VMs
                mock_vm.get_vm_metadata.assert_not_called()

    def test_skipped_when_reprovision_flag(
        self, runner: CliRunner, config_yaml: str
    ) -> None:
        """--reprovision skips version check."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(config_yaml)

            with (
                patch("clauded.cli.LimaVM") as MockVM,
                patch("clauded.cli.Provisioner") as MockProv,
                patch("clauded.cli.__commit__", "def5678"),
            ):
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.name = "clauded-testcli1-abc123"
                mock_vm.get_vm_distro.return_value = "alpine"
                mock_vm.count_active_sessions.return_value = 0
                MockVM.return_value = mock_vm

                mock_provisioner = MagicMock()
                MockProv.return_value = mock_provisioner

                runner.invoke(main, ["--reprovision"])

                # Version check is skipped; reprovisioning happens directly
                mock_vm.get_vm_metadata.assert_not_called()
                mock_provisioner.run.assert_called_once()

    def test_skipped_when_no_metadata(
        self, runner: CliRunner, config_yaml: str
    ) -> None:
        """No /etc/clauded.json → no version check prompt."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(config_yaml)

            with (
                patch("clauded.cli.LimaVM") as MockVM,
                patch("clauded.cli.__commit__", "def5678"),
                patch("clauded.cli._check_library_updates"),
            ):
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.name = "clauded-testcli1-abc123"
                mock_vm.get_vm_distro.return_value = "alpine"
                mock_vm.get_vm_metadata.return_value = None
                mock_vm.count_active_sessions.return_value = 0
                MockVM.return_value = mock_vm

                result = runner.invoke(main, [])

                assert "clauded has been updated" not in result.output
                mock_vm.shell.assert_called_once()

    def test_skipped_when_commit_unknown(
        self, runner: CliRunner, config_yaml: str
    ) -> None:
        """'unknown' commit in metadata → no version check prompt."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(config_yaml)

            with (
                patch("clauded.cli.LimaVM") as MockVM,
                patch("clauded.cli.__commit__", "def5678"),
                patch("clauded.cli._check_library_updates"),
            ):
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.name = "clauded-testcli1-abc123"
                mock_vm.get_vm_distro.return_value = "alpine"
                mock_vm.get_vm_metadata.return_value = {
                    "version": "0.1.0",
                    "commit": "unknown",
                }
                mock_vm.count_active_sessions.return_value = 0
                MockVM.return_value = mock_vm

                result = runner.invoke(main, [])

                assert "clauded has been updated" not in result.output
                mock_vm.shell.assert_called_once()


# ---------------------------------------------------------------------------
# Library update check tests
# ---------------------------------------------------------------------------


class TestLibraryUpdateCheck:
    """Tests for _check_library_updates() via CLI integration."""

    def _mock_vm_with_matching_commit(self, MockVM: MagicMock) -> MagicMock:
        """Create a mock VM that passes version check (same commit)."""
        mock_vm = MagicMock()
        mock_vm.exists.return_value = True
        mock_vm.is_running.return_value = True
        mock_vm.name = "clauded-testcli1-abc123"
        mock_vm.get_vm_distro.return_value = "alpine"
        mock_vm.get_vm_metadata.return_value = {
            "version": "0.1.0",
            "commit": "abc1234",
        }
        mock_vm.count_active_sessions.return_value = 0
        MockVM.return_value = mock_vm
        return mock_vm

    def test_library_check_after_version_match(
        self, runner: CliRunner, config_yaml: str
    ) -> None:
        """Library check runs when clauded versions match."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(config_yaml)

            with (
                patch("clauded.cli.LimaVM") as MockVM,
                patch("clauded.cli.__commit__", "abc1234"),
                patch("clauded.cli.__version__", "0.1.0"),
                patch("clauded.cli._check_library_updates") as mock_check,
            ):
                mock_vm = self._mock_vm_with_matching_commit(MockVM)

                runner.invoke(main, [])

                mock_check.assert_called_once_with(mock_vm, mock_check.call_args[0][1])

    def test_library_check_skipped_after_reprovision(
        self, runner: CliRunner, config_yaml: str
    ) -> None:
        """Library check does not run when user chose to reprovision."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(config_yaml)

            with (
                patch("clauded.cli.LimaVM") as MockVM,
                patch("clauded.cli.Provisioner") as MockProv,
                patch("clauded.cli.__commit__", "def5678"),
                patch("clauded.cli.__version__", "0.2.0"),
                patch("clauded.cli._check_library_updates") as mock_check,
            ):
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.name = "clauded-testcli1-abc123"
                mock_vm.get_vm_distro.return_value = "alpine"
                mock_vm.get_vm_metadata.return_value = {
                    "version": "0.1.0",
                    "commit": "abc1234",
                }
                mock_vm.count_active_sessions.return_value = 0
                MockVM.return_value = mock_vm
                MockProv.return_value = MagicMock()

                # "y" for reprovision
                runner.invoke(main, [], input="y\n")

                mock_check.assert_not_called()

    def test_claude_code_update_detected(
        self, runner: CliRunner, config_yaml: str
    ) -> None:
        """Claude Code pinned version mismatch shown to user."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(config_yaml)

            with (
                patch("clauded.cli.LimaVM") as MockVM,
                patch("clauded.cli.__commit__", "abc1234"),
                patch("clauded.cli.__version__", "0.1.0"),
                patch(
                    "clauded.cli._get_vm_tool_version",
                    side_effect=lambda vm, cmd: (
                        "2.0.0" if "claude" in cmd else "1.0.5"
                    ),
                ),
                patch(
                    "clauded.cli.get_downloads",
                    return_value={"claude_code": {"version": "2.1.62"}},
                ),
                patch(
                    "clauded.cli._get_npm_latest_version",
                    return_value="1.0.5",  # Codex matches → no update
                ),
            ):
                self._mock_vm_with_matching_commit(MockVM)

                # "n" for update, "y" for stop
                result = runner.invoke(main, [], input="n\ny\n")

                assert "Claude Code" in result.output
                assert "2.0.0" in result.output
                assert "2.1.62" in result.output

    def test_codex_update_detected(self, runner: CliRunner, config_yaml: str) -> None:
        """Codex version mismatch shown to user."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(config_yaml)

            with (
                patch("clauded.cli.LimaVM") as MockVM,
                patch("clauded.cli.__commit__", "abc1234"),
                patch("clauded.cli.__version__", "0.1.0"),
                patch(
                    "clauded.cli._get_vm_tool_version",
                    side_effect=lambda vm, cmd: (
                        "2.1.62" if "claude" in cmd else "1.0.5"
                    ),
                ),
                patch(
                    "clauded.cli.get_downloads",
                    return_value={"claude_code": {"version": "2.1.62"}},
                ),
                patch(
                    "clauded.cli._get_npm_latest_version",
                    return_value="1.2.0",
                ),
            ):
                self._mock_vm_with_matching_commit(MockVM)

                result = runner.invoke(main, [], input="n\ny\n")

                assert "Codex" in result.output
                assert "1.0.5" in result.output
                assert "1.2.0" in result.output

    def test_no_updates_no_prompt(self, runner: CliRunner, config_yaml: str) -> None:
        """All versions match → no update prompt."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(config_yaml)

            with (
                patch("clauded.cli.LimaVM") as MockVM,
                patch("clauded.cli.__commit__", "abc1234"),
                patch("clauded.cli.__version__", "0.1.0"),
                patch(
                    "clauded.cli._get_vm_tool_version",
                    side_effect=lambda vm, cmd: (
                        "2.1.62" if "claude" in cmd else "1.0.5"
                    ),
                ),
                patch(
                    "clauded.cli.get_downloads",
                    return_value={"claude_code": {"version": "2.1.62"}},
                ),
                patch(
                    "clauded.cli._get_npm_latest_version",
                    return_value="1.0.5",
                ),
            ):
                self._mock_vm_with_matching_commit(MockVM)

                result = runner.invoke(main, [])

                assert "Library updates available" not in result.output
                assert "Update libraries?" not in result.output

    def test_update_confirmed_runs_commands(
        self, runner: CliRunner, config_yaml: str
    ) -> None:
        """Confirming update runs update commands in VM."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(config_yaml)

            with (
                patch("clauded.cli.LimaVM") as MockVM,
                patch("clauded.cli.__commit__", "abc1234"),
                patch("clauded.cli.__version__", "0.1.0"),
                patch(
                    "clauded.cli._get_vm_tool_version",
                    side_effect=lambda vm, cmd: (
                        "2.0.0" if "claude" in cmd else "1.0.5"
                    ),
                ),
                patch(
                    "clauded.cli.get_downloads",
                    return_value={"claude_code": {"version": "2.1.62"}},
                ),
                patch(
                    "clauded.cli._get_npm_latest_version",
                    return_value="1.2.0",
                ),
                patch(
                    "clauded.cli._update_claude_code", return_value=True
                ) as mock_update_cc,
                patch(
                    "clauded.cli._update_codex", return_value=True
                ) as mock_update_codex,
            ):
                self._mock_vm_with_matching_commit(MockVM)

                # "y" for update, "y" for stop
                runner.invoke(main, [], input="y\ny\n")

                mock_update_cc.assert_called_once()
                assert mock_update_cc.call_args[0][2] == "2.1.62"
                mock_update_codex.assert_called_once()
                assert mock_update_codex.call_args[0][1] == "1.2.0"

    def test_npm_failure_gracefully_skipped(
        self, runner: CliRunner, config_yaml: str
    ) -> None:
        """npm view failure for Codex doesn't block Claude Code update."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(config_yaml)

            with (
                patch("clauded.cli.LimaVM") as MockVM,
                patch("clauded.cli.__commit__", "abc1234"),
                patch("clauded.cli.__version__", "0.1.0"),
                patch(
                    "clauded.cli._get_vm_tool_version",
                    side_effect=lambda vm, cmd: (
                        "2.0.0" if "claude" in cmd else "1.0.5"
                    ),
                ),
                patch(
                    "clauded.cli.get_downloads",
                    return_value={"claude_code": {"version": "2.1.62"}},
                ),
                patch(
                    "clauded.cli._get_npm_latest_version",
                    return_value=None,  # npm failure for Codex
                ),
            ):
                self._mock_vm_with_matching_commit(MockVM)

                # "n" for update prompt, "y" for stop
                result = runner.invoke(main, [], input="n\ny\n")

                # Claude Code still shown (uses pinned version, not npm)
                updates_section = result.output.split("Library updates available")[-1]
                assert "Claude Code" in updates_section
                assert "2.1.62" in updates_section
                # Codex skipped (npm failed)
                assert "Codex" not in updates_section.split("Update libraries?")[0]

    def test_skipped_when_framework_not_installed(self, runner: CliRunner) -> None:
        """No claude-code in config → skip CC check."""
        config_no_cc = """version: "1"
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
  frameworks: []
"""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(config_no_cc)

            with (
                patch("clauded.cli.LimaVM") as MockVM,
                patch("clauded.cli.__commit__", "abc1234"),
                patch("clauded.cli.__version__", "0.1.0"),
                patch("clauded.cli._get_vm_tool_version") as mock_ver,
                patch("clauded.cli._get_npm_latest_version") as mock_npm,
            ):
                mock_vm = MagicMock()
                mock_vm.exists.return_value = True
                mock_vm.is_running.return_value = True
                mock_vm.name = "clauded-testcli1-abc123"
                mock_vm.get_vm_distro.return_value = "alpine"
                mock_vm.get_vm_metadata.return_value = {
                    "version": "0.1.0",
                    "commit": "abc1234",
                }
                mock_vm.count_active_sessions.return_value = 0
                MockVM.return_value = mock_vm

                runner.invoke(main, [])

                # No version checks should happen
                mock_ver.assert_not_called()
                mock_npm.assert_not_called()

    def test_downgrade_not_offered(self, runner: CliRunner, config_yaml: str) -> None:
        """Installed version newer than pinned → no update offered."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(config_yaml)

            with (
                patch("clauded.cli.LimaVM") as MockVM,
                patch("clauded.cli.__commit__", "abc1234"),
                patch("clauded.cli.__version__", "0.1.0"),
                patch(
                    "clauded.cli._get_vm_tool_version",
                    side_effect=lambda vm, cmd: (
                        "2.1.76" if "claude" in cmd else "0.115.0"
                    ),
                ),
                patch(
                    "clauded.cli.get_downloads",
                    return_value={"claude_code": {"version": "2.1.62"}},
                ),
                patch(
                    "clauded.cli._get_npm_latest_version",
                    return_value="0.111.0",
                ),
            ):
                self._mock_vm_with_matching_commit(MockVM)

                result = runner.invoke(main, [])

                assert "Library updates available" not in result.output
                assert "Update libraries?" not in result.output

    def test_update_failure_preserves_existing(
        self, runner: CliRunner, config_yaml: str
    ) -> None:
        """Failed update reports failure, existing version preserved."""
        with runner.isolated_filesystem():
            Path(".clauded.yaml").write_text(config_yaml)

            with (
                patch("clauded.cli.LimaVM") as MockVM,
                patch("clauded.cli.__commit__", "abc1234"),
                patch("clauded.cli.__version__", "0.1.0"),
                patch(
                    "clauded.cli._get_vm_tool_version",
                    side_effect=lambda vm, cmd: (
                        "2.0.0" if "claude" in cmd else "1.0.5"
                    ),
                ),
                patch(
                    "clauded.cli.get_downloads",
                    return_value={"claude_code": {"version": "2.1.62"}},
                ),
                patch("clauded.cli._get_npm_latest_version", return_value="1.0.5"),
                patch("clauded.cli._update_claude_code", return_value=False),
            ):
                self._mock_vm_with_matching_commit(MockVM)

                # "y" for update, "y" for stop
                result = runner.invoke(main, [], input="y\ny\n")

                assert "update failed" in result.output
                assert "Existing version preserved" in result.output
