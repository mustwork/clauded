"""Linguist data loading and language detection.

Thread-safety: All loading functions use functools.lru_cache which is
thread-safe for initialization in CPython (GIL protects the cache dict).
"""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


def _load_yaml_file(filename: str) -> dict[str, Any]:
    """Load a YAML file from the linguist data directory.

    Internal function - use the cached load_* functions instead.
    """
    linguist_dir = Path(__file__).parent
    filepath = linguist_dir / filename

    with open(filepath) as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=1)
def load_languages() -> dict[str, Any]:
    """Load languages.yml mapping extensions to language metadata.

    Thread-safe: Uses lru_cache for initialization protection.
    """
    return _load_yaml_file("languages.yml")


@lru_cache(maxsize=1)
def load_heuristics() -> dict[str, Any]:
    """Load heuristics.yml containing disambiguation rules.

    Thread-safe: Uses lru_cache for initialization protection.
    """
    return _load_yaml_file("heuristics.yml")


@lru_cache(maxsize=1)
def load_vendor_patterns() -> dict[str, Any]:
    """Load vendor.yml containing paths to exclude from detection.

    Thread-safe: Uses lru_cache for initialization protection.
    """
    return _load_yaml_file("vendor.yml")


__all__ = [
    "load_languages",
    "load_heuristics",
    "load_vendor_patterns",
]
