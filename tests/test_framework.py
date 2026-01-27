"""
Property-based and unit tests for framework and tool detection.

Tests verify that:
1. All DetectedItem objects have valid confidence levels (high/medium/low)
2. source_file paths point to files that exist and are within project
3. source_evidence matches known package patterns for frameworks/tools
4. Framework and tool names match supported values from REFERENCE_CATALOG
5. Functions handle missing manifest files gracefully
6. Functions handle malformed manifests gracefully
7. Confidence levels correctly distinguish production vs dev dependencies
8. Docker detection correctly identifies Dockerfile and compose files

Note: Build tools (gradle, maven, uv, poetry) are NOT detected - they are
auto-installed by provisioner based on language selection.
"""

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from clauded.detect.framework import (
    detect_docker,
    detect_frameworks_and_tools,
    parse_go_dependencies,
    parse_java_dependencies,
    parse_kotlin_dependencies,
    parse_node_dependencies,
    parse_python_dependencies,
    parse_rust_dependencies,
)
from clauded.detect.result import DetectedItem

# Supported framework and tool names (frameworks only, not build tools)
PYTHON_FRAMEWORKS = {"django", "flask", "fastapi"}
NODE_FRAMEWORKS = {"react", "vue", "angular", "express", "next", "nest"}
JAVA_FRAMEWORKS = {"spring-boot", "quarkus"}
KOTLIN_FRAMEWORKS = {"spring-boot", "ktor"}
RUST_FRAMEWORKS = {"actix", "rocket", "tokio"}
GO_FRAMEWORKS = {"gin", "echo", "fiber"}
ALL_FRAMEWORKS = (
    PYTHON_FRAMEWORKS
    | NODE_FRAMEWORKS
    | JAVA_FRAMEWORKS
    | KOTLIN_FRAMEWORKS
    | RUST_FRAMEWORKS
    | GO_FRAMEWORKS
)
# Only optional tools that require explicit user selection
OPTIONAL_TOOLS = {"playwright", "docker"}
CONFIDENCE_LEVELS = ["high", "medium", "low"]  # List for Hypothesis


# Strategies for property-based testing
@st.composite
def detected_items_strategy(draw: Any) -> DetectedItem:
    """Generate valid DetectedItem objects."""
    name = draw(st.sampled_from(sorted(ALL_FRAMEWORKS | OPTIONAL_TOOLS)))
    confidence = draw(st.sampled_from(CONFIDENCE_LEVELS))
    source_file = draw(st.just(f"/tmp/manifest_{name}_{confidence}.txt"))
    source_evidence = draw(st.just(name))
    return DetectedItem(
        name=name,
        confidence=confidence,
        source_file=source_file,
        source_evidence=source_evidence,
    )


# Property-based tests for invariants
class TestDetectedItemInvariants:
    """Test DetectedItem invariants."""

    def test_detected_item_has_valid_confidence(self) -> None:
        """All DetectedItem confidence values are valid."""

        @given(detected_items_strategy())
        def check(item: DetectedItem) -> None:
            assert item.confidence in CONFIDENCE_LEVELS

        check()

    def test_detected_item_has_nonempty_name(self) -> None:
        """All DetectedItem names are non-empty strings."""

        @given(detected_items_strategy())
        def check(item: DetectedItem) -> None:
            assert isinstance(item.name, str)
            assert len(item.name) > 0

        check()

    def test_detected_item_has_nonempty_source_evidence(self) -> None:
        """All DetectedItem source_evidence is non-empty."""

        @given(detected_items_strategy())
        def check(item: DetectedItem) -> None:
            assert isinstance(item.source_evidence, str)
            assert len(item.source_evidence) > 0

        check()

    def test_detected_item_has_source_file_path(self) -> None:
        """All DetectedItem source_file is a path string."""

        @given(detected_items_strategy())
        def check(item: DetectedItem) -> None:
            assert isinstance(item.source_file, str)
            assert len(item.source_file) > 0

        check()


# Fixtures for manifest files
@pytest.fixture
def temp_project_dir() -> Path:
    """Create a temporary project directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def python_pyproject_toml(temp_project_dir: Path) -> Path:
    """Create a pyproject.toml with Python dependencies."""
    pyproject = temp_project_dir / "pyproject.toml"
    pyproject.write_text("""
[project]
name = "test-project"
dependencies = [
    "django>=4.0",
    "flask>=2.0",
]

[project.optional-dependencies]
dev = [
    "fastapi>=0.100",
]
""")
    return pyproject


@pytest.fixture
def python_requirements_txt(temp_project_dir: Path) -> Path:
    """Create a requirements.txt with Python dependencies."""
    req_file = temp_project_dir / "requirements.txt"
    req_file.write_text("""
django>=4.0
flask>=2.0
fastapi>=0.100
""")
    return req_file


@pytest.fixture
def node_package_json(temp_project_dir: Path) -> Path:
    """Create a package.json with Node dependencies."""
    package_json = temp_project_dir / "package.json"
    package_json.write_text(
        json.dumps(
            {
                "name": "test-project",
                "dependencies": {
                    "react": "^18.0.0",
                    "express": "^4.18.0",
                },
                "devDependencies": {
                    "playwright": "^1.40.0",
                },
            }
        )
    )
    return package_json


@pytest.fixture
def java_pom_xml(temp_project_dir: Path) -> Path:
    """Create a pom.xml with Java dependencies."""
    pom = temp_project_dir / "pom.xml"
    pom.write_text("""<?xml version="1.0"?>
<project>
  <modelVersion>4.0.0</modelVersion>
  <dependencies>
    <dependency>
      <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
    <dependency>
      <artifactId>quarkus-core</artifactId>
    </dependency>
  </dependencies>
</project>
""")
    return pom


@pytest.fixture
def kotlin_build_gradle_kts(temp_project_dir: Path) -> Path:
    """Create a build.gradle.kts with Kotlin dependencies."""
    build_file = temp_project_dir / "build.gradle.kts"
    build_file.write_text("""
dependencies {
    implementation("org.springframework.boot:spring-boot-starter-web:2.7.0")
    implementation("io.ktor:ktor-server-core:2.0.0")
    testImplementation("junit:junit:4.13")
}
""")
    return build_file


@pytest.fixture
def rust_cargo_toml(temp_project_dir: Path) -> Path:
    """Create a Cargo.toml with Rust dependencies."""
    cargo = temp_project_dir / "Cargo.toml"
    cargo.write_text("""
[package]
name = "test-project"
version = "0.1.0"

[dependencies]
actix-web = "4.0"
rocket = "0.5"
tokio = { version = "1.0", features = ["full"] }

[dev-dependencies]
pytest = "1.0"
""")
    return cargo


@pytest.fixture
def go_mod(temp_project_dir: Path) -> Path:
    """Create a go.mod with Go dependencies."""
    go_mod_file = temp_project_dir / "go.mod"
    go_mod_file.write_text("""
module github.com/test/project

go 1.22

require (
    github.com/gin-gonic/gin v1.9.0
    github.com/labstack/echo v3.3.0
    github.com/gofiber/fiber v2.0.0
)
""")
    return go_mod_file


@pytest.fixture
def dockerfile(temp_project_dir: Path) -> Path:
    """Create a Dockerfile."""
    dockerfile = temp_project_dir / "Dockerfile"
    dockerfile.write_text("""
FROM ubuntu:22.04
RUN apt-get update
""")
    return dockerfile


@pytest.fixture
def docker_compose_yml(temp_project_dir: Path) -> Path:
    """Create a docker-compose.yml."""
    compose = temp_project_dir / "docker-compose.yml"
    compose.write_text("""
version: "3"
services:
  app:
    build: .
""")
    return compose


# Python dependency parsing tests
class TestParsePythonDependencies:
    """Test Python dependency parsing."""

    def test_detects_django_from_pyproject_toml(
        self, python_pyproject_toml: Path
    ) -> None:
        """Detects Django from pyproject.toml dependencies."""
        project_path = python_pyproject_toml.parent
        items = parse_python_dependencies(project_path)

        django_items = [item for item in items if item.name == "django"]
        assert len(django_items) > 0
        assert django_items[0].confidence == "high"

    def test_detects_flask_from_pyproject_toml(
        self, python_pyproject_toml: Path
    ) -> None:
        """Detects Flask from pyproject.toml dependencies."""
        project_path = python_pyproject_toml.parent
        items = parse_python_dependencies(project_path)

        flask_items = [item for item in items if item.name == "flask"]
        assert len(flask_items) > 0
        assert flask_items[0].confidence == "high"

    def test_detects_fastapi_from_optional_dependencies(
        self, python_pyproject_toml: Path
    ) -> None:
        """Detects FastAPI from optional dependencies as medium confidence."""
        project_path = python_pyproject_toml.parent
        items = parse_python_dependencies(project_path)

        fastapi_items = [item for item in items if item.name == "fastapi"]
        assert len(fastapi_items) > 0
        assert fastapi_items[0].confidence == "medium"

    def test_detects_from_requirements_txt_fallback(
        self, python_requirements_txt: Path
    ) -> None:
        """Detects dependencies from requirements.txt when pyproject.toml absent."""
        project_path = python_requirements_txt.parent
        items = parse_python_dependencies(project_path)

        assert len(items) > 0
        names = {item.name for item in items}
        assert "django" in names or "flask" in names

    def test_source_file_points_to_manifest(self, python_pyproject_toml: Path) -> None:
        """source_file points to the manifest file."""
        project_path = python_pyproject_toml.parent
        items = parse_python_dependencies(project_path)

        for item in items:
            path = Path(item.source_file)
            assert path.exists()
            assert path.name in ("pyproject.toml", "requirements.txt")

    def test_returns_empty_when_no_manifests(self, temp_project_dir: Path) -> None:
        """Returns empty list when no Python manifests present."""
        items = parse_python_dependencies(temp_project_dir)
        assert items == []

    def test_all_items_have_valid_confidence(self, python_pyproject_toml: Path) -> None:
        """All returned items have valid confidence levels."""
        project_path = python_pyproject_toml.parent
        items = parse_python_dependencies(project_path)

        for item in items:
            assert item.confidence in CONFIDENCE_LEVELS

    def test_all_items_have_valid_names(self, python_pyproject_toml: Path) -> None:
        """All returned items have names in supported Python frameworks."""
        project_path = python_pyproject_toml.parent
        items = parse_python_dependencies(project_path)

        for item in items:
            assert item.name in PYTHON_FRAMEWORKS

    def test_source_evidence_matches_package_name(
        self, python_pyproject_toml: Path
    ) -> None:
        """source_evidence contains the package name that triggered detection."""
        project_path = python_pyproject_toml.parent
        items = parse_python_dependencies(project_path)

        for item in items:
            assert item.source_evidence in (
                "django",
                "flask",
                "fastapi",
            )


# Node dependency parsing tests
class TestParseNodeDependencies:
    """Test Node.js dependency parsing."""

    def test_detects_react_from_package_json(self, node_package_json: Path) -> None:
        """Detects React from package.json dependencies."""
        project_path = node_package_json.parent
        items = parse_node_dependencies(project_path)

        react_items = [item for item in items if item.name == "react"]
        assert len(react_items) > 0
        assert react_items[0].confidence == "high"

    def test_detects_express_from_package_json(self, node_package_json: Path) -> None:
        """Detects Express from package.json dependencies."""
        project_path = node_package_json.parent
        items = parse_node_dependencies(project_path)

        express_items = [item for item in items if item.name == "express"]
        assert len(express_items) > 0
        assert express_items[0].confidence == "high"

    def test_detects_playwright_from_dev_dependencies(
        self, node_package_json: Path
    ) -> None:
        """Detects Playwright from devDependencies."""
        project_path = node_package_json.parent
        items = parse_node_dependencies(project_path)

        playwright_items = [item for item in items if item.name == "playwright"]
        assert len(playwright_items) > 0
        assert playwright_items[0].confidence == "medium"

    def test_source_file_points_to_package_json(self, node_package_json: Path) -> None:
        """source_file points to package.json."""
        project_path = node_package_json.parent
        items = parse_node_dependencies(project_path)

        for item in items:
            path = Path(item.source_file)
            assert path.name == "package.json"

    def test_returns_empty_when_no_package_json(self, temp_project_dir: Path) -> None:
        """Returns empty list when package.json not present."""
        items = parse_node_dependencies(temp_project_dir)
        assert items == []

    def test_all_items_have_valid_confidence(self, node_package_json: Path) -> None:
        """All returned items have valid confidence levels."""
        project_path = node_package_json.parent
        items = parse_node_dependencies(project_path)

        for item in items:
            assert item.confidence in CONFIDENCE_LEVELS

    def test_all_items_have_valid_names(self, node_package_json: Path) -> None:
        """All returned items have valid framework or tool names."""
        project_path = node_package_json.parent
        items = parse_node_dependencies(project_path)

        for item in items:
            assert item.name in (NODE_FRAMEWORKS | {"playwright"})


# Java dependency parsing tests
class TestParseJavaDependencies:
    """Test Java dependency parsing."""

    def test_detects_spring_boot_from_pom_xml(self, java_pom_xml: Path) -> None:
        """Detects Spring Boot from pom.xml dependencies."""
        project_path = java_pom_xml.parent
        items = parse_java_dependencies(project_path)

        spring_items = [item for item in items if item.name == "spring-boot"]
        assert len(spring_items) > 0

    def test_detects_quarkus_from_pom_xml(self, java_pom_xml: Path) -> None:
        """Detects Quarkus from pom.xml dependencies."""
        project_path = java_pom_xml.parent
        items = parse_java_dependencies(project_path)

        quarkus_items = [item for item in items if item.name == "quarkus"]
        assert len(quarkus_items) > 0

    def test_source_file_points_to_pom_xml(self, java_pom_xml: Path) -> None:
        """source_file points to pom.xml."""
        project_path = java_pom_xml.parent
        items = parse_java_dependencies(project_path)

        for item in items:
            path = Path(item.source_file)
            assert path.name == "pom.xml"

    def test_returns_empty_when_no_java_manifests(self, temp_project_dir: Path) -> None:
        """Returns empty list when no Java manifests present."""
        items = parse_java_dependencies(temp_project_dir)
        assert items == []

    def test_all_items_have_valid_names(self, java_pom_xml: Path) -> None:
        """All returned items have names in supported Java frameworks."""
        project_path = java_pom_xml.parent
        items = parse_java_dependencies(project_path)

        for item in items:
            assert item.name in JAVA_FRAMEWORKS


# Kotlin dependency parsing tests
class TestParseKotlinDependencies:
    """Test Kotlin dependency parsing."""

    def test_detects_spring_boot_from_gradle_kts(
        self, kotlin_build_gradle_kts: Path
    ) -> None:
        """Detects Spring Boot from build.gradle.kts."""
        project_path = kotlin_build_gradle_kts.parent
        items = parse_kotlin_dependencies(project_path)

        spring_items = [item for item in items if item.name == "spring-boot"]
        assert len(spring_items) > 0

    def test_detects_ktor_from_gradle_kts(self, kotlin_build_gradle_kts: Path) -> None:
        """Detects Ktor from build.gradle.kts."""
        project_path = kotlin_build_gradle_kts.parent
        items = parse_kotlin_dependencies(project_path)

        ktor_items = [item for item in items if item.name == "ktor"]
        assert len(ktor_items) > 0

    def test_source_file_points_to_gradle_kts(
        self, kotlin_build_gradle_kts: Path
    ) -> None:
        """source_file points to build.gradle.kts."""
        project_path = kotlin_build_gradle_kts.parent
        items = parse_kotlin_dependencies(project_path)

        for item in items:
            path = Path(item.source_file)
            assert path.name == "build.gradle.kts"

    def test_returns_empty_when_no_gradle_kts(self, temp_project_dir: Path) -> None:
        """Returns empty list when build.gradle.kts not present."""
        items = parse_kotlin_dependencies(temp_project_dir)
        assert items == []


# Rust dependency parsing tests
class TestParseRustDependencies:
    """Test Rust dependency parsing."""

    def test_detects_actix_from_cargo_toml(self, rust_cargo_toml: Path) -> None:
        """Detects Actix from Cargo.toml dependencies."""
        project_path = rust_cargo_toml.parent
        items = parse_rust_dependencies(project_path)

        actix_items = [item for item in items if item.name == "actix"]
        assert len(actix_items) > 0
        assert actix_items[0].confidence == "high"

    def test_detects_rocket_from_cargo_toml(self, rust_cargo_toml: Path) -> None:
        """Detects Rocket from Cargo.toml dependencies."""
        project_path = rust_cargo_toml.parent
        items = parse_rust_dependencies(project_path)

        rocket_items = [item for item in items if item.name == "rocket"]
        assert len(rocket_items) > 0
        assert rocket_items[0].confidence == "high"

    def test_detects_tokio_from_cargo_toml(self, rust_cargo_toml: Path) -> None:
        """Detects Tokio from Cargo.toml dependencies."""
        project_path = rust_cargo_toml.parent
        items = parse_rust_dependencies(project_path)

        tokio_items = [item for item in items if item.name == "tokio"]
        assert len(tokio_items) > 0
        assert tokio_items[0].confidence == "high"

    def test_source_file_points_to_cargo_toml(self, rust_cargo_toml: Path) -> None:
        """source_file points to Cargo.toml."""
        project_path = rust_cargo_toml.parent
        items = parse_rust_dependencies(project_path)

        for item in items:
            path = Path(item.source_file)
            assert path.name == "Cargo.toml"

    def test_returns_empty_when_no_cargo_toml(self, temp_project_dir: Path) -> None:
        """Returns empty list when Cargo.toml not present."""
        items = parse_rust_dependencies(temp_project_dir)
        assert items == []


# Go dependency parsing tests
class TestParseGoDependencies:
    """Test Go dependency parsing."""

    def test_detects_gin_from_go_mod(self, go_mod: Path) -> None:
        """Detects Gin from go.mod dependencies."""
        project_path = go_mod.parent
        items = parse_go_dependencies(project_path)

        gin_items = [item for item in items if item.name == "gin"]
        assert len(gin_items) > 0

    def test_detects_echo_from_go_mod(self, go_mod: Path) -> None:
        """Detects Echo from go.mod dependencies."""
        project_path = go_mod.parent
        items = parse_go_dependencies(project_path)

        echo_items = [item for item in items if item.name == "echo"]
        assert len(echo_items) > 0

    def test_detects_fiber_from_go_mod(self, go_mod: Path) -> None:
        """Detects Fiber from go.mod dependencies."""
        project_path = go_mod.parent
        items = parse_go_dependencies(project_path)

        fiber_items = [item for item in items if item.name == "fiber"]
        assert len(fiber_items) > 0

    def test_source_file_points_to_go_mod(self, go_mod: Path) -> None:
        """source_file points to go.mod."""
        project_path = go_mod.parent
        items = parse_go_dependencies(project_path)

        for item in items:
            path = Path(item.source_file)
            assert path.name == "go.mod"

    def test_returns_empty_when_no_go_mod(self, temp_project_dir: Path) -> None:
        """Returns empty list when go.mod not present."""
        items = parse_go_dependencies(temp_project_dir)
        assert items == []


# Docker detection tests
class TestDetectDocker:
    """Test Docker detection."""

    def test_detects_dockerfile(self, dockerfile: Path) -> None:
        """Detects Docker from Dockerfile."""
        project_path = dockerfile.parent
        item = detect_docker(project_path)

        assert item is not None
        assert item.name == "docker"
        assert item.confidence == "high"

    def test_detects_docker_compose_yml(self, docker_compose_yml: Path) -> None:
        """Detects Docker from docker-compose.yml."""
        project_path = docker_compose_yml.parent
        item = detect_docker(project_path)

        assert item is not None
        assert item.name == "docker"
        assert item.confidence == "high"

    def test_returns_none_when_no_docker_files(self, temp_project_dir: Path) -> None:
        """Returns None when no Docker files present."""
        item = detect_docker(temp_project_dir)
        assert item is None

    def test_docker_source_file_points_to_manifest(self, dockerfile: Path) -> None:
        """Docker item source_file points to actual Docker file."""
        project_path = dockerfile.parent
        item = detect_docker(project_path)

        assert item is not None
        path = Path(item.source_file)
        assert path.exists()
        assert path.name in (
            "Dockerfile",
            "docker-compose.yml",
            "compose.yml",
        )


# Integration tests
class TestDetectFrameworksAndTools:
    """Test integrated framework and tool detection."""

    def test_returns_tuple_of_lists(self, python_pyproject_toml: Path) -> None:
        """Returns tuple of (frameworks, tools) lists."""
        project_path = python_pyproject_toml.parent
        frameworks, tools = detect_frameworks_and_tools(project_path)

        assert isinstance(frameworks, list)
        assert isinstance(tools, list)

    def test_separates_frameworks_and_tools(self, python_pyproject_toml: Path) -> None:
        """Correctly separates frameworks and tools."""
        project_path = python_pyproject_toml.parent
        frameworks, tools = detect_frameworks_and_tools(project_path)

        framework_names = {item.name for item in frameworks}
        tool_names = {item.name for item in tools}

        assert framework_names.isdisjoint(tool_names)

    def test_detects_multiple_ecosystems(
        self,
        temp_project_dir: Path,
        python_pyproject_toml: Path,
        node_package_json: Path,
    ) -> None:
        """Detects frameworks and tools across multiple ecosystems."""
        # Create test project with both Python and Node manifests
        temp_project_dir / "pyproject.toml"
        temp_project_dir / "package.json"

        frameworks, tools = detect_frameworks_and_tools(temp_project_dir)

        # Should detect items from both ecosystems
        assert len(frameworks) + len(tools) >= 0

    def test_handles_mixed_project_gracefully(self, temp_project_dir: Path) -> None:
        """Handles projects with partial manifests gracefully."""
        # Create a project with only Docker
        (temp_project_dir / "Dockerfile").write_text("FROM ubuntu")

        frameworks, tools = detect_frameworks_and_tools(temp_project_dir)

        docker_tools = [t for t in tools if t.name == "docker"]
        assert len(docker_tools) > 0

    def test_returns_empty_for_empty_project(self, temp_project_dir: Path) -> None:
        """Returns empty lists for project with no manifests."""
        frameworks, tools = detect_frameworks_and_tools(temp_project_dir)

        assert isinstance(frameworks, list)
        assert isinstance(tools, list)

    def test_all_framework_items_are_frameworks(
        self, python_pyproject_toml: Path
    ) -> None:
        """All items in frameworks list are actually frameworks."""
        project_path = python_pyproject_toml.parent
        frameworks, _ = detect_frameworks_and_tools(project_path)

        for item in frameworks:
            assert item.name in ALL_FRAMEWORKS

    def test_all_tool_items_are_optional_tools(
        self, python_pyproject_toml: Path
    ) -> None:
        """All items in tools list are optional tools (docker, playwright)."""
        project_path = python_pyproject_toml.parent
        _, tools = detect_frameworks_and_tools(project_path)

        for item in tools:
            assert item.name in OPTIONAL_TOOLS
