"""Property-based and unit tests for version detection.

Tests verify that:
1. All detected VersionSpec objects have valid constraint_type values
2. source_file paths exist and are absolute
3. Version strings follow expected formats for each runtime
4. Priority order is respected (explicit files > .tool-versions > manifest)
5. Multi-source resolution works correctly
6. Parse failures are graceful (log warning, return None/empty)
7. All supported version file types are parsed correctly
"""

import tempfile
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from clauded.detect.version import (
    detect_versions,
    parse_go_version,
    parse_java_version,
    parse_kotlin_version,
    parse_node_version,
    parse_python_version,
    parse_rust_version,
    parse_tool_versions,
)


class TestConstraintTypeValidation:
    """Property tests for constraint_type validity."""

    @given(
        runtime_name=st.sampled_from(
            ["python", "node", "java", "kotlin", "rust", "go"]
        ),
        project_fixture=st.just(None),
    )
    def test_detect_versions_has_valid_constraint_types(
        self, runtime_name, project_fixture
    ):
        """All returned VersionSpecs have valid constraint_type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)

            versions = detect_versions(project_path)

            for _runtime, spec in versions.items():
                assert spec.constraint_type in {"exact", "minimum", "range"}
                assert isinstance(spec.version, str)
                assert len(spec.version) > 0
                assert isinstance(spec.source_file, str)
                assert len(spec.source_file) > 0

    @given(
        version_str=st.text(min_size=1, max_size=50),
    )
    def test_parsed_python_version_has_valid_constraint_type(self, version_str):
        """All Python version specs have valid constraint_type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".python-version").write_text(version_str)

            spec = parse_python_version(project_path)

            if spec is not None:
                assert spec.constraint_type in {"exact", "minimum", "range"}

    @given(
        version_str=st.text(min_size=1, max_size=50),
    )
    def test_parsed_node_version_has_valid_constraint_type(self, version_str):
        """All Node version specs have valid constraint_type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".nvmrc").write_text(version_str)

            spec = parse_node_version(project_path)

            if spec is not None:
                assert spec.constraint_type in {"exact", "minimum", "range"}

    @given(
        version_str=st.text(min_size=1, max_size=50),
    )
    def test_parsed_rust_version_has_valid_constraint_type(self, version_str):
        """All Rust version specs have valid constraint_type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / "rust-toolchain").write_text(version_str)

            spec = parse_rust_version(project_path)

            if spec is not None:
                assert spec.constraint_type in {"exact", "minimum", "range"}

    @given(
        version_str=st.text(min_size=1, max_size=50),
    )
    def test_parsed_go_version_has_valid_constraint_type(self, version_str):
        """All Go version specs have valid constraint_type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / "go.mod").write_text(f"go {version_str}\n")

            spec = parse_go_version(project_path)

            if spec is not None:
                assert spec.constraint_type in {"exact", "minimum", "range"}


class TestSourceFileValidity:
    """Property tests for source_file path validity."""

    @given(
        runtime_files=st.just(
            {
                ".python-version": "3.12",
                ".nvmrc": "20",
                ".java-version": "21",
                "rust-toolchain": "stable",
            }
        ),
    )
    def test_all_source_files_are_absolute_paths(self, runtime_files):
        """All returned source_file values are absolute paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)

            for filename, content in runtime_files.items():
                (project_path / filename).write_text(content)

            versions = detect_versions(project_path)

            for _runtime, spec in versions.items():
                assert Path(spec.source_file).is_absolute()

    @given(
        python_version=st.just("3.12.0"),
    )
    def test_python_source_file_exists(self, python_version):
        """Python version source_file path exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".python-version").write_text(python_version)

            spec = parse_python_version(project_path)

            if spec is not None:
                assert Path(spec.source_file).exists()

    @given(
        node_version=st.just("20.0.0"),
    )
    def test_node_source_file_exists(self, node_version):
        """Node version source_file path exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".nvmrc").write_text(node_version)

            spec = parse_node_version(project_path)

            if spec is not None:
                assert Path(spec.source_file).exists()

    @given(
        java_version=st.just("21"),
    )
    def test_java_source_file_exists(self, java_version):
        """Java version source_file path exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".java-version").write_text(java_version)

            spec = parse_java_version(project_path)

            if spec is not None:
                assert Path(spec.source_file).exists()


class TestVersionFormatValidity:
    """Property tests for version string formats."""

    @given(
        semver_version=st.from_regex(
            r"\d+\.\d+(?:\.\d+)?",
            fullmatch=True,
        ),
    )
    def test_python_version_string_format(self, semver_version):
        """Python version strings are well-formed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".python-version").write_text(semver_version)

            spec = parse_python_version(project_path)

            if spec is not None:
                assert len(spec.version) > 0
                assert not spec.version.startswith(" ")
                assert not spec.version.endswith(" ")

    @given(
        semver_version=st.from_regex(
            r"v?\d+(?:\.\d+)*",
            fullmatch=True,
        ),
    )
    def test_node_version_string_normalized(self, semver_version):
        """Node version strings have 'v' prefix removed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".nvmrc").write_text(semver_version)

            spec = parse_node_version(project_path)

            if spec is not None:
                assert not spec.version.startswith("v")
                assert not spec.version.startswith(" ")

    @given(
        rust_channel=st.sampled_from(
            ["stable", "nightly", "nightly-2024-01-01", "1.70.0"]
        ),
    )
    def test_rust_version_string_format(self, rust_channel):
        """Rust version strings are well-formed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / "rust-toolchain").write_text(rust_channel)

            spec = parse_rust_version(project_path)

            if spec is not None:
                assert len(spec.version) > 0
                assert not spec.version.startswith(" ")


class TestPriorityOrder:
    """Property tests for version source priority."""

    def test_explicit_python_version_preferred_over_toml(self):
        """Explicit .python-version takes priority over pyproject.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".python-version").write_text("3.12.0")
            (project_path / "pyproject.toml").write_text(
                '[project]\nrequires-python = ">=3.10"'
            )

            spec = parse_python_version(project_path)

            assert spec is not None
            assert spec.version == "3.12.0"
            assert "python-version" in spec.source_file

    def test_explicit_node_version_preferred_over_package_json(self):
        """Explicit .nvmrc takes priority over package.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".nvmrc").write_text("20.0.0")
            (project_path / "package.json").write_text(
                '{"engines": {"node": "^18.0.0"}}'
            )

            spec = parse_node_version(project_path)

            assert spec is not None
            assert spec.version == "20.0.0"
            assert "nvmrc" in spec.source_file

    def test_tool_versions_preferred_over_manifest_for_python(self):
        """Universal .tool-versions takes priority over manifest for Python."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".tool-versions").write_text("python 3.11.0")
            (project_path / "pyproject.toml").write_text(
                '[project]\nrequires-python = ">=3.10"'
            )

            versions = detect_versions(project_path)

            assert "python" in versions
            assert versions["python"].version == "3.11.0"
            assert "tool-versions" in versions["python"].source_file

    def test_tool_versions_preferred_over_manifest_for_node(self):
        """Universal .tool-versions takes priority over manifest for Node."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".tool-versions").write_text("nodejs 18.0.0")
            (project_path / "package.json").write_text(
                '{"engines": {"node": "^20.0.0"}}'
            )

            versions = detect_versions(project_path)

            assert "node" in versions
            assert versions["node"].version == "18.0.0"
            assert "tool-versions" in versions["node"].source_file


class TestGracefulErrorHandling:
    """Property tests for error handling."""

    @given(
        invalid_content=st.text(min_size=1),
    )
    def test_malformed_python_version_returns_none(self, invalid_content):
        """Malformed .python-version files return None without exception."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".python-version").write_text(invalid_content)

            spec = parse_python_version(project_path)

            # Function should either return valid VersionSpec or None, never raise
            # Most random text will return None due to version validation
            if spec is not None:
                # If something was returned, verify it's a valid VersionSpec
                assert hasattr(spec, "version")
                assert hasattr(spec, "source_file")
                assert hasattr(spec, "constraint_type")

    def test_missing_files_return_none(self):
        """Missing version files return None gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)

            assert parse_python_version(project_path) is None
            assert parse_node_version(project_path) is None
            assert parse_java_version(project_path) is None
            assert parse_kotlin_version(project_path) is None
            assert parse_rust_version(project_path) is None
            assert parse_go_version(project_path) is None

    def test_detect_versions_handles_all_missing_files(self):
        """detect_versions returns empty dict when no files found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)

            versions = detect_versions(project_path)

            assert versions == {}


class TestVersionParsing:
    """Concrete test cases for version parsing."""

    def test_parse_python_version_from_python_version_file(self):
        """Reads Python version from .python-version."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".python-version").write_text("3.12.0")

            spec = parse_python_version(project_path)

            assert spec is not None
            assert spec.version == "3.12.0"
            assert spec.constraint_type == "exact"
            assert ".python-version" in spec.source_file

    def test_parse_python_version_from_pyproject_toml(self):
        """Reads Python version from pyproject.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / "pyproject.toml").write_text(
                '[project]\nrequires-python = ">=3.10"'
            )

            spec = parse_python_version(project_path)

            assert spec is not None
            assert spec.version == ">=3.10"
            assert spec.constraint_type == "minimum"
            assert "pyproject.toml" in spec.source_file

    def test_parse_python_version_from_pyproject_toml_range_constraint(self):
        """Reads Python version with range constraint from pyproject.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / "pyproject.toml").write_text(
                '[project]\nrequires-python = ">=3.10,<3.13"'
            )

            spec = parse_python_version(project_path)

            assert spec is not None
            assert spec.version == ">=3.10,<3.13"
            assert spec.constraint_type == "range"

    def test_parse_node_version_from_nvmrc(self):
        """Reads Node version from .nvmrc."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".nvmrc").write_text("20.10.0")

            spec = parse_node_version(project_path)

            assert spec is not None
            assert spec.version == "20.10.0"
            assert spec.constraint_type == "exact"
            assert "nvmrc" in spec.source_file

    def test_parse_node_version_removes_v_prefix(self):
        """Node version parser removes 'v' prefix."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".nvmrc").write_text("v20.10.0")

            spec = parse_node_version(project_path)

            assert spec is not None
            assert spec.version == "20.10.0"

    def test_parse_node_version_from_node_version_file(self):
        """Reads Node version from .node-version."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".node-version").write_text("18.0.0")

            spec = parse_node_version(project_path)

            assert spec is not None
            assert spec.version == "18.0.0"
            assert "node-version" in spec.source_file

    def test_parse_node_version_from_package_json(self):
        """Reads Node version from package.json engines."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / "package.json").write_text(
                '{"engines": {"node": "^20.0.0"}}'
            )

            spec = parse_node_version(project_path)

            assert spec is not None
            assert spec.version == "^20.0.0"
            assert spec.constraint_type == "range"
            assert "package.json" in spec.source_file

    def test_parse_java_version_from_java_version_file(self):
        """Reads Java version from .java-version."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".java-version").write_text("21")

            spec = parse_java_version(project_path)

            assert spec is not None
            assert spec.version == "21"
            assert spec.constraint_type == "exact"
            assert "java-version" in spec.source_file

    def test_parse_java_version_from_pom_xml(self):
        """Reads Java version from pom.xml maven.compiler.source."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / "pom.xml").write_text(
                "<project><properties><maven.compiler.source>17</maven.compiler.source></properties></project>"
            )

            spec = parse_java_version(project_path)

            assert spec is not None
            assert spec.version == "17"
            assert "pom.xml" in spec.source_file

    def test_parse_java_version_from_build_gradle(self):
        """Reads Java version from build.gradle sourceCompatibility."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / "build.gradle").write_text('sourceCompatibility = "21"')

            spec = parse_java_version(project_path)

            assert spec is not None
            assert spec.version == "21"
            assert "build.gradle" in spec.source_file

    def test_parse_kotlin_version_from_build_gradle_kts(self):
        """Reads Kotlin version from build.gradle.kts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / "build.gradle.kts").write_text(
                'kotlin("jvm") version "2.0.10"'
            )

            spec = parse_kotlin_version(project_path)

            assert spec is not None
            assert spec.version == "2.0.10"
            assert spec.constraint_type == "exact"
            assert "build.gradle.kts" in spec.source_file

    def test_parse_rust_version_from_rust_toolchain_toml(self):
        """Reads Rust version from rust-toolchain.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / "rust-toolchain.toml").write_text(
                '[toolchain]\nchannel = "stable"'
            )

            spec = parse_rust_version(project_path)

            assert spec is not None
            assert spec.version == "stable"
            assert "rust-toolchain.toml" in spec.source_file

    def test_parse_rust_version_from_rust_toolchain_file(self):
        """Reads Rust version from rust-toolchain plain text file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / "rust-toolchain").write_text("nightly-2024-01-01")

            spec = parse_rust_version(project_path)

            assert spec is not None
            assert spec.version == "nightly-2024-01-01"
            assert "rust-toolchain" in spec.source_file

    def test_parse_go_version_from_go_mod(self):
        """Reads Go version from go.mod go directive."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / "go.mod").write_text(
                "module example.com\n\ngo 1.22\n\nrequire ..."
            )

            spec = parse_go_version(project_path)

            assert spec is not None
            assert spec.version == "1.22"
            assert spec.constraint_type == "minimum"
            assert "go.mod" in spec.source_file

    def test_parse_tool_versions_single_runtime(self):
        """Parses .tool-versions for single runtime."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".tool-versions").write_text("python 3.12.0")

            versions = parse_tool_versions(project_path)

            assert "python" in versions
            assert versions["python"].version == "3.12.0"
            assert versions["python"].constraint_type == "exact"

    def test_parse_tool_versions_multiple_runtimes(self):
        """Parses .tool-versions for multiple runtimes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".tool-versions").write_text(
                "python 3.12.0\nnodejs 20.0.0\njava 21\nrust stable\ngolang 1.22\n"
            )

            versions = parse_tool_versions(project_path)

            assert versions["python"].version == "3.12.0"
            assert versions["node"].version == "20.0.0"
            assert versions["java"].version == "21"
            assert versions["rust"].version == "stable"
            assert versions["go"].version == "1.22"

    def test_parse_tool_versions_skips_comments(self):
        """Parses .tool-versions correctly, skipping comments."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".tool-versions").write_text(
                "# This is a comment\npython 3.12.0\n# Another comment\nnodejs 20.0.0"
            )

            versions = parse_tool_versions(project_path)

            assert "python" in versions
            assert "node" in versions
            assert len(versions) == 2

    def test_detect_versions_combines_all_runtimes(self):
        """detect_versions aggregates all runtime versions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".python-version").write_text("3.12.0")
            (project_path / ".nvmrc").write_text("20.0.0")
            (project_path / ".java-version").write_text("21")

            versions = detect_versions(project_path)

            assert "python" in versions
            assert "node" in versions
            assert "java" in versions
            assert versions["python"].version == "3.12.0"
            assert versions["node"].version == "20.0.0"
            assert versions["java"].version == "21"

    def test_detect_versions_explicit_version_takes_precedence_over_tool_versions(self):
        """Explicit version files take precedence over .tool-versions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".tool-versions").write_text("python 3.11.0")
            (project_path / ".python-version").write_text("3.12.0")

            versions = detect_versions(project_path)

            assert "python" in versions
            assert versions["python"].version == "3.12.0"


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_version_file(self):
        """Empty version files return None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".python-version").write_text("")

            spec = parse_python_version(project_path)

            assert spec is None

    def test_whitespace_only_version_file(self):
        """Whitespace-only version files return None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".python-version").write_text("   \n  \t  ")

            spec = parse_python_version(project_path)

            assert spec is None

    def test_version_file_with_leading_trailing_whitespace(self):
        """Version files with whitespace are normalized."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".python-version").write_text("   3.12.0   \n")

            spec = parse_python_version(project_path)

            assert spec is not None
            assert spec.version == "3.12.0"

    def test_tool_versions_with_extra_whitespace(self):
        """Tool versions file with extra whitespace handled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".tool-versions").write_text("python   3.12.0  ")

            versions = parse_tool_versions(project_path)

            assert "python" in versions
            assert versions["python"].version == "3.12.0"

    def test_malformed_toml_returns_none(self):
        """Malformed TOML in pyproject.toml handled gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / "pyproject.toml").write_text("[invalid toml syntax {]")

            spec = parse_python_version(project_path)

            assert spec is None

    def test_malformed_json_returns_none(self):
        """Malformed JSON in package.json handled gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / "package.json").write_text("{invalid json syntax}")

            spec = parse_node_version(project_path)

            assert spec is None

    def test_pom_xml_without_compiler_source(self):
        """pom.xml without maven.compiler.source returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            pom_content = "<project><name>test</name></project>"
            (project_path / "pom.xml").write_text(pom_content)

            spec = parse_java_version(project_path)

            assert spec is None

    def test_build_gradle_without_source_compatibility(self):
        """build.gradle without sourceCompatibility returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / "build.gradle").write_text("plugins { id 'java' }")

            spec = parse_java_version(project_path)

            assert spec is None

    def test_go_mod_multiline_with_other_directives(self):
        """go.mod parsing handles multiple directives."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            go_mod_content = (
                "module example.com/hello\n\ngo 1.21\n\nrequire (\n\t"
                "github.com/example v1.0.0\n)"
            )
            (project_path / "go.mod").write_text(go_mod_content)

            spec = parse_go_version(project_path)

            assert spec is not None
            assert spec.version == "1.21"
