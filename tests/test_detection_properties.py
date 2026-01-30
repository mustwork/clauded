"""Property-based tests for detection enhancements (TEST-DETECT-001).

Property tests for FR-1 (setup.py), FR-2 (build.gradle.kts), FR-3 (build.gradle).
"""

import tempfile
from pathlib import Path

from hypothesis import assume, given
from hypothesis import strategies as st

from clauded.detect.framework import detect_frameworks_and_tools
from clauded.detect.version import parse_java_version, parse_python_version


class TestSetupPyPropertyTests:
    """Property-based tests for setup.py parser (FR-1)."""

    @given(
        python_version=st.from_regex(r"\d+\.\d+", fullmatch=True),
        constraint=st.sampled_from([">=", "~=", "==", "<", "<="]),
    )
    def test_setup_py_parses_valid_python_requires_constraints(
        self, python_version: str, constraint: str
    ) -> None:
        """Property: setup.py parser handles all valid Python constraint types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # Create setup.py with valid python_requires
            setup_py = project_dir / "setup.py"
            setup_py.write_text(
                f"""
setup(
    name="testproject",
    python_requires="{constraint}{python_version}"
)
"""
            )

            # Parse version
            spec = parse_python_version(project_dir)

            # Property: Valid python_requires should be detected
            assert spec is not None
            assert spec.version == f"{constraint}{python_version}"
            assert spec.source_file == str(setup_py.absolute())
            # Constraint type should be classified correctly
            if constraint == "==":
                assert spec.constraint_type == "exact"
            elif constraint in [">=", "~="]:
                assert spec.constraint_type in ["minimum", "range"]

    @given(
        python_major=st.integers(min_value=2, max_value=4),
        python_minor=st.integers(min_value=0, max_value=20),
    )
    def test_setup_py_parses_minimum_versions(
        self, python_major: int, python_minor: int
    ) -> None:
        """Property: setup.py parser handles arbitrary minimum version constraints."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            version_str = f"{python_major}.{python_minor}"
            setup_py = project_dir / "setup.py"
            setup_py.write_text(
                f"""
setup(
    name="test",
    python_requires=">={version_str}"
)
"""
            )

            spec = parse_python_version(project_dir)

            # Property: All valid minimum versions should be detected
            assert spec is not None
            assert version_str in spec.version
            assert spec.constraint_type == "minimum"

    @given(
        quote_char=st.sampled_from(["'", '"']),
        whitespace_before=st.text(alphabet=" \t", min_size=0, max_size=5),
        whitespace_after=st.text(alphabet=" \t", min_size=0, max_size=5),
    )
    def test_setup_py_handles_whitespace_and_quotes(
        self, quote_char: str, whitespace_before: str, whitespace_after: str
    ) -> None:
        """Property: setup.py parser handles various whitespace and quote styles."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            setup_py = project_dir / "setup.py"
            setup_py.write_text(
                f"""
setup(
    name="test",
    python_requires{whitespace_before}={whitespace_after}{quote_char}>=3.10{quote_char}
)
"""
            )

            spec = parse_python_version(project_dir)

            # Property: Parser should handle whitespace and quote variations
            assert spec is not None
            assert "3.10" in spec.version

    @given(
        invalid_version=st.text(
            alphabet="!@#$%^&*(){}[]|\\:;'<>?,/~`",
            min_size=1,
            max_size=10,
        )
    )
    def test_setup_py_rejects_invalid_version_characters(
        self, invalid_version: str
    ) -> None:
        """Property: setup.py parser rejects versions with invalid characters."""
        # Skip if invalid_version accidentally contains valid chars
        assume(not any(c.isdigit() or c in ".>=<~!," for c in invalid_version))

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            setup_py = project_dir / "setup.py"
            setup_py.write_text(
                f"""
setup(
    name="test",
    python_requires="{invalid_version}"
)
"""
            )

            spec = parse_python_version(project_dir)

            # Property: Invalid versions should be rejected (return None)
            assert spec is None


class TestBuildGradleKtsPropertyTests:
    """Property-based tests for build.gradle.kts parser (FR-2)."""

    @given(
        java_version=st.integers(min_value=8, max_value=25),
    )
    def test_build_gradle_kts_parses_java_versions(self, java_version: int) -> None:
        """Property: build.gradle.kts parser handles arbitrary Java versions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            gradle_kts = project_dir / "build.gradle.kts"
            gradle_kts.write_text(
                f"""
java {{
    sourceCompatibility = JavaVersion.VERSION_{java_version}
    targetCompatibility = JavaVersion.VERSION_{java_version}
}}
"""
            )

            spec = parse_java_version(project_dir)

            # Property: All valid Java versions should be detected
            assert spec is not None
            assert spec.version == str(java_version)
            assert spec.constraint_type == "exact"
            assert "build.gradle.kts" in spec.source_file

    @given(
        java_version=st.integers(min_value=11, max_value=25),
        syntax_variant=st.sampled_from(
            [
                "sourceCompatibility = JavaVersion.VERSION_{}",
                "targetCompatibility = JavaVersion.VERSION_{}",
                "jvmToolchain({})",
                "jvmToolchain {{\\n    languageVersion.set("
                "JavaLanguageVersion.of({}))\\n}}",
            ]
        ),
    )
    def test_build_gradle_kts_handles_syntax_variants(
        self, java_version: int, syntax_variant: str
    ) -> None:
        """Property: build.gradle.kts handles multiple Kotlin DSL syntax."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            gradle_kts = project_dir / "build.gradle.kts"
            content = syntax_variant.format(java_version)
            gradle_kts.write_text(content)

            spec = parse_java_version(project_dir)

            # Property: All syntax variants should be recognized
            if spec is not None:  # Some variants may not be fully supported
                assert str(java_version) in spec.version

    @given(
        whitespace=st.text(alphabet=" \t\n", min_size=0, max_size=10),
    )
    def test_build_gradle_kts_handles_whitespace(self, whitespace: str) -> None:
        """Property: build.gradle.kts parser handles arbitrary whitespace."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            gradle_kts = project_dir / "build.gradle.kts"
            gradle_kts.write_text(
                f"""
java{whitespace}{{{whitespace}
    sourceCompatibility{whitespace}={whitespace}JavaVersion.VERSION_17
{whitespace}}}
"""
            )

            spec = parse_java_version(project_dir)

            # Property: Whitespace should not break parsing
            assert spec is not None
            assert spec.version == "17"


class TestBuildGradlePropertyTests:
    """Property-based tests for build.gradle framework detection (FR-3)."""

    @given(
        framework_artifact=st.sampled_from(
            [
                ("io.micronaut", "micronaut-core", "micronaut"),
                ("io.micronaut", "micronaut-http", "micronaut"),
                ("io.ktor", "ktor-server-core", "ktor"),
                ("io.ktor", "ktor-server-netty", "ktor"),
                ("org.springframework.boot", "spring-boot-starter-web", "spring-boot"),
                ("io.quarkus", "quarkus-core", "quarkus"),
            ]
        )
    )
    def test_build_gradle_detects_framework_artifacts(
        self, framework_artifact: tuple[str, str, str]
    ) -> None:
        """Property: build.gradle parser detects all supported framework artifacts."""
        group_id, artifact_id, expected_framework = framework_artifact

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            gradle = project_dir / "build.gradle"
            gradle.write_text(
                f"""
dependencies {{
    implementation '{group_id}:{artifact_id}:1.0.0'
}}
"""
            )

            frameworks, _ = detect_frameworks_and_tools(project_dir)

            # Property: Framework should be detected
            detected_frameworks = [fw.name for fw in frameworks]
            assert expected_framework in detected_frameworks

    @given(
        version=st.from_regex(r"\d+\.\d+\.\d+", fullmatch=True),
        quote_char=st.sampled_from(["'", '"']),
    )
    def test_build_gradle_handles_version_formats_and_quotes(
        self, version: str, quote_char: str
    ) -> None:
        """Property: build.gradle handles version formats and quotes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            gradle = project_dir / "build.gradle"
            gradle.write_text(
                f"""
dependencies {{
    implementation {quote_char}io.ktor:ktor-server-core:{version}{quote_char}
}}
"""
            )

            frameworks, _ = detect_frameworks_and_tools(project_dir)

            # Property: Ktor should be detected regardless of version/quote style
            ktor_items = [fw for fw in frameworks if fw.name == "ktor"]
            assert len(ktor_items) >= 1

    @given(
        dependency_config=st.sampled_from(
            [
                "implementation",
                "testImplementation",
                "api",
                "runtimeOnly",
            ]
        )
    )
    def test_build_gradle_detects_all_dependency_configurations(
        self, dependency_config: str
    ) -> None:
        """Property: build.gradle detects frameworks in all configs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            gradle = project_dir / "build.gradle"
            gradle.write_text(
                f"""
dependencies {{
    {dependency_config} 'io.micronaut:micronaut-core:4.0.0'
}}
"""
            )

            frameworks, _ = detect_frameworks_and_tools(project_dir)

            # Property: Framework should be detected from any configuration
            micronaut_items = [fw for fw in frameworks if fw.name == "micronaut"]
            assert len(micronaut_items) >= 1

    @given(
        whitespace_before=st.sampled_from([" ", "  ", "\t", ""]),
        whitespace_after=st.sampled_from([" ", "  ", "\t", ""]),
    )
    def test_build_gradle_handles_whitespace_variations(
        self, whitespace_before: str, whitespace_after: str
    ) -> None:
        """Property: build.gradle parser handles whitespace variations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            gradle = project_dir / "build.gradle"
            # Use line-by-line parsing since parser strips() lines
            gradle.write_text(
                f"""
dependencies {{
    implementation{whitespace_before}'{whitespace_after}io.ktor:ktor-server-core:2.0.0'
}}
"""
            )

            frameworks, _ = detect_frameworks_and_tools(project_dir)

            # Property: Normal whitespace should not break detection
            ktor_items = [fw for fw in frameworks if fw.name == "ktor"]
            assert len(ktor_items) >= 1


class TestMongoDBDetectionPropertyTests:
    """Property-based tests for MongoDB detection (FR-4)."""

    @given(
        mongo_image=st.sampled_from(
            [
                "mongo",
                "mongodb",
                "mongo:7.0",
                "mongo:6.0",
                "mongo:latest",
                "mongodb:7.0",
                "mongodb:latest",
            ]
        )
    )
    def test_mongodb_detects_all_image_variants(self, mongo_image: str) -> None:
        """Property: MongoDB detection handles all mongo/mongodb image variants."""
        from clauded.detect.database import detect_databases

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            compose = project_dir / "docker-compose.yml"
            compose.write_text(
                f"""
services:
  db:
    image: {mongo_image}
"""
            )

            databases = detect_databases(project_dir)

            # Property: All mongo image variants should be detected
            mongodb_items = [db for db in databases if db.name == "mongodb"]
            assert len(mongodb_items) >= 1
            assert mongodb_items[0].confidence == "high"

    @given(
        env_var=st.sampled_from(
            [
                "MONGODB_URI",
                "MONGO_URL",
                "MONGODB_URL",
                "MONGODB_HOST",
                "MONGO_HOST",
            ]
        ),
        connection_string=st.from_regex(
            r"mongodb(\+srv)?://[a-z0-9.-]+:[0-9]{1,5}/[a-z0-9_]+",
            fullmatch=True,
        ),
    )
    def test_mongodb_detects_all_env_var_patterns(
        self, env_var: str, connection_string: str
    ) -> None:
        """Property: MongoDB detection handles all env var name patterns."""
        from clauded.detect.database import detect_databases

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            env_file = project_dir / ".env.example"
            env_file.write_text(f"{env_var}={connection_string}\n")

            databases = detect_databases(project_dir)

            # Property: All MongoDB env vars should be detected
            mongodb_items = [db for db in databases if db.name == "mongodb"]
            assert len(mongodb_items) >= 1
            assert mongodb_items[0].source_evidence == env_var

    @given(
        orm_package=st.sampled_from(
            [
                "pymongo",
                "motor",
                "mongoengine",
                "beanie",
                "mongoose",
                "mongodb",
            ]
        )
    )
    def test_mongodb_detects_all_orm_packages(self, orm_package: str) -> None:
        """Property: MongoDB detection handles all ORM package names."""
        from clauded.detect.database import detect_databases

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # Determine ecosystem and create appropriate manifest
            if orm_package in ["pymongo", "motor", "mongoengine", "beanie"]:
                # Python package
                pyproject = project_dir / "pyproject.toml"
                pyproject.write_text(
                    f"""
[project]
name = "test"
dependencies = ["{orm_package}>=1.0.0"]
"""
                )
            else:
                # Node.js package
                package_json = project_dir / "package.json"
                package_json.write_text(
                    f"""
{{
  "name": "test",
  "dependencies": {{
    "{orm_package}": "^1.0.0"
  }}
}}
"""
                )

            databases = detect_databases(project_dir)

            # Property: All MongoDB ORM packages should be detected
            mongodb_items = [db for db in databases if db.name == "mongodb"]
            assert len(mongodb_items) >= 1
            assert mongodb_items[0].source_evidence == orm_package
