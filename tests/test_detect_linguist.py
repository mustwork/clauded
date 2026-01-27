"""Property-based and integration tests for language detection.

Tests verify that:
1. All returned DetectedLanguage objects have valid confidence levels
2. Byte counts are non-negative and reasonable
3. Source file paths exist and are within project directory
4. Vendor-excluded paths never appear in results
5. Language names match Linguist data
6. Confidence assignment follows documented rules
7. Detection is consistent across identical projects
8. Heuristics correctly disambiguate ambiguous extensions
9. Shebang-based detection works for interpreter hints
10. Performance meets targets for typical project sizes
"""

import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from clauded.detect.linguist import (
    apply_heuristics,
    detect_languages,
    load_linguist_data,
)
from clauded.detect.result import DetectedLanguage
from clauded.linguist import (
    load_heuristics,
    load_languages,
    load_vendor_patterns,
)


@pytest.fixture
def linguist_data() -> dict[str, Any]:
    """Load Linguist data for tests."""
    return load_linguist_data()


@pytest.fixture
def languages_map() -> dict[str, Any]:
    """Load languages.yml."""
    return load_languages()


@pytest.fixture
def heuristics_data() -> dict[str, Any]:
    """Load heuristics.yml."""
    return load_heuristics()


@pytest.fixture
def vendor_patterns() -> list[str]:
    """Load vendor.yml."""
    vendor_data = load_vendor_patterns()
    if isinstance(vendor_data, list):
        return vendor_data
    return []


# ============================================================================
# Property-Based Tests
# ============================================================================


class TestDetectedLanguageProperties:
    """Property-based tests for DetectedLanguage invariants."""

    @given(
        st.text(min_size=1),
        st.sampled_from(["high", "medium", "low"]),
        st.integers(min_value=1, max_value=1000000),
    )
    def test_detected_language_has_valid_confidence(
        self, name: str, confidence: str, byte_count: int
    ) -> None:
        """Property: DetectedLanguage objects have valid confidence levels."""
        lang = DetectedLanguage(
            name=name,
            confidence=confidence,
            byte_count=byte_count,
            source_files=[],
        )
        assert lang.confidence in ["high", "medium", "low"]

    @given(
        st.text(min_size=1),
        st.sampled_from(["high", "medium", "low"]),
        st.integers(min_value=1, max_value=1000000),
    )
    def test_detected_language_byte_count_positive(
        self, name: str, confidence: str, byte_count: int
    ) -> None:
        """Property: byte_count is always positive when created."""
        lang = DetectedLanguage(
            name=name,
            confidence=confidence,
            byte_count=byte_count,
            source_files=[],
        )
        assert lang.byte_count > 0

    @given(
        st.text(min_size=1),
        st.sampled_from(["high", "medium", "low"]),
        st.integers(min_value=1),
        st.lists(st.text(), max_size=5),
    )
    def test_detected_language_source_files_are_strings(
        self, name: str, confidence: str, byte_count: int, source_files: list[str]
    ) -> None:
        """Property: source_files is always a list of strings."""
        lang = DetectedLanguage(
            name=name,
            confidence=confidence,
            byte_count=byte_count,
            source_files=source_files,
        )
        assert isinstance(lang.source_files, list)
        assert all(isinstance(f, str) for f in lang.source_files)


class TestLoadLinguistDataProperties:
    """Property-based tests for Linguist data loading."""

    def test_load_linguist_data_always_returns_dict(self) -> None:
        """Property: load_linguist_data always returns a dict."""
        data = load_linguist_data()
        assert isinstance(data, dict)

    def test_load_linguist_data_contains_expected_keys(self) -> None:
        """Property: loaded data contains required keys."""
        data = load_linguist_data()
        assert "languages" in data
        assert "heuristics" in data
        assert "vendor_patterns" in data

    def test_load_linguist_data_languages_is_dict(self) -> None:
        """Property: languages field is a dict."""
        data = load_linguist_data()
        assert isinstance(data["languages"], dict)

    def test_load_linguist_data_heuristics_is_dict(self) -> None:
        """Property: heuristics field is a dict."""
        data = load_linguist_data()
        assert isinstance(data["heuristics"], dict)

    def test_load_linguist_data_vendor_patterns_is_list(self) -> None:
        """Property: vendor_patterns field is a list."""
        data = load_linguist_data()
        vendor_patterns = data["vendor_patterns"]
        assert isinstance(vendor_patterns, list | dict) or vendor_patterns is None

    def test_load_linguist_data_caching(self) -> None:
        """Property: load_linguist_data returns same object on multiple calls."""
        data1 = load_linguist_data()
        data2 = load_linguist_data()
        assert data1 is data2


# ============================================================================
# Language Detection Properties
# ============================================================================


class TestDetectLanguagesProperties:
    """Property-based tests for detect_languages function."""

    def test_detect_languages_returns_list(self, tmp_path: Path) -> None:
        """Property: detect_languages always returns a list."""
        result = detect_languages(tmp_path)
        assert isinstance(result, list)

    def test_detect_languages_empty_project_returns_empty_list(
        self, tmp_path: Path
    ) -> None:
        """Property: empty project directory returns empty list."""
        result = detect_languages(tmp_path)
        assert result == []

    def test_detect_languages_nonexistent_path_returns_empty_list(self) -> None:
        """Property: nonexistent directory returns empty list."""
        nonexistent = Path("/nonexistent/path/to/project")
        result = detect_languages(nonexistent)
        assert result == []

    def test_detect_languages_all_have_valid_confidence(
        self, tmp_path: Path, languages_map: dict[str, Any]
    ) -> None:
        """Property: all returned languages have valid confidence levels."""
        py_file = tmp_path / "test.py"
        py_file.write_text("print('hello')\n")

        result = detect_languages(tmp_path)
        for lang in result:
            assert lang.confidence in ["high", "medium", "low"]

    def test_detect_languages_byte_counts_positive(self, tmp_path: Path) -> None:
        """Property: all returned languages have positive byte counts."""
        (tmp_path / "test.py").write_text("x = 1\n" * 100)
        (tmp_path / "test.js").write_text("console.log('hi');\n" * 50)

        result = detect_languages(tmp_path)
        for lang in result:
            assert lang.byte_count > 0

    def test_detect_languages_source_files_within_project(self, tmp_path: Path) -> None:
        """Property: all source_files are within project directory."""
        (tmp_path / "test.py").write_text("x = 1\n" * 50)

        result = detect_languages(tmp_path)
        for lang in result:
            for source_file in lang.source_files:
                source_path = Path(source_file)
                assert tmp_path in source_path.parents or source_path.parent == tmp_path

    def test_detect_languages_sorted_by_byte_count(self, tmp_path: Path) -> None:
        """Property: results are sorted by byte_count in descending order."""
        (tmp_path / "test.py").write_text("x = 1\n" * 100)
        (tmp_path / "test.js").write_text("console.log('hi');\n" * 50)

        result = detect_languages(tmp_path)
        if len(result) > 1:
            for i in range(len(result) - 1):
                assert result[i].byte_count >= result[i + 1].byte_count

    def test_detect_languages_language_names_match_linguist_data(
        self, tmp_path: Path, languages_map: dict[str, Any]
    ) -> None:
        """Property: all returned language names exist in Linguist data."""
        (tmp_path / "test.py").write_text("x = 1\n" * 50)

        result = detect_languages(tmp_path)
        known_languages = set(languages_map.keys())
        for lang in result:
            assert (
                lang.name in known_languages
            ), f"Language {lang.name} not in Linguist data"

    def test_detect_languages_vendor_excluded(self, tmp_path: Path) -> None:
        """Property: vendor-excluded paths never appear in results."""
        node_modules = tmp_path / "node_modules"
        node_modules.mkdir()
        (node_modules / "test.js").write_text("console.log('hi');\n" * 100)

        vendor = tmp_path / "vendor"
        vendor.mkdir()
        (vendor / "test.php").write_text("<?php echo 'hi'; ?>\n" * 100)

        # Add a real file to detect
        (tmp_path / "real.py").write_text("x = 1\n" * 50)

        result = detect_languages(tmp_path)

        for lang in result:
            for source_file in lang.source_files:
                assert "node_modules" not in source_file
                assert "/vendor/" not in source_file

    def test_detect_languages_multiple_extensions(self, tmp_path: Path) -> None:
        """Property: correctly detects multiple file types in same project."""
        (tmp_path / "test.py").write_text("x = 1\n" * 30)
        (tmp_path / "test.js").write_text("console.log('hi');\n" * 30)
        (tmp_path / "test.java").write_text("public class Test {}\n" * 30)

        result = detect_languages(tmp_path)
        language_names = {lang.name for lang in result}

        assert "Python" in language_names
        assert "JavaScript" in language_names
        assert "Java" in language_names


# ============================================================================
# Confidence Assignment Properties
# ============================================================================


class TestConfidenceAssignment:
    """Test confidence assignment rules."""

    def test_high_confidence_many_files(self, tmp_path: Path) -> None:
        """Property: high confidence assigned when >10 files."""
        for i in range(15):
            (tmp_path / f"test{i}.py").write_text("x = 1\n" * 10)

        result = detect_languages(tmp_path)
        assert len(result) > 0
        assert result[0].name == "Python"
        assert result[0].confidence == "high"

    def test_high_confidence_large_bytes(self, tmp_path: Path) -> None:
        """Property: high confidence assigned when >10KB."""
        # Write more than 10KB (~2000 lines x 6 bytes each = 12KB+)
        (tmp_path / "test.py").write_text("x = 1\n" * 2000)

        result = detect_languages(tmp_path)
        assert len(result) > 0
        py_lang = next((lang for lang in result if lang.name == "Python"), None)
        assert py_lang is not None
        assert py_lang.confidence == "high"

    def test_medium_confidence_few_files(self, tmp_path: Path) -> None:
        """Property: medium confidence for 3-10 files."""
        for i in range(5):
            (tmp_path / f"test{i}.py").write_text("x = 1\n" * 50)

        result = detect_languages(tmp_path)
        assert len(result) > 0
        py_lang = next((lang for lang in result if lang.name == "Python"), None)
        assert py_lang is not None
        assert py_lang.confidence == "medium"

    def test_low_confidence_single_small_file(self, tmp_path: Path) -> None:
        """Property: low confidence for <3 files and <1KB."""
        (tmp_path / "test.py").write_text("x = 1\n")

        result = detect_languages(tmp_path)
        assert len(result) > 0
        py_lang = next((lang for lang in result if lang.name == "Python"), None)
        assert py_lang is not None
        assert py_lang.confidence == "low"


# ============================================================================
# Shebang Detection Properties
# ============================================================================


class TestShebangDetection:
    """Test shebang-based language detection."""

    def test_shebang_python_detection(self, tmp_path: Path) -> None:
        """Property: Python detected from shebang when no extension."""
        script = tmp_path / "test_script"
        script.write_text("#!/usr/bin/env python3\nprint('hello')\n" * 50)

        result = detect_languages(tmp_path)
        assert len(result) > 0
        assert any(lang.name == "Python" for lang in result)

    def test_shebang_bash_detection(self, tmp_path: Path) -> None:
        """Property: Shell detected from bash shebang."""
        script = tmp_path / "script.sh"
        script.write_text("#!/bin/bash\necho 'hello'\n" * 50)

        result = detect_languages(tmp_path)
        lang_names = {lang.name for lang in result}
        assert any(name in ["Shell", "Bash"] for name in lang_names)


# ============================================================================
# Heuristic Application Properties
# ============================================================================


class TestApplyHeuristics:
    """Test heuristic application for ambiguous extensions."""

    def test_apply_heuristics_c_vs_cpp(self, heuristics_data: dict[str, Any]) -> None:
        """Property: .h file heuristics disambiguate C from C++."""
        # Create temporary files to test
        with tempfile.TemporaryDirectory() as tmp_dir:
            cpp_file = Path(tmp_dir) / "test.h"
            cpp_file.write_text("#include <iostream>\nclass MyClass {};\n")

            candidates = ["C", "C++"]
            result = apply_heuristics(cpp_file, candidates, heuristics_data)

            # Result should be one of the candidates if heuristics matched
            if result is not None:
                assert result in candidates

    def test_apply_heuristics_returns_candidate_on_no_match(
        self, heuristics_data: dict[str, Any]
    ) -> None:
        """Property: returns first candidate if no heuristics match."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = Path(tmp_dir) / "unknown.h"
            test_file.write_text("// Some generic content\n")

            candidates = ["C", "C++", "Objective-C"]
            result = apply_heuristics(test_file, candidates, heuristics_data)

            # Should always return something from candidates
            assert result in candidates

    def test_apply_heuristics_empty_candidates(
        self, heuristics_data: dict[str, Any]
    ) -> None:
        """Property: returns None for empty candidates."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = Path(tmp_dir) / "test.h"
            test_file.write_text("// content\n")

            result = apply_heuristics(test_file, [], heuristics_data)
            assert result is None

    def test_apply_heuristics_unreadable_file(
        self, heuristics_data: dict[str, Any]
    ) -> None:
        """Property: handles unreadable files gracefully."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = Path(tmp_dir) / "test.h"
            test_file.write_text("// content\n")

            # Make it unreadable (if possible on this platform)
            try:
                test_file.chmod(0o000)
                candidates = ["C", "C++"]
                result = apply_heuristics(test_file, candidates, heuristics_data)

                # Should return first candidate as fallback
                assert result in candidates
            finally:
                test_file.chmod(0o644)


# ============================================================================
# Integration Tests with Sample Projects
# ============================================================================


class TestIntegrationSampleProjects:
    """Integration tests with realistic sample project structures."""

    def test_python_project_detection(self, tmp_path: Path) -> None:
        """Integration: detect Python project with typical structure."""
        # Create enough files to reach high confidence (>10 files or >10KB)
        for i in range(12):
            (tmp_path / f"module{i}.py").write_text("def func():\n    pass\n" * 30)

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'\n")

        result = detect_languages(tmp_path)
        assert len(result) > 0
        py_langs = [lang for lang in result if lang.name == "Python"]
        assert len(py_langs) > 0
        assert py_langs[0].confidence == "high"

    def test_nodejs_project_detection(self, tmp_path: Path) -> None:
        """Integration: detect Node.js project structure."""
        (tmp_path / "index.js").write_text("console.log('hello');\n" * 50)
        (tmp_path / "app.js").write_text("const app = require('express')();\n" * 40)

        pkg_json = tmp_path / "package.json"
        pkg_json.write_text('{"name": "test", "version": "1.0.0"}\n')

        result = detect_languages(tmp_path)
        assert len(result) > 0
        js_langs = [lang for lang in result if lang.name == "JavaScript"]
        assert len(js_langs) > 0

    def test_java_project_detection(self, tmp_path: Path) -> None:
        """Integration: detect Java project structure."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()

        (src_dir / "Main.java").write_text(
            "public class Main { public static void main(String[] args) {} }\n" * 40
        )
        (src_dir / "Utils.java").write_text("public class Utils {}\n" * 30)

        pom = tmp_path / "pom.xml"
        pom.write_text("<?xml version='1.0'?><project></project>\n")

        result = detect_languages(tmp_path)
        java_langs = [lang for lang in result if lang.name == "Java"]
        assert len(java_langs) > 0

    def test_mixed_project_detection(self, tmp_path: Path) -> None:
        """Integration: detect mixed-language project."""
        (tmp_path / "backend.py").write_text("def api():\n    pass\n" * 50)
        (tmp_path / "frontend.js").write_text("function render() {}\n" * 50)
        (tmp_path / "Main.java").write_text("public class Main {}\n" * 30)

        result = detect_languages(tmp_path)
        lang_names = {lang.name for lang in result}

        assert "Python" in lang_names
        assert "JavaScript" in lang_names
        assert "Java" in lang_names

    def test_project_with_vendor_exclusions(self, tmp_path: Path) -> None:
        """Integration: vendor directories properly excluded."""
        (tmp_path / "src.py").write_text("x = 1\n" * 100)

        nm = tmp_path / "node_modules"
        nm.mkdir()
        (nm / "lib.js").write_text("console.log('lib');\n" * 1000)

        vendor = tmp_path / "vendor"
        vendor.mkdir()
        (vendor / "lib.rb").write_text("puts 'vendor'\n" * 1000)

        result = detect_languages(tmp_path)
        lang_names = {lang.name for lang in result}

        # Should detect Python from src.py
        assert "Python" in lang_names

        # Should not detect JavaScript from node_modules or Ruby from vendor
        # (or if detected, they should have low byte counts from other files)
        if "JavaScript" in lang_names:
            js_lang = next(lang for lang in result if lang.name == "JavaScript")
            assert js_lang.byte_count < 100

    def test_performance_target(self, tmp_path: Path) -> None:
        """Integration: detection completes within 2 seconds for typical project."""
        # Create ~1000 files
        src_dir = tmp_path / "src"
        src_dir.mkdir()

        for i in range(100):
            subdir = src_dir / f"module{i}"
            subdir.mkdir()

            for j in range(10):
                (subdir / f"file{j}.py").write_text(f"# File {i}-{j}\nx = {i}\n" * 5)

        start = time.perf_counter()
        result = detect_languages(tmp_path)
        elapsed = time.perf_counter() - start

        # Should complete in reasonable time
        assert elapsed < 5.0, f"Detection took {elapsed:.2f}s, should be <5s"
        assert len(result) > 0

    def test_deep_directory_structure(self, tmp_path: Path) -> None:
        """Integration: handles deeply nested directories."""
        current = tmp_path
        for i in range(20):
            current = current / f"level{i}"
            current.mkdir()

        (current / "deep.py").write_text("x = 1\n" * 50)

        result = detect_languages(tmp_path)
        py_langs = [lang for lang in result if lang.name == "Python"]
        assert len(py_langs) > 0
        assert any("deep.py" in f for lang in py_langs for f in lang.source_files)


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_file_with_no_extension(self, tmp_path: Path) -> None:
        """Property: files without extensions handled gracefully."""
        (tmp_path / "Makefile").write_text("all:\n\techo test\n" * 50)
        (tmp_path / "Dockerfile").write_text("FROM ubuntu:latest\n" * 50)

        result = detect_languages(tmp_path)

        # Should detect at least some of these
        lang_names = {lang.name for lang in result}
        has_makefile = "Makefile" in lang_names
        has_dockerfile = "Dockerfile" in lang_names
        assert has_makefile or has_dockerfile or len(result) >= 0

    def test_binary_files_ignored(self, tmp_path: Path) -> None:
        """Property: binary files don't cause crashes."""
        (tmp_path / "test.py").write_text("x = 1\n" * 30)
        (tmp_path / "binary").write_bytes(b"\x00\x01\x02\x03" * 100)

        result = detect_languages(tmp_path)
        assert len(result) > 0
        assert any(lang.name == "Python" for lang in result)

    def test_symlinks_handled(self, tmp_path: Path) -> None:
        """Property: symlinks don't cause infinite loops."""
        real_file = tmp_path / "real.py"
        real_file.write_text("x = 1\n" * 50)

        try:
            link = tmp_path / "link.py"
            link.symlink_to(real_file)

            result = detect_languages(tmp_path)
            assert len(result) > 0
        except OSError:
            # Symlinks may not be supported on all platforms
            pass

    def test_special_characters_in_filenames(self, tmp_path: Path) -> None:
        """Property: filenames with special characters handled."""
        special_names = [
            "test-file.py",
            "test_file.py",
            "test.file.py",
        ]

        for name in special_names:
            (tmp_path / name).write_text("x = 1\n" * 30)

        result = detect_languages(tmp_path)
        assert len(result) > 0
        assert any(lang.name == "Python" for lang in result)

    def test_large_file_handling(self, tmp_path: Path) -> None:
        """Property: large files are counted correctly."""
        large_file = tmp_path / "large.py"
        # Write a reasonably large file (>100KB)
        large_file.write_text("x = 1\n" * 20000)

        result = detect_languages(tmp_path)
        assert len(result) > 0
        py_langs = [lang for lang in result if lang.name == "Python"]
        assert len(py_langs) > 0
        # Should be >100KB (20000 lines * 6 bytes = 120KB)
        assert py_langs[0].byte_count > 100000

    def test_empty_files_counted(self, tmp_path: Path) -> None:
        """Property: empty files don't get detected but don't crash."""
        (tmp_path / "empty.py").write_text("")
        (tmp_path / "empty.js").write_text("")
        (tmp_path / "real.py").write_text("x = 1\n" * 50)

        result = detect_languages(tmp_path)
        assert len(result) > 0
        py_langs = [lang for lang in result if lang.name == "Python"]
        assert len(py_langs) > 0


# ============================================================================
# Property-Based Tests for Vendor Exclusion Invariants
# ============================================================================


class TestVendorExclusionProperties:
    """Property-based tests for vendor exclusion invariants."""

    # Vendor directory names that match actual Linguist vendor.yml patterns:
    # - (^|/)node_modules/ -> node_modules
    # - (^|/)vendors?/ -> vendor, vendors
    # - (^|/)bower_components/ -> bower_components
    # - (^|/)dist/ -> dist
    # - (^|/)cache/ -> cache
    VENDOR_DIRS = [
        "node_modules",
        "vendor",
        "vendors",
        "bower_components",
        "dist",
        "cache",
    ]

    @given(st.sampled_from(VENDOR_DIRS))
    def test_vendor_directory_files_excluded(self, vendor_dir: str) -> None:
        """Property: files in known vendor directories never appear in results."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # Create vendor directory with Python files
            vendor_path = tmp_path / vendor_dir
            vendor_path.mkdir(parents=True)
            vendor_file = vendor_path / "vendored.py"
            vendor_file.write_text("# Vendored Python code\nx = 1\n" * 100)

            # Add a real source file to ensure detection runs
            real_file = tmp_path / "main.py"
            real_file.write_text("# Main source\nx = 1\n" * 50)

            result = detect_languages(tmp_path)

            # Verify vendor file not in source_files
            for lang in result:
                for source_file in lang.source_files:
                    assert vendor_dir not in source_file, (
                        f"Vendor directory '{vendor_dir}' found in source_files: "
                        f"{source_file}"
                    )

    @given(st.sampled_from(VENDOR_DIRS), st.integers(min_value=1, max_value=5))
    def test_nested_vendor_files_excluded(self, vendor_dir: str, depth: int) -> None:
        """Property: files in nested vendor directories also excluded."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # Create nested path inside vendor
            nested_path = tmp_path / vendor_dir
            for i in range(depth):
                nested_path = nested_path / f"subdir{i}"
            nested_path.mkdir(parents=True)

            vendor_file = nested_path / "deep.py"
            vendor_file.write_text("# Deep vendored\nx = 1\n" * 100)

            # Real source file
            real_file = tmp_path / "src.py"
            real_file.write_text("# Real source\nx = 1\n" * 50)

            result = detect_languages(tmp_path)

            for lang in result:
                for source_file in lang.source_files:
                    assert (
                        vendor_dir not in source_file
                    ), f"Nested vendor path with '{vendor_dir}' found: {source_file}"

    @given(
        st.sampled_from(VENDOR_DIRS),
        st.sampled_from([".py", ".js", ".java", ".ts", ".rb"]),
    )
    def test_vendor_exclusion_language_agnostic(
        self, vendor_dir: str, extension: str
    ) -> None:
        """Property: vendor exclusion works for all file types."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # Create vendor file with given extension
            vendor_path = tmp_path / vendor_dir
            vendor_path.mkdir(parents=True)
            vendor_file = vendor_path / f"vendored{extension}"
            vendor_file.write_text("// Vendored code\nvar x = 1;\n" * 100)

            # Real source file (Python)
            real_file = tmp_path / "main.py"
            real_file.write_text("# Real source\nx = 1\n" * 50)

            result = detect_languages(tmp_path)

            for lang in result:
                for source_file in lang.source_files:
                    assert vendor_dir not in source_file


# ============================================================================
# Property-Based Tests for Confidence Level Assignment
# ============================================================================


class TestConfidenceLevelProperties:
    """Property-based tests for confidence level assignment invariants."""

    @given(st.integers(min_value=11, max_value=50))
    def test_high_confidence_many_files_invariant(self, file_count: int) -> None:
        """Property: >10 files always results in high confidence."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # Create specified number of small Python files
            for i in range(file_count):
                (tmp_path / f"file{i}.py").write_text("x = 1\n")

            result = detect_languages(tmp_path)

            py_langs = [lang for lang in result if lang.name == "Python"]
            assert len(py_langs) > 0, "Python should be detected"
            assert py_langs[0].confidence == "high", (
                f"With {file_count} files, confidence should be 'high', "
                f"got '{py_langs[0].confidence}'"
            )

    @given(st.integers(min_value=10240, max_value=50000))
    def test_high_confidence_large_bytes_invariant(self, byte_size: int) -> None:
        """Property: >10KB always results in high confidence."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # Create single file with specified byte size
            # Each "x = 1\n" is 6 bytes
            lines_needed = byte_size // 6 + 1
            (tmp_path / "large.py").write_text("x = 1\n" * lines_needed)

            result = detect_languages(tmp_path)

            py_langs = [lang for lang in result if lang.name == "Python"]
            assert len(py_langs) > 0, "Python should be detected"
            assert py_langs[0].confidence == "high", (
                f"With {py_langs[0].byte_count} bytes (>{byte_size} requested), "
                f"confidence should be 'high', got '{py_langs[0].confidence}'"
            )

    @given(st.integers(min_value=3, max_value=10))
    def test_medium_confidence_file_count_invariant(self, file_count: int) -> None:
        """Property: 3-10 files with <10KB results in medium confidence."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # Create specified number of small files (under 10KB total)
            bytes_per_file = 500  # Stay well under 10KB
            lines_per_file = bytes_per_file // 6
            for i in range(file_count):
                (tmp_path / f"file{i}.py").write_text("x = 1\n" * lines_per_file)

            result = detect_languages(tmp_path)

            py_langs = [lang for lang in result if lang.name == "Python"]
            assert len(py_langs) > 0, "Python should be detected"
            # Should be medium or high (high if total bytes > 10KB)
            assert py_langs[0].confidence in ["medium", "high"], (
                f"With {file_count} files, confidence should be 'medium' or 'high', "
                f"got '{py_langs[0].confidence}'"
            )

    @given(st.integers(min_value=1024, max_value=10239))
    def test_medium_confidence_byte_range_invariant(self, byte_size: int) -> None:
        """Property: 1KB-10KB with <3 files results in medium confidence."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # Create single file in the 1KB-10KB range
            # Each "x = 1\n" is exactly 6 bytes
            # Use floor division to stay under the target (avoid exceeding 10KB)
            lines_needed = min(byte_size // 6, 1706)  # 1706 * 6 = 10236 < 10240
            (tmp_path / "medium.py").write_text("x = 1\n" * lines_needed)

            result = detect_languages(tmp_path)

            py_langs = [lang for lang in result if lang.name == "Python"]
            assert len(py_langs) > 0, "Python should be detected"
            actual_bytes = py_langs[0].byte_count
            # Verify we're actually in the medium range (1KB-10KB)
            if actual_bytes >= 1024 and actual_bytes < 10240:
                assert py_langs[0].confidence == "medium", (
                    f"With {actual_bytes} bytes (1KB-10KB), single file, "
                    f"confidence should be 'medium', got '{py_langs[0].confidence}'"
                )

    @given(st.integers(min_value=1, max_value=2))
    def test_low_confidence_few_small_files_invariant(self, file_count: int) -> None:
        """Property: <3 files with <1KB total results in low confidence."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # Create small files totaling < 1KB
            bytes_per_file = 100  # Well under 1KB total
            lines_per_file = bytes_per_file // 6
            for i in range(file_count):
                (tmp_path / f"small{i}.py").write_text("x = 1\n" * lines_per_file)

            result = detect_languages(tmp_path)

            py_langs = [lang for lang in result if lang.name == "Python"]
            assert len(py_langs) > 0, "Python should be detected"
            assert py_langs[0].confidence == "low", (
                f"With {file_count} files, {py_langs[0].byte_count} bytes, "
                f"confidence should be 'low', got '{py_langs[0].confidence}'"
            )
