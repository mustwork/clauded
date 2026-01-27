"""Wizard integration for detection feature.

This module provides modified wizard.run() function that accepts detection results
and uses them to pre-populate defaults and pre-check multi-select items.
"""

from pathlib import Path

import questionary
from questionary import Choice

from ..config import Config
from .result import DetectionResult


def run_with_detection(
    project_path: Path, detection: DetectionResult | None = None
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
        3. For each runtime (Python, Node, Java, Kotlin, Rust, Go):
           a. Determine default value from detection or static default
           b. Present questionary select with default
           c. Store answer
        4. For tools:
           a. Determine which tools to pre-check from detection
           b. Present questionary checkbox with checked items
           c. Store answer
        5. For databases:
           a. Determine which databases to pre-check from detection
           b. Present questionary checkbox with checked items
           c. Store answer
        6. For frameworks:
           a. Determine which frameworks to pre-check from detection
           b. Always include claude-code
           c. Present questionary checkbox with checked items
           c. Store answer
        7. Optionally ask for VM resource customization
        8. Return Config.from_wizard(answers, project_path)
    """
    from .cli_integration import create_wizard_defaults, display_detection_summary

    print("\n  clauded - VM Environment Setup\n")

    # Create defaults from detection if provided
    if detection:
        display_detection_summary(detection)
        defaults = create_wizard_defaults(detection)
    else:
        defaults_dict: dict[str, str | list[str]] = {
            "python": "3.12",
            "node": "20",
            "java": "21",
            "kotlin": "2.0",
            "rust": "stable",
            "go": "1.22",
            "tools": [],
            "databases": [],
            "frameworks": ["claude-code"],
            "cpus": "4",
            "memory": "8GiB",
            "disk": "20GiB",
        }
        defaults = defaults_dict

    answers: dict[str, str | list[str]] = {}

    # Python version
    answers["python"] = questionary.select(
        "Python version?",
        choices=["3.12", "3.11", "3.10", "None"],
        default=str(defaults.get("python", "3.12")),
    ).ask()

    if answers["python"] is None:
        raise KeyboardInterrupt()

    # Node version
    answers["node"] = questionary.select(
        "Node.js version?",
        choices=["22", "20", "18", "None"],
        default=str(defaults.get("node", "20")),
    ).ask()

    if answers["node"] is None:
        raise KeyboardInterrupt()

    # Java version
    answers["java"] = questionary.select(
        "Java version?",
        choices=["21", "17", "11", "None"],
        default=str(defaults.get("java", "21")),
    ).ask()

    if answers["java"] is None:
        raise KeyboardInterrupt()

    # Kotlin version
    answers["kotlin"] = questionary.select(
        "Kotlin version?",
        choices=["2.0", "1.9", "None"],
        default=str(defaults.get("kotlin", "2.0")),
    ).ask()

    if answers["kotlin"] is None:
        raise KeyboardInterrupt()

    # Rust version
    answers["rust"] = questionary.select(
        "Rust version?",
        choices=["stable", "nightly", "None"],
        default=str(defaults.get("rust", "stable")),
    ).ask()

    if answers["rust"] is None:
        raise KeyboardInterrupt()

    # Go version
    answers["go"] = questionary.select(
        "Go version?",
        choices=["1.22", "1.21", "1.20", "None"],
        default=str(defaults.get("go", "1.22")),
    ).ask()

    if answers["go"] is None:
        raise KeyboardInterrupt()

    # Tools
    tools_default = defaults.get("tools", [])
    detected_tools = set(tools_default) if isinstance(tools_default, list) else set()
    answers["tools"] = questionary.checkbox(
        "Select tools:",
        choices=[
            Choice("docker", checked="docker" in detected_tools),
            Choice("aws-cli", checked="aws-cli" in detected_tools),
            Choice("gh", checked="gh" in detected_tools),
        ],
    ).ask()

    if answers["tools"] is None:
        raise KeyboardInterrupt()

    # Databases
    databases_default = defaults.get("databases", [])
    detected_databases = (
        set(databases_default) if isinstance(databases_default, list) else set()
    )
    answers["databases"] = questionary.checkbox(
        "Select databases:",
        choices=[
            Choice("postgresql", checked="postgresql" in detected_databases),
            Choice("redis", checked="redis" in detected_databases),
            Choice("mysql", checked="mysql" in detected_databases),
        ],
    ).ask()

    if answers["databases"] is None:
        raise KeyboardInterrupt()

    # Frameworks - always include claude-code
    frameworks_default = defaults.get("frameworks", ["claude-code"])
    detected_frameworks = (
        set(frameworks_default) if isinstance(frameworks_default, list) else set()
    )
    additional_frameworks = questionary.checkbox(
        "Additional frameworks:",
        choices=[
            Choice("playwright", checked="playwright" in detected_frameworks),
        ],
    ).ask()

    if additional_frameworks is None:
        raise KeyboardInterrupt()

    # Always include claude-code
    answers["frameworks"] = ["claude-code"] + additional_frameworks

    # VM resources
    if questionary.confirm("Customize VM resources?", default=False).ask():
        answers["cpus"] = questionary.text(
            "CPUs:", default=str(defaults.get("cpus", "4"))
        ).ask()
        answers["memory"] = questionary.text(
            "Memory:", default=str(defaults.get("memory", "8GiB"))
        ).ask()
        answers["disk"] = questionary.text(
            "Disk:", default=str(defaults.get("disk", "20GiB"))
        ).ask()
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
           - Go: extract major.minor (1.22 from 1.22.3)
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
            # Extract major.minor: "1.22.3" → "1.22"
            match = re.match(r"^(\d+\.\d+)", clean_version)
            if match:
                normalized = match.group(1)
                return normalized if normalized in choices else None

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
