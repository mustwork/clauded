"""Integration tests for atomic config update with rollback feature."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from clauded.config import Config
from clauded.lima import destroy_vm_by_name


class TestAtomicUpdateContextManager:
    """Integration tests for Config.atomic_update() context manager."""

    def test_atomic_update_success_clears_previous_vm_name(
        self, tmp_path: Path
    ) -> None:
        """On success, atomic_update clears previous_vm_name and saves config."""
        config_path = tmp_path / ".clauded.yaml"

        # Create initial config
        config = Config.from_wizard(
            {"cpus": "4", "memory": "8GiB", "disk": "20GiB"}, tmp_path
        )
        old_vm_name = config.vm_name
        config.save(config_path)

        # Use atomic_update to transition to new VM name
        new_vm_name = "clauded-newvm-123456"
        with config.atomic_update(new_vm_name, config_path) as yielded_old_name:
            # Inside context: previous_vm_name should be set
            assert config.previous_vm_name == old_vm_name
            assert config.vm_name == new_vm_name
            assert yielded_old_name == old_vm_name

            # Verify config was saved with both names
            reloaded = Config.load(config_path)
            assert reloaded.vm_name == new_vm_name
            assert reloaded.previous_vm_name == old_vm_name

        # After successful exit: previous_vm_name cleared
        assert config.previous_vm_name is None
        assert config.vm_name == new_vm_name

        # Verify config saved without previous_vm_name
        reloaded = Config.load(config_path)
        assert reloaded.vm_name == new_vm_name
        assert reloaded.previous_vm_name is None

    def test_atomic_update_rollback_on_exception(self, tmp_path: Path) -> None:
        """On exception, atomic_update rolls back vm_name and clears previous."""
        config_path = tmp_path / ".clauded.yaml"

        config = Config.from_wizard(
            {"cpus": "4", "memory": "8GiB", "disk": "20GiB"}, tmp_path
        )
        old_vm_name = config.vm_name
        config.save(config_path)

        new_vm_name = "clauded-newvm-123456"

        # Simulate exception during VM operation
        with pytest.raises(RuntimeError, match="VM creation failed"):
            with config.atomic_update(new_vm_name, config_path):
                # Inside context: names updated
                assert config.vm_name == new_vm_name
                assert config.previous_vm_name == old_vm_name
                raise RuntimeError("VM creation failed")

        # After exception: rolled back to old_vm_name
        assert config.vm_name == old_vm_name
        assert config.previous_vm_name is None

        # Verify config saved with rollback
        reloaded = Config.load(config_path)
        assert reloaded.vm_name == old_vm_name
        assert reloaded.previous_vm_name is None

    def test_atomic_update_with_no_previous_vm(self, tmp_path: Path) -> None:
        """atomic_update works when there's no previous VM (first-time setup)."""
        config_path = tmp_path / ".clauded.yaml"

        config = Config.from_wizard(
            {"cpus": "4", "memory": "8GiB", "disk": "20GiB"}, tmp_path
        )
        # Clear vm_name to simulate first-time setup
        config.vm_name = ""
        config.save(config_path)

        new_vm_name = "clauded-newvm-123456"

        with config.atomic_update(new_vm_name, config_path) as old_vm_name:
            assert old_vm_name is None
            assert config.vm_name == new_vm_name
            assert config.previous_vm_name is None

        # After success: vm_name set, no previous
        assert config.vm_name == new_vm_name
        assert config.previous_vm_name is None

    def test_atomic_update_same_name_is_noop(self, tmp_path: Path) -> None:
        """atomic_update with same name doesn't prompt for cleanup."""
        config_path = tmp_path / ".clauded.yaml"

        config = Config.from_wizard(
            {"cpus": "4", "memory": "8GiB", "disk": "20GiB"}, tmp_path
        )
        vm_name = config.vm_name
        config.save(config_path)

        with config.atomic_update(vm_name, config_path) as old_vm_name:
            # Names are the same
            assert old_vm_name == vm_name
            assert config.vm_name == vm_name
            assert config.previous_vm_name == vm_name

        # After success: previous_vm_name cleared
        assert config.vm_name == vm_name
        assert config.previous_vm_name is None

    def test_atomic_update_multiple_exceptions_safe(self, tmp_path: Path) -> None:
        """Multiple exceptions in atomic_update don't corrupt state."""
        config_path = tmp_path / ".clauded.yaml"

        config = Config.from_wizard(
            {"cpus": "4", "memory": "8GiB", "disk": "20GiB"}, tmp_path
        )
        original_name = config.vm_name
        config.save(config_path)

        # First exception
        with pytest.raises(ValueError):
            with config.atomic_update("vm1", config_path):
                raise ValueError("First failure")

        assert config.vm_name == original_name
        assert config.previous_vm_name is None

        # Second exception
        with pytest.raises(KeyError):
            with config.atomic_update("vm2", config_path):
                raise KeyError("Second failure")

        assert config.vm_name == original_name
        assert config.previous_vm_name is None


class TestConfigLoadSaveWithPreviousVmName:
    """Test that Config.load/save handle previous_vm_name field correctly."""

    def test_save_persists_previous_vm_name_when_set(self, tmp_path: Path) -> None:
        """Config.save() writes previous_vm_name to YAML when set."""
        config_path = tmp_path / ".clauded.yaml"

        config = Config.from_wizard(
            {"cpus": "4", "memory": "8GiB", "disk": "20GiB"}, tmp_path
        )
        config.previous_vm_name = "old-vm-name"
        config.save(config_path)

        # Read YAML directly to verify field
        with open(config_path) as f:
            data = yaml.safe_load(f)

        assert data["vm"]["previous_name"] == "old-vm-name"

    def test_save_omits_previous_vm_name_when_none(self, tmp_path: Path) -> None:
        """Config.save() omits previous_vm_name from YAML when None."""
        config_path = tmp_path / ".clauded.yaml"

        config = Config.from_wizard(
            {"cpus": "4", "memory": "8GiB", "disk": "20GiB"}, tmp_path
        )
        config.previous_vm_name = None
        config.save(config_path)

        # Read YAML directly
        with open(config_path) as f:
            data = yaml.safe_load(f)

        assert "previous_name" not in data["vm"]

    def test_load_reads_previous_vm_name_when_present(self, tmp_path: Path) -> None:
        """Config.load() reads previous_vm_name from YAML when present."""
        config_path = tmp_path / ".clauded.yaml"

        # Write config with previous_vm_name
        config = Config.from_wizard(
            {"cpus": "4", "memory": "8GiB", "disk": "20GiB"}, tmp_path
        )
        config.previous_vm_name = "old-vm"
        config.save(config_path)

        # Load and verify
        loaded = Config.load(config_path)
        assert loaded.previous_vm_name == "old-vm"

    def test_load_defaults_previous_vm_name_to_none(self, tmp_path: Path) -> None:
        """Config.load() defaults previous_vm_name to None when absent."""
        config_path = tmp_path / ".clauded.yaml"

        # Write config without previous_vm_name
        config = Config.from_wizard(
            {"cpus": "4", "memory": "8GiB", "disk": "20GiB"}, tmp_path
        )
        config.save(config_path)

        # Load and verify
        loaded = Config.load(config_path)
        assert loaded.previous_vm_name is None


class TestCrashRecoveryIntegration:
    """Integration tests for crash recovery on startup."""

    def test_handle_crash_recovery_prompts_and_clears(self, tmp_path: Path) -> None:
        """_handle_crash_recovery prompts user and clears previous_vm_name."""
        from clauded.cli import _handle_crash_recovery

        config_path = tmp_path / ".clauded.yaml"

        # Create config with previous_vm_name set (crash scenario)
        config = Config.from_wizard(
            {"cpus": "4", "memory": "8GiB", "disk": "20GiB"}, tmp_path
        )
        config.previous_vm_name = "old-crashed-vm"
        config.save(config_path)

        # Mock subprocess to show both VMs exist
        with patch("clauded.cli.subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = f"{config.vm_name}\nold-crashed-vm\n"
            mock_run.return_value = mock_result

            # Mock confirm to decline deletion
            with patch("clauded.cli.click.confirm") as mock_confirm:
                mock_confirm.return_value.ask.return_value = False

                _handle_crash_recovery(config, config_path)

                # Should prompt user
                mock_confirm.assert_called_once_with(
                    "Delete previous VM 'old-crashed-vm'?", default=False
                )

        # previous_vm_name should be cleared
        assert config.previous_vm_name is None

        # Config should be saved without previous_vm_name
        loaded = Config.load(config_path)
        assert loaded.previous_vm_name is None

    def test_handle_crash_recovery_deletes_vm_when_confirmed(
        self, tmp_path: Path
    ) -> None:
        """_handle_crash_recovery deletes VM when user confirms."""
        from clauded.cli import _handle_crash_recovery

        config_path = tmp_path / ".clauded.yaml"

        config = Config.from_wizard(
            {"cpus": "4", "memory": "8GiB", "disk": "20GiB"}, tmp_path
        )
        config.previous_vm_name = "old-vm-to-delete"
        config.save(config_path)

        # Mock subprocess to show both VMs exist
        with patch("clauded.cli.subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = f"{config.vm_name}\nold-vm-to-delete\n"
            mock_run.return_value = mock_result

            # Mock confirm to confirm deletion
            with patch("clauded.cli.click.confirm") as mock_confirm:
                with patch("clauded.cli.destroy_vm_by_name") as mock_destroy:
                    mock_confirm.return_value.ask.return_value = True

                    _handle_crash_recovery(config, config_path)

                    # Should delete VM
                    mock_destroy.assert_called_once_with("old-vm-to-delete")

        # previous_vm_name cleared
        assert config.previous_vm_name is None

    def test_handle_crash_recovery_handles_keyboard_interrupt(
        self, tmp_path: Path
    ) -> None:
        """_handle_crash_recovery handles KeyboardInterrupt gracefully."""
        from clauded.cli import _handle_crash_recovery

        config_path = tmp_path / ".clauded.yaml"

        config = Config.from_wizard(
            {"cpus": "4", "memory": "8GiB", "disk": "20GiB"}, tmp_path
        )
        config.previous_vm_name = "interrupted-vm"
        config.save(config_path)

        # Mock subprocess to show both VMs exist
        with patch("clauded.cli.subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = f"{config.vm_name}\ninterrupted-vm\n"
            mock_run.return_value = mock_result

            # Simulate user interruption
            with patch("clauded.cli.click.confirm") as mock_confirm:
                mock_confirm.return_value.ask.return_value = None  # Interrupt

                # Should not raise, should clear state
                _handle_crash_recovery(config, config_path)

        # previous_vm_name should still be cleared
        assert config.previous_vm_name is None

    def test_handle_crash_recovery_noop_when_no_previous_vm(
        self, tmp_path: Path
    ) -> None:
        """_handle_crash_recovery does nothing when previous_vm_name is None."""
        from clauded.cli import _handle_crash_recovery

        config_path = tmp_path / ".clauded.yaml"

        config = Config.from_wizard(
            {"cpus": "4", "memory": "8GiB", "disk": "20GiB"}, tmp_path
        )
        config.previous_vm_name = None
        config.save(config_path)

        # Should not prompt or save
        with patch("clauded.cli.click.confirm") as mock_confirm:
            _handle_crash_recovery(config, config_path)

            # No prompt
            mock_confirm.assert_not_called()

        # Config unchanged
        assert config.previous_vm_name is None


class TestDestroyVmByName:
    """Test destroy_vm_by_name helper function."""

    def test_destroy_vm_by_name_calls_limactl(self) -> None:
        """destroy_vm_by_name calls limactl delete with correct args."""
        with patch("clauded.lima.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            destroy_vm_by_name("test-vm")

            mock_run.assert_called_once_with(
                ["limactl", "delete", "-f", "test-vm"], check=True
            )

    def test_destroy_vm_by_name_handles_lima_not_installed(self) -> None:
        """destroy_vm_by_name handles missing lima gracefully."""
        with patch("clauded.lima.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            with pytest.raises(SystemExit) as exc_info:
                destroy_vm_by_name("test-vm")

            assert exc_info.value.code == 1


class TestEndToEndScenarios:
    """End-to-end integration tests combining multiple components."""

    def test_e2e_config_edit_with_provisioning_failure_rolls_back(
        self, tmp_path: Path
    ) -> None:
        """E2E: Config edit with provisioning failure rolls back vm_name."""
        config_path = tmp_path / ".clauded.yaml"

        # Initial config
        config = Config.from_wizard(
            {"cpus": "4", "memory": "8GiB", "disk": "20GiB", "python": "3.11"},
            tmp_path,
        )
        config.save(config_path)

        # Simulate edit flow: new config with different python version
        new_config = Config.from_wizard(
            {"cpus": "4", "memory": "8GiB", "disk": "20GiB", "python": "3.12"},
            tmp_path,
        )
        new_vm_name = new_config.vm_name

        # Use atomic_update and simulate provisioning failure
        with pytest.raises(RuntimeError, match="Provisioning failed"):
            with new_config.atomic_update(new_vm_name, config_path):
                # Config updated
                assert new_config.vm_name == new_vm_name

                # Simulate provisioning failure
                raise RuntimeError("Provisioning failed")

        # After rollback: config should have original vm_name
        # (In this case, vm_name is deterministic so it's the same)
        assert new_config.previous_vm_name is None

        # Reload from disk to verify persistence
        loaded = Config.load(config_path)
        assert loaded.previous_vm_name is None

    def test_e2e_crash_recovery_after_interrupted_update(self, tmp_path: Path) -> None:
        """E2E: System crashes during update, startup detects and prompts."""
        from clauded.cli import _handle_crash_recovery

        config_path = tmp_path / ".clauded.yaml"

        # Simulate interrupted update: config has previous_vm_name set
        config = Config.from_wizard(
            {"cpus": "4", "memory": "8GiB", "disk": "20GiB"}, tmp_path
        )
        config.previous_vm_name = "old-vm-before-crash"
        config.save(config_path)

        # On next startup: load config
        loaded_config = Config.load(config_path)
        assert loaded_config.previous_vm_name == "old-vm-before-crash"

        # Mock subprocess to show both VMs exist
        with patch("clauded.cli.subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = f"{loaded_config.vm_name}\nold-vm-before-crash\n"
            mock_run.return_value = mock_result

            # Crash recovery should trigger
            with patch("clauded.cli.click.confirm") as mock_confirm:
                with patch("clauded.cli.destroy_vm_by_name") as mock_destroy:
                    # User confirms deletion
                    mock_confirm.return_value.ask.return_value = True

                    _handle_crash_recovery(loaded_config, config_path)

                    # VM deleted
                    mock_destroy.assert_called_once_with("old-vm-before-crash")

        # State cleaned up
        assert loaded_config.previous_vm_name is None

        # Config persisted
        final_config = Config.load(config_path)
        assert final_config.previous_vm_name is None


class TestBlockerIssues:
    """Tests for blocker issues identified by system-verifier."""

    def test_atomic_update_catches_base_exception(self, tmp_path: Path) -> None:
        """TC-2: Verify atomic_update catches BaseException (KeyboardInterrupt)."""
        config_path = tmp_path / ".clauded.yaml"

        config = Config.from_wizard(
            {"cpus": "4", "memory": "8GiB", "disk": "20GiB"}, tmp_path
        )
        original_name = config.vm_name
        config.save(config_path)

        new_vm_name = "clauded-newvm-123456"

        # Simulate KeyboardInterrupt (BaseException, not Exception)
        with pytest.raises(KeyboardInterrupt):
            with config.atomic_update(new_vm_name, config_path):
                assert config.vm_name == new_vm_name
                raise KeyboardInterrupt()

        # Should rollback even for BaseException
        assert config.vm_name == original_name
        assert config.previous_vm_name is None

        # Verify config saved with rollback
        loaded = Config.load(config_path)
        assert loaded.vm_name == original_name
        assert loaded.previous_vm_name is None

    def test_atomic_update_catches_system_exit(self, tmp_path: Path) -> None:
        """TC-2: Verify atomic_update catches SystemExit."""
        config_path = tmp_path / ".clauded.yaml"

        config = Config.from_wizard(
            {"cpus": "4", "memory": "8GiB", "disk": "20GiB"}, tmp_path
        )
        original_name = config.vm_name
        config.save(config_path)

        new_vm_name = "clauded-newvm-789"

        with pytest.raises(SystemExit):
            with config.atomic_update(new_vm_name, config_path):
                raise SystemExit(1)

        # Should rollback for SystemExit
        assert config.vm_name == original_name
        assert config.previous_vm_name is None

    def test_vm_name_path_traversal_validation_in_load(self, tmp_path: Path) -> None:
        """TC-4: Verify path traversal validation when loading config."""
        config_path = tmp_path / ".clauded.yaml"

        # Create malicious config with path traversal in vm_name
        malicious_yaml = """version: "1"
vm:
  name: "../../../etc/passwd"
  cpus: 4
  memory: 8GiB
  disk: 20GiB
mount:
  host: /test
  guest: /test
environment:
  python: "3.12"
  tools: []
  databases: []
  frameworks: []
"""
        config_path.write_text(malicious_yaml)

        # Should raise ValueError
        with pytest.raises(ValueError, match="cannot contain path separators"):
            Config.load(config_path)

    def test_vm_name_path_traversal_validation_in_atomic_update(
        self, tmp_path: Path
    ) -> None:
        """TC-4: Verify path traversal validation in atomic_update."""
        config_path = tmp_path / ".clauded.yaml"

        config = Config.from_wizard(
            {"cpus": "4", "memory": "8GiB", "disk": "20GiB"}, tmp_path
        )
        config.save(config_path)

        # Try to use malicious VM name
        with pytest.raises(ValueError, match="cannot contain path separators"):
            with config.atomic_update("../../malicious", config_path):
                pass

    def test_vm_name_with_backslash_rejected(self, tmp_path: Path) -> None:
        """TC-4: Verify backslash (Windows path separator) rejected."""
        config_path = tmp_path / ".clauded.yaml"

        config = Config.from_wizard(
            {"cpus": "4", "memory": "8GiB", "disk": "20GiB"}, tmp_path
        )
        config.save(config_path)

        with pytest.raises(ValueError, match="cannot contain path separators"):
            with config.atomic_update(r"malicious\path", config_path):
                pass

    def test_previous_vm_name_path_traversal_validation(self, tmp_path: Path) -> None:
        """TC-4: Verify path traversal validation for previous_vm_name."""
        config_path = tmp_path / ".clauded.yaml"

        malicious_yaml = """version: "1"
vm:
  name: "safe-name"
  previous_name: "../../../etc/passwd"
  cpus: 4
  memory: 8GiB
  disk: 20GiB
mount:
  host: /test
  guest: /test
environment:
  python: "3.12"
  tools: []
  databases: []
  frameworks: []
"""
        config_path.write_text(malicious_yaml)

        with pytest.raises(ValueError, match="cannot contain path separators"):
            Config.load(config_path)

    def test_crash_recovery_restores_vm_name_when_current_missing(
        self, tmp_path: Path
    ) -> None:
        """TC-5: Verify crash recovery restores vm_name if current VM missing."""
        from clauded.cli import _handle_crash_recovery

        config_path = tmp_path / ".clauded.yaml"

        config = Config.from_wizard(
            {"cpus": "4", "memory": "8GiB", "disk": "20GiB"}, tmp_path
        )
        config.previous_vm_name = "old-vm-that-exists"
        config.vm_name = "new-vm-that-doesnt-exist"
        config.save(config_path)

        # Mock limactl to return that new VM doesn't exist
        with patch("clauded.cli.subprocess.run") as mock_run:
            # First call: check if limactl works
            # Second call: get VM list (new VM not in list)
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "old-vm-that-exists\n"
            mock_run.return_value = mock_result

            _handle_crash_recovery(config, config_path)

        # Should rollback to previous_vm_name
        assert config.vm_name == "old-vm-that-exists"
        assert config.previous_vm_name is None

        # Verify persistence
        loaded = Config.load(config_path)
        assert loaded.vm_name == "old-vm-that-exists"
        assert loaded.previous_vm_name is None

    def test_crash_recovery_prompts_delete_when_current_exists(
        self, tmp_path: Path
    ) -> None:
        """TC-5: Verify crash recovery prompts for deletion when current VM exists."""
        from clauded.cli import _handle_crash_recovery

        config_path = tmp_path / ".clauded.yaml"

        config = Config.from_wizard(
            {"cpus": "4", "memory": "8GiB", "disk": "20GiB"}, tmp_path
        )
        config.previous_vm_name = "old-vm"
        config.vm_name = "new-vm"
        config.save(config_path)

        # Mock limactl to show both VMs exist
        with patch("clauded.cli.subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "old-vm\nnew-vm\n"
            mock_run.return_value = mock_result

            with patch("clauded.cli.click.confirm") as mock_confirm:
                with patch("clauded.cli.destroy_vm_by_name") as mock_destroy:
                    mock_confirm.return_value.ask.return_value = True

                    _handle_crash_recovery(config, config_path)

                    # Should prompt to delete old VM
                    mock_confirm.assert_called_once()
                    mock_destroy.assert_called_once_with("old-vm")

        # Should clear previous_vm_name but keep current
        assert config.vm_name == "new-vm"
        assert config.previous_vm_name is None

    def test_e2e_cli_workflow_with_atomic_update(self, tmp_path: Path) -> None:
        """TC-1: E2E test covering main() -> atomic_update() -> shell()."""
        from click.testing import CliRunner

        from clauded.cli import main

        runner = CliRunner()

        with runner.isolated_filesystem():
            config_path = Path(".clauded.yaml")

            # Create initial config
            config = Config.from_wizard(
                {"cpus": "4", "memory": "8GiB", "disk": "20GiB", "python": "3.12"},
                Path.cwd(),
            )
            config.save(config_path)

            # Mock all external dependencies
            with patch("clauded.cli.LimaVM") as MockVM:
                with patch("clauded.cli.run_edit_with_detection") as mock_edit:
                    with patch("clauded.cli.Provisioner") as MockProv:
                        with patch("clauded.cli._require_interactive_terminal"):
                            # Setup mocks
                            mock_vm = MagicMock()
                            mock_vm.exists.return_value = True
                            mock_vm.is_running.return_value = True
                            mock_vm.count_active_sessions.return_value = 0
                            mock_vm.name = config.vm_name
                            MockVM.return_value = mock_vm

                            # Mock run_edit_with_detection to return new config
                            new_config = Config.from_wizard(
                                {
                                    "cpus": "4",
                                    "memory": "8GiB",
                                    "disk": "20GiB",
                                    "python": "3.11",
                                },
                                Path.cwd(),
                            )
                            # Mock atomic_update properly
                            new_config_mock = MagicMock(spec=Config)
                            new_config_mock.vm_name = new_config.vm_name
                            new_config_mock.mount_guest = str(Path.cwd())
                            mock_ctx = MagicMock()
                            mock_ctx.__enter__.return_value = None
                            new_config_mock.atomic_update.return_value = mock_ctx
                            mock_edit.return_value = new_config_mock

                            mock_prov = MagicMock()
                            MockProv.return_value = mock_prov

                            # Run CLI
                            result = runner.invoke(main, ["--edit"])

                            # Verify workflow
                            assert result.exit_code == 0
                            mock_edit.assert_called_once()
                            new_config_mock.atomic_update.assert_called_once()
                            mock_prov.run.assert_called_once()
                            mock_vm.shell.assert_called_once()

    def test_crash_simulation_with_power_loss(self, tmp_path: Path) -> None:
        """TC-3: Simulate actual crash by not completing context manager."""
        from clauded.cli import _handle_crash_recovery

        config_path = tmp_path / ".clauded.yaml"

        # Start atomic update but don't complete it (simulate crash)
        config = Config.from_wizard(
            {"cpus": "4", "memory": "8GiB", "disk": "20GiB"}, tmp_path
        )
        original_vm = config.vm_name
        config.save(config_path)

        new_vm_name = "clauded-newvm-crash"

        # Enter atomic_update but simulate crash before exit
        ctx = config.atomic_update(new_vm_name, config_path)
        old_vm = ctx.__enter__()
        assert old_vm == original_vm

        # At this point, config file has previous_vm_name set
        crashed_config = Config.load(config_path)
        assert crashed_config.previous_vm_name == original_vm
        assert crashed_config.vm_name == new_vm_name

        # Simulate crash (don't call __exit__)
        # Now simulate restart and recovery
        recovery_config = Config.load(config_path)

        # Mock VM list to show new VM doesn't exist (creation failed before crash)
        with patch("clauded.cli.subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = f"{original_vm}\n"
            mock_run.return_value = mock_result

            _handle_crash_recovery(recovery_config, config_path)

        # Should have rolled back
        assert recovery_config.vm_name == original_vm
        assert recovery_config.previous_vm_name is None
