"""Linguist data loading and language detection."""

from pathlib import Path
from typing import Any

import yaml


def load_yaml_file(filename: str) -> dict[str, Any]:
    """Load a YAML file from the linguist data directory."""
    linguist_dir = Path(__file__).parent
    filepath = linguist_dir / filename

    with open(filepath) as f:
        return yaml.safe_load(f) or {}


def load_languages() -> dict[str, Any]:
    """Load languages.yml mapping extensions to language metadata."""
    return load_yaml_file("languages.yml")


def load_heuristics() -> dict[str, Any]:
    """Load heuristics.yml containing disambiguation rules."""
    return load_yaml_file("heuristics.yml")


def load_vendor_patterns() -> dict[str, Any]:
    """Load vendor.yml containing paths to exclude from detection."""
    return load_yaml_file("vendor.yml")


__all__ = [
    "load_languages",
    "load_heuristics",
    "load_vendor_patterns",
    "load_yaml_file",
]
