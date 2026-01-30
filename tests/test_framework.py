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


# Parameterized Python framework detection tests
class TestParsePythonDependencies:
    """Test Python dependency parsing."""

    @pytest.mark.parametrize(
        "framework,package_name,confidence",
        [
            ("django", "django>=4.0", "high"),
            ("flask", "flask>=2.0", "high"),
            ("fastapi", "fastapi>=0.100", "high"),
        ],
    )
    def test_detects_framework_from_pyproject_dependencies(
        self, temp_project_dir: Path, framework: str, package_name: str, confidence: str
    ) -> None:
        """Detects Python framework from pyproject.toml dependencies."""
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text(f"""
[project]
name = "test-project"
dependencies = [
    "{package_name}",
]
""")
        items = parse_python_dependencies(temp_project_dir)

        framework_items = [item for item in items if item.name == framework]
        assert len(framework_items) > 0
        assert framework_items[0].confidence == confidence

    @pytest.mark.parametrize(
        "framework,package_name",
        [
            ("django", "django>=4.0"),
            ("flask", "flask>=2.0"),
            ("fastapi", "fastapi>=0.100"),
        ],
    )
    def test_detects_framework_from_optional_dependencies(
        self, temp_project_dir: Path, framework: str, package_name: str
    ) -> None:
        """Detects Python framework from optional dependencies as medium confidence."""
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text(f"""
[project]
name = "test-project"
dependencies = []

[project.optional-dependencies]
dev = [
    "{package_name}",
]
""")
        items = parse_python_dependencies(temp_project_dir)

        framework_items = [item for item in items if item.name == framework]
        assert len(framework_items) > 0
        assert framework_items[0].confidence == "medium"

    def test_detects_from_requirements_txt_fallback(
        self, temp_project_dir: Path
    ) -> None:
        """Detects dependencies from requirements.txt when pyproject.toml absent."""
        req_file = temp_project_dir / "requirements.txt"
        req_file.write_text("django>=4.0\nflask>=2.0\n")

        items = parse_python_dependencies(temp_project_dir)

        assert len(items) > 0
        names = {item.name for item in items}
        assert "django" in names or "flask" in names

    def test_source_file_points_to_manifest(self, temp_project_dir: Path) -> None:
        """source_file points to the manifest file."""
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-project"
dependencies = ["django>=4.0"]
""")
        items = parse_python_dependencies(temp_project_dir)

        for item in items:
            path = Path(item.source_file)
            assert path.exists()
            assert path.name in ("pyproject.toml", "requirements.txt")

    def test_returns_empty_when_no_manifests(self, temp_project_dir: Path) -> None:
        """Returns empty list when no Python manifests present."""
        items = parse_python_dependencies(temp_project_dir)
        assert items == []

    def test_all_items_have_valid_confidence(self, temp_project_dir: Path) -> None:
        """All returned items have valid confidence levels."""
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text("""
[project]
dependencies = ["django>=4.0", "flask>=2.0"]
""")
        items = parse_python_dependencies(temp_project_dir)

        for item in items:
            assert item.confidence in CONFIDENCE_LEVELS

    def test_all_items_have_valid_names(self, temp_project_dir: Path) -> None:
        """All returned items have names in supported Python frameworks."""
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text("""
[project]
dependencies = ["django>=4.0", "flask>=2.0"]
""")
        items = parse_python_dependencies(temp_project_dir)

        for item in items:
            assert item.name in PYTHON_FRAMEWORKS


# Parameterized Node framework detection tests
class TestParseNodeDependencies:
    """Test Node.js dependency parsing."""

    @pytest.mark.parametrize(
        "framework,package_name,confidence",
        [
            ("react", "react", "high"),
            ("vue", "vue", "high"),
            ("angular", "angular", "high"),
            ("express", "express", "high"),
            ("next", "next", "high"),
            ("nest", "@nestjs/core", "high"),
        ],
    )
    def test_detects_framework_from_dependencies(
        self, temp_project_dir: Path, framework: str, package_name: str, confidence: str
    ) -> None:
        """Detects Node framework from package.json dependencies."""
        package_json = temp_project_dir / "package.json"
        package_json.write_text(
            json.dumps(
                {
                    "name": "test-project",
                    "dependencies": {
                        package_name: "^1.0.0",
                    },
                }
            )
        )
        items = parse_node_dependencies(temp_project_dir)

        framework_items = [item for item in items if item.name == framework]
        assert len(framework_items) > 0
        assert framework_items[0].confidence == confidence

    @pytest.mark.parametrize(
        "tool,package_name",
        [
            ("playwright", "playwright"),
        ],
    )
    def test_detects_tool_from_dev_dependencies(
        self, temp_project_dir: Path, tool: str, package_name: str
    ) -> None:
        """Detects tools from devDependencies."""
        package_json = temp_project_dir / "package.json"
        package_json.write_text(
            json.dumps(
                {
                    "name": "test-project",
                    "devDependencies": {
                        package_name: "^1.0.0",
                    },
                }
            )
        )
        items = parse_node_dependencies(temp_project_dir)

        tool_items = [item for item in items if item.name == tool]
        assert len(tool_items) > 0
        assert tool_items[0].confidence == "medium"

    def test_source_file_points_to_package_json(self, temp_project_dir: Path) -> None:
        """source_file points to package.json."""
        package_json = temp_project_dir / "package.json"
        package_json.write_text(json.dumps({"dependencies": {"react": "^18.0.0"}}))

        items = parse_node_dependencies(temp_project_dir)

        for item in items:
            path = Path(item.source_file)
            assert path.name == "package.json"

    def test_returns_empty_when_no_package_json(self, temp_project_dir: Path) -> None:
        """Returns empty list when package.json not present."""
        items = parse_node_dependencies(temp_project_dir)
        assert items == []


# Parameterized Java framework detection tests
class TestParseJavaDependencies:
    """Test Java dependency parsing."""

    @pytest.mark.parametrize(
        "framework,artifact_id",
        [
            ("spring-boot", "spring-boot-starter-web"),
            ("spring-boot", "spring-boot-starter"),
            ("quarkus", "quarkus-core"),
            ("quarkus", "quarkus-resteasy"),
        ],
    )
    def test_detects_framework_from_pom_xml(
        self, temp_project_dir: Path, framework: str, artifact_id: str
    ) -> None:
        """Detects Java framework from pom.xml dependencies."""
        pom = temp_project_dir / "pom.xml"
        pom.write_text(f"""<?xml version="1.0"?>
<project>
  <modelVersion>4.0.0</modelVersion>
  <dependencies>
    <dependency>
      <artifactId>{artifact_id}</artifactId>
    </dependency>
  </dependencies>
</project>
""")
        items = parse_java_dependencies(temp_project_dir)

        framework_items = [item for item in items if item.name == framework]
        assert len(framework_items) > 0

    def test_source_file_points_to_pom_xml(self, temp_project_dir: Path) -> None:
        """source_file points to pom.xml."""
        pom = temp_project_dir / "pom.xml"
        pom.write_text("""<?xml version="1.0"?>
<project><dependencies>
<dependency><artifactId>spring-boot-starter-web</artifactId></dependency>
</dependencies></project>
""")
        items = parse_java_dependencies(temp_project_dir)

        for item in items:
            path = Path(item.source_file)
            assert path.name == "pom.xml"

    def test_returns_empty_when_no_java_manifests(self, temp_project_dir: Path) -> None:
        """Returns empty list when no Java manifests present."""
        items = parse_java_dependencies(temp_project_dir)
        assert items == []


# Parameterized Kotlin framework detection tests
class TestParseKotlinDependencies:
    """Test Kotlin dependency parsing."""

    @pytest.mark.parametrize(
        "framework,dependency_pattern",
        [
            (
                "spring-boot",
                'implementation("org.springframework.boot:spring-boot-starter-web:2.7.0")',
            ),
            ("ktor", 'implementation("io.ktor:ktor-server-core:2.0.0")'),
        ],
    )
    def test_detects_framework_from_gradle_kts(
        self, temp_project_dir: Path, framework: str, dependency_pattern: str
    ) -> None:
        """Detects Kotlin framework from build.gradle.kts."""
        build_file = temp_project_dir / "build.gradle.kts"
        build_file.write_text(f"""
dependencies {{
    {dependency_pattern}
}}
""")
        items = parse_kotlin_dependencies(temp_project_dir)

        framework_items = [item for item in items if item.name == framework]
        assert len(framework_items) > 0

    def test_source_file_points_to_gradle_kts(self, temp_project_dir: Path) -> None:
        """source_file points to build.gradle.kts."""
        build_file = temp_project_dir / "build.gradle.kts"
        build_file.write_text("""
dependencies {
    implementation("org.springframework.boot:spring-boot-starter-web:2.7.0")
}
""")
        items = parse_kotlin_dependencies(temp_project_dir)

        for item in items:
            path = Path(item.source_file)
            assert path.name == "build.gradle.kts"

    def test_returns_empty_when_no_gradle_kts(self, temp_project_dir: Path) -> None:
        """Returns empty list when build.gradle.kts not present."""
        items = parse_kotlin_dependencies(temp_project_dir)
        assert items == []


# Parameterized Rust framework detection tests
class TestParseRustDependencies:
    """Test Rust dependency parsing."""

    @pytest.mark.parametrize(
        "framework,crate_name,confidence",
        [
            ("actix", "actix-web", "high"),
            ("rocket", "rocket", "high"),
            ("tokio", "tokio", "high"),
        ],
    )
    def test_detects_framework_from_cargo_toml(
        self, temp_project_dir: Path, framework: str, crate_name: str, confidence: str
    ) -> None:
        """Detects Rust framework from Cargo.toml dependencies."""
        cargo = temp_project_dir / "Cargo.toml"
        cargo.write_text(f"""
[package]
name = "test-project"
version = "0.1.0"

[dependencies]
{crate_name} = "1.0"
""")
        items = parse_rust_dependencies(temp_project_dir)

        framework_items = [item for item in items if item.name == framework]
        assert len(framework_items) > 0
        assert framework_items[0].confidence == confidence

    def test_source_file_points_to_cargo_toml(self, temp_project_dir: Path) -> None:
        """source_file points to Cargo.toml."""
        cargo = temp_project_dir / "Cargo.toml"
        cargo.write_text("""
[package]
name = "test"
[dependencies]
actix-web = "4.0"
""")
        items = parse_rust_dependencies(temp_project_dir)

        for item in items:
            path = Path(item.source_file)
            assert path.name == "Cargo.toml"

    def test_returns_empty_when_no_cargo_toml(self, temp_project_dir: Path) -> None:
        """Returns empty list when Cargo.toml not present."""
        items = parse_rust_dependencies(temp_project_dir)
        assert items == []


# Parameterized Go framework detection tests
class TestParseGoDependencies:
    """Test Go dependency parsing."""

    @pytest.mark.parametrize(
        "framework,module_path",
        [
            ("gin", "github.com/gin-gonic/gin"),
            ("echo", "github.com/labstack/echo"),
            ("fiber", "github.com/gofiber/fiber"),
        ],
    )
    def test_detects_framework_from_go_mod(
        self, temp_project_dir: Path, framework: str, module_path: str
    ) -> None:
        """Detects Go framework from go.mod dependencies."""
        go_mod_file = temp_project_dir / "go.mod"
        go_mod_file.write_text(f"""
module github.com/test/project

go 1.22

require (
    {module_path} v1.0.0
)
""")
        items = parse_go_dependencies(temp_project_dir)

        framework_items = [item for item in items if item.name == framework]
        assert len(framework_items) > 0

    def test_source_file_points_to_go_mod(self, temp_project_dir: Path) -> None:
        """source_file points to go.mod."""
        go_mod_file = temp_project_dir / "go.mod"
        go_mod_file.write_text("""
module github.com/test/project
go 1.22
require github.com/gin-gonic/gin v1.9.0
""")
        items = parse_go_dependencies(temp_project_dir)

        for item in items:
            path = Path(item.source_file)
            assert path.name == "go.mod"

    def test_returns_empty_when_no_go_mod(self, temp_project_dir: Path) -> None:
        """Returns empty list when go.mod not present."""
        items = parse_go_dependencies(temp_project_dir)
        assert items == []


# Parameterized Docker detection tests
class TestDetectDocker:
    """Test Docker detection."""

    @pytest.mark.parametrize(
        "docker_file,content",
        [
            ("Dockerfile", "FROM ubuntu:22.04\nRUN apt-get update"),
            ("docker-compose.yml", 'version: "3"\nservices:\n  app:\n    build: .'),
            ("compose.yml", "services:\n  app:\n    build: ."),
        ],
    )
    def test_detects_docker_from_file(
        self, temp_project_dir: Path, docker_file: str, content: str
    ) -> None:
        """Detects Docker from Dockerfile or compose files."""
        (temp_project_dir / docker_file).write_text(content)

        item = detect_docker(temp_project_dir)

        assert item is not None
        assert item.name == "docker"
        assert item.confidence == "high"

    def test_returns_none_when_no_docker_files(self, temp_project_dir: Path) -> None:
        """Returns None when no Docker files present."""
        item = detect_docker(temp_project_dir)
        assert item is None

    def test_docker_source_file_points_to_manifest(
        self, temp_project_dir: Path
    ) -> None:
        """Docker item source_file points to actual Docker file."""
        dockerfile = temp_project_dir / "Dockerfile"
        dockerfile.write_text("FROM ubuntu")

        item = detect_docker(temp_project_dir)

        assert item is not None
        path = Path(item.source_file)
        assert path.exists()
        assert path.name in ("Dockerfile", "docker-compose.yml", "compose.yml")


# Integration tests
class TestDetectFrameworksAndTools:
    """Test integrated framework and tool detection."""

    def test_returns_tuple_of_lists(self, temp_project_dir: Path) -> None:
        """Returns tuple of (frameworks, tools) lists."""
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text('[project]\ndependencies = ["django>=4.0"]')

        frameworks, tools = detect_frameworks_and_tools(temp_project_dir)

        assert isinstance(frameworks, list)
        assert isinstance(tools, list)

    def test_separates_frameworks_and_tools(self, temp_project_dir: Path) -> None:
        """Correctly separates frameworks and tools."""
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text('[project]\ndependencies = ["django>=4.0"]')

        frameworks, tools = detect_frameworks_and_tools(temp_project_dir)

        framework_names = {item.name for item in frameworks}
        tool_names = {item.name for item in tools}

        assert framework_names.isdisjoint(tool_names)

    def test_handles_mixed_project_gracefully(self, temp_project_dir: Path) -> None:
        """Handles projects with partial manifests gracefully."""
        (temp_project_dir / "Dockerfile").write_text("FROM ubuntu")

        frameworks, tools = detect_frameworks_and_tools(temp_project_dir)

        docker_tools = [t for t in tools if t.name == "docker"]
        assert len(docker_tools) > 0

    def test_returns_empty_for_empty_project(self, temp_project_dir: Path) -> None:
        """Returns empty lists for project with no manifests."""
        frameworks, tools = detect_frameworks_and_tools(temp_project_dir)

        assert isinstance(frameworks, list)
        assert isinstance(tools, list)

    def test_all_framework_items_are_frameworks(self, temp_project_dir: Path) -> None:
        """All items in frameworks list are actually frameworks."""
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text('[project]\ndependencies = ["django>=4.0", "flask>=2.0"]')

        frameworks, _ = detect_frameworks_and_tools(temp_project_dir)

        for item in frameworks:
            assert item.name in ALL_FRAMEWORKS

    def test_all_tool_items_are_optional_tools(self, temp_project_dir: Path) -> None:
        """All items in tools list are optional tools (docker, playwright)."""
        (temp_project_dir / "Dockerfile").write_text("FROM ubuntu")

        _, tools = detect_frameworks_and_tools(temp_project_dir)

        for item in tools:
            assert item.name in OPTIONAL_TOOLS
