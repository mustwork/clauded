"""Tests for clauded.wizard module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from questionary import Choice

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
        go="1.23.5",
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
        python="3.9",  # No longer in choices (3.12, 3.11, 3.10)
        node="16",  # No longer in choices (22, 20, 18)
        java="8",  # No longer in choices (21, 17, 11)
        kotlin="1.8",  # No longer in choices (2.0, 1.9)
        rust="beta",  # No longer in choices (stable, nightly)
        go="1.22",  # No longer in choices (1.23.5, 1.22.10)
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
        with patch("clauded.wizard.questionary") as mock_questionary:
            # Track checkbox calls
            checkbox_calls = []

            def track_checkbox(*args, **kwargs):
                checkbox_calls.append(kwargs)
                mock = MagicMock()
                # Return language values for languages that are checked
                choices = kwargs.get("choices", [])
                if choices and isinstance(choices[0], Choice):
                    # Language selection: return checked languages
                    mock.ask.return_value = [c.value for c in choices if c.checked]
                else:
                    mock.ask.return_value = []
                return mock

            mock_questionary.checkbox.side_effect = track_checkbox

            # Track select calls
            select_calls = []

            def track_select(*args, **kwargs):
                select_calls.append(kwargs)
                mock = MagicMock()
                mock.ask.return_value = kwargs.get("default")
                return mock

            mock_questionary.select.side_effect = track_select

            mock_confirm = MagicMock()
            mock_confirm.ask.return_value = True
            mock_questionary.confirm.return_value = mock_confirm

            result = wizard.run_edit(sample_config, tmp_path)

            assert result is not None
            assert isinstance(result, Config)

    def test_run_edit_with_outdated_version_gracefully_falls_back(
        self, outdated_config: Config, tmp_path: Path
    ) -> None:
        """run_edit handles outdated config versions by falling back to latest.

        When a config has a version like "3.9" that is no longer in the choices
        list (now "3.12", "3.11", "3.10"), the wizard should fall back to the
        first (latest) version as the default selection.
        """
        with patch("clauded.wizard.questionary") as mock_questionary:
            # Track checkbox calls
            checkbox_calls = []

            def track_checkbox(*args, **kwargs):
                checkbox_calls.append(kwargs)
                mock = MagicMock()
                choices = kwargs.get("choices", [])
                if choices and isinstance(choices[0], Choice):
                    mock.ask.return_value = [c.value for c in choices if c.checked]
                else:
                    mock.ask.return_value = []
                return mock

            mock_questionary.checkbox.side_effect = track_checkbox

            # Track select calls
            select_calls = []

            def track_select(*args, **kwargs):
                select_calls.append(kwargs)
                mock = MagicMock()
                mock.ask.return_value = kwargs.get("default")
                return mock

            mock_questionary.select.side_effect = track_select

            mock_confirm = MagicMock()
            mock_confirm.ask.return_value = True
            mock_questionary.confirm.return_value = mock_confirm

            result = wizard.run_edit(outdated_config, tmp_path)

            assert result is not None
            assert isinstance(result, Config)

    def test_run_edit_preselects_configured_languages(
        self, sample_config: Config, tmp_path: Path
    ) -> None:
        """run_edit should pre-check languages that are configured in the config."""
        with patch("clauded.wizard.questionary") as mock_questionary:
            checkbox_calls = []

            def track_checkbox(*args, **kwargs):
                checkbox_calls.append(kwargs)
                mock = MagicMock()
                choices = kwargs.get("choices", [])
                if choices and isinstance(choices[0], Choice):
                    mock.ask.return_value = [c.value for c in choices if c.checked]
                else:
                    mock.ask.return_value = []
                return mock

            mock_questionary.checkbox.side_effect = track_checkbox

            mock_select = MagicMock()
            mock_select.ask.return_value = "3.12"
            mock_questionary.select.return_value = mock_select

            mock_confirm = MagicMock()
            mock_confirm.ask.return_value = True
            mock_questionary.confirm.return_value = mock_confirm

            wizard.run_edit(sample_config, tmp_path)

            # First checkbox should be language selection
            language_checkbox = checkbox_calls[0]
            choices = language_checkbox["choices"]

            # Find which languages are checked
            checked_languages = {c.value for c in choices if c.checked}

            # sample_config has python, node, rust, go configured (not None)
            assert "python" in checked_languages
            assert "node" in checked_languages
            assert "rust" in checked_languages
            assert "go" in checked_languages
            # java and kotlin are None, so not checked
            assert "java" not in checked_languages
            assert "kotlin" not in checked_languages


class TestWizardRunEditValidDefaults:
    """Tests verifying that run_edit always passes valid defaults to questionary."""

    def test_run_edit_passes_valid_defaults_for_version_selects(
        self, sample_config: Config, tmp_path: Path
    ) -> None:
        """run_edit should pass valid default values for all version select prompts."""
        with patch("clauded.wizard.questionary") as mock_questionary:
            # For checkbox, return selected languages
            def mock_checkbox_func(*args, **kwargs):
                mock = MagicMock()
                choices = kwargs.get("choices", [])
                if choices and isinstance(choices[0], Choice):
                    mock.ask.return_value = [c.value for c in choices if c.checked]
                else:
                    mock.ask.return_value = []
                return mock

            mock_questionary.checkbox.side_effect = mock_checkbox_func

            # Track select calls to verify defaults
            select_calls = []

            def track_select(*args, **kwargs):
                select_calls.append(kwargs)
                mock = MagicMock()
                choices = kwargs.get("choices", [])
                mock.ask.return_value = choices[0] if choices else None
                return mock

            mock_questionary.select.side_effect = track_select

            mock_confirm = MagicMock()
            mock_confirm.ask.return_value = True
            mock_questionary.confirm.return_value = mock_confirm

            result = wizard.run_edit(sample_config, tmp_path)

            # Verify that all select calls had valid defaults
            for call in select_calls:
                default = call.get("default")
                choices = call.get("choices", [])
                assert (
                    default in choices
                ), f"Invalid default '{default}' not in choices {choices}"

            assert result is not None
            assert isinstance(result, Config)

    def test_valid_config_values_are_preserved_in_version_selects(
        self, sample_config: Config, tmp_path: Path
    ) -> None:
        """run_edit should use current config version as default in version selects."""
        with patch("clauded.wizard.questionary") as mock_questionary:
            # For checkbox, return selected languages
            def mock_checkbox_func(*args, **kwargs):
                mock = MagicMock()
                choices = kwargs.get("choices", [])
                if choices and isinstance(choices[0], Choice):
                    mock.ask.return_value = [c.value for c in choices if c.checked]
                else:
                    mock.ask.return_value = []
                return mock

            mock_questionary.checkbox.side_effect = mock_checkbox_func

            # Track select calls
            select_calls = []

            def track_select(*args, **kwargs):
                select_calls.append(kwargs)
                mock = MagicMock()
                mock.ask.return_value = kwargs.get("default")
                return mock

            mock_questionary.select.side_effect = track_select

            mock_confirm = MagicMock()
            mock_confirm.ask.return_value = True
            mock_questionary.confirm.return_value = mock_confirm

            wizard.run_edit(sample_config, tmp_path)

            # Find the Python version select (should have 3.12, 3.11, 3.10 as choices)
            python_call = next(
                (
                    c
                    for c in select_calls
                    if c.get("choices") == ["3.12", "3.11", "3.10"]
                ),
                None,
            )
            assert python_call is not None
            assert python_call["default"] == "3.11"  # sample_config.python

            # Find the Go version select
            go_call = next(
                (c for c in select_calls if c.get("choices") == ["1.23.5", "1.22.10"]),
                None,
            )
            assert go_call is not None
            assert go_call["default"] == "1.23.5"  # sample_config.go
