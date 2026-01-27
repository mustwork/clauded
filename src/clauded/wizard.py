"""Interactive setup wizard for clauded."""

from pathlib import Path

import questionary
from questionary import Choice, Style

from .config import Config

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
    in the available choices (e.g., Go "1.22" when choices are now "1.25.6", "1.24.12").
    """
    if value and value in choices:
        return value
    return "None"


def run(project_path: Path) -> Config:
    """Run the interactive wizard and return a Config."""

    print("\n  clauded - VM Environment Setup\n")

    answers: dict[str, str | list[str] | bool] = {}

    # Language version choices, display names, and package managers
    language_config: dict[str, dict[str, str | list[str]]] = {
        "python": {
            "name": "Python",
            "versions": ["3.12", "3.11", "3.10"],
            "label": "Python (uv, uvx, pip, pipx)",
        },
        "node": {
            "name": "Node.js",
            "versions": ["22", "20", "18"],
            "label": "Node.js (npm, npx)",
        },
        "java": {
            "name": "Java",
            "versions": ["21", "17", "11"],
            "label": "Java (maven, gradle)",
        },
        "kotlin": {
            "name": "Kotlin",
            "versions": ["2.0", "1.9"],
            "label": "Kotlin (maven, gradle)",
        },
        "rust": {
            "name": "Rust",
            "versions": ["stable", "nightly"],
            "label": "Rust (cargo)",
        },
        "go": {
            "name": "Go",
            "versions": ["1.25.6", "1.24.12"],
            "label": "Go (go mod)",
        },
    }

    # Default languages to pre-select
    default_languages = {"python", "node"}

    # Languages - checkbox to select which to include
    selected_languages = questionary.checkbox(
        "Select languages:",
        choices=[
            Choice(
                str(language_config[lang]["label"]),
                value=lang,
                checked=lang in default_languages,
            )
            for lang in language_config
        ],
        style=WIZARD_STYLE,
        instruction="(space to select, enter to confirm)",
    ).ask()

    if selected_languages is None:
        raise KeyboardInterrupt()

    # For each selected language, ask for version (default to first/latest)
    for lang in language_config:
        if lang in selected_languages:
            lang_cfg = language_config[lang]
            versions = lang_cfg["versions"]
            assert isinstance(versions, list)

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

    # Tools (multi-select, default: docker)
    # Note: git and npm are always installed via common and node roles
    # Note: uv/poetry auto-installed with Python, maven/gradle with Java/Kotlin
    answers["tools"] = questionary.checkbox(
        "Select tools:",
        choices=[
            Choice("docker", checked=True),
            Choice("aws-cli", checked=False),
            Choice("gh", checked=False),
        ],
        style=WIZARD_STYLE,
        instruction="(space to select, enter to confirm)",
    ).ask()

    if answers["tools"] is None:
        raise KeyboardInterrupt()

    # Databases (multi-select, no defaults)
    answers["databases"] = questionary.checkbox(
        "Select databases:",
        choices=["postgresql", "redis", "mysql"],
        style=WIZARD_STYLE,
        instruction="(space to select, enter to confirm)",
    ).ask()

    if answers["databases"] is None:
        raise KeyboardInterrupt()

    # Additional frameworks (multi-select) - claude-code is always included
    additional_frameworks = questionary.checkbox(
        "Additional frameworks:",
        choices=[
            Choice("playwright", checked=False),
        ],
        style=WIZARD_STYLE,
        instruction="(space to select, enter to confirm)",
    ).ask()

    if additional_frameworks is None:
        raise KeyboardInterrupt()

    # Always include claude-code
    answers["frameworks"] = ["claude-code"] + additional_frameworks

    # Claude Code permissions - default is to skip (auto-accept all)
    answers["claude_dangerously_skip_permissions"] = questionary.confirm(
        "Auto-accept Claude Code permission prompts in VM?",
        default=True,
        style=WIZARD_STYLE,
    ).ask()

    if answers["claude_dangerously_skip_permissions"] is None:
        raise KeyboardInterrupt()

    # VM resources
    if questionary.confirm("Customize VM resources?", default=False).ask():
        answers["cpus"] = questionary.text("CPUs:", default="4").ask()
        answers["memory"] = questionary.text("Memory:", default="8GiB").ask()
        answers["disk"] = questionary.text("Disk:", default="20GiB").ask()
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

    # Language version choices, display names, and package managers
    language_config: dict[str, dict[str, str | list[str]]] = {
        "python": {
            "name": "Python",
            "versions": ["3.12", "3.11", "3.10"],
            "label": "Python (uv, uvx, pip, pipx)",
        },
        "node": {
            "name": "Node.js",
            "versions": ["22", "20", "18"],
            "label": "Node.js (npm, npx)",
        },
        "java": {
            "name": "Java",
            "versions": ["21", "17", "11"],
            "label": "Java (maven, gradle)",
        },
        "kotlin": {
            "name": "Kotlin",
            "versions": ["2.0", "1.9"],
            "label": "Kotlin (maven, gradle)",
        },
        "rust": {
            "name": "Rust",
            "versions": ["stable", "nightly"],
            "label": "Rust (cargo)",
        },
        "go": {
            "name": "Go",
            "versions": ["1.25.6", "1.24.12"],
            "label": "Go (go mod)",
        },
    }

    # Languages - checkbox to select which to include (pre-check currently configured)
    selected_languages = questionary.checkbox(
        "Select languages:",
        choices=[
            Choice(
                str(language_config[lang]["label"]),
                value=lang,
                checked=getattr(config, lang) is not None,
            )
            for lang in language_config
        ],
        style=WIZARD_STYLE,
        instruction="(space to select, enter to confirm)",
    ).ask()

    if selected_languages is None:
        raise KeyboardInterrupt()

    # For each selected language, ask for version (default to current or latest)
    for lang in language_config:
        if lang in selected_languages:
            lang_cfg = language_config[lang]
            versions = lang_cfg["versions"]
            assert isinstance(versions, list)

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

    # Tools - pre-check current selections
    # Note: git and npm are always installed via common and node roles
    # Note: uv/poetry auto-installed with Python, maven/gradle with Java/Kotlin
    answers["tools"] = questionary.checkbox(
        "Select tools:",
        choices=[
            Choice("docker", checked="docker" in config.tools),
            Choice("aws-cli", checked="aws-cli" in config.tools),
            Choice("gh", checked="gh" in config.tools),
        ],
        style=WIZARD_STYLE,
        instruction="(space to select, enter to confirm)",
    ).ask()

    if answers["tools"] is None:
        raise KeyboardInterrupt()

    # Databases - pre-check current selections
    answers["databases"] = questionary.checkbox(
        "Select databases:",
        choices=[
            Choice("postgresql", checked="postgresql" in config.databases),
            Choice("redis", checked="redis" in config.databases),
            Choice("mysql", checked="mysql" in config.databases),
        ],
        style=WIZARD_STYLE,
        instruction="(space to select, enter to confirm)",
    ).ask()

    if answers["databases"] is None:
        raise KeyboardInterrupt()

    # Additional frameworks - pre-check current selections (claude-code always included)
    additional_frameworks = questionary.checkbox(
        "Additional frameworks:",
        choices=[
            Choice("playwright", checked="playwright" in config.frameworks),
        ],
        style=WIZARD_STYLE,
        instruction="(space to select, enter to confirm)",
    ).ask()

    if additional_frameworks is None:
        raise KeyboardInterrupt()

    answers["frameworks"] = ["claude-code"] + additional_frameworks

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
