"""Download metadata and integrity verification for supply chain security.

This module provides:
- Centralized access to download URLs, versions, and SHA256 checksums
- Integrity verification utilities for downloaded files
- Ansible-compatible metadata export

All external downloads must be defined in downloads.yml with pinned versions
and verified checksums.
"""

import hashlib
from pathlib import Path
from typing import Any

import yaml


class IntegrityError(Exception):
    """Raised when a downloaded file fails integrity verification."""

    pass


class DownloadMetadataError(Exception):
    """Raised when download metadata is missing or invalid."""

    pass


def _load_downloads_yaml() -> dict[str, Any]:
    """Load the downloads.yml metadata file."""
    downloads_path = Path(__file__).parent / "downloads.yml"
    with open(downloads_path) as f:
        data = yaml.safe_load(f)
    return dict(data)


_DOWNLOADS: dict[str, Any] | None = None


def get_downloads() -> dict[str, Any]:
    """Get the downloads metadata dictionary.

    Returns a cached copy of the downloads.yml content.
    """
    global _DOWNLOADS
    if _DOWNLOADS is None:
        _DOWNLOADS = _load_downloads_yaml()
    return _DOWNLOADS


def get_alpine_image() -> dict[str, str]:
    """Get Alpine Linux cloud image metadata.

    Returns:
        Dict with 'url', 'sha256', 'version', 'arch' keys
    """
    downloads = get_downloads()
    alpine: dict[str, str] = downloads["alpine_image"]
    return alpine


def get_tool_metadata(tool: str, version: str | None = None) -> dict[str, Any]:
    """Get metadata for a specific tool and version.

    Args:
        tool: Tool name (go, kotlin, maven, gradle, uv, bun, rustup)
        version: Specific version, or None for default

    Returns:
        Dict with 'url', 'sha256' and other tool-specific keys

    Raises:
        DownloadMetadataError: If tool or version not found
    """
    downloads = get_downloads()

    if tool not in downloads:
        raise DownloadMetadataError(f"Unknown tool: {tool}")

    tool_data = downloads[tool]

    # Tools with multiple versions (go, kotlin, maven, gradle)
    if "versions" in tool_data:
        if version is None:
            version = tool_data.get("default_version")
        if version not in tool_data["versions"]:
            available = ", ".join(tool_data["versions"].keys())
            raise DownloadMetadataError(
                f"Version {version} not found for {tool}. Available: {available}"
            )
        return {
            "version": version,
            **tool_data["versions"][version],
        }

    # Single-version tools (uv, bun, rustup)
    return dict(tool_data)


def verify_sha256(file_path: Path, expected_sha256: str) -> None:
    """Verify a file's SHA256 checksum.

    Args:
        file_path: Path to the file to verify
        expected_sha256: Expected SHA256 hex digest

    Raises:
        IntegrityError: If checksum doesn't match
        FileNotFoundError: If file doesn't exist
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)

    actual = sha256_hash.hexdigest()
    if actual.lower() != expected_sha256.lower():
        raise IntegrityError(
            f"Checksum verification failed for {file_path}\n"
            f"  Expected: {expected_sha256}\n"
            f"  Actual:   {actual}"
        )


def get_ansible_download_vars() -> dict[str, Any]:
    """Get download metadata formatted for Ansible playbook variables.

    Returns:
        Dict suitable for inclusion in Ansible playbook vars
    """
    downloads = get_downloads()

    # Normalize Go version format (remove leading 'go' if present from config)
    def normalize_go_version(version: str) -> str:
        return version.lstrip("go").strip()

    return {
        "downloads": {
            "alpine_image": downloads["alpine_image"],
            "go": downloads["go"],
            "kotlin": downloads["kotlin"],
            "uv": downloads["uv"],
            "bun": downloads["bun"],
            "rustup": downloads["rustup"],
            "maven": downloads["maven"],
            "gradle": downloads["gradle"],
        },
        "_normalize_go_version": normalize_go_version,
    }
