"""Wizard integration for detection feature.

This module provides modified wizard.run() function that accepts detection results
and uses them to pre-populate defaults and pre-check multi-select items.
"""

from pathlib import Path

import click

from ..config import Config
from ..constants import LANGUAGE_CONFIG
from ..spinner import spinner
from ..wizard import _menu_multi_select, _menu_select
from . import detect
from .result import DetectionResult


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
        - Detection defaults used for menu default/preselected parameters
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
            "dart": "None",
            "c": "None",
            "tools": [],
            "databases": [],
            "frameworks": ["claude-code"],
            "cpus": "4",
            "memory": "8GiB",
            "disk": "20GiB",
        }
        defaults = defaults_dict

    answers: dict[str, str | list[str] | bool] = {}

    # Languages - multi-select
    # Note: defaults.get(lang) may return None (key missing) or "None" (not detected)
    # Both should result in unchecked; only explicit version strings mean pre-select
    selected_languages = _menu_multi_select(
        "Select languages:",
        [
            (
                str(LANGUAGE_CONFIG[lang]["label"]),
                lang,
                defaults.get(lang) not in (None, "None"),
            )
            for lang in LANGUAGE_CONFIG
        ],
    )

    if selected_languages is None:
        raise KeyboardInterrupt()

    # For each selected language, ask for version (default to detected)
    for lang in LANGUAGE_CONFIG:
        if lang in selected_languages:
            lang_cfg = LANGUAGE_CONFIG[lang]
            versions = lang_cfg["versions"]
            default_val = defaults.get(lang, versions[0])
            default_version = (
                str(default_val) if not isinstance(default_val, list) else versions[0]
            )
            if default_version == "None":
                default_version = versions[0]

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

    # Tools, databases, and testing combined (multi-select with separators)
    tools_default = defaults.get("tools", [])
    detected_tools = set(tools_default) if isinstance(tools_default, list) else set()
    databases_default = defaults.get("databases", [])
    detected_databases = (
        set(databases_default) if isinstance(databases_default, list) else set()
    )
    tool_selections = _menu_multi_select(
        "Select tools:",
        [
            ("docker", "docker", "docker" in detected_tools),
            ("aws-cli", "aws-cli", "aws-cli" in detected_tools),
            ("gh", "gh", "gh" in detected_tools),
        ],
    )
    database_selections = _menu_multi_select(
        "Select databases:",
        [
            ("postgresql", "postgresql", "postgresql" in detected_databases),
            ("redis", "redis", "redis" in detected_databases),
            ("mysql", "mysql", "mysql" in detected_databases),
            ("sqlite", "sqlite", "sqlite" in detected_databases),
            ("mongodb", "mongodb", "mongodb" in detected_databases),
        ],
    )
    framework_selections = _menu_multi_select(
        "Select frameworks:",
        [
            ("playwright", "playwright", "playwright" in detected_tools),
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
        cpus = click.prompt("CPUs", default=str(defaults.get("cpus", "4")))
        if cpus is None:
            raise KeyboardInterrupt()
        answers["cpus"] = cpus

        memory = click.prompt("Memory", default=str(defaults.get("memory", "8GiB")))
        if memory is None:
            raise KeyboardInterrupt()
        answers["memory"] = memory

        disk = click.prompt("Disk", default=str(defaults.get("disk", "20GiB")))
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
           - Go: find choice matching major.minor (1.23.5 from 1.23)
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
            # Go choices now include full patch versions (1.23.5, 1.22.10)
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
    return confidence in ("high", "medium")
