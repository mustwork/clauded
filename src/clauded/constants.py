"""Shared constants for clauded."""

from typing import TypedDict


class LanguageInfo(TypedDict):
    """Type definition for language configuration."""

    name: str
    versions: list[str]
    label: str


# Language version choices, display names, and package managers
# Used by wizard.py and wizard_integration.py
LANGUAGE_CONFIG: dict[str, LanguageInfo] = {
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

# Default languages to pre-select in wizard
DEFAULT_LANGUAGES = {"python", "node"}


def confidence_marker(confidence: str) -> str:
    """Return display marker for a confidence level.

    Args:
        confidence: Confidence level string ("high", "medium", or "low")

    Returns:
        Display marker string: "" for high, " (detected)" for medium,
        " (suggestion)" for low confidence.
    """
    if confidence == "high":
        return ""
    elif confidence == "medium":
        return " (detected)"
    else:  # low
        return " (suggestion)"
