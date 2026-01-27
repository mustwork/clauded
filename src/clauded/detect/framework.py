"""Framework and tool detection from manifest file dependencies."""

import json
import logging
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Literal

from .result import DetectedItem
from .utils import extract_package_name, is_safe_path, safe_read_text

logger = logging.getLogger(__name__)

# Framework and tool mappings
# Frameworks are detected for informational display
PYTHON_FRAMEWORKS = {"django", "flask", "fastapi"}
NODE_FRAMEWORKS = {"react", "vue", "angular", "express", "next", "nest"}
JAVA_FRAMEWORKS = {"spring-boot", "quarkus"}
KOTLIN_FRAMEWORKS = {"spring-boot", "ktor"}
RUST_FRAMEWORKS = {"actix", "rocket", "tokio"}
GO_FRAMEWORKS = {"gin", "echo", "fiber"}
# NOTE: Build tools (gradle, maven, uv, poetry) are NOT detected here
# because they are auto-installed by provisioner.py based on language selection.
# Only optional tools that require explicit user selection are detected.
OPTIONAL_TOOLS = {"playwright", "docker"}

# Package name to framework name mappings (frameworks only, not build tools)
PYTHON_PACKAGE_MAPPING = {
    "django": "django",
    "flask": "flask",
    "fastapi": "fastapi",
}

NODE_PACKAGE_MAPPING = {
    "react": "react",
    "vue": "vue",
    "angular": "angular",
    "express": "express",
    "next": "next",
    "nest": "nest",
    "@nestjs/core": "nest",
    "playwright": "playwright",  # Optional tool, detected for wizard pre-selection
}

JAVA_ARTIFACT_MAPPING = {
    "spring-boot-starter": "spring-boot",
    "spring-boot-starter-web": "spring-boot",
    "spring-boot-starter-data": "spring-boot",
    "quarkus-core": "quarkus",
    "quarkus-rest": "quarkus",
}

KOTLIN_ARTIFACT_MAPPING = {
    "spring-boot-starter": "spring-boot",
    "spring-boot-starter-web": "spring-boot",
    "ktor-server": "ktor",
}

RUST_CRATE_MAPPING = {
    "actix-web": "actix",
    "rocket": "rocket",
    "tokio": "tokio",
}

GO_MODULE_MAPPING = {
    "github.com/gin-gonic/gin": "gin",
    "github.com/labstack/echo": "echo",
    "github.com/gofiber/fiber": "fiber",
}


def detect_frameworks_and_tools(
    project_path: Path,
) -> tuple[list[DetectedItem], list[DetectedItem]]:
    """Detect frameworks and tools from manifest file dependencies.

    CONTRACT:
      Inputs:
        - project_path: directory path, must exist and be readable

      Outputs:
        - tuple of two collections:
          1. frameworks: DetectedItem objects for frameworks
             (django, react, spring-boot, etc.)
          2. tools: DetectedItem objects for tools
             (playwright, docker, gradle, etc.)
        - empty collections if no manifest files found

      Invariants:
        - All source_file paths are absolute paths within project_path
        - Confidence levels: high (production), medium (dev), low (hint)
        - Never raises exceptions - logs warnings and returns partial results
        - Frameworks and tools are mutually exclusive (no item in both lists)

      Properties:
        - Completeness: checks all standard manifest files per ecosystem
        - Accuracy: matches known package names to clauded-supported frameworks/tools

      Algorithm:
        1. Initialize empty framework and tool lists
        2. Scan for manifest files in project_path:
           - Python: pyproject.toml, requirements.txt
           - Node: package.json
           - Java: pom.xml
           - Kotlin: build.gradle.kts
           - Rust: Cargo.toml
           - Go: go.mod
        3. For each manifest file found:
           a. Parse dependencies (production and dev)
           b. Match dependency names against known framework/tool mappings
           c. Create DetectedItem with appropriate confidence
           d. Add to frameworks or tools list
        4. Check for Docker (Dockerfile or compose files)
        5. Check for build tools (gradle wrapper, maven wrapper)
        6. Return tuple of (frameworks, tools)

      Framework/Tool Mappings:
        Python frameworks: django, flask, fastapi
        Python tools: pytest, poetry, uv
        Node frameworks: react, vue, angular, express, next, nest
        Node tools: playwright, jest, webpack
        Java frameworks: spring-boot, quarkus
        Kotlin frameworks: ktor
        Rust frameworks: actix, rocket, tokio
        Go frameworks: gin, echo, fiber
        Tools: docker, gradle, maven, playwright
    """
    logger.debug(f"Detecting frameworks and tools in {project_path}")

    frameworks: list[DetectedItem] = []
    tools: list[DetectedItem] = []

    # Collect all items from each ecosystem
    all_items: list[DetectedItem] = []

    logger.debug("Parsing Python dependencies...")
    python_items = parse_python_dependencies(project_path)
    logger.debug(f"  Found {len(python_items)} Python items")
    all_items.extend(python_items)

    logger.debug("Parsing Node dependencies...")
    node_items = parse_node_dependencies(project_path)
    logger.debug(f"  Found {len(node_items)} Node items")
    all_items.extend(node_items)

    logger.debug("Parsing Java dependencies...")
    java_items = parse_java_dependencies(project_path)
    logger.debug(f"  Found {len(java_items)} Java items")
    all_items.extend(java_items)

    logger.debug("Parsing Kotlin dependencies...")
    kotlin_items = parse_kotlin_dependencies(project_path)
    logger.debug(f"  Found {len(kotlin_items)} Kotlin items")
    all_items.extend(kotlin_items)

    logger.debug("Parsing Rust dependencies...")
    rust_items = parse_rust_dependencies(project_path)
    logger.debug(f"  Found {len(rust_items)} Rust items")
    all_items.extend(rust_items)

    logger.debug("Parsing Go dependencies...")
    go_items = parse_go_dependencies(project_path)
    logger.debug(f"  Found {len(go_items)} Go items")
    all_items.extend(go_items)

    # Detect optional tools (docker, playwright)
    docker_item = detect_docker(project_path)
    if docker_item:
        all_items.append(docker_item)

    # Separate frameworks and optional tools
    # NOTE: Build tools (gradle, maven, uv, poetry) are NOT detected here
    # because they are auto-installed by provisioner based on language selection
    all_frameworks = (
        PYTHON_FRAMEWORKS
        | NODE_FRAMEWORKS
        | JAVA_FRAMEWORKS
        | KOTLIN_FRAMEWORKS
        | RUST_FRAMEWORKS
        | GO_FRAMEWORKS
    )

    for item in all_items:
        if item.name in all_frameworks:
            frameworks.append(item)
        elif item.name in OPTIONAL_TOOLS:
            tools.append(item)

    return frameworks, tools


def parse_python_dependencies(project_path: Path) -> list[DetectedItem]:
    """Parse Python dependencies from pyproject.toml or requirements.txt.

    CONTRACT:
      Inputs:
        - project_path: directory path containing Python manifest files

      Outputs:
        - collection of DetectedItem objects for detected frameworks/tools
        - empty collection if no Python manifests found

      Invariants:
        - Priority: pyproject.toml > requirements.txt
        - Extracts from [project.dependencies] and [project.optional-dependencies]
        - Production deps = high confidence, optional deps = medium confidence
        - Never raises exceptions

      Algorithm:
        1. Check pyproject.toml:
           a. Parse TOML
           b. Extract project.dependencies list
           c. Extract project.optional-dependencies dict values
           d. Match package names against known Python frameworks/tools
        2. If pyproject.toml not found, check requirements.txt:
           a. Read line by line
           b. Parse package names (ignore version specifiers)
           c. Match against known frameworks/tools
        3. Return collection of DetectedItem objects
    """
    items: list[DetectedItem] = []

    pyproject_path = project_path / "pyproject.toml"
    if pyproject_path.exists() and is_safe_path(pyproject_path, project_path):
        try:
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)

            project = data.get("project", {})

            # Parse main dependencies
            dependencies = project.get("dependencies", [])
            for dep in dependencies:
                package_name = extract_package_name(dep)
                if package_name in PYTHON_PACKAGE_MAPPING:
                    framework_name = PYTHON_PACKAGE_MAPPING[package_name]
                    items.append(
                        DetectedItem(
                            name=framework_name,
                            confidence="high",
                            source_file=str(pyproject_path),
                            source_evidence=package_name,
                        )
                    )

            # Parse optional dependencies
            optional_deps = project.get("optional-dependencies", {})
            for deps_list in optional_deps.values():
                for dep in deps_list:
                    package_name = extract_package_name(dep)
                    if package_name in PYTHON_PACKAGE_MAPPING:
                        framework_name = PYTHON_PACKAGE_MAPPING[package_name]
                        items.append(
                            DetectedItem(
                                name=framework_name,
                                confidence="medium",
                                source_file=str(pyproject_path),
                                source_evidence=package_name,
                            )
                        )
        except Exception as e:
            logger.warning(f"Failed to parse pyproject.toml: {e}")

        return items

    # Fallback to requirements.txt
    requirements_path = project_path / "requirements.txt"
    if requirements_path.exists() and is_safe_path(requirements_path, project_path):
        content = safe_read_text(requirements_path, project_path)
        if content:
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                package_name = extract_package_name(line)
                if package_name in PYTHON_PACKAGE_MAPPING:
                    framework_name = PYTHON_PACKAGE_MAPPING[package_name]
                    items.append(
                        DetectedItem(
                            name=framework_name,
                            confidence="high",
                            source_file=str(requirements_path),
                            source_evidence=package_name,
                        )
                    )

    return items


def parse_node_dependencies(project_path: Path) -> list[DetectedItem]:
    """Parse Node.js dependencies from package.json.

    CONTRACT:
      Inputs:
        - project_path: directory path containing package.json

      Outputs:
        - collection of DetectedItem objects for detected frameworks/tools
        - empty collection if package.json not found

      Invariants:
        - Extracts from dependencies and devDependencies
        - Production deps = high confidence, dev deps = medium confidence
        - Never raises exceptions

      Algorithm:
        1. Check for package.json file
        2. Parse JSON
        3. Extract dependencies and devDependencies objects
        4. Match package names against known Node frameworks/tools
        5. Return collection of DetectedItem objects
    """
    items: list[DetectedItem] = []

    package_json_path = project_path / "package.json"
    if not package_json_path.exists():
        return items
    if not is_safe_path(package_json_path, project_path):
        return items

    content = safe_read_text(package_json_path, project_path)
    if not content:
        return items

    try:
        data = json.loads(content)

        # Parse dependencies (high confidence)
        dependencies = data.get("dependencies", {})
        for package_name in dependencies.keys():
            if package_name in NODE_PACKAGE_MAPPING:
                framework_name = NODE_PACKAGE_MAPPING[package_name]
                items.append(
                    DetectedItem(
                        name=framework_name,
                        confidence="high",
                        source_file=str(package_json_path),
                        source_evidence=package_name,
                    )
                )

        # Parse devDependencies (medium confidence)
        dev_dependencies = data.get("devDependencies", {})
        for package_name in dev_dependencies.keys():
            if package_name in NODE_PACKAGE_MAPPING:
                framework_name = NODE_PACKAGE_MAPPING[package_name]
                items.append(
                    DetectedItem(
                        name=framework_name,
                        confidence="medium",
                        source_file=str(package_json_path),
                        source_evidence=package_name,
                    )
                )
    except Exception as e:
        logger.warning(f"Failed to parse package.json: {e}")

    return items


def parse_java_dependencies(project_path: Path) -> list[DetectedItem]:
    """Parse Java dependencies from pom.xml or build.gradle.

    CONTRACT:
      Inputs:
        - project_path: directory path containing Java build files

      Outputs:
        - collection of DetectedItem objects for detected frameworks/tools
        - empty collection if no Java build files found

      Invariants:
        - Checks both pom.xml and build.gradle (not mutually exclusive)
        - Extracts artifactId from Maven, implementation() from Gradle
        - Never raises exceptions

      Algorithm:
        1. Check pom.xml:
           a. Parse XML
           b. Extract dependencies/dependency/artifactId elements
           c. Match against known Java frameworks
        2. Check build.gradle:
           a. Parse Groovy/text for implementation() declarations
           b. Extract artifact names
           c. Match against known Java frameworks
        3. Return combined collection of DetectedItem objects
    """
    items: list[DetectedItem] = []

    # Parse pom.xml
    pom_path = project_path / "pom.xml"
    if pom_path.exists() and is_safe_path(pom_path, project_path):
        content = safe_read_text(pom_path, project_path)
        if content:
            try:
                root = ET.fromstring(content)
                # Search for dependencies without strict namespace handling
                for dep in root.findall(".//dependency"):
                    artifact_id_elem = dep.find("artifactId")
                    if artifact_id_elem is not None and artifact_id_elem.text:
                        artifact_id = artifact_id_elem.text
                        for pattern, framework_name in JAVA_ARTIFACT_MAPPING.items():
                            if pattern in artifact_id:
                                items.append(
                                    DetectedItem(
                                        name=framework_name,
                                        confidence="high",
                                        source_file=str(pom_path),
                                        source_evidence=artifact_id,
                                    )
                                )
                                break
            except Exception as e:
                logger.warning(f"Failed to parse pom.xml: {e}")

    # Parse build.gradle (Groovy DSL)
    build_gradle_path = project_path / "build.gradle"
    if build_gradle_path.exists() and is_safe_path(build_gradle_path, project_path):
        content = safe_read_text(build_gradle_path, project_path)
        if content:
            try:
                for line in content.splitlines():
                    line = line.strip()
                    # Look for implementation(), testImplementation(), api()
                    for prefix in (
                        "implementation",
                        "testImplementation",
                        "api",
                        "runtimeOnly",
                    ):
                        if prefix in line:
                            # Extract artifact from Groovy DSL
                            artifact = _extract_gradle_dependency(line)
                            if artifact:
                                for pattern, fw_name in JAVA_ARTIFACT_MAPPING.items():
                                    if pattern in artifact:
                                        is_test = "test" in prefix.lower()
                                        conf: Literal["high", "medium"] = (
                                            "medium" if is_test else "high"
                                        )
                                        items.append(
                                            DetectedItem(
                                                name=fw_name,
                                                confidence=conf,
                                                source_file=str(build_gradle_path),
                                                source_evidence=artifact,
                                            )
                                        )
                                        break
            except Exception as e:
                logger.warning(f"Failed to parse build.gradle: {e}")

    return items


def parse_kotlin_dependencies(project_path: Path) -> list[DetectedItem]:
    """Parse Kotlin dependencies from build.gradle.kts.

    CONTRACT:
      Inputs:
        - project_path: directory path containing build.gradle.kts

      Outputs:
        - collection of DetectedItem objects for detected frameworks/tools
        - empty collection if build.gradle.kts not found

      Invariants:
        - Extracts from implementation() and testImplementation() declarations
        - Never raises exceptions

      Algorithm:
        1. Check for build.gradle.kts file
        2. Parse Kotlin DSL for dependency declarations
        3. Extract artifact names from dependency strings
        4. Match against known Kotlin frameworks
        5. Return collection of DetectedItem objects
    """
    items: list[DetectedItem] = []

    gradle_kts_path = project_path / "build.gradle.kts"
    if not gradle_kts_path.exists():
        return items
    if not is_safe_path(gradle_kts_path, project_path):
        return items

    content = safe_read_text(gradle_kts_path, project_path)
    if not content:
        return items

    try:
        for line in content.splitlines():
            line = line.strip()
            # Look for implementation() and testImplementation() declarations
            for prefix in (
                "implementation(",
                "testImplementation(",
                "api(",
                "runtimeOnly(",
            ):
                if prefix in line:
                    # Extract artifact name from dependency string
                    # e.g., implementation("org.springframework.boot:
                    # spring-boot-starter-web:2.7.0")
                    artifact = _extract_gradle_dependency(line)
                    if artifact:
                        for pattern, framework_name in KOTLIN_ARTIFACT_MAPPING.items():
                            if pattern in artifact:
                                confidence_level: Literal["high", "medium"] = (
                                    "medium" if "test" in prefix else "high"
                                )
                                items.append(
                                    DetectedItem(
                                        name=framework_name,
                                        confidence=confidence_level,
                                        source_file=str(gradle_kts_path),
                                        source_evidence=artifact,
                                    )
                                )
                                break
    except Exception as e:
        logger.warning(f"Failed to parse build.gradle.kts: {e}")

    return items


def parse_rust_dependencies(project_path: Path) -> list[DetectedItem]:
    """Parse Rust dependencies from Cargo.toml.

    CONTRACT:
      Inputs:
        - project_path: directory path containing Cargo.toml

      Outputs:
        - collection of DetectedItem objects for detected frameworks/tools
        - empty collection if Cargo.toml not found

      Invariants:
        - Extracts from [dependencies] and [dev-dependencies] sections
        - Never raises exceptions

      Algorithm:
        1. Check for Cargo.toml file
        2. Parse TOML
        3. Extract dependencies and dev-dependencies tables
        4. Match crate names against known Rust frameworks
        5. Return collection of DetectedItem objects
    """
    items: list[DetectedItem] = []

    cargo_path = project_path / "Cargo.toml"
    if not cargo_path.exists():
        return items
    if not is_safe_path(cargo_path, project_path):
        return items

    try:
        with open(cargo_path, "rb") as f:
            data = tomllib.load(f)

        # Parse dependencies
        dependencies = data.get("dependencies", {})
        for crate_name in dependencies.keys():
            if crate_name in RUST_CRATE_MAPPING:
                framework_name = RUST_CRATE_MAPPING[crate_name]
                items.append(
                    DetectedItem(
                        name=framework_name,
                        confidence="high",
                        source_file=str(cargo_path),
                        source_evidence=crate_name,
                    )
                )

        # Parse dev-dependencies
        dev_dependencies = data.get("dev-dependencies", {})
        for crate_name in dev_dependencies.keys():
            if crate_name in RUST_CRATE_MAPPING:
                framework_name = RUST_CRATE_MAPPING[crate_name]
                items.append(
                    DetectedItem(
                        name=framework_name,
                        confidence="medium",
                        source_file=str(cargo_path),
                        source_evidence=crate_name,
                    )
                )
    except Exception as e:
        logger.warning(f"Failed to parse Cargo.toml: {e}")

    return items


def parse_go_dependencies(project_path: Path) -> list[DetectedItem]:
    """Parse Go dependencies from go.mod.

    CONTRACT:
      Inputs:
        - project_path: directory path containing go.mod

      Outputs:
        - collection of DetectedItem objects for detected frameworks/tools
        - empty collection if go.mod not found

      Invariants:
        - Extracts from require directives
        - Matches module paths (e.g., github.com/gin-gonic/gin)
        - Never raises exceptions

      Algorithm:
        1. Check for go.mod file
        2. Parse module directives line by line
        3. Extract require statements
        4. Match module paths against known Go frameworks
        5. Return collection of DetectedItem objects
    """
    items: list[DetectedItem] = []

    go_mod_path = project_path / "go.mod"
    if not go_mod_path.exists():
        return items
    if not is_safe_path(go_mod_path, project_path):
        return items

    content = safe_read_text(go_mod_path, project_path)
    if not content:
        return items

    try:
        in_require_block = False

        for line in content.splitlines():
            line = line.strip()

            if line.startswith("require"):
                if "(" in line:
                    in_require_block = True
                else:
                    # Single line require
                    module_path = line[7:].strip()
                    _check_go_module(module_path, go_mod_path, items)
            elif in_require_block:
                if line.endswith(")"):
                    in_require_block = False
                elif line and not line.startswith("#"):
                    _check_go_module(line, go_mod_path, items)
    except Exception as e:
        logger.warning(f"Failed to parse go.mod: {e}")

    return items


def _extract_gradle_dependency(line: str) -> str:
    """Extract artifact name from Gradle dependency declaration.

    Examples:
      - implementation("org.springframework.boot:spring-boot-starter-web:2.7.0")
        -> "spring-boot-starter-web"
      - implementation("io.ktor:ktor-server-core:2.0.0")
        -> "ktor-server-core"
    """
    # Find content between quotes
    if '"' in line:
        start = line.find('"') + 1
        end = line.find('"', start)
        if end > start:
            dep_string = line[start:end]
            # Format: groupId:artifactId:version
            parts = dep_string.split(":")
            if len(parts) >= 2:
                return parts[1]

    return ""


def _check_go_module(
    module_path: str, go_mod_path: Path, items: list[DetectedItem]
) -> None:
    """Check if a Go module path matches known Go frameworks.

    Extracts the base module name and matches it against GO_MODULE_MAPPING.
    """
    # Extract version specifier if present
    # (e.g., "github.com/gin-gonic/gin v1.9.0" -> "github.com/gin-gonic/gin")
    module_path = module_path.split()[0] if " " in module_path else module_path

    for module_pattern, framework_name in GO_MODULE_MAPPING.items():
        if module_pattern in module_path:
            items.append(
                DetectedItem(
                    name=framework_name,
                    confidence="high",
                    source_file=str(go_mod_path),
                    source_evidence=module_path,
                )
            )
            break


def detect_docker(project_path: Path) -> DetectedItem | None:
    """Detect Docker requirement from Dockerfile or compose files.

    CONTRACT:
      Inputs:
        - project_path: directory path

      Outputs:
        - DetectedItem: if Dockerfile or docker-compose.yml found
        - None: if no Docker files found

      Invariants:
        - High confidence if files exist
        - source_file is the detected file path

      Algorithm:
        1. Check for Dockerfile
        2. Check for docker-compose.yml or compose.yml
        3. If either exists, return DetectedItem for docker tool
    """
    dockerfile = project_path / "Dockerfile"
    if dockerfile.exists() and is_safe_path(dockerfile, project_path):
        return DetectedItem(
            name="docker",
            confidence="high",
            source_file=str(dockerfile),
            source_evidence="Dockerfile",
        )

    docker_compose = project_path / "docker-compose.yml"
    if docker_compose.exists() and is_safe_path(docker_compose, project_path):
        return DetectedItem(
            name="docker",
            confidence="high",
            source_file=str(docker_compose),
            source_evidence="docker-compose.yml",
        )

    compose = project_path / "compose.yml"
    if compose.exists() and is_safe_path(compose, project_path):
        return DetectedItem(
            name="docker",
            confidence="high",
            source_file=str(compose),
            source_evidence="compose.yml",
        )

    return None
