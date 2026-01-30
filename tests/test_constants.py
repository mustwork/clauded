"""Tests for constants module."""

import pytest

from clauded.constants import (
    DEFAULT_LANGUAGES,
    LANGUAGE_CONFIG,
    confidence_marker,
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
