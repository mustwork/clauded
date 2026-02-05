"""Interactive setup wizard for clauded."""

from pathlib import Path

import click

try:
    from simple_term_menu import TerminalMenu  # type: ignore[import-untyped]
except ModuleNotFoundError as exc:  # pragma: no cover - import-time dependency guard
    raise RuntimeError(
        "simple-term-menu is required for the interactive wizard. "
        "Install it with your package manager or pip."
    ) from exc

from .config import Config
from .constants import DEFAULT_LANGUAGES, LANGUAGE_CONFIG


def _build_menu(
    entries: list[str], *, title: str | None, **kwargs: object
) -> TerminalMenu:
    """Create a TerminalMenu with backward-compatible kwargs."""
    base_kwargs: dict[str, object] = {"clear_screen": False}
    base_kwargs.update(kwargs)
    try:
        return TerminalMenu(entries, title=title, **base_kwargs)
    except TypeError:
        for key in (
            "preselected_entries",
            "show_multi_select_hint",
            "menu_cursor_index",
            "multi_select",
            "multi_select_select_on_accept",
            "multi_select_empty_ok",
        ):
            base_kwargs.pop(key, None)
        try:
            return TerminalMenu(entries, title=title, **base_kwargs)
        except TypeError:
            return TerminalMenu(entries)


def _menu_select(title: str, items: list[tuple[str, str]], default_index: int) -> str:
    """Single-select menu returning the chosen value."""
    entries = [label for label, _value in items]
    menu = _build_menu(
        entries,
        title=title,
        menu_cursor_index=default_index,
    )
    choice = menu.show()
    if choice is None:
        raise KeyboardInterrupt()
    if isinstance(choice, list | tuple):
        choice = choice[0]
    return items[int(choice)][1]


def _menu_multi_select(title: str, items: list[tuple[str, str, bool]]) -> list[str]:
    """Multi-select menu returning chosen values."""
    entries = [label for label, _value, _pre in items]
    preselected = [i for i, (_label, _value, pre) in enumerate(items) if pre]
    menu = _build_menu(
        entries,
        title=title,
        multi_select=True,
        show_multi_select_hint=True,
        preselected_entries=preselected,
        multi_select_select_on_accept=False,
        multi_select_empty_ok=True,
    )
    choice = menu.show()
    # Distinguish cancel (Escape) from accept with empty selection (Enter)
    # simple-term-menu returns None for both, but sets chosen_accept_key only on accept
    if choice is None and menu.chosen_accept_key is None:
        raise KeyboardInterrupt()
    if choice is None:
        # Empty selection accepted with Enter
        return []
    if isinstance(choice, int):
        indices = [choice]
    else:
        indices = list(choice)
    return [items[i][1] for i in indices]


def _get_valid_default(value: str | None, choices: list[str]) -> str:
    """Return value if it's in choices, otherwise return 'None'.

    This handles the case where a config has an old version that's no longer
    in the available choices (e.g., Go "1.20" when choices are now "1.23.5", "1.22.10").
    """
    if value and value in choices:
        return value
    return "None"


def run(project_path: Path) -> Config:
    """Run the interactive wizard and return a Config."""

    print("\n  clauded - VM Environment Setup\n")

    answers: dict[str, str | list[str] | bool] = {}

    # Languages - multi-select
    selected_languages = _menu_multi_select(
        "Select languages:",
        [
            (str(LANGUAGE_CONFIG[lang]["label"]), lang, lang in DEFAULT_LANGUAGES)
            for lang in LANGUAGE_CONFIG
        ],
    )

    if selected_languages is None:
        raise KeyboardInterrupt()

    # For each selected language, ask for version (default to first/latest)
    for lang in LANGUAGE_CONFIG:
        if lang in selected_languages:
            lang_cfg = LANGUAGE_CONFIG[lang]
            versions = lang_cfg["versions"]

            default_index = 0
            version = _menu_select(
                f"{lang_cfg['name']} version?",
                [(v, v) for v in versions],
                default_index,
            )

            if version is None:
                raise KeyboardInterrupt()
            answers[lang] = version
        else:
            answers[lang] = "None"

    # Tools, databases, and frameworks combined (multi-select with separators)
    # Note: git and npm are always installed via common and node roles
    # Note: uv/poetry auto-installed with Python, maven/gradle with Java/Kotlin
    tool_selections = _menu_multi_select(
        "Select tools:",
        [
            ("docker", "docker", True),
            ("aws-cli", "aws-cli", False),
            ("gh", "gh", False),
        ],
    )
    database_selections = _menu_multi_select(
        "Select databases:",
        [
            ("postgresql", "postgresql", False),
            ("redis", "redis", False),
            ("mysql", "mysql", False),
            ("sqlite", "sqlite", False),
            ("mongodb", "mongodb", False),
        ],
    )
    framework_selections = _menu_multi_select(
        "Select frameworks:",
        [
            ("playwright", "playwright", False),
        ],
    )
    selections = tool_selections + database_selections + framework_selections

    if selections is None:
        raise KeyboardInterrupt()

    # Split selections into tools, databases, and frameworks
    tool_options = {"docker", "aws-cli", "gh"}
    database_options = {"postgresql", "redis", "mysql", "sqlite", "mongodb"}
    answers["tools"] = [s for s in selections if s in tool_options]
    answers["databases"] = [s for s in selections if s in database_options]
    # Always include claude-code
    answers["frameworks"] = ["claude-code"] + [
        s for s in selections if s not in tool_options and s not in database_options
    ]

    # Playwright browser selection (if playwright was selected)
    if "playwright" in framework_selections:
        browser_selections = _menu_multi_select(
            "Select Playwright browsers to install:",
            [
                ("Chromium", "chromium", True),
                ("Firefox", "firefox", True),
                ("WebKit", "webkit", True),
            ],
        )
        if browser_selections is None:
            raise KeyboardInterrupt()
        answers["playwright_browsers"] = browser_selections
    else:
        answers["playwright_browsers"] = []

    # Claude Code permissions - default is to skip (auto-accept all)
    answers["claude_dangerously_skip_permissions"] = click.confirm(
        "Auto-accept Claude Code permission prompts in VM?",
        default=True,
    )

    if answers["claude_dangerously_skip_permissions"] is None:
        raise KeyboardInterrupt()

    # Keep VM running - default is to shut down on exit
    answers["keep_vm_running"] = click.confirm(
        "Keep VM running after shell exit?",
        default=False,
    )

    if answers["keep_vm_running"] is None:
        raise KeyboardInterrupt()

    # VM resources
    customize_resources = click.confirm("Customize VM resources?", default=False)

    if customize_resources is None:
        raise KeyboardInterrupt()

    if customize_resources:
        cpus = click.prompt("CPUs", default="4")
        if cpus is None:
            raise KeyboardInterrupt()
        answers["cpus"] = cpus

        memory = click.prompt("Memory", default="8GiB")
        if memory is None:
            raise KeyboardInterrupt()
        answers["memory"] = memory

        disk = click.prompt("Disk", default="20GiB")
        if disk is None:
            raise KeyboardInterrupt()
        answers["disk"] = disk
    else:
        answers["cpus"] = "4"
        answers["memory"] = "8GiB"
        answers["disk"] = "20GiB"

    return Config.from_wizard(answers, project_path)


def run_edit(config: Config, project_path: Path) -> Config:
    """Re-run wizard with current config values pre-selected.

    VM resources (CPUs, memory, disk) are preserved from the original config
    since they cannot be changed without recreating the VM.
    """

    print("\n  clauded - Edit VM Configuration\n")
    print("  (VM resources cannot be changed without recreation)\n")

    answers: dict[str, str | list[str] | bool] = {}

    # Languages - multi-select
    selected_languages = _menu_multi_select(
        "Select languages:",
        [
            (
                str(LANGUAGE_CONFIG[lang]["label"]),
                lang,
                getattr(config, lang) is not None,
            )
            for lang in LANGUAGE_CONFIG
        ],
    )

    if selected_languages is None:
        raise KeyboardInterrupt()

    # For each selected language, ask for version (default to current or latest)
    for lang in LANGUAGE_CONFIG:
        if lang in selected_languages:
            lang_cfg = LANGUAGE_CONFIG[lang]
            versions = lang_cfg["versions"]

            # Get current version, default to first (latest) if not set or invalid
            current_version = getattr(config, lang)
            default_version = (
                current_version if current_version in versions else versions[0]
            )

            default_index = (
                versions.index(default_version) if default_version in versions else 0
            )
            version = _menu_select(
                f"{lang_cfg['name']} version?",
                [(v, v) for v in versions],
                default_index,
            )

            if version is None:
                raise KeyboardInterrupt()
            answers[lang] = version
        else:
            answers[lang] = "None"

    # Tools, databases, and frameworks combined - pre-check current selections
    # Note: git and npm are always installed via common and node roles
    # Note: uv/poetry auto-installed with Python, maven/gradle with Java/Kotlin
    tool_selections = _menu_multi_select(
        "Select tools:",
        [
            ("docker", "docker", "docker" in config.tools),
            ("aws-cli", "aws-cli", "aws-cli" in config.tools),
            ("gh", "gh", "gh" in config.tools),
        ],
    )
    database_selections = _menu_multi_select(
        "Select databases:",
        [
            ("postgresql", "postgresql", "postgresql" in config.databases),
            ("redis", "redis", "redis" in config.databases),
            ("mysql", "mysql", "mysql" in config.databases),
            ("sqlite", "sqlite", "sqlite" in config.databases),
            ("mongodb", "mongodb", "mongodb" in config.databases),
        ],
    )
    framework_selections = _menu_multi_select(
        "Select frameworks:",
        [
            ("playwright", "playwright", "playwright" in config.frameworks),
        ],
    )
    selections = tool_selections + database_selections + framework_selections

    if selections is None:
        raise KeyboardInterrupt()

    # Split selections into tools, databases, and frameworks
    tool_options = {"docker", "aws-cli", "gh"}
    database_options = {"postgresql", "redis", "mysql", "sqlite", "mongodb"}
    answers["tools"] = [s for s in selections if s in tool_options]
    answers["databases"] = [s for s in selections if s in database_options]
    # Always include claude-code
    answers["frameworks"] = ["claude-code"] + [
        s for s in selections if s not in tool_options and s not in database_options
    ]

    # Playwright browser selection (if playwright was selected)
    if "playwright" in framework_selections:
        # Pre-select browsers from current config, or all if none configured
        default_browsers = ["chromium", "firefox", "webkit"]
        current_browsers = config.playwright_browsers or default_browsers
        browser_selections = _menu_multi_select(
            "Select Playwright browsers to install:",
            [
                ("Chromium", "chromium", "chromium" in current_browsers),
                ("Firefox", "firefox", "firefox" in current_browsers),
                ("WebKit", "webkit", "webkit" in current_browsers),
            ],
        )
        if browser_selections is None:
            raise KeyboardInterrupt()
        answers["playwright_browsers"] = browser_selections
    else:
        answers["playwright_browsers"] = []

    # Claude Code permissions - pre-select current value
    answers["claude_dangerously_skip_permissions"] = click.confirm(
        "Auto-accept Claude Code permission prompts in VM?",
        default=config.claude_dangerously_skip_permissions,
    )

    if answers["claude_dangerously_skip_permissions"] is None:
        raise KeyboardInterrupt()

    # Keep VM running - pre-select current value
    answers["keep_vm_running"] = click.confirm(
        "Keep VM running after shell exit?",
        default=config.keep_vm_running,
    )

    if answers["keep_vm_running"] is None:
        raise KeyboardInterrupt()

    # Preserve VM resources from original config (cannot be changed without recreation)
    answers["cpus"] = str(config.cpus)
    answers["memory"] = config.memory
    answers["disk"] = config.disk

    return Config.from_wizard(answers, project_path)
