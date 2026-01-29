"""Wizard integration for detection feature.

This module provides modified wizard.run() function that accepts detection results
and uses them to pre-populate defaults and pre-check multi-select items.
"""

from pathlib import Path

import questionary
from questionary import Choice, Separator, Style

from ..config import Config
from ..spinner import spinner
from . import detect
from .result import DetectionResult

# Custom style: no text inversion, use cyan highlighting and circle indicators
WIZARD_STYLE = Style(
    [
        ("highlighted", "noreverse fg:ansibrightcyan"),  # Cyan text, no inversion
        ("selected", "noreverse fg:ansibrightcyan"),  # Cyan for checked items
        ("pointer", "noreverse fg:ansicyan bold"),  # Bold cyan pointer
        ("answer", "fg:ansigreen"),  # Green submitted answer
    ]
)


def run_with_detection(
    project_path: Path,
    detection: DetectionResult | None = None,
    *,
    debug: bool = False,
) -> Config:
    """Run interactive wizard with detection-based defaults.

    CONTRACT:
      Inputs:
        - project_path: directory path to project root
        - detection: DetectionResult with pre-populated defaults, or None for
          static defaults

      Outputs:
        - Config: configuration object from wizard answers

      Invariants:
        - If detection is None, uses static defaults (same as original wizard.run)
        - User can override all detection results
        - Never raises exceptions except KeyboardInterrupt on user cancellation

      Properties:
        - Detection defaults used for questionary default/checked parameters
        - High/medium confidence → pre-selected
        - Low confidence → available but not pre-selected

      Algorithm:
        1. Print wizard header
        2. Display detection summary if detection provided
        3. Languages (single checkbox screen):
           a. Show all languages with latest versions
           b. Pre-check detected languages
           c. Install latest version for each selected language
        4. Tools, databases, frameworks: checkbox with detection-based defaults
        5. Optionally ask for VM resource customization
        6. Return Config.from_wizard(answers, project_path)
    """
    from .cli_integration import create_wizard_defaults, display_detection_summary

    print("\n  clauded - VM Environment Setup\n")

    # Run detection if not provided
    if detection is None:
        with spinner("Detecting project configuration"):
            detection = detect(project_path, debug=debug)

    # Create defaults from detection if provided
    has_detection = detection and (
        detection.languages or detection.versions or detection.frameworks
    )
    if has_detection:
        display_detection_summary(detection)
        defaults = create_wizard_defaults(detection)
    else:
        defaults_dict: dict[str, str | list[str]] = {
            "python": "None",
            "node": "None",
            "java": "None",
            "kotlin": "None",
            "rust": "None",
            "go": "None",
            "tools": [],
            "databases": [],
            "frameworks": ["claude-code"],
            "cpus": "4",
            "memory": "8GiB",
            "disk": "20GiB",
        }
        defaults = defaults_dict

    answers: dict[str, str | list[str]] = {}

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

    # Languages - single checkbox for all
    selected_languages = questionary.checkbox(
        "Select languages:",
        choices=[
            Choice(
                str(language_config[lang]["label"]),
                value=lang,
                checked=defaults.get(lang) != "None",
            )
            for lang in language_config
        ],
        style=WIZARD_STYLE,
        instruction="(space to select, enter to confirm)",
    ).ask()

    if selected_languages is None:
        raise KeyboardInterrupt()

    # For each selected language, ask for version (default to detected)
    for lang in language_config:
        if lang in selected_languages:
            config = language_config[lang]
            versions = config["versions"]
            assert isinstance(versions, list)
            default_val = defaults.get(lang, versions[0])
            default_version = (
                str(default_val) if not isinstance(default_val, list) else versions[0]
            )
            if default_version == "None":
                default_version = versions[0]

            version = questionary.select(
                f"{config['name']} version?",
                choices=versions,
                default=default_version if default_version in versions else versions[0],
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
    tools_default = defaults.get("tools", [])
    detected_tools = set(tools_default) if isinstance(tools_default, list) else set()
    databases_default = defaults.get("databases", [])
    detected_databases = (
        set(databases_default) if isinstance(databases_default, list) else set()
    )
    frameworks_default = defaults.get("frameworks", ["claude-code"])
    detected_frameworks = (
        set(frameworks_default) if isinstance(frameworks_default, list) else set()
    )
    selections = questionary.checkbox(
        "Select tools, databases, and frameworks:",
        choices=[
            Separator("── Tools ──"),
            Choice("docker", checked="docker" in detected_tools),
            Choice("aws-cli", checked="aws-cli" in detected_tools),
            Choice("gh", checked="gh" in detected_tools),
            Separator("── Databases ──"),
            Choice("postgresql", checked="postgresql" in detected_databases),
            Choice("redis", checked="redis" in detected_databases),
            Choice("mysql", checked="mysql" in detected_databases),
            Choice("sqlite", checked="sqlite" in detected_databases),
            Separator("── Frameworks ──"),
            Choice("playwright", checked="playwright" in detected_frameworks),
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

    # VM resources
    customize_resources = questionary.confirm(
        "Customize VM resources?", default=False
    ).ask()

    if customize_resources is None:
        raise KeyboardInterrupt()

    if customize_resources:
        cpus = questionary.text("CPUs:", default=str(defaults.get("cpus", "4"))).ask()
        if cpus is None:
            raise KeyboardInterrupt()
        answers["cpus"] = cpus

        memory = questionary.text(
            "Memory:", default=str(defaults.get("memory", "8GiB"))
        ).ask()
        if memory is None:
            raise KeyboardInterrupt()
        answers["memory"] = memory

        disk = questionary.text(
            "Disk:", default=str(defaults.get("disk", "20GiB"))
        ).ask()
        if disk is None:
            raise KeyboardInterrupt()
        answers["disk"] = disk
    else:
        answers["cpus"] = str(defaults.get("cpus", "4"))
        answers["memory"] = str(defaults.get("memory", "8GiB"))
        answers["disk"] = str(defaults.get("disk", "20GiB"))

    return Config.from_wizard(answers, project_path)


def normalize_version_for_choice(
    version: str, runtime: str, choices: list[str]
) -> str | None:
    """Normalize detected version string to match wizard choice format.

    CONTRACT:
      Inputs:
        - version: detected version string (may include patch, constraints, etc.)
        - runtime: runtime name ("python", "node", "java", etc.)
        - choices: list of valid wizard choices for this runtime

      Outputs:
        - choice string: from choices list that matches detected version
        - None: if detected version doesn't match any choice

      Invariants:
        - Returned value must be in choices list or None
        - Never raises exceptions

      Properties:
        - Version matching examples:
          * "3.12.0" + choices=["3.12", "3.11"] → "3.12"
          * ">=3.10" + choices=["3.12", "3.11", "3.10"] → "3.10" (minimum)
          * "20.10.0" + choices=["22", "20", "18"] → "20"
          * "stable" + choices=["stable", "nightly"] → "stable"

      Algorithm:
        1. Parse version string based on runtime:
           - Python: extract major.minor (3.12 from 3.12.0 or >=3.10)
           - Node: extract major (20 from 20.10.0 or ^20.0.0)
           - Java: extract major (21 from 21 or 21.0.1)
           - Kotlin: extract major.minor (2.0 from 2.0.10)
           - Rust: use as-is (stable, nightly, or version)
           - Go: find choice matching major.minor (1.25.6 from 1.25)
        2. Check if normalized version in choices list
        3. Return matching choice or None
    """
    import re

    try:
        if not version or not choices:
            return None

        # Remove constraint operators
        clean_version = re.sub(r"^[><=~^]+\s*", "", version).strip()

        if runtime == "python":
            # Extract major.minor: "3.12.0" → "3.12", "3.12" → "3.12"
            match = re.match(r"^(\d+\.\d+)", clean_version)
            if match:
                normalized = match.group(1)
                return normalized if normalized in choices else None
        elif runtime == "node":
            # Extract major: "20.10.0" → "20"
            match = re.match(r"^(\d+)", clean_version)
            if match:
                normalized = match.group(1)
                return normalized if normalized in choices else None
        elif runtime == "java":
            # Extract major: "21.0.1" → "21" or "21" → "21"
            match = re.match(r"^(\d+)", clean_version)
            if match:
                normalized = match.group(1)
                return normalized if normalized in choices else None
        elif runtime == "kotlin":
            # Extract major.minor: "2.0.10" → "2.0"
            match = re.match(r"^(\d+\.\d+)", clean_version)
            if match:
                normalized = match.group(1)
                return normalized if normalized in choices else None
        elif runtime == "rust":
            # Use as-is for Rust (stable, nightly, or version number)
            if clean_version in choices:
                return clean_version
            # Try matching stable/nightly even with suffixes
            if clean_version.startswith("stable"):
                return "stable" if "stable" in choices else None
            if clean_version.startswith("nightly"):
                return "nightly" if "nightly" in choices else None
            # Try extracting version number from nightly-YYYY-MM-DD format
            if "stable" in choices and clean_version and clean_version[0].isdigit():
                return "stable"
        elif runtime == "go":
            # Go choices now include full patch versions (1.25.6, 1.24.12)
            # First check if exact match
            if clean_version in choices:
                return clean_version
            # Extract major.minor and find matching choice
            match = re.match(r"^(\d+\.\d+)", clean_version)
            if match:
                major_minor = match.group(1)
                # Find choice that starts with this major.minor
                for choice in choices:
                    if choice.startswith(major_minor):
                        return choice
            return None

        return None
    except Exception:
        return None


def map_confidence_to_checked(confidence: str) -> bool:
    """Determine if item should be pre-checked based on confidence level.

    CONTRACT:
      Inputs:
        - confidence: confidence level ("high", "medium", "low")

      Outputs:
        - boolean: True if should be pre-checked, False otherwise

      Invariants:
        - High confidence → True
        - Medium confidence → True
        - Low confidence → False
        - Never raises exceptions

      Algorithm:
        Simple mapping: high|medium → True, low → False
    """
    # TODO: Trivial implementation - will implement directly
    return confidence in ("high", "medium")
