"""Specific test for Ktor detection from build.gradle.

SPEC-DETECT-002 fix validation.
"""

import tempfile
from pathlib import Path

from clauded.detect.framework import detect_frameworks_and_tools


def test_ktor_detection_from_build_gradle() -> None:
    """Test that Ktor is detected from build.gradle (FR-3 requirement)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        # Create build.gradle with Ktor dependency (from spec example)
        build_gradle = project_dir / "build.gradle"
        build_gradle.write_text(
            """
dependencies {
    implementation 'io.ktor:ktor-server-core:2.0.0'
}
"""
        )

        # Detect frameworks
        frameworks, _ = detect_frameworks_and_tools(project_dir)

        # Verify Ktor is detected
        ktor_items = [fw for fw in frameworks if fw.name == "ktor"]
        assert len(ktor_items) == 1
        assert ktor_items[0].confidence == "high"
        assert "build.gradle" in ktor_items[0].source_file
        assert "ktor-server-core" in ktor_items[0].source_evidence


def test_ktor_detection_multiple_artifacts() -> None:
    """Test that Ktor is detected from various artifact names."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        build_gradle = project_dir / "build.gradle"
        build_gradle.write_text(
            """
dependencies {
    implementation 'io.ktor:ktor-server-core:2.0.0'
    implementation 'io.ktor:ktor-server-netty:2.0.0'
}
"""
        )

        frameworks, _ = detect_frameworks_and_tools(project_dir)

        # Verify Ktor is detected (may appear multiple times, one per artifact)
        ktor_items = [fw for fw in frameworks if fw.name == "ktor"]
        assert len(ktor_items) >= 1
        assert all(item.name == "ktor" for item in ktor_items)


def test_ktor_detection_with_spring_boot() -> None:
    """Test that Ktor and Spring Boot are both detected when present."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        build_gradle = project_dir / "build.gradle"
        build_gradle.write_text(
            """
dependencies {
    implementation 'org.springframework.boot:spring-boot-starter-web:3.0.0'
    implementation 'io.ktor:ktor-server-core:2.0.0'
}
"""
        )

        frameworks, _ = detect_frameworks_and_tools(project_dir)

        # Verify both frameworks detected
        framework_names = [fw.name for fw in frameworks]
        assert "spring-boot" in framework_names
        assert "ktor" in framework_names
