"""Runtime version detection from version files and manifests."""

import json
import logging
import re
from pathlib import Path
from typing import Literal

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[import-not-found, no-redef]

from .result import VersionSpec
from .utils import is_safe_path, safe_read_text

logger = logging.getLogger(__name__)

# Version validation patterns (SEC-002: Prevent command injection)
# These patterns ensure version strings contain only safe characters
VERSION_PATTERNS: dict[str, re.Pattern[str]] = {
    # Python: exact versions, constraints (>=, ~=, <, <=), ranges (>=x,<y)
    "python": re.compile(
        r"^(\d+\.\d+(\.\d+)?|"  # Exact: 3.12, 3.12.0
        r"[><=~!]+\d+\.\d+(\.\d+)?(,[><=]+\d+\.\d+(\.\d+)?)?)$"
    ),
    # Node: exact, semver ranges, wildcards
    "node": re.compile(r"^v?\d+(\.\d+)*([.xX*])?$|^\^?\d+(\.\d+)*$|^>=?\d+(\.\d+)*$"),
    "java": re.compile(r"^\d+(\.\d+)*$"),
    "kotlin": re.compile(r"^\d+\.\d+(\.\d+)?$"),
    "rust": re.compile(r"^(stable|nightly|beta)(-\d{4}-\d{2}-\d{2})?$|^\d+\.\d+\.\d+$"),
    "go": re.compile(r"^\d+\.\d+(\.\d+)?$"),
}


def _validate_version(version: str, runtime: str) -> bool:
    """Validate version string against runtime-specific pattern.

    Returns True if version is safe (matches expected pattern), False otherwise.
    This prevents command injection via malicious version strings.
    """
    pattern = VERSION_PATTERNS.get(runtime)
    if not pattern:
        # Unknown runtime - be conservative and reject
        return False
    return bool(pattern.match(version))


def detect_versions(project_path: Path) -> dict[str, VersionSpec]:
    """Detect runtime versions from version specification files.

    CONTRACT:
      Inputs:
        - project_path: directory path, must exist and be readable

      Outputs:
        - dictionary mapping runtime names to VersionSpec objects
          * Keys: "python", "node", "java", "kotlin", "rust", "go"
          * Values: VersionSpec with version string, source file, constraint type
        - empty dictionary if no version files found

      Invariants:
        - All source_file paths are absolute paths within project_path
        - Version strings are normalized (no whitespace, consistent format)
        - Constraint types: "exact" (3.12.0), "minimum" (>=3.10), "range" (^1.20)
        - Never raises exceptions - logs warnings and returns partial results

      Properties:
        - Priority order: explicit version files > .tool-versions > manifest files
        - Multi-source resolution: when multiple sources specify same runtime,
          higher priority source wins
        - Completeness: checks all standard version file locations per runtime

      Algorithm:
        1. Initialize empty version dictionary
        2. For each runtime (python, node, java, kotlin, rust, go):
           a. Check explicit version file (.python-version, .nvmrc, etc.)
           b. If not found, check .tool-versions (asdf format)
           c. If not found, check manifest files (pyproject.toml, package.json, etc.)
           d. If version found, parse and normalize version string
           e. Determine constraint type (exact, minimum, range)
           f. Store VersionSpec in dictionary with runtime key
        3. Return dictionary of detected versions

      Version File Priority (per runtime):
        Python: .python-version > .tool-versions > pyproject.toml [requires-python]
        Node: .nvmrc > .node-version > .tool-versions > package.json [engines.node]
        Java: .java-version > .tool-versions > pom.xml > build.gradle
        Kotlin: build.gradle.kts kotlin plugin version
        Rust: rust-toolchain.toml > rust-toolchain
        Go: go.mod [go directive]
    """
    logger.debug(f"Detecting versions in {project_path}")
    versions: dict[str, VersionSpec] = {}

    for runtime, parser in [
        ("python", parse_python_version),
        ("node", parse_node_version),
        ("java", parse_java_version),
        ("kotlin", parse_kotlin_version),
        ("rust", parse_rust_version),
        ("go", parse_go_version),
    ]:
        spec = parser(project_path)
        if spec:
            versions[runtime] = spec

    return versions


def _normalize_version(version: str) -> str:
    """Normalize version string by stripping whitespace."""
    return version.strip()


def _classify_constraint_type(version: str) -> Literal["exact", "minimum", "range"]:
    """Classify version constraint type from version string.

    Returns "exact", "minimum", or "range".
    """
    version = version.strip()

    if re.match(r"^\d+(\.\d+)*$", version):
        return "exact"

    if re.match(r"^(>=|<=|>|<)", version):
        if "," in version or " " in version.replace(">=", "").replace("<=", ""):
            return "range"
        return "minimum"

    if re.match(r"^(\^|~|=~|!=|~=)", version):
        return "range"

    if "||" in version or "|" in version:
        return "range"

    if "x" in version or "X" in version:
        return "range"

    return "exact"


def parse_python_version(project_path: Path) -> VersionSpec | None:
    """Parse Python version from .python-version or pyproject.toml.

    CONTRACT:
      Inputs:
        - project_path: directory path containing version files

      Outputs:
        - VersionSpec: with version, source file, constraint type
        - None: if no Python version files found or parse errors

      Invariants:
        - Priority: .python-version > .tool-versions > pyproject.toml > setup.py
        - Version normalized (no leading/trailing whitespace)
        - Never raises exceptions

      Algorithm:
        1. Check for .python-version file
           - If exists: read first line, strip whitespace, return as exact version
        2. If not found, check .tool-versions for python entry
        3. If not found, check pyproject.toml
           - Parse TOML, extract project.requires-python field
           - Parse constraint syntax (>=3.10, ~=3.12, etc.)
           - Determine constraint type from syntax
        4. If not found, check setup.py
           - Parse python_requires argument using regex
           - Extract version constraint
        5. Return VersionSpec or None
    """
    python_version_file = project_path / ".python-version"
    if python_version_file.exists() and is_safe_path(python_version_file, project_path):
        content = safe_read_text(python_version_file, project_path)
        if content:
            version = content.strip()
            if version:
                normalized = _normalize_version(version)
                if not _validate_version(normalized, "python"):
                    logger.warning(f"Invalid Python version format: {version}")
                    return None
                return VersionSpec(
                    version=normalized,
                    source_file=str(python_version_file.absolute()),
                    constraint_type="exact",
                )

    tool_versions = parse_tool_versions(project_path)
    if "python" in tool_versions:
        return tool_versions["python"]

    pyproject_file = project_path / "pyproject.toml"
    if pyproject_file.exists() and is_safe_path(pyproject_file, project_path):
        try:
            with open(pyproject_file, "rb") as f:
                data = tomllib.load(f)
            requires_python = data.get("project", {}).get("requires-python")
            if requires_python:
                requires_python = _normalize_version(requires_python)
                if not _validate_version(requires_python, "python"):
                    logger.warning(f"Invalid Python version format: {requires_python}")
                    return None
                return VersionSpec(
                    version=requires_python,
                    source_file=str(pyproject_file.absolute()),
                    constraint_type=_classify_constraint_type(requires_python),
                )
        except Exception as e:
            logger.warning(f"Failed to parse pyproject.toml: {e}")

    # Fallback to setup.py
    setup_py_file = project_path / "setup.py"
    if setup_py_file.exists() and is_safe_path(setup_py_file, project_path):
        content = safe_read_text(setup_py_file, project_path)
        if content:
            try:
                # Match python_requires='>=3.10' or python_requires=">=3.10"
                match = re.search(
                    r"python_requires\s*=\s*['\"]([^'\"]+)['\"]",
                    content,
                )
                if match:
                    python_requires = _normalize_version(match.group(1))
                    if not _validate_version(python_requires, "python"):
                        logger.warning(
                            f"Invalid Python version in setup.py: {python_requires}"
                        )
                    else:
                        return VersionSpec(
                            version=python_requires,
                            source_file=str(setup_py_file.absolute()),
                            constraint_type=_classify_constraint_type(python_requires),
                        )
            except Exception as e:
                logger.warning(f"Failed to parse setup.py: {e}")

    return None


def parse_node_version(project_path: Path) -> VersionSpec | None:
    """Parse Node.js version from .nvmrc, .node-version, or package.json.

    CONTRACT:
      Inputs:
        - project_path: directory path containing version files

      Outputs:
        - VersionSpec: with version, source file, constraint type
        - None: if no Node version files found or parse errors

      Invariants:
        - Priority: .nvmrc > .node-version > .tool-versions > package.json [engines]
        - Version normalized (remove 'v' prefix if present)
        - Never raises exceptions

      Algorithm:
        1. Check .nvmrc file - read first line, strip whitespace
        2. If not found, check .node-version file - read first line
        3. If not found, check .tool-versions for nodejs/node entry
        4. If not found, parse package.json engines.node field
        5. Parse semver constraint syntax (16.x, >=18.0.0, ^20.0.0)
        6. Return VersionSpec or None
    """
    nvmrc_file = project_path / ".nvmrc"
    if nvmrc_file.exists() and is_safe_path(nvmrc_file, project_path):
        content = safe_read_text(nvmrc_file, project_path)
        if content:
            version = content.strip()
            if version:
                normalized = _normalize_version(version.lstrip("v"))
                if not _validate_version(normalized, "node"):
                    logger.warning(f"Invalid Node version format: {version}")
                    return None
                return VersionSpec(
                    version=normalized,
                    source_file=str(nvmrc_file.absolute()),
                    constraint_type="exact",
                )

    node_version_file = project_path / ".node-version"
    if node_version_file.exists() and is_safe_path(node_version_file, project_path):
        content = safe_read_text(node_version_file, project_path)
        if content:
            version = content.strip()
            if version:
                normalized = _normalize_version(version.lstrip("v"))
                if not _validate_version(normalized, "node"):
                    logger.warning(f"Invalid Node version format: {version}")
                    return None
                return VersionSpec(
                    version=normalized,
                    source_file=str(node_version_file.absolute()),
                    constraint_type="exact",
                )

    tool_versions = parse_tool_versions(project_path)
    if "node" in tool_versions:
        return tool_versions["node"]

    package_json_file = project_path / "package.json"
    if package_json_file.exists() and is_safe_path(package_json_file, project_path):
        content = safe_read_text(package_json_file, project_path)
        if content:
            try:
                data = json.loads(content)
                engines_node = data.get("engines", {}).get("node")
                if engines_node:
                    engines_node = _normalize_version(engines_node)
                    if not _validate_version(engines_node, "node"):
                        logger.warning(f"Invalid Node version format: {engines_node}")
                        return None
                    return VersionSpec(
                        version=engines_node,
                        source_file=str(package_json_file.absolute()),
                        constraint_type=_classify_constraint_type(engines_node),
                    )
            except Exception as e:
                logger.warning(f"Failed to parse package.json: {e}")

    return None


def parse_java_version(project_path: Path) -> VersionSpec | None:
    """Parse Java version from version files and build configurations.

    CONTRACT:
      Inputs:
        - project_path: directory path containing version files

      Outputs:
        - VersionSpec: with version, source file, constraint type
        - None: if no Java version files found or parse errors

      Invariants:
        - Priority: .java-version > .tool-versions > pom.xml > build.gradle
          > build.gradle.kts
        - Version is major version only (11, 17, 21)
        - Never raises exceptions

      Algorithm:
        1. Check .java-version file - read first line, extract major version
        2. If not found, check .tool-versions for java entry
        3. If not found, parse pom.xml for maven.compiler.source
        4. If not found, parse build.gradle for sourceCompatibility
        5. If not found, parse build.gradle.kts for sourceCompatibility or jvmToolchain
        6. Return VersionSpec or None
    """
    java_version_file = project_path / ".java-version"
    if java_version_file.exists() and is_safe_path(java_version_file, project_path):
        content = safe_read_text(java_version_file, project_path)
        if content:
            version = content.strip()
            if version:
                normalized = _normalize_version(version)
                if not _validate_version(normalized, "java"):
                    logger.warning(f"Invalid Java version format: {version}")
                    return None
                return VersionSpec(
                    version=normalized,
                    source_file=str(java_version_file.absolute()),
                    constraint_type="exact",
                )

    tool_versions = parse_tool_versions(project_path)
    if "java" in tool_versions:
        return tool_versions["java"]

    pom_file = project_path / "pom.xml"
    if pom_file.exists() and is_safe_path(pom_file, project_path):
        content = safe_read_text(pom_file, project_path)
        if content:
            try:
                match = re.search(
                    r"<maven\.compiler\.source>(\d+(?:\.\d+)*)</maven\.compiler\.source>",
                    content,
                )
                if match:
                    version = match.group(1)
                    if not _validate_version(version, "java"):
                        logger.warning(f"Invalid Java version format: {version}")
                    else:
                        return VersionSpec(
                            version=version,
                            source_file=str(pom_file.absolute()),
                            constraint_type="exact",
                        )
            except Exception as e:
                logger.warning(f"Failed to parse pom.xml: {e}")

    build_gradle = project_path / "build.gradle"
    if build_gradle.exists() and is_safe_path(build_gradle, project_path):
        content = safe_read_text(build_gradle, project_path)
        if content:
            try:
                pattern = r"sourceCompatibility\s*=\s*['\"]?(\d+(?:\.\d+)*)['\"]?"
                match = re.search(pattern, content)
                if match:
                    version = match.group(1)
                    if not _validate_version(version, "java"):
                        logger.warning(f"Invalid Java version format: {version}")
                    else:
                        return VersionSpec(
                            version=version,
                            source_file=str(build_gradle.absolute()),
                            constraint_type="exact",
                        )
            except Exception as e:
                logger.warning(f"Failed to parse build.gradle: {e}")

    # Check build.gradle.kts for Java version
    build_gradle_kts = project_path / "build.gradle.kts"
    if build_gradle_kts.exists() and is_safe_path(build_gradle_kts, project_path):
        content = safe_read_text(build_gradle_kts, project_path)
        if content:
            try:
                # Check for sourceCompatibility
                pattern = r"sourceCompatibility\s*=\s*JavaVersion\.VERSION_(\d+)"
                match = re.search(pattern, content)
                if not match:
                    # Also check for jvmToolchain
                    pattern = r"jvmToolchain\s*\(\s*(\d+)\s*\)"
                    match = re.search(pattern, content)
                if not match:
                    # Check for JavaLanguageVersion.of(X) in toolchain config
                    pattern = r"JavaLanguageVersion\.of\s*\(\s*(\d+)\s*\)"
                    match = re.search(pattern, content)

                if match:
                    version = match.group(1)
                    if not _validate_version(version, "java"):
                        logger.warning(f"Invalid Java version format: {version}")
                    else:
                        return VersionSpec(
                            version=version,
                            source_file=str(build_gradle_kts.absolute()),
                            constraint_type="exact",
                        )
            except Exception as e:
                logger.warning(f"Failed to parse build.gradle.kts: {e}")

    return None


def parse_kotlin_version(project_path: Path) -> VersionSpec | None:
    """Parse Kotlin version from build.gradle.kts kotlin plugin version.

    CONTRACT:
      Inputs:
        - project_path: directory path containing build files

      Outputs:
        - VersionSpec: with version, source file, constraint type
        - None: if no Kotlin version found or parse errors

      Invariants:
        - Extracts from kotlin("jvm") version or kotlin plugin declaration
        - Version is semver format (1.9.0, 2.0.0)
        - Never raises exceptions

      Algorithm:
        1. Check for build.gradle.kts file
        2. Parse for kotlin plugin version declaration
        3. Extract version string from plugin syntax
        4. Return VersionSpec or None
    """
    build_gradle_kts = project_path / "build.gradle.kts"
    if build_gradle_kts.exists() and is_safe_path(build_gradle_kts, project_path):
        content = safe_read_text(build_gradle_kts, project_path)
        if content:
            try:
                p1 = r'kotlin\s*\(\s*["\']jvm["\']\s*\)\s+version\s+["\']([^"\']+)["\']'
                match = re.search(p1, content)
                if not match:
                    p2 = (
                        r'id\s*\(\s*["\']org\.jetbrains\.kotlin\.jvm["\']\s*\)\s+'
                        r'version\s+["\']([^"\']+)["\']'
                    )
                    match = re.search(p2, content)
                if not match:
                    p3 = r'kotlin\s*\(["\']jvm["\']\)\s+version\s+["\']([^"\']+)["\']'
                    match = re.search(p3, content)

                if match:
                    version = _normalize_version(match.group(1))
                    if not _validate_version(version, "kotlin"):
                        logger.warning(f"Invalid Kotlin version format: {version}")
                        return None
                    return VersionSpec(
                        version=version,
                        source_file=str(build_gradle_kts.absolute()),
                        constraint_type="exact",
                    )
            except Exception as e:
                logger.warning(f"Failed to parse build.gradle.kts: {e}")

    return None


def parse_rust_version(project_path: Path) -> VersionSpec | None:
    """Parse Rust version from rust-toolchain.toml or rust-toolchain file.

    CONTRACT:
      Inputs:
        - project_path: directory path containing toolchain files

      Outputs:
        - VersionSpec: with version/channel, source file, constraint type
        - None: if no Rust version files found or parse errors

      Invariants:
        - Priority: rust-toolchain.toml > rust-toolchain
        - Version can be channel (stable, nightly, beta) or specific version
        - Never raises exceptions

      Algorithm:
        1. Check rust-toolchain.toml - parse TOML, extract toolchain.channel
        2. If not found, check rust-toolchain file - read first line
        3. Normalize channel names (stable, nightly-YYYY-MM-DD, 1.70.0)
        4. Return VersionSpec or None
    """
    rust_toolchain_toml = project_path / "rust-toolchain.toml"
    if rust_toolchain_toml.exists() and is_safe_path(rust_toolchain_toml, project_path):
        try:
            with open(rust_toolchain_toml, "rb") as f:
                data = tomllib.load(f)
            channel = data.get("toolchain", {}).get("channel")
            if channel:
                normalized = _normalize_version(channel)
                if not _validate_version(normalized, "rust"):
                    logger.warning(f"Invalid Rust version format: {channel}")
                    return None
                return VersionSpec(
                    version=normalized,
                    source_file=str(rust_toolchain_toml.absolute()),
                    constraint_type="exact",
                )
        except Exception as e:
            logger.warning(f"Failed to parse rust-toolchain.toml: {e}")

    rust_toolchain = project_path / "rust-toolchain"
    if rust_toolchain.exists() and is_safe_path(rust_toolchain, project_path):
        content = safe_read_text(rust_toolchain, project_path)
        if content:
            normalized = _normalize_version(content.strip())
            if normalized:
                if not _validate_version(normalized, "rust"):
                    logger.warning(f"Invalid Rust version format: {normalized}")
                    return None
                return VersionSpec(
                    version=normalized,
                    source_file=str(rust_toolchain.absolute()),
                    constraint_type="exact",
                )

    return None


def parse_go_version(project_path: Path) -> VersionSpec | None:
    """Parse Go version from go.mod go directive.

    CONTRACT:
      Inputs:
        - project_path: directory path containing go.mod

      Outputs:
        - VersionSpec: with version, source file, constraint type
        - None: if no go.mod found or parse errors

      Invariants:
        - Extracts from "go 1.21" directive line in go.mod
        - Version is semver format (1.20, 1.21, 1.22)
        - Never raises exceptions

      Algorithm:
        1. Check for go.mod file
        2. Read line by line looking for "go X.Y" directive
        3. Extract version from directive
        4. Return VersionSpec with "minimum" constraint type
    """
    go_mod_file = project_path / "go.mod"
    if go_mod_file.exists() and is_safe_path(go_mod_file, project_path):
        content = safe_read_text(go_mod_file, project_path)
        if content:
            try:
                for line in content.splitlines():
                    line = line.strip()
                    if line.startswith("go "):
                        version = _normalize_version(line[3:].strip())
                        if version:
                            if not _validate_version(version, "go"):
                                logger.warning(f"Invalid Go version format: {version}")
                                return None
                            return VersionSpec(
                                version=version,
                                source_file=str(go_mod_file.absolute()),
                                constraint_type="minimum",
                            )
            except Exception as e:
                logger.warning(f"Failed to parse go.mod: {e}")

    return None


def parse_tool_versions(project_path: Path) -> dict[str, VersionSpec]:
    """Parse .tool-versions file (asdf format) for all runtimes.

    CONTRACT:
      Inputs:
        - project_path: directory path containing .tool-versions

      Outputs:
        - dictionary mapping runtime names to VersionSpec objects
        - empty dictionary if .tool-versions not found or parse errors

      Invariants:
        - File format: "runtime_name version" per line
        - Supports: python, nodejs, java, rust, golang with name mapping
        - Never raises exceptions

      Algorithm:
        1. Check for .tool-versions file
        2. Read line by line
        3. For each line:
           a. Split by whitespace into runtime and version
           b. Map runtime names (nodejs→node, golang→go)
           c. Create VersionSpec with exact constraint type
        4. Return dictionary of detected versions
    """
    tool_versions_file = project_path / ".tool-versions"
    if not tool_versions_file.exists():
        return {}
    if not is_safe_path(tool_versions_file, project_path):
        return {}

    versions: dict[str, VersionSpec] = {}
    runtime_mapping = {"nodejs": "node", "golang": "go"}

    content = safe_read_text(tool_versions_file, project_path)
    if not content:
        return {}

    try:
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            if len(parts) < 2:
                continue

            runtime_name, version = parts[0], parts[1]
            runtime_name = runtime_mapping.get(runtime_name, runtime_name)

            if runtime_name in {"python", "node", "java", "kotlin", "rust", "go"}:
                normalized = _normalize_version(version)
                if not _validate_version(normalized, runtime_name):
                    logger.warning(
                        f"Invalid {runtime_name} version format in .tool-versions: "
                        f"{version}"
                    )
                    continue
                versions[runtime_name] = VersionSpec(
                    version=normalized,
                    source_file=str(tool_versions_file.absolute()),
                    constraint_type="exact",
                )
    except Exception as e:
        logger.warning(f"Failed to parse .tool-versions: {e}")

    return versions
