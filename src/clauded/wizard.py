"""Interactive setup wizard for clauded."""

from pathlib import Path

import questionary
from questionary import Choice, Separator, Style

from .config import Config
from .constants import DEFAULT_LANGUAGES, LANGUAGE_CONFIG

# Custom style: no text inversion, use cyan highlighting and circle indicators
WIZARD_STYLE = Style(
    [
        ("highlighted", "noreverse fg:ansibrightcyan"),  # Cyan text, no inversion
        ("selected", "noreverse fg:ansibrightcyan"),  # Cyan for checked items
        ("pointer", "noreverse fg:ansicyan bold"),  # Bold cyan pointer
        ("answer", "fg:ansigreen"),  # Green submitted answer
    ]
)


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

    # Languages - checkbox to select which to include
    selected_languages = questionary.checkbox(
        "Select languages:",
        choices=[
            Choice(
                str(LANGUAGE_CONFIG[lang]["label"]),
                value=lang,
                checked=lang in DEFAULT_LANGUAGES,
            )
            for lang in LANGUAGE_CONFIG
        ],
        style=WIZARD_STYLE,
        instruction="(space to select, enter to confirm)",
    ).ask()

    if selected_languages is None:
        raise KeyboardInterrupt()

    # For each selected language, ask for version (default to first/latest)
    for lang in LANGUAGE_CONFIG:
        if lang in selected_languages:
            lang_cfg = LANGUAGE_CONFIG[lang]
            versions = lang_cfg["versions"]

            version = questionary.select(
                f"{lang_cfg['name']} version?",
                choices=versions,
                default=versions[0],
                use_indicator=True,
                style=WIZARD_STYLE,
                instruction="(enter to confirm)",
            ).ask()

            if version is None:
                raise KeyboardInterrupt()
            answers[lang] = version
        else:
            answers[lang] = "None"

    # Tools, databases, and frameworks combined (multi-select with separators)
    # Note: git and npm are always installed via common and node roles
    # Note: uv/poetry auto-installed with Python, maven/gradle with Java/Kotlin
    selections = questionary.checkbox(
        "Select tools, databases, and frameworks:",
        choices=[
            Separator("── Tools ──"),
            Choice("docker", checked=True),
            Choice("aws-cli", checked=False),
            Choice("gh", checked=False),
            Separator("── Databases ──"),
            Choice("postgresql", checked=False),
            Choice("redis", checked=False),
            Choice("mysql", checked=False),
            Choice("sqlite", checked=False),
            Separator("── Frameworks ──"),
            Choice("playwright", checked=False),
        ],
        style=WIZARD_STYLE,
        instruction="(space to select, enter to confirm)",
    ).ask()

    if selections is None:
        raise KeyboardInterrupt()

    # Split selections into tools, databases, and frameworks
    tool_options = {"docker", "aws-cli", "gh"}
    database_options = {"postgresql", "redis", "mysql", "sqlite"}
    answers["tools"] = [s for s in selections if s in tool_options]
    answers["databases"] = [s for s in selections if s in database_options]
    # Always include claude-code
    answers["frameworks"] = ["claude-code"] + [
        s for s in selections if s not in tool_options and s not in database_options
    ]

    # Claude Code permissions - default is to skip (auto-accept all)
    answers["claude_dangerously_skip_permissions"] = questionary.confirm(
        "Auto-accept Claude Code permission prompts in VM?",
        default=True,
        style=WIZARD_STYLE,
    ).ask()

    if answers["claude_dangerously_skip_permissions"] is None:
        raise KeyboardInterrupt()

    # VM resources
    customize_resources = questionary.confirm(
        "Customize VM resources?", default=False
    ).ask()

    if customize_resources is None:
        raise KeyboardInterrupt()

    if customize_resources:
        cpus = questionary.text("CPUs:", default="4").ask()
        if cpus is None:
            raise KeyboardInterrupt()
        answers["cpus"] = cpus

        memory = questionary.text("Memory:", default="8GiB").ask()
        if memory is None:
            raise KeyboardInterrupt()
        answers["memory"] = memory

        disk = questionary.text("Disk:", default="20GiB").ask()
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

    # Languages - checkbox to select which to include (pre-check currently configured)
    selected_languages = questionary.checkbox(
        "Select languages:",
        choices=[
            Choice(
                str(LANGUAGE_CONFIG[lang]["label"]),
                value=lang,
                checked=getattr(config, lang) is not None,
            )
            for lang in LANGUAGE_CONFIG
        ],
        style=WIZARD_STYLE,
        instruction="(space to select, enter to confirm)",
    ).ask()

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

            version = questionary.select(
                f"{lang_cfg['name']} version?",
                choices=versions,
                default=default_version,
                use_indicator=True,
                style=WIZARD_STYLE,
                instruction="(enter to confirm)",
            ).ask()

            if version is None:
                raise KeyboardInterrupt()
            answers[lang] = version
        else:
            answers[lang] = "None"

    # Tools, databases, and frameworks combined - pre-check current selections
    # Note: git and npm are always installed via common and node roles
    # Note: uv/poetry auto-installed with Python, maven/gradle with Java/Kotlin
    selections = questionary.checkbox(
        "Select tools, databases, and frameworks:",
        choices=[
            Separator("── Tools ──"),
            Choice("docker", checked="docker" in config.tools),
            Choice("aws-cli", checked="aws-cli" in config.tools),
            Choice("gh", checked="gh" in config.tools),
            Separator("── Databases ──"),
            Choice("postgresql", checked="postgresql" in config.databases),
            Choice("redis", checked="redis" in config.databases),
            Choice("mysql", checked="mysql" in config.databases),
            Choice("sqlite", checked="sqlite" in config.databases),
            Separator("── Frameworks ──"),
            Choice("playwright", checked="playwright" in config.frameworks),
        ],
        style=WIZARD_STYLE,
        instruction="(space to select, enter to confirm)",
    ).ask()

    if selections is None:
        raise KeyboardInterrupt()

    # Split selections into tools, databases, and frameworks
    tool_options = {"docker", "aws-cli", "gh"}
    database_options = {"postgresql", "redis", "mysql", "sqlite"}
    answers["tools"] = [s for s in selections if s in tool_options]
    answers["databases"] = [s for s in selections if s in database_options]
    # Always include claude-code
    answers["frameworks"] = ["claude-code"] + [
        s for s in selections if s not in tool_options and s not in database_options
    ]

    # Claude Code permissions - pre-select current value
    answers["claude_dangerously_skip_permissions"] = questionary.confirm(
        "Auto-accept Claude Code permission prompts in VM?",
        default=config.claude_dangerously_skip_permissions,
        style=WIZARD_STYLE,
    ).ask()

    if answers["claude_dangerously_skip_permissions"] is None:
        raise KeyboardInterrupt()

    # Preserve VM resources from original config (cannot be changed without recreation)
    answers["cpus"] = str(config.cpus)
    answers["memory"] = config.memory
    answers["disk"] = config.disk

    return Config.from_wizard(answers, project_path)
