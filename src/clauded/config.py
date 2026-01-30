"""Configuration management for .clauded.yaml files."""

import hashlib
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .constants import LANGUAGE_CONFIG

logger = logging.getLogger(__name__)

# Current config schema version
CURRENT_VERSION = "1"


class ConfigVersionError(Exception):
    """Raised when config version is incompatible."""

    pass


class ConfigValidationError(Exception):
    """Raised when config values are invalid."""

    pass


def _validate_runtime_version(
    language: str, version: str | None, *, strict: bool = True
) -> str | None:
    """Validate that a runtime version is supported.

    Args:
        language: Language key (python, node, java, kotlin, rust, go)
        version: Version string to validate, or None
        strict: If True, raise error for unsupported versions.
                If False, log warning and return the version anyway.

    Returns:
        The version string if valid, or None if version was None

    Raises:
        ConfigValidationError: If strict=True and version is not supported
    """
    if version is None:
        return None

    if language not in LANGUAGE_CONFIG:
        return version

    supported = LANGUAGE_CONFIG[language]["versions"]
    if version not in supported:
        lang_name = LANGUAGE_CONFIG[language]["name"]
        msg = (
            f"Unsupported {lang_name} version '{version}'. "
            f"Supported versions: {', '.join(supported)}"
        )
        if strict:
            raise ConfigValidationError(msg)
        logger.warning(msg)

    return version


def _migrate_config(data: dict) -> dict:
    """Migrate older config formats to current version.

    Currently a no-op for v1, but establishes the pattern for future upgrades.

    Args:
        data: Raw config data loaded from YAML

    Returns:
        Migrated config data compatible with current version
    """
    # v1 -> v1: No migration needed
    return data


def _validate_version(version: str | None) -> str:
    """Validate config version and return normalized version string.

    Args:
        version: Version string from config, or None if missing

    Returns:
        Validated version string

    Raises:
        ConfigVersionError: If version is incompatible
    """
    if version is None:
        logger.warning("Config file missing version field, assuming version '1'")
        return CURRENT_VERSION

    # Try to parse as integer for comparison
    try:
        version_num = int(version)
        current_num = int(CURRENT_VERSION)

        if version_num > current_num:
            raise ConfigVersionError(
                f"Config file requires clauded version {version} or newer. "
                f"Current clauded supports config version {CURRENT_VERSION}. "
                "Please upgrade clauded to use this config."
            )

        if version_num == current_num:
            return version

        # version_num < current_num would be handled by migration
        return version

    except ValueError:
        # Version string isn't a valid integer
        raise ConfigVersionError(
            f"Unrecognized config version '{version}'. "
            f"Supported versions: {CURRENT_VERSION}"
        ) from None


def _sanitize_vm_name(name: str) -> str:
    """Sanitize a string for use in VM names (valid hostname component)."""
    # Convert to lowercase, replace invalid chars with hyphens
    sanitized = re.sub(r"[^a-z0-9-]", "-", name.lower())
    # Collapse multiple hyphens and strip leading/trailing hyphens
    sanitized = re.sub(r"-+", "-", sanitized).strip("-")
    # Truncate to reasonable length (leaving room for prefix and hash)
    return sanitized[:20] if sanitized else "project"


@dataclass
class Config:
    """Represents a .clauded.yaml configuration."""

    version: str = "1"

    # VM settings
    vm_name: str = ""
    cpus: int = 4
    memory: str = "8GiB"
    disk: str = "20GiB"
    vm_image: str | None = None

    # Mount settings
    mount_host: str = ""
    mount_guest: str = ""

    @property
    def project_name(self) -> str:
        """Get the project name from the mount path."""
        if self.mount_host:
            return Path(self.mount_host).name
        return "unknown"

    # Environment
    python: str | None = None
    node: str | None = None
    java: str | None = None
    kotlin: str | None = None
    rust: str | None = None
    go: str | None = None
    tools: list[str] = field(default_factory=list)
    databases: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)

    # Claude Code settings
    claude_dangerously_skip_permissions: bool = True

    # SSH settings
    ssh_host_key_checking: bool = True

    @classmethod
    def from_wizard(cls, answers: dict[str, Any], project_path: Path) -> "Config":
        """Create a Config from wizard answers."""
        project_name = _sanitize_vm_name(project_path.name)
        path_hash = hashlib.sha256(str(project_path).encode()).hexdigest()[:6]
        vm_name = f"clauded-{project_name}-{path_hash}"

        return cls(
            vm_name=vm_name,
            cpus=int(answers.get("cpus", 4)),
            memory=answers.get("memory", "8GiB"),
            disk=answers.get("disk", "20GiB"),
            mount_host=str(project_path),
            mount_guest=str(project_path),
            python=answers.get("python") if answers.get("python") != "None" else None,
            node=answers.get("node") if answers.get("node") != "None" else None,
            java=answers.get("java") if answers.get("java") != "None" else None,
            kotlin=answers.get("kotlin") if answers.get("kotlin") != "None" else None,
            rust=answers.get("rust") if answers.get("rust") != "None" else None,
            go=answers.get("go") if answers.get("go") != "None" else None,
            tools=answers.get("tools", []),
            databases=answers.get("databases", []),
            frameworks=answers.get("frameworks", []),
            claude_dangerously_skip_permissions=answers.get(
                "claude_dangerously_skip_permissions", True
            ),
            ssh_host_key_checking=answers.get("ssh_host_key_checking", True),
        )

    @classmethod
    def load(cls, path: Path) -> "Config":
        """Load config from a .clauded.yaml file.

        Performs validation and migration:
        - Validates schema version compatibility
        - Migrates older config formats
        - Ensures mount_guest matches mount_host (auto-corrects if different)

        Raises:
            ConfigVersionError: If config version is incompatible
        """
        with open(path) as f:
            data = yaml.safe_load(f)

        # Validate and normalize version
        version = _validate_version(data.get("version"))

        # Migrate older configs if needed
        data = _migrate_config(data)

        # Validate mount paths - auto-correct if different
        mount_host = data["mount"]["host"]
        mount_guest = data["mount"]["guest"]
        if mount_guest != mount_host:
            logger.warning(
                f"Config mount_guest ({mount_guest}) differs from mount_host "
                f"({mount_host}). Auto-correcting mount_guest to match mount_host."
            )
            mount_guest = mount_host

        # Validate runtime versions (strict validation for supported versions)
        env = data.get("environment", {})
        python_ver = _validate_runtime_version("python", env.get("python"))
        node_ver = _validate_runtime_version("node", env.get("node"))
        java_ver = _validate_runtime_version("java", env.get("java"))
        kotlin_ver = _validate_runtime_version("kotlin", env.get("kotlin"))
        rust_ver = _validate_runtime_version("rust", env.get("rust"))
        go_ver = _validate_runtime_version("go", env.get("go"))

        return cls(
            version=version,
            vm_name=data["vm"]["name"],
            cpus=data["vm"]["cpus"],
            memory=data["vm"]["memory"],
            disk=data["vm"]["disk"],
            vm_image=data["vm"].get("image"),
            mount_host=mount_host,
            mount_guest=mount_guest,
            python=python_ver,
            node=node_ver,
            java=java_ver,
            kotlin=kotlin_ver,
            rust=rust_ver,
            go=go_ver,
            tools=env.get("tools") or [],
            databases=env.get("databases") or [],
            frameworks=env.get("frameworks") or [],
            claude_dangerously_skip_permissions=data.get("claude", {}).get(
                "dangerously_skip_permissions", True
            ),
            ssh_host_key_checking=data.get("ssh", {}).get("host_key_checking", True),
        )

    def save(self, path: Path) -> None:
        """Save config to a .clauded.yaml file."""
        vm_data: dict[str, Any] = {
            "name": self.vm_name,
            "cpus": self.cpus,
            "memory": self.memory,
            "disk": self.disk,
        }
        if self.vm_image is not None:
            vm_data["image"] = self.vm_image

        data = {
            "version": self.version,
            "vm": vm_data,
            "mount": {
                "host": self.mount_host,
                "guest": self.mount_guest,
            },
            "environment": {
                "python": self.python,
                "node": self.node,
                "java": self.java,
                "kotlin": self.kotlin,
                "rust": self.rust,
                "go": self.go,
                "tools": self.tools,
                "databases": self.databases,
                "frameworks": self.frameworks,
            },
            "claude": {
                "dangerously_skip_permissions": (
                    self.claude_dangerously_skip_permissions
                ),
            },
            "ssh": {
                "host_key_checking": self.ssh_host_key_checking,
            },
        }

        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
