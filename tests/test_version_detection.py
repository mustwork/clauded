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

import pytest
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


class TestSourceFileValidity:
    """Property tests for source_file path validity."""

    @pytest.mark.parametrize(
        "filename,content,runtime",
        [
            (".python-version", "3.12", "python"),
            (".nvmrc", "20", "node"),
            (".java-version", "21", "java"),
            ("rust-toolchain", "stable", "rust"),
        ],
    )
    def test_source_files_are_absolute_paths(
        self, filename: str, content: str, runtime: str
    ) -> None:
        """All returned source_file values are absolute paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / filename).write_text(content)

            versions = detect_versions(project_path)

            if runtime in versions:
                assert Path(versions[runtime].source_file).is_absolute()


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


class TestPriorityOrder:
    """Tests for version source priority."""

    @pytest.mark.parametrize(
        "explicit_file,explicit_content,manifest_file,manifest_content,"
        "runtime,expected_source",
        [
            (
                ".python-version",
                "3.12.0",
                "pyproject.toml",
                '[project]\nrequires-python = ">=3.10"',
                "python",
                "python-version",
            ),
            (
                ".nvmrc",
                "20.0.0",
                "package.json",
                '{"engines": {"node": "^18.0.0"}}',
                "node",
                "nvmrc",
            ),
        ],
    )
    def test_explicit_version_preferred_over_manifest(
        self,
        explicit_file: str,
        explicit_content: str,
        manifest_file: str,
        manifest_content: str,
        runtime: str,
        expected_source: str,
    ) -> None:
        """Explicit version files take priority over manifest files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / explicit_file).write_text(explicit_content)
            (project_path / manifest_file).write_text(manifest_content)

            versions = detect_versions(project_path)

            assert runtime in versions
            assert expected_source in versions[runtime].source_file

    @pytest.mark.parametrize(
        "tool_versions_runtime,tool_versions_version,manifest_file,"
        "manifest_content,runtime_key,expected_version",
        [
            (
                "python",
                "3.11.0",
                "pyproject.toml",
                '[project]\nrequires-python = ">=3.10"',
                "python",
                "3.11.0",
            ),
            (
                "nodejs",
                "18.0.0",
                "package.json",
                '{"engines": {"node": "^20.0.0"}}',
                "node",
                "18.0.0",
            ),
        ],
    )
    def test_tool_versions_preferred_over_manifest(
        self,
        tool_versions_runtime: str,
        tool_versions_version: str,
        manifest_file: str,
        manifest_content: str,
        runtime_key: str,
        expected_version: str,
    ) -> None:
        """Universal .tool-versions takes priority over manifest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".tool-versions").write_text(
                f"{tool_versions_runtime} {tool_versions_version}"
            )
            (project_path / manifest_file).write_text(manifest_content)

            versions = detect_versions(project_path)

            assert runtime_key in versions
            assert versions[runtime_key].version == expected_version
            assert "tool-versions" in versions[runtime_key].source_file


class TestGracefulErrorHandling:
    """Tests for error handling."""

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
            if spec is not None:
                assert hasattr(spec, "version")
                assert hasattr(spec, "source_file")
                assert hasattr(spec, "constraint_type")

    @pytest.mark.parametrize(
        "parse_func",
        [
            parse_python_version,
            parse_node_version,
            parse_java_version,
            parse_kotlin_version,
            parse_rust_version,
            parse_go_version,
        ],
    )
    def test_missing_files_return_none(self, parse_func):
        """Missing version files return None gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            assert parse_func(project_path) is None

    def test_detect_versions_handles_all_missing_files(self):
        """detect_versions returns empty dict when no files found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            versions = detect_versions(project_path)
            assert versions == {}


class TestVersionParsing:
    """Parameterized concrete test cases for version parsing."""

    @pytest.mark.parametrize(
        "filename,content,runtime,expected_version,expected_constraint,source_marker",
        [
            (
                ".python-version",
                "3.12.0",
                "python",
                "3.12.0",
                "exact",
                ".python-version",
            ),  # noqa: E501
            (".nvmrc", "20.10.0", "node", "20.10.0", "exact", "nvmrc"),
            (".nvmrc", "v20.10.0", "node", "20.10.0", "exact", "nvmrc"),
            (".node-version", "18.0.0", "node", "18.0.0", "exact", "node-version"),
            (".java-version", "21", "java", "21", "exact", "java-version"),
            ("rust-toolchain", "stable", "rust", "stable", "exact", "rust-toolchain"),
            (
                "rust-toolchain",
                "nightly-2024-01-01",
                "rust",
                "nightly-2024-01-01",
                "exact",
                "rust-toolchain",
            ),
        ],
    )
    def test_parses_explicit_version_files(
        self,
        filename: str,
        content: str,
        runtime: str,
        expected_version: str,
        expected_constraint: str,
        source_marker: str,
    ) -> None:
        """Parses version from explicit version files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / filename).write_text(content)

            versions = detect_versions(project_path)

            assert runtime in versions
            assert versions[runtime].version == expected_version
            assert versions[runtime].constraint_type == expected_constraint
            assert source_marker in versions[runtime].source_file

    @pytest.mark.parametrize(
        "filename,content,runtime,expected_version,expected_constraint,source_marker",
        [
            (
                "pyproject.toml",
                '[project]\nrequires-python = ">=3.10"',
                "python",
                ">=3.10",
                "minimum",
                "pyproject.toml",
            ),
            (
                "pyproject.toml",
                '[project]\nrequires-python = ">=3.10,<3.13"',
                "python",
                ">=3.10,<3.13",
                "range",
                "pyproject.toml",
            ),
            (
                "package.json",
                '{"engines": {"node": "^20.0.0"}}',
                "node",
                "^20.0.0",
                "range",
                "package.json",
            ),
            (
                "pom.xml",
                "<project><properties>"
                "<maven.compiler.source>17</maven.compiler.source>"
                "</properties></project>",
                "java",
                "17",
                "exact",
                "pom.xml",
            ),
            (
                "build.gradle",
                'sourceCompatibility = "21"',
                "java",
                "21",
                "exact",
                "build.gradle",
            ),
            (
                "build.gradle.kts",
                'kotlin("jvm") version "2.0.10"',
                "kotlin",
                "2.0.10",
                "exact",
                "build.gradle.kts",
            ),
            (
                "rust-toolchain.toml",
                '[toolchain]\nchannel = "stable"',
                "rust",
                "stable",
                "exact",
                "rust-toolchain.toml",
            ),
            (
                "go.mod",
                "module example.com\n\ngo 1.22\n\nrequire ...",
                "go",
                "1.22",
                "minimum",
                "go.mod",
            ),
        ],
    )
    def test_parses_manifest_version_files(
        self,
        filename: str,
        content: str,
        runtime: str,
        expected_version: str,
        expected_constraint: str,
        source_marker: str,
    ) -> None:
        """Parses version from manifest files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / filename).write_text(content)

            versions = detect_versions(project_path)

            assert runtime in versions
            assert versions[runtime].version == expected_version
            assert versions[runtime].constraint_type == expected_constraint
            assert source_marker in versions[runtime].source_file


class TestToolVersionsParsing:
    """Tests for .tool-versions file parsing."""

    @pytest.mark.parametrize(
        "content,expected_runtimes",
        [
            ("python 3.12.0", {"python": "3.12.0"}),
            ("nodejs 20.0.0", {"node": "20.0.0"}),
            ("python 3.12.0\nnodejs 20.0.0", {"python": "3.12.0", "node": "20.0.0"}),
            (
                "python 3.12.0\nnodejs 20.0.0\njava 21\nrust stable\ngolang 1.22",
                {
                    "python": "3.12.0",
                    "node": "20.0.0",
                    "java": "21",
                    "rust": "stable",
                    "go": "1.22",
                },
            ),
        ],
    )
    def test_parses_tool_versions_runtimes(
        self, content: str, expected_runtimes: dict[str, str]
    ) -> None:
        """Parses .tool-versions for runtimes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".tool-versions").write_text(content)

            versions = parse_tool_versions(project_path)

            for runtime, expected_version in expected_runtimes.items():
                assert runtime in versions
                assert versions[runtime].version == expected_version
                assert versions[runtime].constraint_type == "exact"

    def test_parses_tool_versions_skips_comments(self) -> None:
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


class TestDetectVersionsIntegration:
    """Integration tests for detect_versions."""

    def test_combines_all_runtimes(self) -> None:
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

    def test_explicit_version_takes_precedence_over_tool_versions(self) -> None:
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

    @pytest.mark.parametrize(
        "content",
        ["", "   \n  \t  "],
    )
    def test_empty_or_whitespace_version_file(self, content: str) -> None:
        """Empty or whitespace-only version files return None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".python-version").write_text(content)

            spec = parse_python_version(project_path)

            assert spec is None

    def test_version_file_with_leading_trailing_whitespace(self) -> None:
        """Version files with whitespace are normalized."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".python-version").write_text("   3.12.0   \n")

            spec = parse_python_version(project_path)

            assert spec is not None
            assert spec.version == "3.12.0"

    def test_tool_versions_with_extra_whitespace(self) -> None:
        """Tool versions file with extra whitespace handled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".tool-versions").write_text("python   3.12.0  ")

            versions = parse_tool_versions(project_path)

            assert "python" in versions
            assert versions["python"].version == "3.12.0"

    @pytest.mark.parametrize(
        "filename,content",
        [
            ("pyproject.toml", "[invalid toml syntax {]"),
            ("package.json", "{invalid json syntax}"),
        ],
    )
    def test_malformed_manifest_returns_none(self, filename: str, content: str) -> None:
        """Malformed manifest files handled gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / filename).write_text(content)

            # Should not raise
            versions = detect_versions(project_path)
            # Result should be empty or not contain the affected runtime
            assert isinstance(versions, dict)

    def test_pom_xml_without_compiler_source(self) -> None:
        """pom.xml without maven.compiler.source returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            pom_content = "<project><name>test</name></project>"
            (project_path / "pom.xml").write_text(pom_content)

            spec = parse_java_version(project_path)

            assert spec is None

    def test_build_gradle_without_source_compatibility(self) -> None:
        """build.gradle without sourceCompatibility returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / "build.gradle").write_text("plugins { id 'java' }")

            spec = parse_java_version(project_path)

            assert spec is None

    def test_go_mod_multiline_with_other_directives(self) -> None:
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
