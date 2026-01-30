"""Tests for constants module."""

import pytest

from clauded.constants import (
    DEFAULT_LANGUAGES,
    LANGUAGE_CONFIG,
    confidence_marker,
    get_supported_versions,
    validate_version,
)


class TestLanguageConfig:
    """Test LANGUAGE_CONFIG constant."""

    def test_contains_expected_languages(self) -> None:
        """LANGUAGE_CONFIG contains all expected languages."""
        expected = {"python", "node", "java", "kotlin", "rust", "go"}
        assert set(LANGUAGE_CONFIG.keys()) == expected

    def test_each_language_has_required_fields(self) -> None:
        """Each language in config has name, versions, and label fields."""
        for lang, config in LANGUAGE_CONFIG.items():
            assert "name" in config, f"{lang} missing 'name' field"
            assert "versions" in config, f"{lang} missing 'versions' field"
            assert "label" in config, f"{lang} missing 'label' field"

    def test_versions_are_non_empty_lists(self) -> None:
        """Each language has at least one version."""
        for lang, config in LANGUAGE_CONFIG.items():
            versions = config["versions"]
            assert isinstance(versions, list), f"{lang} versions is not a list"
            assert len(versions) > 0, f"{lang} has no versions"

    def test_specific_language_values(self) -> None:
        """Spot check specific language values."""
        # Python
        assert LANGUAGE_CONFIG["python"]["name"] == "Python"
        assert "3.12" in LANGUAGE_CONFIG["python"]["versions"]

        # Node
        assert LANGUAGE_CONFIG["node"]["name"] == "Node.js"
        assert "22" in LANGUAGE_CONFIG["node"]["versions"]

        # Rust
        assert LANGUAGE_CONFIG["rust"]["name"] == "Rust"
        assert "stable" in LANGUAGE_CONFIG["rust"]["versions"]


class TestDefaultLanguages:
    """Test DEFAULT_LANGUAGES constant."""

    def test_default_languages_are_python_and_node(self) -> None:
        """Default languages should be python and node."""
        assert DEFAULT_LANGUAGES == {"python", "node"}

    def test_default_languages_exist_in_config(self) -> None:
        """All default languages exist in LANGUAGE_CONFIG."""
        for lang in DEFAULT_LANGUAGES:
            assert lang in LANGUAGE_CONFIG


class TestConfidenceMarker:
    """Test confidence_marker function."""

    def test_high_confidence_returns_empty(self) -> None:
        """High confidence returns empty string."""
        assert confidence_marker("high") == ""

    def test_medium_confidence_returns_detected(self) -> None:
        """Medium confidence returns ' (detected)'."""
        assert confidence_marker("medium") == " (detected)"

    def test_low_confidence_returns_suggestion(self) -> None:
        """Low confidence returns ' (suggestion)'."""
        assert confidence_marker("low") == " (suggestion)"

    def test_unknown_confidence_returns_suggestion(self) -> None:
        """Unknown confidence level defaults to suggestion."""
        assert confidence_marker("unknown") == " (suggestion)"
        assert confidence_marker("") == " (suggestion)"

    @pytest.mark.parametrize(
        "confidence,expected",
        [
            ("high", ""),
            ("medium", " (detected)"),
            ("low", " (suggestion)"),
        ],
    )
    def test_confidence_marker_parametrized(
        self, confidence: str, expected: str
    ) -> None:
        """Parametrized test for confidence marker mapping."""
        assert confidence_marker(confidence) == expected


class TestGetSupportedVersions:
    """Test get_supported_versions function."""

    def test_returns_python_versions(self) -> None:
        """Returns supported Python versions."""
        versions = get_supported_versions("python")
        assert "3.12" in versions
        assert "3.11" in versions
        assert "3.10" in versions

    def test_returns_node_versions(self) -> None:
        """Returns supported Node.js versions."""
        versions = get_supported_versions("node")
        assert "22" in versions
        assert "20" in versions
        assert "18" in versions

    def test_returns_go_versions(self) -> None:
        """Returns supported Go versions."""
        versions = get_supported_versions("go")
        assert "1.23.5" in versions
        assert "1.22.10" in versions

    def test_returns_rust_versions(self) -> None:
        """Returns supported Rust versions."""
        versions = get_supported_versions("rust")
        assert "stable" in versions
        assert "nightly" in versions

    def test_raises_for_unknown_language(self) -> None:
        """Raises KeyError for unknown language."""
        with pytest.raises(KeyError):
            get_supported_versions("unknown")

    def test_all_languages_have_versions(self) -> None:
        """All configured languages have non-empty version lists."""
        for lang in LANGUAGE_CONFIG:
            versions = get_supported_versions(lang)
            assert len(versions) > 0


class TestValidateVersion:
    """Test validate_version function."""

    def test_accepts_valid_python_version(self) -> None:
        """Accepts valid Python version."""
        result = validate_version("python", "3.12")
        assert result == "3.12"

    def test_accepts_valid_node_version(self) -> None:
        """Accepts valid Node.js version."""
        result = validate_version("node", "20")
        assert result == "20"

    def test_accepts_valid_go_version(self) -> None:
        """Accepts valid Go version."""
        result = validate_version("go", "1.23.5")
        assert result == "1.23.5"

    def test_accepts_valid_rust_version(self) -> None:
        """Accepts valid Rust version."""
        result = validate_version("rust", "stable")
        assert result == "stable"

    def test_accepts_none_version(self) -> None:
        """Accepts None version (language not selected)."""
        result = validate_version("python", None)
        assert result is None

    def test_rejects_unsupported_python_version(self) -> None:
        """Rejects unsupported Python version with clear error."""
        with pytest.raises(ValueError) as exc_info:
            validate_version("python", "2.7")

        assert "Unsupported Python version '2.7'" in str(exc_info.value)
        assert "Supported versions:" in str(exc_info.value)
        assert "3.12" in str(exc_info.value)

    def test_rejects_unsupported_node_version(self) -> None:
        """Rejects unsupported Node.js version with clear error."""
        with pytest.raises(ValueError) as exc_info:
            validate_version("node", "16")

        assert "Unsupported Node.js version '16'" in str(exc_info.value)
        assert "22" in str(exc_info.value)

    def test_rejects_unsupported_go_version(self) -> None:
        """Rejects unsupported Go version with clear error."""
        with pytest.raises(ValueError) as exc_info:
            validate_version("go", "1.20")

        assert "Unsupported Go version '1.20'" in str(exc_info.value)

    @pytest.mark.parametrize(
        "language,version",
        [
            ("python", "3.12"),
            ("python", "3.11"),
            ("python", "3.10"),
            ("node", "22"),
            ("node", "20"),
            ("node", "18"),
            ("java", "21"),
            ("java", "17"),
            ("java", "11"),
            ("kotlin", "2.0"),
            ("kotlin", "1.9"),
            ("rust", "stable"),
            ("rust", "nightly"),
            ("go", "1.23.5"),
            ("go", "1.22.10"),
        ],
    )
    def test_all_documented_versions_are_valid(
        self, language: str, version: str
    ) -> None:
        """All versions listed in LANGUAGE_CONFIG are valid."""
        result = validate_version(language, version)
        assert result == version
