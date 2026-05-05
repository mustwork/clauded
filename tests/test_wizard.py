"""Tests for clauded.wizard module."""

from pathlib import Path
from unittest.mock import patch

import pytest

from clauded import wizard
from clauded.config import Config


def _record_framework_items(
    captured: list[list[tuple[str, str, bool]]],
):
    """Build a multi-select side effect that captures Select frameworks: items."""

    def side_effect(title, items):
        if title == "Select frameworks:":
            captured.append(list(items))
            return []
        if title == "Select languages:":
            return [value for _label, value, pre in items if pre]
        return []

    return side_effect


@pytest.fixture
def sample_config() -> Config:
    """Create a sample config with current valid values."""
    return Config(
        vm_name="test-vm",
        cpus=1,
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
        frameworks=["claude-code", "codex"],
        claude_dangerously_skip_permissions=True,
    )


@pytest.fixture
def outdated_config() -> Config:
    """Create a config with outdated version values that are no longer in choices."""
    return Config(
        vm_name="test-vm",
        cpus=1,
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
        frameworks=["claude-code", "codex"],
        claude_dangerously_skip_permissions=True,
    )


class TestWizardRunEdit:
    """Tests for wizard.run_edit() function."""

    def test_run_edit_with_valid_config_values(
        self, sample_config: Config, tmp_path: Path
    ) -> None:
        """run_edit should work with config values that match available choices."""
        with (
            patch("clauded.wizard._menu_multi_select") as mock_multi_select,
            patch("clauded.wizard._menu_select") as mock_select,
            patch("clauded.wizard.click.confirm") as mock_confirm,
            patch("clauded.wizard.click.prompt", return_value=""),
        ):

            def multi_select_side_effect(title, items):
                if title == "Select languages:":
                    return [value for _label, value, pre in items if pre]
                return []

            mock_multi_select.side_effect = multi_select_side_effect

            def select_side_effect(_title, items, default_index):
                return items[default_index][1]

            mock_select.side_effect = select_side_effect
            mock_confirm.return_value = True

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
        with (
            patch("clauded.wizard._menu_multi_select") as mock_multi_select,
            patch("clauded.wizard._menu_select") as mock_select,
            patch("clauded.wizard.click.confirm") as mock_confirm,
            patch("clauded.wizard.click.prompt", return_value=""),
        ):

            def multi_select_side_effect(title, items):
                if title == "Select languages:":
                    return [value for _label, value, pre in items if pre]
                return []

            mock_multi_select.side_effect = multi_select_side_effect

            select_calls = []

            def select_side_effect(title, items, default_index):
                select_calls.append((title, items, default_index))
                return items[default_index][1]

            mock_select.side_effect = select_side_effect
            mock_confirm.return_value = True

            result = wizard.run_edit(outdated_config, tmp_path)

            assert result is not None
            assert isinstance(result, Config)
            python_call = next(
                (
                    call
                    for call in select_calls
                    if [item[0] for item in call[1]] == ["3.12", "3.11", "3.10"]
                ),
                None,
            )
            assert python_call is not None
            assert python_call[2] == 0

    def test_run_edit_preselects_configured_languages(
        self, sample_config: Config, tmp_path: Path
    ) -> None:
        """run_edit should pre-check languages that are configured in the config."""
        with (
            patch("clauded.wizard._menu_multi_select") as mock_multi_select,
            patch("clauded.wizard._menu_select") as mock_select,
            patch("clauded.wizard.click.confirm") as mock_confirm,
            patch("clauded.wizard.click.prompt", return_value=""),
        ):
            language_items: list[tuple[str, str, bool]] = []

            def multi_select_side_effect(title, items):
                if title == "Select languages:":
                    language_items.extend(items)
                    return [value for _label, value, pre in items if pre]
                return []

            mock_multi_select.side_effect = multi_select_side_effect
            mock_select.side_effect = lambda _title, items, default_index: items[
                default_index
            ][1]
            mock_confirm.return_value = True

            wizard.run_edit(sample_config, tmp_path)

            checked_languages = {value for _label, value, pre in language_items if pre}
            assert "python" in checked_languages
            assert "node" in checked_languages
            assert "rust" in checked_languages
            assert "go" in checked_languages
            assert "java" not in checked_languages
            assert "kotlin" not in checked_languages


class TestWizardRunEditValidDefaults:
    """Tests verifying that run_edit always passes valid defaults to menus."""

    def test_run_edit_passes_valid_defaults_for_version_selects(
        self, sample_config: Config, tmp_path: Path
    ) -> None:
        """run_edit should pass valid default values for all version select prompts."""
        with (
            patch("clauded.wizard._menu_multi_select") as mock_multi_select,
            patch("clauded.wizard._menu_select") as mock_select,
            patch("clauded.wizard.click.confirm") as mock_confirm,
            patch("clauded.wizard.click.prompt", return_value=""),
        ):

            def multi_select_side_effect(title, items):
                if title == "Select languages:":
                    return [value for _label, value, pre in items if pre]
                return []

            mock_multi_select.side_effect = multi_select_side_effect

            select_calls = []

            def track_select(_title, items, default_index):
                select_calls.append((items, default_index))
                return items[default_index][1]

            mock_select.side_effect = track_select
            mock_confirm.return_value = True

            result = wizard.run_edit(sample_config, tmp_path)

            for items, default_index in select_calls:
                assert 0 <= default_index < len(items)

            assert result is not None
            assert isinstance(result, Config)

    def test_valid_config_values_are_preserved_in_version_selects(
        self, sample_config: Config, tmp_path: Path
    ) -> None:
        """run_edit should use current config version as default in version selects."""
        with (
            patch("clauded.wizard._menu_multi_select") as mock_multi_select,
            patch("clauded.wizard._menu_select") as mock_select,
            patch("clauded.wizard.click.confirm") as mock_confirm,
            patch("clauded.wizard.click.prompt", return_value=""),
        ):

            def multi_select_side_effect(title, items):
                if title == "Select languages:":
                    return [value for _label, value, pre in items if pre]
                return []

            mock_multi_select.side_effect = multi_select_side_effect

            select_calls = []

            def track_select(_title, items, default_index):
                select_calls.append((items, default_index))
                return items[default_index][1]

            mock_select.side_effect = track_select
            mock_confirm.return_value = True

            wizard.run_edit(sample_config, tmp_path)

            python_call = next(
                (
                    call
                    for call in select_calls
                    if [item[0] for item in call[0]] == ["3.12", "3.11", "3.10"]
                ),
                None,
            )
            assert python_call is not None
            assert python_call[1] == 1

            go_call = next(
                (
                    call
                    for call in select_calls
                    if [item[0] for item in call[0]] == ["1.23.5", "1.22.10"]
                ),
                None,
            )
            assert go_call is not None
            assert go_call[1] == 0


class TestWizardHarnessStep:
    """Tests for the new 'Select harness:' step (Story 03)."""

    @staticmethod
    def _capture_harness_call(
        harness_calls: list[tuple[list[tuple[str, str]], int]],
    ):
        """Build a _menu_select side effect that records harness-step calls."""

        def side_effect(title, items, default_index):
            if title == "Select harness:":
                harness_calls.append((list(items), default_index))
                return items[default_index][1]
            return items[default_index][1]

        return side_effect

    @staticmethod
    def _fake_confirm_default_false(prompt: str, default: bool = False, **_kwargs):
        if "Customize" in prompt:
            return False
        return True

    def test_run_offers_harness_with_three_entries(self, tmp_path: Path) -> None:
        """AC-009: run() prompts for harness with three entries; default index 0."""
        harness_calls: list[tuple[list[tuple[str, str]], int]] = []
        with (
            patch("clauded.wizard._menu_multi_select") as mock_multi,
            patch("clauded.wizard._menu_select") as mock_select,
            patch(
                "clauded.wizard.click.confirm",
                side_effect=self._fake_confirm_default_false,
            ),
            patch("clauded.wizard.click.prompt", return_value=""),
        ):
            mock_multi.side_effect = (
                lambda title, items: [v for _l, v, pre in items if pre]
                if title == "Select languages:"
                else []
            )
            mock_select.side_effect = self._capture_harness_call(harness_calls)

            wizard.run(tmp_path)

        assert harness_calls, "harness step was never invoked"
        items, default_index = harness_calls[0]
        values = [value for _label, value in items]
        assert values == ["claude-code", "codex", "opencode"]
        assert default_index == 0

    def test_run_auto_adds_opencode_when_chosen_as_harness(
        self, tmp_path: Path
    ) -> None:
        """AC-010: picking opencode as harness auto-adds opencode to frameworks."""
        with (
            patch("clauded.wizard._menu_multi_select") as mock_multi,
            patch("clauded.wizard._menu_select") as mock_select,
            patch(
                "clauded.wizard.click.confirm",
                side_effect=self._fake_confirm_default_false,
            ),
            patch("clauded.wizard.click.prompt", return_value=""),
        ):

            def multi(title, items):
                if title == "Select languages:":
                    return [v for _l, v, pre in items if pre]
                if title == "Select frameworks:":
                    return ["playwright"]
                return []

            mock_multi.side_effect = multi

            def select(title, items, default_index):
                if title == "Select harness:":
                    return "opencode"
                return items[default_index][1]

            mock_select.side_effect = select

            result = wizard.run(tmp_path)

        assert result.harness == "opencode"
        assert "opencode" in result.frameworks

    def test_run_does_not_duplicate_opencode_when_already_selected(
        self, tmp_path: Path
    ) -> None:
        """No duplicate when user picked both the framework and the harness."""
        with (
            patch("clauded.wizard._menu_multi_select") as mock_multi,
            patch("clauded.wizard._menu_select") as mock_select,
            patch(
                "clauded.wizard.click.confirm",
                side_effect=self._fake_confirm_default_false,
            ),
            patch("clauded.wizard.click.prompt", return_value=""),
        ):

            def multi(title, items):
                if title == "Select languages:":
                    return [v for _l, v, pre in items if pre]
                if title == "Select frameworks:":
                    return ["opencode"]
                return []

            mock_multi.side_effect = multi

            def select(title, items, default_index):
                if title == "Select harness:":
                    return "opencode"
                return items[default_index][1]

            mock_select.side_effect = select

            result = wizard.run(tmp_path)

        assert result.harness == "opencode"
        assert result.frameworks.count("opencode") == 1

    def test_run_edit_preselects_current_harness(self, tmp_path: Path) -> None:
        """AC-011: run_edit() pre-selects the persisted harness via default_index."""
        config = Config(
            vm_name="test-vm",
            cpus=1,
            memory="8GiB",
            disk="20GiB",
            mount_host="/test/project",
            mount_guest="/workspace",
            python="3.12",
            node="20",
            frameworks=["claude-code", "codex"],
            harness="codex",
        )
        harness_calls: list[tuple[list[tuple[str, str]], int]] = []
        with (
            patch("clauded.wizard._menu_multi_select") as mock_multi,
            patch("clauded.wizard._menu_select") as mock_select,
            patch(
                "clauded.wizard.click.confirm",
                side_effect=self._fake_confirm_default_false,
            ),
            patch("clauded.wizard.click.prompt", return_value=""),
        ):
            mock_multi.side_effect = (
                lambda title, items: [v for _l, v, pre in items if pre]
                if title == "Select languages:"
                else []
            )
            mock_select.side_effect = self._capture_harness_call(harness_calls)

            result = wizard.run_edit(config, tmp_path)

        assert harness_calls, "harness step was never invoked"
        items, default_index = harness_calls[0]
        assert items[default_index][1] == "codex"
        assert result.harness == "codex"


class TestWizardFrameworksMultiselect:
    """Tests for the frameworks multi-select offered by run() and run_edit()."""

    def test_run_offers_opencode_framework(self, tmp_path: Path) -> None:
        """run() lists opencode alongside playwright in the frameworks menu."""
        captured: list[list[tuple[str, str, bool]]] = []

        def fake_confirm(prompt, default=False, **_kwargs):
            # Decline customising VM resources (default-false branch);
            # accept other yes/no prompts.
            if "Customize" in prompt:
                return False
            return True

        with (
            patch("clauded.wizard._menu_multi_select") as mock_multi_select,
            patch("clauded.wizard._menu_select") as mock_select,
            patch("clauded.wizard.click.confirm", side_effect=fake_confirm),
            patch("clauded.wizard.click.prompt", return_value=""),
        ):
            mock_multi_select.side_effect = _record_framework_items(captured)
            mock_select.side_effect = lambda _t, items, default_index: items[
                default_index
            ][1]

            wizard.run(tmp_path)

        assert captured, "frameworks multi-select was never invoked"
        framework_values = {value for _label, value, _pre in captured[0]}
        assert "opencode" in framework_values
        assert "playwright" in framework_values

    def test_run_edit_offers_opencode_framework(
        self, sample_config: Config, tmp_path: Path
    ) -> None:
        """run_edit() lists opencode alongside playwright in the frameworks menu."""
        captured: list[list[tuple[str, str, bool]]] = []

        with (
            patch("clauded.wizard._menu_multi_select") as mock_multi_select,
            patch("clauded.wizard._menu_select") as mock_select,
            patch("clauded.wizard.click.confirm", return_value=True),
            patch("clauded.wizard.click.prompt", return_value=""),
        ):
            mock_multi_select.side_effect = _record_framework_items(captured)
            mock_select.side_effect = lambda _t, items, default_index: items[
                default_index
            ][1]

            wizard.run_edit(sample_config, tmp_path)

        assert captured, "frameworks multi-select was never invoked"
        framework_values = {value for _label, value, _pre in captured[0]}
        assert "opencode" in framework_values
        assert "playwright" in framework_values
