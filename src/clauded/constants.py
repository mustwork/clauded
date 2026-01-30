"""Shared constants for clauded."""

from typing import TypedDict


class LanguageInfo(TypedDict):
    """Type definition for language configuration."""

    name: str
    versions: list[str]
    label: str


# Language version choices, display names, and package managers
# Used by wizard.py and wizard_integration.py
#
# IMPORTANT: These versions must match what's available in downloads.yml for
# Node.js and Go. For Python, versions are installed via uv python install.
# For Java/Kotlin, versions are installed via apk (openjdk packages).
# For Rust, versions are installed via rustup.
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
        "versions": ["1.23.5", "1.22.10"],
        "label": "Go (go mod)",
    },
}


def get_supported_versions(language: str) -> list[str]:
    """Get supported versions for a language.

    Args:
        language: Language key (python, node, java, kotlin, rust, go)

    Returns:
        List of supported version strings

    Raises:
        KeyError: If language is not recognized
    """
    return LANGUAGE_CONFIG[language]["versions"]


def validate_version(language: str, version: str | None) -> str | None:
    """Validate that a version is supported for a language.

    Args:
        language: Language key (python, node, java, kotlin, rust, go)
        version: Version string to validate, or None

    Returns:
        The version string if valid, or None if version was None

    Raises:
        ValueError: If version is not supported for the language
    """
    if version is None:
        return None

    supported = get_supported_versions(language)
    if version not in supported:
        raise ValueError(
            f"Unsupported {LANGUAGE_CONFIG[language]['name']} version '{version}'. "
            f"Supported versions: {', '.join(supported)}"
        )
    return version


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
