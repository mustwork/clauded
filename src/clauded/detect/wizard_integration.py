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


def apply_detection_to_config(
    config: "Config",
    project_path: Path,
    *,
    debug: bool = False,
) -> tuple["Config", bool]:
    """Apply detection results to config (additive merge without wizard).

    CONTRACT:
      Inputs:
        - config: existing Config object
        - project_path: directory path to project root
        - debug: enable debug logging

      Outputs:
        - tuple of (updated Config, bool indicating if changes were made)

      Invariants:
        - User's existing choices are preserved
        - Detection adds new requirements but doesn't remove user choices
        - Returns a new Config object, does not mutate the input

      Algorithm:
        1. Run detection
        2. Create detection defaults
        3. Merge with existing config (additive)
        4. Create new Config with merged values
        5. Return (new config, changes_made)
    """
    from .cli_integration import create_wizard_defaults

    # Run detection
    with spinner("Detecting project configuration"):
        detection = detect(project_path, debug=debug)

    # Check if detection found anything
    has_detection = detection and (
        detection.languages
        or detection.versions
        or detection.frameworks
        or detection.mcp_runtimes
        or detection.tools
    )

    if not has_detection:
        return config, False

    # Create defaults and merge with existing config
    detection_defaults = create_wizard_defaults(detection)
    merged = merge_detection_with_config(detection_defaults, config)

    # Check if anything changed
    changes_made = False

    # Check runtimes
    for runtime in ("python", "node", "java", "kotlin", "rust", "go", "dart", "c"):
        config_value = getattr(config, runtime, None)
        merged_value = merged.get(runtime)
        if merged_value == "None":
            merged_value = None
        if config_value != merged_value:
            changes_made = True
            break

    # Check tools/databases/frameworks
    if not changes_made:
        if set(config.tools or []) != set(merged.get("tools", [])):
            changes_made = True
        elif set(config.databases or []) != set(merged.get("databases", [])):
            changes_made = True
        elif set(config.frameworks or []) != set(merged.get("frameworks", [])):
            changes_made = True

    if not changes_made:
        return config, False

    # Create new config with merged values (preserve VM settings from original)
    from ..config import Config as ConfigClass  # noqa: F811

    new_config = ConfigClass(
        version=config.version,
        vm_name=config.vm_name,
        cpus=config.cpus,
        memory=config.memory,
        disk=config.disk,
        vm_image=config.vm_image,
        mount_host=config.mount_host,
        mount_guest=config.mount_guest,
        python=str(merged["python"]) if merged["python"] != "None" else None,
        node=str(merged["node"]) if merged["node"] != "None" else None,
        java=str(merged["java"]) if merged["java"] != "None" else None,
        kotlin=str(merged["kotlin"]) if merged["kotlin"] != "None" else None,
        rust=str(merged["rust"]) if merged["rust"] != "None" else None,
        go=str(merged["go"]) if merged["go"] != "None" else None,
        dart=str(merged["dart"]) if merged["dart"] != "None" else None,
        c=str(merged["c"]) if merged["c"] != "None" else None,
        tools=list(merged.get("tools", [])),
        databases=list(merged.get("databases", [])),
        frameworks=list(merged.get("frameworks", [])),
        claude_dangerously_skip_permissions=config.claude_dangerously_skip_permissions,
        ssh_host_key_checking=config.ssh_host_key_checking,
        keep_vm_running=config.keep_vm_running,
    )

    return new_config, True


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


def merge_detection_with_config(
    detection_defaults: dict[str, str | list[str]],
    config: "Config",
) -> dict[str, str | list[str]]:
    """Merge detection results with existing config (additive).

    CONTRACT:
      Inputs:
        - detection_defaults: dict from create_wizard_defaults()
        - config: existing Config object

      Outputs:
        - dict with merged defaults for wizard

      Invariants:
        - User's existing choices are preserved
        - Detection adds new requirements but doesn't remove user choices
        - For runtimes: if user has version, keep it; if detection finds required
          runtime and user doesn't have it, add detected version
        - For tools/databases/frameworks: union of existing and detected

      Algorithm:
        1. Start with detection defaults as base
        2. For each runtime: if config has it, use config value
        3. For tools/databases/frameworks: union of config and detection
        4. Preserve VM resources from config
    """
    merged: dict[str, str | list[str]] = {}

    # Runtimes: keep user choice if set, otherwise use detection
    for runtime in ("python", "node", "java", "kotlin", "rust", "go", "dart", "c"):
        config_value = getattr(config, runtime, None)
        if config_value is not None:
            # User has this runtime configured - keep their version
            merged[runtime] = config_value
        else:
            # User doesn't have it - use detection (may be "None" or a version)
            merged[runtime] = detection_defaults.get(runtime, "None")

    # Tools: union of existing and detected
    config_tools = set(config.tools) if config.tools else set()
    detected_tools = set(detection_defaults.get("tools", []))
    merged["tools"] = list(config_tools | detected_tools)

    # Databases: union of existing and detected
    config_databases = set(config.databases) if config.databases else set()
    detected_databases = set(detection_defaults.get("databases", []))
    merged["databases"] = list(config_databases | detected_databases)

    # Frameworks: union of existing and detected (claude-code always included)
    config_frameworks = set(config.frameworks) if config.frameworks else set()
    detected_frameworks = set(detection_defaults.get("frameworks", []))
    frameworks_list = list(config_frameworks | detected_frameworks)
    if "claude-code" not in frameworks_list:
        frameworks_list.insert(0, "claude-code")
    merged["frameworks"] = frameworks_list

    # VM resources from config (cannot change without recreation)
    merged["cpus"] = str(config.cpus)
    merged["memory"] = config.memory
    merged["disk"] = config.disk

    return merged


def run_edit_with_detection(
    config: "Config",
    project_path: Path,
    *,
    debug: bool = False,
) -> "Config":
    """Run edit wizard with detection, merging results with existing config.

    CONTRACT:
      Inputs:
        - config: existing Config object
        - project_path: directory path to project root
        - debug: enable debug logging

      Outputs:
        - Config: updated configuration from wizard

      Invariants:
        - Detection runs and merges with existing config
        - User can override all values in wizard
        - VM resources preserved from original config

      Algorithm:
        1. Run detection
        2. Create detection defaults
        3. Merge with existing config (additive)
        4. Display detection summary
        5. Run wizard with merged defaults
    """
    from .cli_integration import create_wizard_defaults, display_detection_summary

    print("\n  clauded - Edit VM Configuration\n")
    print("  (VM resources cannot be changed without recreation)\n")

    # Run detection
    with spinner("Detecting project configuration"):
        detection = detect(project_path, debug=debug)

    # Create defaults and merge with existing config
    has_detection = detection and (
        detection.languages
        or detection.versions
        or detection.frameworks
        or detection.mcp_runtimes
    )
    if has_detection:
        display_detection_summary(detection)
        detection_defaults = create_wizard_defaults(detection)
        defaults = merge_detection_with_config(detection_defaults, config)
    else:
        # No detection results - use existing config values
        defaults = {
            "python": config.python or "None",
            "node": config.node or "None",
            "java": config.java or "None",
            "kotlin": config.kotlin or "None",
            "rust": config.rust or "None",
            "go": config.go or "None",
            "dart": config.dart or "None",
            "c": config.c or "None",
            "tools": list(config.tools) if config.tools else [],
            "databases": list(config.databases) if config.databases else [],
            "frameworks": list(config.frameworks) if config.frameworks else [],
            "cpus": str(config.cpus),
            "memory": config.memory,
            "disk": config.disk,
        }

    answers: dict[str, str | list[str] | bool] = {}

    # Languages - multi-select with merged defaults
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

    # For each selected language, ask for version (default to merged value)
    for lang in LANGUAGE_CONFIG:
        if lang in selected_languages:
            lang_cfg = LANGUAGE_CONFIG[lang]
            versions = lang_cfg["versions"]
            default_val = defaults.get(lang, versions[0])
            default_version = (
                str(default_val) if not isinstance(default_val, list) else versions[0]
            )
            if default_version == "None" or default_version not in versions:
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

    # Tools, databases, and frameworks with merged defaults
    tools_default = defaults.get("tools", [])
    merged_tools = set(tools_default) if isinstance(tools_default, list) else set()
    databases_default = defaults.get("databases", [])
    merged_databases = (
        set(databases_default) if isinstance(databases_default, list) else set()
    )
    frameworks_default = defaults.get("frameworks", [])
    merged_frameworks = (
        set(frameworks_default) if isinstance(frameworks_default, list) else set()
    )

    tool_selections = _menu_multi_select(
        "Select tools:",
        [
            ("docker", "docker", "docker" in merged_tools),
            ("aws-cli", "aws-cli", "aws-cli" in merged_tools),
            ("gh", "gh", "gh" in merged_tools),
        ],
    )
    database_selections = _menu_multi_select(
        "Select databases:",
        [
            ("postgresql", "postgresql", "postgresql" in merged_databases),
            ("redis", "redis", "redis" in merged_databases),
            ("mysql", "mysql", "mysql" in merged_databases),
            ("sqlite", "sqlite", "sqlite" in merged_databases),
            ("mongodb", "mongodb", "mongodb" in merged_databases),
        ],
    )
    framework_selections = _menu_multi_select(
        "Select frameworks:",
        [
            ("playwright", "playwright", "playwright" in merged_frameworks),
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
