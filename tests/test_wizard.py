"""Tests for clauded.wizard module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from clauded import wizard
from clauded.config import Config


@pytest.fixture
def sample_config() -> Config:
    """Create a sample config with current valid values."""
    return Config(
        vm_name="test-vm",
        cpus=4,
        memory="8GiB",
        disk="20GiB",
        mount_host="/test/project",
        mount_guest="/workspace",
        python="3.11",
        node="20",
        java=None,
        kotlin=None,
        rust="stable",
        go="1.25.6",
        tools=["docker"],
        databases=["postgresql"],
        frameworks=["claude-code"],
        claude_dangerously_skip_permissions=True,
    )


@pytest.fixture
def outdated_config() -> Config:
    """Create a config with outdated version values that are no longer in choices."""
    return Config(
        vm_name="test-vm",
        cpus=4,
        memory="8GiB",
        disk="20GiB",
        mount_host="/test/project",
        mount_guest="/workspace",
        python="3.9",  # No longer in choices (3.12, 3.11, 3.10, None)
        node="16",  # No longer in choices (22, 20, 18, None)
        java="8",  # No longer in choices (21, 17, 11, None)
        kotlin="1.8",  # No longer in choices (2.0, 1.9, None)
        rust="beta",  # No longer in choices (stable, nightly, None)
        go="1.22",  # No longer in choices (1.25.6, 1.24.12, None)
        tools=["docker"],
        databases=[],
        frameworks=["claude-code"],
        claude_dangerously_skip_permissions=True,
    )


class TestWizardRunEdit:
    """Tests for wizard.run_edit() function."""

    def test_run_edit_with_valid_config_values(
        self, sample_config: Config, tmp_path: Path
    ) -> None:
        """run_edit should work with config values that match available choices."""
        # Mock all questionary prompts to return valid values
        with patch("clauded.wizard.questionary") as mock_questionary:
            # Set up mock returns for all prompts
            mock_select = MagicMock()
            mock_select.ask.return_value = "3.11"
            mock_questionary.select.return_value = mock_select

            mock_checkbox = MagicMock()
            mock_checkbox.ask.return_value = ["docker"]
            mock_questionary.checkbox.return_value = mock_checkbox

            mock_confirm = MagicMock()
            mock_confirm.ask.return_value = True
            mock_questionary.confirm.return_value = mock_confirm

            # This should not raise an exception
            result = wizard.run_edit(sample_config, tmp_path)

            assert result is not None
            assert isinstance(result, Config)

    def test_run_edit_with_outdated_version_gracefully_falls_back(
        self, outdated_config: Config, tmp_path: Path
    ) -> None:
        """run_edit handles outdated config versions by falling back to 'None'.

        When a config has a version like "3.9" that is no longer in the choices
        list (now "3.12", "3.11", "3.10", "None"), the wizard should fall back
        to "None" as the default selection instead of raising a ValueError.
        """
        with patch("clauded.wizard.questionary") as mock_questionary:
            # Set up mock returns for all prompts
            mock_select = MagicMock()
            mock_select.ask.return_value = "None"  # User selects None
            mock_questionary.select.return_value = mock_select

            mock_checkbox = MagicMock()
            mock_checkbox.ask.return_value = []
            mock_questionary.checkbox.return_value = mock_checkbox

            mock_confirm = MagicMock()
            mock_confirm.ask.return_value = True
            mock_questionary.confirm.return_value = mock_confirm

            # This should NOT raise an exception
            result = wizard.run_edit(outdated_config, tmp_path)

            assert result is not None
            assert isinstance(result, Config)

    def test_run_edit_with_outdated_python_version_falls_back_to_none(
        self, tmp_path: Path
    ) -> None:
        """run_edit falls back to 'None' when config has outdated Python version."""
        config = Config(
            vm_name="test-vm",
            cpus=4,
            memory="8GiB",
            disk="20GiB",
            mount_host="/test/project",
            mount_guest="/workspace",
            python="3.9",  # Not in choices: 3.12, 3.11, 3.10, None
            node=None,
            java=None,
            kotlin=None,
            rust=None,
            go=None,
            tools=[],
            databases=[],
            frameworks=["claude-code"],
            claude_dangerously_skip_permissions=True,
        )

        with patch("clauded.wizard.questionary") as mock_questionary:
            # Track select calls to verify default
            select_calls = []

            def track_select(*args, **kwargs):
                select_calls.append(kwargs)
                mock = MagicMock()
                mock.ask.return_value = kwargs.get("default")
                return mock

            mock_questionary.select.side_effect = track_select

            mock_checkbox = MagicMock()
            mock_checkbox.ask.return_value = []
            mock_questionary.checkbox.return_value = mock_checkbox

            mock_confirm = MagicMock()
            mock_confirm.ask.return_value = True
            mock_questionary.confirm.return_value = mock_confirm

            wizard.run_edit(config, tmp_path)

            # The first select call should be for Python with default "None"
            # because "3.9" is not in the choices
            assert select_calls[0]["default"] == "None"


class TestWizardRunEditValidDefaults:
    """Tests verifying that run_edit always passes valid defaults to questionary."""

    def test_run_edit_passes_valid_defaults_for_all_versions(
        self, outdated_config: Config, tmp_path: Path
    ) -> None:
        """run_edit should pass valid default values for all select prompts."""
        with patch("clauded.wizard.questionary") as mock_questionary:
            # Track all calls to select() to verify defaults
            select_calls = []

            def track_select(*args, **kwargs):
                select_calls.append(kwargs)
                mock = MagicMock()
                # Return first choice
                choices = kwargs.get("choices", [])
                mock.ask.return_value = choices[0] if choices else None
                return mock

            mock_questionary.select.side_effect = track_select

            mock_checkbox = MagicMock()
            mock_checkbox.ask.return_value = []
            mock_questionary.checkbox.return_value = mock_checkbox

            mock_confirm = MagicMock()
            mock_confirm.ask.return_value = True
            mock_questionary.confirm.return_value = mock_confirm

            result = wizard.run_edit(outdated_config, tmp_path)

            # Verify that all select calls had valid defaults
            for call in select_calls:
                default = call.get("default")
                choices = call.get("choices", [])
                assert (
                    default in choices
                ), f"Invalid default '{default}' not in choices {choices}"

            assert result is not None
            assert isinstance(result, Config)

    def test_valid_config_values_are_preserved(
        self, sample_config: Config, tmp_path: Path
    ) -> None:
        """run_edit should preserve valid config values as defaults."""
        with patch("clauded.wizard.questionary") as mock_questionary:
            # Track all calls to select()
            select_calls = []

            def track_select(*args, **kwargs):
                select_calls.append(kwargs)
                mock = MagicMock()
                # Return the default value (which should be the config value)
                mock.ask.return_value = kwargs.get("default")
                return mock

            mock_questionary.select.side_effect = track_select

            mock_checkbox = MagicMock()
            mock_checkbox.ask.return_value = ["docker"]
            mock_questionary.checkbox.return_value = mock_checkbox

            mock_confirm = MagicMock()
            mock_confirm.ask.return_value = True
            mock_questionary.confirm.return_value = mock_confirm

            wizard.run_edit(sample_config, tmp_path)

            # Find the Python version call and verify the default is preserved
            python_call = next(
                (c for c in select_calls if "3.12" in c.get("choices", [])), None
            )
            assert python_call is not None
            assert python_call["default"] == "3.11"  # sample_config.python

            # Find the Go version call and verify the default is preserved
            go_call = next(
                (c for c in select_calls if "1.25.6" in c.get("choices", [])), None
            )
            assert go_call is not None
            assert go_call["default"] == "1.25.6"  # sample_config.go
