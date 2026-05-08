"""Configuration management for .clauded.yaml files."""

import hashlib
import logging
import os
import re
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

from .constants import LANGUAGE_CONFIG

logger = logging.getLogger(__name__)

# Current config schema version
CURRENT_VERSION = "1"

# Accepted values for the top-level `harness:` field in .clauded.yaml.
# Single source of truth used by Config.load validation, the wizard menu, and
# the --harness CLI flag's click.Choice (added by later stories).
HARNESS_NAMES: tuple[str, ...] = ("claude-code", "codex", "opencode")

# Documentation-only alias. Config.harness stores `str` for dataclass
# compatibility; callers that want type-narrowing can opt in via this alias.
HarnessName = Literal["claude-code", "codex", "opencode"]

# Curated claude-code-router provider names accepted in vm.claude_code_router.providers.
# Ollama is implicit (auto-discovered) and Anthropic passthrough is unconditional;
# neither appears here.
CCR_PROVIDER_WHITELIST: frozenset[str] = frozenset({"minimax", "groq", "together"})

# Model alias keys accepted in vm.claude_code_router.overrides. Each key maps a
# short alias to an explicit "<provider>/<model>" string that the role translates
# into CCR's "<provider>,<model>" routing syntax (in /etc/clauded/ccr-router.js).
CCR_OVERRIDE_KEYS: frozenset[str] = frozenset({"haiku", "sonnet", "opus"})

# Pino log levels accepted by CCR (passed through to config.json LOG_LEVEL).
CCR_LOG_LEVELS: frozenset[str] = frozenset(
    {"fatal", "error", "warn", "info", "debug", "trace"}
)


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


def _validate_vm_name(vm_name: str) -> str:
    """Validate VM name for security (no path traversal).

    Args:
        vm_name: VM name from config

    Returns:
        Validated VM name

    Raises:
        ValueError: If VM name contains path traversal characters
    """
    if not vm_name:
        raise ValueError("VM name cannot be empty")

    # Check for path traversal attempts
    if ".." in vm_name or "/" in vm_name or "\\" in vm_name:
        raise ValueError(
            f"Invalid VM name '{vm_name}': cannot contain path separators or '..'"
        )

    return vm_name


# Strict pattern: digits and dots only (e.g. "2.1.62", "1.2.0", "20")
_VERSION_PIN_RE = re.compile(r"^[0-9]+(\.[0-9]+)*$")


def _validate_version_pin(key: str, value: str | None) -> str | None:
    """Validate a framework version pin for safety and consistency.

    Accepts None (meaning "latest"), or a concrete version string consisting
    only of digits and dots (e.g. "2.1.62").  The sentinel string "latest"
    is normalized to None so that downstream code has exactly one
    representation of "resolve at runtime".

    Args:
        key: Config key name (for error messages, e.g. "claude-code")
        value: Version string, "latest", or None

    Returns:
        Validated version string, or None for "latest"

    Raises:
        ConfigValidationError: If value is not a safe version string
    """
    if value is None:
        return None

    if not isinstance(value, str):
        raise ConfigValidationError(
            f"Invalid version pin for '{key}': expected a version string, "
            f"got {type(value).__name__}"
        )

    # Normalize "latest" to None (means "resolve at runtime")
    if value == "latest":
        return None

    if not _VERSION_PIN_RE.match(value):
        raise ConfigValidationError(
            f"Invalid version pin for '{key}': '{value}'. "
            "Version pins must contain only digits and dots (e.g. '2.1.62')."
        )

    return value


def _validate_harness(value: object, frameworks: list[str]) -> str:
    """Validate the harness identifier and enforce the harness ⇒ framework rule.

    Args:
        value: Raw harness value from YAML (or None when the key is absent).
        frameworks: Already-parsed list of framework identifiers from the same
            config; required for the harness ⇒ framework cross-check.

    Returns:
        Resolved harness name (defaults to "claude-code" when value is None).

    Raises:
        ConfigValidationError: When value is a non-string, an unknown harness,
            or names a framework that is not in the frameworks list. The
            provisioner only installs frameworks that appear in
            ``config.frameworks``, so the launched harness binary must also
            be present in that list — otherwise the VM ships without the
            chosen binary and the shell launch fails at runtime.
    """
    if value is None:
        value = "claude-code"

    if not isinstance(value, str):
        raise ConfigValidationError(
            f"Invalid harness value: expected one of {list(HARNESS_NAMES)}, "
            f"got {type(value).__name__}"
        )

    if value not in HARNESS_NAMES:
        raise ConfigValidationError(
            f"Unknown harness '{value}'. Accepted values: {', '.join(HARNESS_NAMES)}."
        )

    if value not in frameworks:
        raise ConfigValidationError(
            f"harness '{value}' requires '{value}' in frameworks. "
            "Run `clauded --edit` to add it to the frameworks list, "
            "or pick a different harness."
        )

    return value


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
    cpus: int = 1
    memory: str = "8GiB"
    disk: str = "20GiB"
    vm_image: str | None = None

    # Mount settings
    mount_host: str = ""
    mount_guest: str = ""

    # Atomic update tracking (for rollback/crash recovery)
    previous_vm_name: str | None = None

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
    dart: str | None = None
    c: str | None = None
    tools: list[str] = field(default_factory=list)
    databases: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=lambda: ["claude-code"])
    playwright_browsers: list[str] = field(default_factory=list)

    # Framework version pins (None = "latest")
    claude_code_version: str | None = None
    codex_version: str | None = None
    opencode_version: str | None = None

    # Claude Code settings
    claude_dangerously_skip_permissions: bool = True

    # SSH settings
    ssh_host_key_checking: bool = True

    # VM behavior
    keep_vm_running: bool = False

    # claude-code-router proxy feature (vm.claude_code_router in .clauded.yaml).
    # When enabled, the claude-code harness launch is wrapped with a script that
    # ensures CCR is running on 127.0.0.1:3456 and sets ANTHROPIC_BASE_URL.
    ccr_enabled: bool = False
    ccr_providers: list[str] = field(default_factory=list)
    ccr_overrides: dict[str, str] = field(default_factory=dict)
    # CCR's pino LOG_LEVEL (vm.claude_code_router.log_level). Default `warn`
    # keeps production sessions quiet; bump to `debug` or `trace` when
    # investigating routing or upstream-auth issues. CCR's pino transformer log
    # already records outbound URL and headers at level=20 (debug), so a Node
    # http-debug knob is unnecessary (and didn't work anyway — undici/fetch
    # doesn't honor NODE_DEBUG=http,https).
    ccr_log_level: str = "warn"

    # Host environment variables to forward into the VM shell session
    forward_env: list[str] = field(default_factory=list)

    # Active coding harness for this project (claude-code | codex | opencode).
    # Persisted at the top level of .clauded.yaml; always emitted by save().
    harness: str = "claude-code"

    @classmethod
    def from_wizard(cls, answers: dict[str, Any], project_path: Path) -> "Config":
        """Create a Config from wizard answers."""
        project_name = _sanitize_vm_name(project_path.name)
        path_hash = hashlib.sha256(str(project_path).encode()).hexdigest()[:6]
        vm_name = f"clauded-{project_name}-{path_hash}"

        return cls(
            vm_name=vm_name,
            cpus=int(answers.get("cpus", 1)),
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
            dart=answers.get("dart") if answers.get("dart") != "None" else None,
            c=answers.get("c") if answers.get("c") != "None" else None,
            tools=answers.get("tools", []),
            databases=answers.get("databases", []),
            frameworks=answers.get("frameworks") or ["claude-code"],
            playwright_browsers=answers.get("playwright_browsers", []),
            claude_dangerously_skip_permissions=answers.get(
                "claude_dangerously_skip_permissions", True
            ),
            ssh_host_key_checking=answers.get("ssh_host_key_checking", True),
            keep_vm_running=answers.get("keep_vm_running", False),
            ccr_enabled=answers.get("ccr_enabled", False),
            ccr_providers=answers.get("ccr_providers", []),
            ccr_overrides=answers.get("ccr_overrides", {}),
            ccr_log_level=answers.get("ccr_log_level", "warn"),
            forward_env=answers.get("forward_env", []),
            harness=answers.get("harness", "claude-code"),
        )

    @contextmanager
    def atomic_update(
        self, new_vm_name: str, config_path: Path
    ) -> Generator[str | None, None, None]:
        """Context manager for atomic VM name updates with rollback.

        Provides transactional semantics for config updates tied to VM operations.
        Stores the current vm_name as previous_vm_name, updates to new name,
        and handles rollback on failure or cleanup on success.

        CONTRACT:
          Inputs:
            - new_vm_name: string, non-empty VM name for the new/updated VM
            - config_path: Path object, location of .clauded.yaml file to update

          Outputs:
            - yields: previous VM name (string or None if no previous VM existed)

          Invariants:
            - Config file always references a valid VM name after exit
            - previous_vm_name field is cleared after successful completion or rollback
            - All exceptions are propagated after rollback

          Properties:
            - Exception safety: ANY exception triggers rollback to previous state
            - Idempotent cleanup: previous_vm_name always cleared on exit
            - State consistency: config saved after every state transition

          Algorithm:
            1. Capture current state (old_vm_name = self.vm_name)
            2. Update to new state:
               self.vm_name = new_vm_name
               previous_vm_name = old_vm_name
            3. Save config with both names (enables crash recovery)
            4. Yield old_vm_name to caller for VM operations
            5. On normal exit (success):
               - Clear previous_vm_name
               - Save config
            6. On exception (failure):
               - Restore vm_name = previous_vm_name
               - Clear previous_vm_name
               - Save config
               - Re-raise exception

        Usage:
            with config.atomic_update(new_vm_name, config_path) as old_vm:
                # Perform VM operations that might fail
                vm.create()
                # On success: old_vm contains previous name (or None)
                # Caller responsible for prompting user to delete old_vm
        """
        # Validate new VM name for security
        _validate_vm_name(new_vm_name)

        old_vm_name = self.vm_name
        self.previous_vm_name = old_vm_name if old_vm_name else None
        self.vm_name = new_vm_name

        # Save config with both names (crash recovery state)
        self.save(config_path)

        try:
            yield old_vm_name if old_vm_name else None
            # Success path: clear previous_vm_name
            self.previous_vm_name = None
            self.save(config_path)
        except BaseException:
            # Failure path: rollback to previous state
            # Catches Exception, KeyboardInterrupt, SystemExit for cleanup
            self.vm_name = self.previous_vm_name if self.previous_vm_name else ""
            self.previous_vm_name = None
            self.save(config_path)
            raise

    @classmethod
    def load(cls, path: Path, *, allow_alpine_legacy: bool = False) -> "Config":
        """Load config from a .clauded.yaml file.

        Performs validation and migration:
        - Validates schema version compatibility
        - Migrates older config formats
        - Ensures mount_guest matches mount_host (auto-corrects if different)

        When ``allow_alpine_legacy`` is True, configs with ``vm.distro: alpine``
        load without raising. The CLI uses this for ``--destroy``/``--stop`` so
        the FR5 migration message (which directs users to ``clauded --destroy``)
        is actually executable on a legacy Alpine project.

        Raises:
            ConfigVersionError: If config version is incompatible
            ConfigValidationError: If ``vm.distro: alpine`` and
                ``allow_alpine_legacy`` is False (FR5 migration error).
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

        # Handle legacy vm.distro field. The field is no longer part of the
        # schema; only "ubuntu" (silently discarded) and "alpine" (FR5
        # migration error, or legacy bypass for --destroy/--stop) are
        # recognized legacy values. Anything else — typos, deprecated distros,
        # malformed configs — is rejected, matching the pre-epic strictness of
        # the removed _validate_distro() helper.
        _distro = data.get("vm", {}).get("distro")
        if _distro is not None:
            if _distro == "alpine":
                if not allow_alpine_legacy:
                    raise ConfigValidationError(
                        "Alpine Linux is no longer supported. This project's\n"
                        ".clauded.yaml is configured for Alpine, and your"
                        " existing VM is Alpine-based.\n"
                        "\n"
                        "To migrate to Ubuntu (the only supported distro):\n"
                        "\n"
                        "  1. Destroy the existing VM:    clauded --destroy\n"
                        "     (Project files are safe — they live on the"
                        " host filesystem.)\n"
                        "  2. Remove the line `distro: alpine` from"
                        " .clauded.yaml.\n"
                        "  3. Run `clauded` to provision a fresh Ubuntu VM.\n"
                        "\n"
                        "See CHANGELOG.md and docs/migration-from-alpine.md"
                        " for details."
                    )
                # alpine + allow_alpine_legacy: fall through silently for
                # --destroy/--stop on a legacy Alpine project.
            elif _distro == "ubuntu":
                logger.info(
                    "vm.distro is no longer used; you can remove it from .clauded.yaml"
                )
            else:
                raise ConfigValidationError(
                    f"Unknown vm.distro value {_distro!r} in .clauded.yaml. "
                    "The vm.distro field is no longer used and should be "
                    "removed; only the legacy value 'ubuntu' is accepted for "
                    "backward compatibility."
                )

        # Validate runtime versions (strict validation for supported versions)
        env = data.get("environment", {})
        python_ver = _validate_runtime_version("python", env.get("python"))
        node_ver = _validate_runtime_version("node", env.get("node"))
        java_ver = _validate_runtime_version("java", env.get("java"))
        kotlin_ver = _validate_runtime_version("kotlin", env.get("kotlin"))
        rust_ver = _validate_runtime_version("rust", env.get("rust"))
        go_ver = _validate_runtime_version("go", env.get("go"))
        dart_ver = _validate_runtime_version("dart", env.get("dart"))
        c_ver = _validate_runtime_version("c", env.get("c"))

        # Parse and validate version pins
        raw_versions = data.get("versions", {})
        if raw_versions is None:
            raw_versions = {}
        if not isinstance(raw_versions, dict):
            raise ConfigValidationError(
                f"'versions' must be a mapping, got {type(raw_versions).__name__}"
            )
        claude_code_pin = _validate_version_pin(
            "claude-code", raw_versions.get("claude-code")
        )
        codex_pin = _validate_version_pin("codex", raw_versions.get("codex"))
        opencode_pin = _validate_version_pin("opencode", raw_versions.get("opencode"))

        # Validate VM names for security
        vm_name = _validate_vm_name(data["vm"]["name"])
        previous_vm = data.get("vm", {}).get("previous_name")
        if previous_vm:
            previous_vm = _validate_vm_name(previous_vm)

        # Validate harness AFTER frameworks parsing so the harness ⇒ framework
        # invariant can be checked against the resolved frameworks list.
        frameworks_value = env.get("frameworks") or []
        harness_value = _validate_harness(data.get("harness"), frameworks_value)

        # Parse vm.claude_code_router block (optional; missing → defaults).
        ccr_block = data.get("vm", {}).get("claude_code_router") or {}
        ccr_enabled = ccr_block.get("enabled", False)
        if not isinstance(ccr_enabled, bool):
            raise ConfigValidationError(
                f"vm.claude_code_router.enabled must be a boolean, got "
                f"{type(ccr_enabled).__name__!r} ({ccr_enabled!r})"
            )
        ccr_providers_raw = ccr_block.get("providers") or []
        for provider in ccr_providers_raw:
            if provider not in CCR_PROVIDER_WHITELIST:
                raise ConfigValidationError(
                    f"Unknown claude_code_router provider {provider!r}. "
                    f"Allowed values: {', '.join(sorted(CCR_PROVIDER_WHITELIST))}"
                )
        ccr_providers: list[str] = list(ccr_providers_raw)

        ccr_overrides_raw = ccr_block.get("overrides")
        if ccr_overrides_raw is None:
            ccr_overrides_raw = {}
        if not isinstance(ccr_overrides_raw, dict):
            raise ConfigValidationError(
                "vm.claude_code_router.overrides must be a mapping, "
                f"got {type(ccr_overrides_raw).__name__!r}"
            )
        for key, value in ccr_overrides_raw.items():
            if key not in CCR_OVERRIDE_KEYS:
                raise ConfigValidationError(
                    f"Unknown claude_code_router override key {key!r}. "
                    f"Allowed keys: {', '.join(sorted(CCR_OVERRIDE_KEYS))}"
                )
            if not isinstance(value, str) or not value:
                raise ConfigValidationError(
                    f"vm.claude_code_router.overrides[{key!r}] must be a "
                    f"non-empty string, got {value!r}"
                )
            if "/" not in value:
                raise ConfigValidationError(
                    f"vm.claude_code_router.overrides[{key!r}] must use "
                    f"'<provider>/<model>' syntax (e.g. 'ollama/qwen3:latest', "
                    f"'minimax/MiniMax-M2.7'), got {value!r}"
                )
        ccr_overrides: dict[str, str] = dict(ccr_overrides_raw)

        ccr_log_level = ccr_block.get("log_level", "warn")
        if not isinstance(ccr_log_level, str) or ccr_log_level not in CCR_LOG_LEVELS:
            raise ConfigValidationError(
                f"vm.claude_code_router.log_level must be one of "
                f"{sorted(CCR_LOG_LEVELS)}, got {ccr_log_level!r}"
            )

        return cls(
            version=version,
            vm_name=vm_name,
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
            dart=dart_ver,
            c=c_ver,
            tools=env.get("tools") or [],
            databases=env.get("databases") or [],
            frameworks=env.get("frameworks") or [],
            playwright_browsers=env.get("playwright_browsers") or [],
            claude_code_version=claude_code_pin,
            codex_version=codex_pin,
            opencode_version=opencode_pin,
            claude_dangerously_skip_permissions=data.get("claude", {}).get(
                "dangerously_skip_permissions", True
            ),
            ssh_host_key_checking=data.get("ssh", {}).get("host_key_checking", True),
            keep_vm_running=data.get("vm", {}).get("keep_running", False),
            ccr_enabled=ccr_enabled,
            ccr_providers=ccr_providers,
            ccr_overrides=ccr_overrides,
            ccr_log_level=ccr_log_level,
            forward_env=data.get("vm", {}).get("forward_env") or [],
            previous_vm_name=previous_vm,
            harness=harness_value,
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
        if self.previous_vm_name is not None:
            vm_data["previous_name"] = self.previous_vm_name
        if self.keep_vm_running:
            vm_data["keep_running"] = self.keep_vm_running
        if self.ccr_enabled:
            ccr_block: dict[str, Any] = {
                "enabled": True,
                "providers": list(self.ccr_providers),
            }
            if self.ccr_overrides:
                ccr_block["overrides"] = dict(self.ccr_overrides)
            if self.ccr_log_level != "warn":
                ccr_block["log_level"] = self.ccr_log_level
            vm_data["claude_code_router"] = ccr_block
        if self.forward_env:
            vm_data["forward_env"] = self.forward_env

        data: dict[str, Any] = {
            "version": self.version,
            "harness": self.harness,
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
                "dart": self.dart,
                "c": self.c,
                "tools": self.tools,
                "databases": self.databases,
                "frameworks": self.frameworks,
                "playwright_browsers": self.playwright_browsers,
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

        # Only emit versions section when at least one version is pinned
        versions: dict[str, str] = {}
        if self.claude_code_version:
            versions["claude-code"] = self.claude_code_version
        if self.codex_version:
            versions["codex"] = self.codex_version
        if self.opencode_version:
            versions["opencode"] = self.opencode_version
        if versions:
            data["versions"] = versions

        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            f.flush()
            os.fsync(f.fileno())
