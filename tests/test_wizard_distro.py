"""Tests for wizard distro selection functionality."""

from pathlib import Path
from unittest.mock import patch

from clauded.wizard import run


class TestWizardDistroSelection:
    """Test distro selection in wizard."""

    def test_wizard_shows_distro_as_first_question(self, tmp_path: Path) -> None:
        """Wizard shows distro selection as the first question."""
        with patch("clauded.wizard._menu_select") as mock_menu_select:
            with patch("clauded.wizard._menu_multi_select") as mock_multi_select:
                with patch("clauded.wizard.click.confirm") as mock_confirm:
                    # Set up return values
                    mock_menu_select.side_effect = [
                        "alpine",  # Distro selection (FIRST)
                        "3.12",  # Python version
                    ]
                    mock_multi_select.side_effect = [
                        ["python"],  # Languages
                        [],  # Tools
                        [],  # Databases
                        [],  # Frameworks
                    ]
                    mock_confirm.side_effect = [
                        True,  # claude_dangerously_skip_permissions
                        False,  # keep_vm_running
                        False,  # customize_resources
                    ]

                    config = run(tmp_path)

                    # Verify distro selection was FIRST call to _menu_select
                    assert mock_menu_select.call_count >= 1
                    first_call = mock_menu_select.call_args_list[0]
                    assert "Select Linux distribution:" in first_call[0][0]

                    # Verify config has distro set
                    assert config.vm_distro == "alpine"

    def test_wizard_defaults_to_alpine(self, tmp_path: Path) -> None:
        """Wizard defaults to Alpine Linux."""
        with patch("clauded.wizard._menu_select") as mock_menu_select:
            with patch("clauded.wizard._menu_multi_select") as mock_multi_select:
                with patch("clauded.wizard.click.confirm") as mock_confirm:
                    mock_menu_select.side_effect = [
                        "alpine",  # Distro selection
                    ]
                    mock_multi_select.side_effect = [
                        [],  # Languages
                        [],  # Tools
                        [],  # Databases
                        [],  # Frameworks
                    ]
                    mock_confirm.side_effect = [
                        True,  # claude_dangerously_skip_permissions
                        False,  # keep_vm_running
                        False,  # customize_resources
                    ]

                    run(tmp_path)

                    # Check distro menu was called with alpine as default
                    first_call = mock_menu_select.call_args_list[0]
                    distro_items = first_call[0][1]  # Second positional arg
                    default_index = first_call[0][2]  # Third positional arg

                    # Find alpine in distro_items
                    alpine_index = None
                    for i, (_display_name, value) in enumerate(distro_items):
                        if value == "alpine":
                            alpine_index = i
                            break

                    assert alpine_index is not None
                    assert default_index == alpine_index

    def test_wizard_with_distro_override_alpine(self, tmp_path: Path) -> None:
        """Wizard with distro_override='alpine' pre-selects alpine."""
        with patch("clauded.wizard._menu_select") as mock_menu_select:
            with patch("clauded.wizard._menu_multi_select") as mock_multi_select:
                with patch("clauded.wizard.click.confirm") as mock_confirm:
                    # Distro should NOT be asked when override provided
                    mock_menu_select.side_effect = [
                        "3.12",  # Python version
                    ]
                    mock_multi_select.side_effect = [
                        ["python"],  # Languages
                        [],  # Tools
                        [],  # Databases
                        [],  # Frameworks
                    ]
                    mock_confirm.side_effect = [
                        True,  # claude_dangerously_skip_permissions
                        False,  # keep_vm_running
                        False,  # customize_resources
                    ]

                    config = run(tmp_path, distro_override="alpine")

                    # Verify distro selection was NOT asked (skipped)
                    for call in mock_menu_select.call_args_list:
                        assert "Select Linux distribution:" not in str(call)

                    # Verify config has distro set from override
                    assert config.vm_distro == "alpine"

    def test_wizard_with_distro_override_ubuntu(self, tmp_path: Path) -> None:
        """Wizard with distro_override='ubuntu' pre-selects ubuntu."""
        with patch("clauded.wizard._menu_select") as mock_menu_select:
            with patch("clauded.wizard._menu_multi_select") as mock_multi_select:
                with patch("clauded.wizard.click.confirm") as mock_confirm:
                    mock_menu_select.side_effect = []
                    mock_multi_select.side_effect = [
                        [],  # Languages
                        [],  # Tools
                        [],  # Databases
                        [],  # Frameworks
                    ]
                    mock_confirm.side_effect = [
                        True,  # claude_dangerously_skip_permissions
                        False,  # keep_vm_running
                        False,  # customize_resources
                    ]

                    config = run(tmp_path, distro_override="ubuntu")

                    # Verify distro selection was NOT asked
                    for call in mock_menu_select.call_args_list:
                        assert "Select Linux distribution:" not in str(call)

                    # Verify config has distro set from override
                    assert config.vm_distro == "ubuntu"

    def test_wizard_shows_alpine_and_ubuntu_options(self, tmp_path: Path) -> None:
        """Wizard shows Alpine Linux and Ubuntu as distro options."""
        with patch("clauded.wizard._menu_select") as mock_menu_select:
            with patch("clauded.wizard._menu_multi_select") as mock_multi_select:
                with patch("clauded.wizard.click.confirm") as mock_confirm:
                    mock_menu_select.side_effect = [
                        "ubuntu",  # User selects Ubuntu
                    ]
                    mock_multi_select.side_effect = [
                        [],  # Languages
                        [],  # Tools
                        [],  # Databases
                        [],  # Frameworks
                    ]
                    mock_confirm.side_effect = [
                        True,  # claude_dangerously_skip_permissions
                        False,  # keep_vm_running
                        False,  # customize_resources
                    ]

                    run(tmp_path)

                    # Check distro menu shows both options
                    first_call = mock_menu_select.call_args_list[0]
                    distro_items = first_call[0][1]

                    distro_values = [value for _display_name, value in distro_items]
                    assert "alpine" in distro_values
                    assert "ubuntu" in distro_values

                    # Check display names
                    distro_displays = [
                        display_name for display_name, _value in distro_items
                    ]
                    assert "Alpine Linux" in distro_displays
                    assert "Ubuntu" in distro_displays

    def test_wizard_user_selects_ubuntu(self, tmp_path: Path) -> None:
        """User can select Ubuntu in wizard."""
        with patch("clauded.wizard._menu_select") as mock_menu_select:
            with patch("clauded.wizard._menu_multi_select") as mock_multi_select:
                with patch("clauded.wizard.click.confirm") as mock_confirm:
                    mock_menu_select.side_effect = [
                        "ubuntu",  # User selects Ubuntu
                    ]
                    mock_multi_select.side_effect = [
                        [],  # Languages
                        [],  # Tools
                        [],  # Databases
                        [],  # Frameworks
                    ]
                    mock_confirm.side_effect = [
                        True,
                        False,
                        False,
                    ]

                    config = run(tmp_path)

                    assert config.vm_distro == "ubuntu"


class TestWizardDistroIntegration:
    """Test distro selection integration with run_with_detection."""

    def test_run_with_detection_shows_distro_first(self, tmp_path: Path) -> None:
        """run_with_detection shows distro selection as first question."""
        from clauded.detect.wizard_integration import run_with_detection

        # _select_distro is defined in wizard.py and calls _menu_select there
        with patch("clauded.wizard._menu_select") as mock_menu_select:
            with patch(
                "clauded.detect.wizard_integration._menu_multi_select"
            ) as mock_multi_select:
                with patch(
                    "clauded.detect.wizard_integration.click.confirm"
                ) as mock_confirm:
                    with patch(
                        "clauded.detect.wizard_integration.detect"
                    ) as mock_detect:
                        # Mock detection result
                        from clauded.detect.result import DetectionResult

                        mock_detect.return_value = DetectionResult(
                            languages={}, versions={}, frameworks=set()
                        )

                        mock_menu_select.side_effect = [
                            "alpine",  # Distro selection (FIRST)
                        ]
                        mock_multi_select.side_effect = [
                            [],  # Languages
                            [],  # Tools
                            [],  # Databases
                            [],  # Frameworks
                        ]
                        mock_confirm.side_effect = [
                            True,
                            False,
                            False,
                        ]

                        config = run_with_detection(tmp_path)

                        # Verify distro selection was FIRST
                        assert mock_menu_select.call_count >= 1
                        first_call = mock_menu_select.call_args_list[0]
                        assert "Select Linux distribution:" in first_call[0][0]

                        assert config.vm_distro == "alpine"

    def test_run_with_detection_respects_distro_override(self, tmp_path: Path) -> None:
        """run_with_detection respects distro_override parameter."""
        from clauded.detect.wizard_integration import run_with_detection

        # Patch at the import location in wizard_integration, not wizard
        with patch(
            "clauded.detect.wizard_integration._menu_select"
        ) as mock_menu_select:
            with patch(
                "clauded.detect.wizard_integration._menu_multi_select"
            ) as mock_multi_select:
                with patch(
                    "clauded.detect.wizard_integration.click.confirm"
                ) as mock_confirm:
                    with patch(
                        "clauded.detect.wizard_integration.detect"
                    ) as mock_detect:
                        from clauded.detect.result import DetectionResult

                        mock_detect.return_value = DetectionResult(
                            languages={}, versions={}, frameworks=set()
                        )

                        mock_menu_select.side_effect = []
                        mock_multi_select.side_effect = [
                            [],  # Languages
                            [],  # Tools
                            [],  # Databases
                            [],  # Frameworks
                        ]
                        mock_confirm.side_effect = [
                            True,
                            False,
                            False,
                        ]

                        config = run_with_detection(tmp_path, distro_override="ubuntu")

                        # Distro selection should be skipped
                        for call in mock_menu_select.call_args_list:
                            assert "Select Linux distribution:" not in str(call)

                        assert config.vm_distro == "ubuntu"
