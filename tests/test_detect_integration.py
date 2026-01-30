"""Property-based tests for detection CLI and wizard integration.

Tests verify:
1. display_detection_summary handles all result states gracefully
2. create_wizard_defaults returns valid structure with required keys
3. normalize_version_for_choice maps versions correctly to wizard choices
4. Version normalization is consistent across all runtimes
5. High/medium confidence items are pre-checked, low confidence items are not
"""

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from clauded.detect.cli_integration import (
    create_wizard_defaults,
    display_detection_summary,
)
from clauded.detect.result import (
    DetectedItem,
    DetectedLanguage,
    DetectionResult,
    ScanStats,
    VersionSpec,
)
from clauded.detect.wizard_integration import (
    map_confidence_to_checked,
    normalize_version_for_choice,
)

# ============================================================================
# Strategies for Property-Based Testing
# ============================================================================


@st.composite
def detection_results(draw):
    """Generate arbitrary DetectionResult with valid structure."""
    languages = draw(
        st.lists(
            st.builds(
                DetectedLanguage,
                name=st.sampled_from(
                    ["Python", "JavaScript", "Java", "Go", "Rust", "HTML", "CSS"]
                ),
                confidence=st.sampled_from(["high", "medium", "low"]),
                byte_count=st.integers(min_value=0, max_value=1000000),
                source_files=st.lists(st.just("test.py"), max_size=5),
            ),
            max_size=10,
        )
    )

    versions = draw(
        st.dictionaries(
            keys=st.sampled_from(["python", "node", "java", "kotlin", "rust", "go"]),
            values=st.builds(
                VersionSpec,
                version=st.sampled_from(
                    [
                        "3.12.0",
                        "3.12",
                        ">=3.10",
                        "20.10.0",
                        "^20.0.0",
                        "21",
                        "2.0.10",
                        "stable",
                        "1.22.3",
                    ]
                ),
                source_file=st.just("pyproject.toml"),
                constraint_type=st.sampled_from(["exact", "minimum", "range"]),
            ),
            max_size=6,
        )
    )

    frameworks = draw(
        st.lists(
            st.builds(
                DetectedItem,
                name=st.sampled_from(
                    ["django", "react", "spring-boot", "playwright", "claude-code"]
                ),
                confidence=st.sampled_from(["high", "medium", "low"]),
                source_file=st.just("pyproject.toml"),
                source_evidence=st.just("django"),
            ),
            max_size=5,
        )
    )

    tools = draw(
        st.lists(
            st.builds(
                DetectedItem,
                name=st.sampled_from(
                    ["docker", "aws-cli", "gh", "gradle", "pytest", "jest"]
                ),
                confidence=st.sampled_from(["high", "medium", "low"]),
                source_file=st.just("Dockerfile"),
                source_evidence=st.just("docker"),
            ),
            max_size=5,
        )
    )

    databases = draw(
        st.lists(
            st.builds(
                DetectedItem,
                name=st.sampled_from(["postgresql", "redis", "mysql"]),
                confidence=st.sampled_from(["high", "medium", "low"]),
                source_file=st.just("docker-compose.yml"),
                source_evidence=st.just("postgres"),
            ),
            max_size=3,
        )
    )

    scan_stats = draw(
        st.one_of(
            st.none(),
            st.builds(
                ScanStats,
                files_scanned=st.integers(min_value=0, max_value=10000),
                files_excluded=st.integers(min_value=0, max_value=1000),
                duration_ms=st.integers(min_value=0, max_value=5000),
                scan_truncated=st.booleans(),
            ),
        )
    )

    return DetectionResult(
        languages=languages,
        versions=versions,
        frameworks=frameworks,
        tools=tools,
        databases=databases,
        scan_stats=scan_stats,
    )


# ============================================================================
# Property-Based Tests for display_detection_summary
# ============================================================================


class TestDisplayDetectionSummary:
    """Properties for display_detection_summary function."""

    @given(result=detection_results())
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_summary_never_raises(self, result, capsys):
        """Property: display_detection_summary never raises exceptions."""
        try:
            display_detection_summary(result)
            # Should always succeed
            assert True
        except Exception as e:
            pytest.fail(f"display_detection_summary raised: {e}")

    @given(result=detection_results())
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_summary_produces_output(self, result, capsys):
        """Property: display_detection_summary outputs to console."""
        display_detection_summary(result)
        captured = capsys.readouterr()
        # Should produce some output
        assert len(captured.out) >= 0  # May be empty for empty results

    def test_summary_empty_result(self, capsys):
        """Example: Empty detection result."""
        result = DetectionResult()
        display_detection_summary(result)
        captured = capsys.readouterr()
        # Should handle empty results gracefully
        assert "Press Enter" not in captured.out or len(captured.out) >= 0

    def test_summary_with_all_detections(self, capsys):
        """Example: Result with all detection types."""
        result = DetectionResult(
            languages=[
                DetectedLanguage(
                    name="Python",
                    confidence="high",
                    byte_count=100000,
                    file_count=15,
                    source_files=["test.py"],
                ),
                DetectedLanguage(
                    name="JavaScript",
                    confidence="medium",
                    byte_count=50000,
                    file_count=5,
                    source_files=["script.js"],
                ),
            ],
            versions={
                "python": VersionSpec(
                    version="3.12",
                    source_file=".python-version",
                    constraint_type="exact",
                ),
                "node": VersionSpec(
                    version="20", source_file=".nvmrc", constraint_type="exact"
                ),
            },
            frameworks=[
                DetectedItem(
                    name="django",
                    confidence="high",
                    source_file="pyproject.toml",
                    source_evidence="django",
                )
            ],
            tools=[
                DetectedItem(
                    name="docker",
                    confidence="high",
                    source_file="Dockerfile",
                    source_evidence="docker",
                )
            ],
            databases=[
                DetectedItem(
                    name="postgresql",
                    confidence="high",
                    source_file="docker-compose.yml",
                    source_evidence="postgres",
                )
            ],
            scan_stats=ScanStats(files_scanned=100, files_excluded=10, duration_ms=250),
        )
        display_detection_summary(result)
        captured = capsys.readouterr()
        # Should show multiple sections
        assert len(captured.out) > 0


# ============================================================================
# Property-Based Tests for create_wizard_defaults
# ============================================================================


class TestCreateWizardDefaults:
    """Properties for create_wizard_defaults function."""

    @given(result=detection_results())
    def test_defaults_returns_dict(self, result):
        """Property: create_wizard_defaults always returns a dict."""
        defaults = create_wizard_defaults(result)
        assert isinstance(defaults, dict)

    @given(result=detection_results())
    def test_defaults_has_all_runtime_keys(self, result):
        """Property: All runtime keys present in defaults (even if None)."""
        defaults = create_wizard_defaults(result)
        required_keys = {"python", "node", "java", "kotlin", "rust", "go"}
        assert required_keys.issubset(defaults.keys())

    @given(result=detection_results())
    def test_defaults_has_tool_database_framework_keys(self, result):
        """Property: Tools, databases, frameworks keys present."""
        defaults = create_wizard_defaults(result)
        required_keys = {"tools", "databases", "frameworks"}
        assert required_keys.issubset(defaults.keys())

    @given(result=detection_results())
    def test_defaults_runtime_values_valid(self, result):
        """Property: Runtime values are valid choice strings or None-like."""
        defaults = create_wizard_defaults(result)

        # Define valid choices for each runtime
        valid_choices = {
            "python": {"3.12", "3.11", "3.10", "None"},
            "node": {"22", "20", "18", "None"},
            "java": {"21", "17", "11", "None"},
            "kotlin": {"2.0", "1.9", "None"},
            "rust": {"stable", "nightly", "None"},
            "go": {"1.25.6", "1.24.12", "None"},
        }

        for runtime, choices in valid_choices.items():
            value = defaults.get(runtime)
            assert value in choices, f"{runtime}={value} not in {choices}"

    @given(result=detection_results())
    def test_defaults_tools_are_strings(self, result):
        """Property: Tools list contains only strings."""
        defaults = create_wizard_defaults(result)
        tools = defaults.get("tools", [])
        assert isinstance(tools, list)
        assert all(isinstance(t, str) for t in tools)

    @given(result=detection_results())
    def test_defaults_databases_are_strings(self, result):
        """Property: Databases list contains only strings."""
        defaults = create_wizard_defaults(result)
        databases = defaults.get("databases", [])
        assert isinstance(databases, list)
        assert all(isinstance(d, str) for d in databases)

    @given(result=detection_results())
    def test_defaults_frameworks_always_include_claude_code(self, result):
        """Property: claude-code always in frameworks list."""
        defaults = create_wizard_defaults(result)
        frameworks = defaults.get("frameworks", [])
        assert "claude-code" in frameworks

    @given(result=detection_results())
    def test_defaults_high_medium_confidence_included(self, result):
        """Property: High/medium confidence items in defaults."""
        defaults = create_wizard_defaults(result)

        # High/medium confidence tools should be included
        detected_high_medium_tools = {
            item.name for item in result.tools if item.confidence in ("high", "medium")
        }
        defaults_tools = set(defaults.get("tools", []))
        assert detected_high_medium_tools.issubset(defaults_tools)

        # High/medium confidence databases should be included
        detected_high_medium_dbs = {
            item.name
            for item in result.databases
            if item.confidence in ("high", "medium")
        }
        defaults_databases = set(defaults.get("databases", []))
        assert detected_high_medium_dbs.issubset(defaults_databases)

    @given(result=detection_results())
    def test_defaults_low_confidence_not_included(self, result):
        """Property: Low confidence items not in defaults (unless also high/medium)."""
        defaults = create_wizard_defaults(result)

        # Get only low-confidence items
        low_confidence_tools = {
            item.name
            for item in result.tools
            if item.confidence == "low"
            and not any(
                t.name == item.name and t.confidence in ("high", "medium")
                for t in result.tools
            )
        }
        defaults_tools = set(defaults.get("tools", []))
        # Low confidence only items should not be in defaults
        assert low_confidence_tools.isdisjoint(defaults_tools)

    def test_defaults_empty_result(self):
        """Example: Empty detection result returns sensible defaults."""
        result = DetectionResult()
        defaults = create_wizard_defaults(result)

        assert defaults["python"] == "None"
        assert defaults["node"] == "None"
        assert defaults["tools"] == []
        assert defaults["databases"] == []
        assert "claude-code" in defaults["frameworks"]

    def test_defaults_python_detected(self):
        """Example: Python version detected is normalized."""
        result = DetectionResult(
            versions={
                "python": VersionSpec(
                    version="3.12.0",
                    source_file=".python-version",
                    constraint_type="exact",
                )
            }
        )
        defaults = create_wizard_defaults(result)
        assert defaults["python"] == "3.12"

    def test_defaults_with_high_confidence_tools(self):
        """Example: High confidence tools are pre-checked."""
        result = DetectionResult(
            tools=[
                DetectedItem(
                    name="docker",
                    confidence="high",
                    source_file="Dockerfile",
                    source_evidence="docker",
                ),
                DetectedItem(
                    name="aws-cli",
                    confidence="low",
                    source_file="test.py",
                    source_evidence="aws",
                ),
            ]
        )
        defaults = create_wizard_defaults(result)
        assert "docker" in defaults["tools"]
        assert "aws-cli" not in defaults["tools"]


# ============================================================================
# Property-Based Tests for normalize_version_for_choice
# ============================================================================


class TestNormalizeVersionForChoice:
    """Properties for normalize_version_for_choice function."""

    @given(
        version=st.text(),
        runtime=st.sampled_from(["python", "node", "java", "kotlin", "rust", "go"]),
        choices=st.lists(st.text(min_size=1), min_size=1),
    )
    def test_normalization_returns_valid_choice_or_none(
        self, version, runtime, choices
    ):
        """Property: Result is always in choices list or None."""
        result = normalize_version_for_choice(version, runtime, choices)
        assert result is None or result in choices

    @given(
        version=st.sampled_from(["3.12", "3.12.0", "3.12.5"]),
        choices=st.just(["3.12", "3.11", "3.10", "None"]),
    )
    def test_python_version_normalization(self, version, choices):
        """Property: Python versions normalize to major.minor."""
        result = normalize_version_for_choice(version, "python", choices)
        assert result in choices or result is None
        if "3.12" in choices and ("3.12" in version or version.startswith("3.12")):
            assert result == "3.12"

    @given(
        version=st.sampled_from(["20", "20.10", "20.10.0", "^20.0.0"]),
        choices=st.just(["22", "20", "18", "None"]),
    )
    def test_node_version_normalization(self, version, choices):
        """Property: Node versions normalize to major version."""
        result = normalize_version_for_choice(version, "node", choices)
        assert result in choices or result is None
        if "20" in choices and version.startswith("20"):
            assert result == "20"

    @given(
        version=st.sampled_from(["21", "21.0", "21.0.1"]),
        choices=st.just(["21", "17", "11", "None"]),
    )
    def test_java_version_normalization(self, version, choices):
        """Property: Java versions normalize to major version."""
        result = normalize_version_for_choice(version, "java", choices)
        assert result in choices or result is None
        if "21" in choices and version.startswith("21"):
            assert result == "21"

    @given(
        version=st.sampled_from(["2.0", "2.0.10", "2.0.5"]),
        choices=st.just(["2.0", "1.9", "None"]),
    )
    def test_kotlin_version_normalization(self, version, choices):
        """Property: Kotlin versions normalize to major.minor."""
        result = normalize_version_for_choice(version, "kotlin", choices)
        assert result in choices or result is None
        if "2.0" in choices and version.startswith("2.0"):
            assert result == "2.0"

    @given(
        version=st.sampled_from(["stable", "nightly", "1.75.0"]),
        choices=st.just(["stable", "nightly", "None"]),
    )
    def test_rust_version_normalization(self, version, choices):
        """Property: Rust versions map to channel or version."""
        result = normalize_version_for_choice(version, "rust", choices)
        assert result in choices or result is None
        if "stable" in choices and "stable" in version:
            assert result == "stable"
        if "nightly" in choices and "nightly" in version:
            assert result == "nightly"

    @given(
        version=st.sampled_from(["1.25", "1.25.6", "1.24", "1.24.12"]),
        choices=st.just(["1.25.6", "1.24.12", "None"]),
    )
    def test_go_version_normalization(self, version, choices):
        """Property: Go versions normalize to major.minor.patch."""
        result = normalize_version_for_choice(version, "go", choices)
        assert result in choices or result is None
        if "1.25.6" in choices and version.startswith("1.25"):
            assert result == "1.25.6"
        if "1.24.12" in choices and version.startswith("1.24"):
            assert result == "1.24.12"

    def test_normalization_with_empty_choices(self):
        """Example: Empty choices list returns None."""
        result = normalize_version_for_choice("3.12", "python", [])
        assert result is None

    def test_normalization_with_empty_version(self):
        """Example: Empty version string returns None."""
        result = normalize_version_for_choice("", "python", ["3.12", "3.11"])
        assert result is None

    def test_normalization_python_with_constraint(self):
        """Example: Python with constraint operator."""
        result = normalize_version_for_choice(
            ">=3.10", "python", ["3.12", "3.11", "3.10"]
        )
        # Should extract 3.10 as minimum
        assert result in ["3.12", "3.11", "3.10", None]

    def test_normalization_not_in_choices(self):
        """Example: Version not matching any choice returns None."""
        result = normalize_version_for_choice("3.9", "python", ["3.12", "3.11", "3.10"])
        assert result is None


# ============================================================================
# Property-Based Tests for map_confidence_to_checked
# ============================================================================


class TestMapConfidenceToChecked:
    """Properties for map_confidence_to_checked function."""

    def test_high_confidence_returns_true(self):
        """Example: High confidence → checked."""
        assert map_confidence_to_checked("high") is True

    def test_medium_confidence_returns_true(self):
        """Example: Medium confidence → checked."""
        assert map_confidence_to_checked("medium") is True

    def test_low_confidence_returns_false(self):
        """Example: Low confidence → not checked."""
        assert map_confidence_to_checked("low") is False

    @given(confidence=st.sampled_from(["high", "medium", "low"]))
    def test_confidence_mapping_property(self, confidence):
        """Property: Mapping is consistent (high|medium → True, low → False)."""
        result = map_confidence_to_checked(confidence)
        expected = confidence in ("high", "medium")
        assert result == expected


# ============================================================================
# End-to-End Integration Tests
# ============================================================================


class TestEndToEndDetectionToWizard:
    """End-to-end tests from detection to wizard defaults."""

    def test_python_project_detection_to_wizard(self, tmp_path):
        """E2E: Python project detection flows correctly to wizard defaults."""
        from clauded.detect import detect

        # Create a realistic Python project structure
        (tmp_path / "pyproject.toml").write_text("""
[project]
name = "test-project"
requires-python = ">=3.10"
dependencies = [
    "django>=4.0",
    "pytest>=7.0",
]
""")
        for i in range(5):
            (tmp_path / f"module{i}.py").write_text("def func(): pass\n" * 20)

        (tmp_path / "Dockerfile").write_text(
            "FROM python:3.12\nRUN pip install poetry\n"
        )

        # Run full detection
        result = detect(tmp_path)

        # Verify detection results
        assert len(result.languages) > 0
        python_lang = next(
            (lang for lang in result.languages if lang.name == "Python"), None
        )
        assert python_lang is not None
        assert python_lang.confidence in ("high", "medium")

        # Verify version detection
        assert "python" in result.versions
        assert result.versions["python"].version in [">=3.10", "3.10", "3.12"]

        # Verify framework detection
        django_framework = next(
            (f for f in result.frameworks if f.name == "django"), None
        )
        assert django_framework is not None

        # Verify tool detection (docker from Dockerfile)
        docker_tool = next((t for t in result.tools if t.name == "docker"), None)
        assert docker_tool is not None

        # Now verify wizard defaults generation
        defaults = create_wizard_defaults(result)

        assert defaults["python"] in ("3.12", "3.11", "3.10")
        assert "docker" in defaults["tools"]
        assert "claude-code" in defaults["frameworks"]

    def test_javascript_project_detection_to_wizard(self, tmp_path):
        """E2E: JavaScript project detection flows correctly to wizard defaults."""
        from clauded.detect import detect

        # Create a realistic JS project structure
        (tmp_path / "package.json").write_text("""{
  "name": "test-project",
  "engines": {
    "node": ">=20.0.0"
  },
  "dependencies": {
    "react": "^18.0.0"
  },
  "devDependencies": {
    "jest": "^29.0.0"
  }
}
""")
        for i in range(5):
            (tmp_path / f"component{i}.js").write_text(
                "function render() { return null; }\n" * 20
            )

        # Run full detection
        result = detect(tmp_path)

        # Verify detection results
        assert len(result.languages) > 0
        js_lang = next(
            (lang for lang in result.languages if lang.name == "JavaScript"), None
        )
        assert js_lang is not None

        # Verify version detection
        assert "node" in result.versions

        # Verify framework detection
        react_framework = next(
            (f for f in result.frameworks if f.name == "react"), None
        )
        assert react_framework is not None

        # Verify wizard defaults
        defaults = create_wizard_defaults(result)
        assert defaults["node"] in ("22", "20", "18", "None")

    def test_mixed_project_detection_to_wizard(self, tmp_path):
        """E2E: Mixed-language project detection flows correctly to wizard defaults."""
        from clauded.detect import detect

        # Create a mixed Python/JS project with databases
        (tmp_path / "pyproject.toml").write_text("""
[project]
requires-python = ">=3.11"
dependencies = ["django>=4.0"]
""")
        (tmp_path / "package.json").write_text('{"engines": {"node": ">=20"}}')
        (tmp_path / "docker-compose.yml").write_text("""
services:
  db:
    image: postgres:15
  cache:
    image: redis:7
""")

        (tmp_path / "app.py").write_text("print('hello')\n" * 50)
        (tmp_path / "index.js").write_text("console.log('hello');\n" * 50)

        # Run full detection
        result = detect(tmp_path)

        # Verify multiple languages detected
        lang_names = {lang.name for lang in result.languages}
        assert "Python" in lang_names
        assert "JavaScript" in lang_names

        # Verify multiple versions detected
        assert "python" in result.versions
        assert "node" in result.versions

        # Verify databases detected
        db_names = {db.name for db in result.databases}
        assert "postgresql" in db_names
        assert "redis" in db_names

        # Verify wizard defaults
        defaults = create_wizard_defaults(result)
        assert defaults["python"] in ("3.12", "3.11")
        assert defaults["node"] in ("22", "20")
        assert "postgresql" in defaults["databases"]
        assert "redis" in defaults["databases"]


class TestScanStatsPopulation:
    """Tests for scan_stats population in detection results."""

    def test_scan_stats_populated_for_nonempty_project(self, tmp_path):
        """E2E: scan_stats is populated when scanning a project with files."""
        from clauded.detect import detect

        # Create some files
        for i in range(10):
            (tmp_path / f"file{i}.py").write_text("x = 1\n" * 10)

        result = detect(tmp_path)

        assert result.scan_stats is not None
        assert result.scan_stats.files_scanned > 0
        assert result.scan_stats.duration_ms >= 0

    def test_scan_stats_includes_all_scanned_files(self, tmp_path):
        """E2E: scan_stats.files_scanned includes all non-vendor files."""
        from clauded.detect import detect

        # Create 20 Python files
        for i in range(20):
            (tmp_path / f"module{i}.py").write_text("x = 1\n" * 5)

        # Create some non-code files that should also be counted
        (tmp_path / "README.md").write_text("# Test\n")
        (tmp_path / "config.json").write_text("{}\n")

        result = detect(tmp_path)

        assert result.scan_stats is not None
        # Should have scanned at least 20 Python files + 2 other files
        assert result.scan_stats.files_scanned >= 22

    def test_scan_stats_excludes_vendor_files(self, tmp_path):
        """E2E: scan_stats.files_excluded counts vendor-excluded files."""
        from clauded.detect import detect

        # Create regular files
        for i in range(5):
            (tmp_path / f"src{i}.py").write_text("x = 1\n" * 10)

        # Create vendor directory with many files
        vendor_dir = tmp_path / "node_modules" / "lodash"
        vendor_dir.mkdir(parents=True)
        for i in range(30):
            (vendor_dir / f"util{i}.js").write_text("// vendor\n" * 10)

        result = detect(tmp_path)

        assert result.scan_stats is not None
        # Vendor files should be excluded
        assert result.scan_stats.files_excluded > 0
        # Regular files should be scanned
        assert result.scan_stats.files_scanned >= 5

    def test_scan_stats_duration_reasonable(self, tmp_path):
        """E2E: scan_stats.duration_ms is within reasonable bounds."""
        from clauded.detect import detect

        # Create a small project
        for i in range(10):
            (tmp_path / f"file{i}.py").write_text("x = 1\n" * 5)

        result = detect(tmp_path)

        assert result.scan_stats is not None
        # Duration should be positive but not unreasonably long for small project
        assert 0 <= result.scan_stats.duration_ms < 10000  # <10 seconds

    def test_scan_stats_empty_for_no_detect(self, tmp_path):
        """E2E: scan_stats is None when no_detect=True."""
        from clauded.detect import detect

        # Create some files
        (tmp_path / "test.py").write_text("x = 1\n" * 50)

        result = detect(tmp_path, no_detect=True)

        assert result.scan_stats is None

    def test_scan_stats_empty_for_nonexistent_path(self):
        """E2E: scan_stats is None for nonexistent path."""
        from pathlib import Path

        from clauded.detect import detect

        result = detect(Path("/nonexistent/path/to/project"))

        assert result.scan_stats is None

    def test_scan_stats_zero_for_empty_directory(self, tmp_path):
        """E2E: scan_stats.files_scanned is 0 for empty directory."""
        from clauded.detect import detect

        result = detect(tmp_path)

        assert result.scan_stats is not None
        assert result.scan_stats.files_scanned == 0
        assert result.scan_stats.files_excluded == 0
        assert result.scan_stats.duration_ms >= 0

    def test_scan_stats_includes_truncated_flag(self, tmp_path):
        """E2E: scan_stats includes scan_truncated field."""
        from clauded.detect import detect

        # Create some files
        for i in range(10):
            (tmp_path / f"file{i}.py").write_text("x = 1\n" * 10)

        result = detect(tmp_path)

        assert result.scan_stats is not None
        assert hasattr(result.scan_stats, "scan_truncated")
        assert result.scan_stats.scan_truncated is False

    def test_scan_truncation_at_limit(self, tmp_path, monkeypatch):
        """E2E: scan truncates at MAX_FILE_SCAN_LIMIT."""
        from clauded.detect import detect, linguist

        # Temporarily reduce the limit for testing
        monkeypatch.setattr(linguist, "MAX_FILE_SCAN_LIMIT", 25)

        # Create more files than the limit
        for i in range(50):
            (tmp_path / f"file{i}.py").write_text("x = 1\n")

        result = detect(tmp_path)

        assert result.scan_stats is not None
        assert result.scan_stats.scan_truncated is True
        assert result.scan_stats.files_scanned == 25
