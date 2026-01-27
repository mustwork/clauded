"""
Property-based and unit tests for Linguist data vendoring.

Tests verify that:
1. All three required YAML files are valid and loadable
2. languages.yml contains expected programming languages and extensions
3. heuristics.yml contains valid disambiguation rules
4. vendor.yml contains common path exclusions
5. File data structure consistency and invariants
"""

import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from hypothesis import given
from hypothesis import strategies as st

LINGUIST_DIR = Path(__file__).parent.parent / "src" / "clauded" / "linguist"


# Load data once for property-based tests
def _load_languages() -> dict[str, Any]:
    """Load languages.yml for property testing."""
    with open(LINGUIST_DIR / "languages.yml") as f:
        data = yaml.safe_load(f)
    return data or {}


def _load_heuristics() -> dict[str, Any]:
    """Load heuristics.yml for property testing."""
    with open(LINGUIST_DIR / "heuristics.yml") as f:
        data = yaml.safe_load(f)
    return data or {}


# Property test strategies
_languages_dict = _load_languages()
_language_names = list(_languages_dict.keys())
_language_definitions = list(_languages_dict.items())

_heuristics_dict = _load_heuristics()
_disambiguations = _heuristics_dict.get("disambiguations", [])
_disambiguation_rules = [
    (dis_idx, rule)
    for dis_idx, dis in enumerate(_disambiguations)
    for rule in dis.get("rules", [])
]


# Property-based tests
@given(st.sampled_from(_language_names))
def test_each_language_name_has_definition(language_name: str) -> None:
    """Property: each language name from our sample has a valid definition."""
    definition = _languages_dict[language_name]
    assert isinstance(definition, dict)
    assert "type" in definition


@given(st.sampled_from(_language_definitions))
def test_language_definition_structure(
    language_def_tuple: tuple[str, dict[str, Any]],
) -> None:
    """Property: all language definitions follow the schema."""
    name, definition = language_def_tuple
    assert isinstance(definition, dict)
    assert "type" in definition
    valid_types = ("programming", "markup", "prose", "data")
    assert definition["type"] in valid_types

    # Note: Some languages may not have extensions, filenames, or interpreters
    # if they're aliases, grouped, or detected by content analysis.
    # This is acceptable in Linguist data.


@given(st.sampled_from(_language_definitions))
def test_language_extensions_format(
    language_def_tuple: tuple[str, dict[str, Any]],
) -> None:
    """Property: all extensions are properly formatted."""
    name, definition = language_def_tuple
    extensions = definition.get("extensions", [])
    if extensions:
        assert isinstance(extensions, list)
        for ext in extensions:
            assert isinstance(ext, str)
            assert ext.startswith("."), f"{name}: extension {ext} missing dot"


@given(st.sampled_from(_disambiguation_rules))
def test_heuristic_rule_has_language(rule_tuple: tuple[int, dict[str, Any]]) -> None:
    """Property: all heuristic rules specify a language."""
    dis_idx, rule = rule_tuple
    assert "language" in rule, f"Rule in disambiguation {dis_idx} missing language"
    # Language can be a string or list of strings (for multi-language rules)
    language = rule["language"]
    if isinstance(language, list):
        assert all(isinstance(lang, str) for lang in language)
    else:
        assert isinstance(language, str)


class TestLanguistDataPresence:
    """Verify all required Linguist data files are present."""

    def test_languages_yml_exists(self) -> None:
        """languages.yml file must exist."""
        assert (LINGUIST_DIR / "languages.yml").exists()

    def test_heuristics_yml_exists(self) -> None:
        """heuristics.yml file must exist."""
        assert (LINGUIST_DIR / "heuristics.yml").exists()

    def test_vendor_yml_exists(self) -> None:
        """vendor.yml file must exist."""
        assert (LINGUIST_DIR / "vendor.yml").exists()


class TestLanguagesYaml:
    """Test languages.yml structure and content."""

    @pytest.fixture
    def languages(self) -> dict[str, Any]:
        """Load languages.yml."""
        with open(LINGUIST_DIR / "languages.yml") as f:
            data = yaml.safe_load(f)
        return data or {}

    def test_languages_is_valid_yaml(self) -> None:
        """languages.yml must be valid YAML."""
        with open(LINGUIST_DIR / "languages.yml") as f:
            data = yaml.safe_load(f)
        assert data is not None
        assert isinstance(data, dict)

    def test_languages_not_empty(self, languages: dict[str, Any]) -> None:
        """languages.yml must contain language definitions."""
        assert len(languages) > 0

    def test_expected_languages_present(self, languages: dict[str, Any]) -> None:
        """languages.yml must contain common programming languages."""
        expected_languages = {"Python", "JavaScript", "Java", "Rust", "Go", "Kotlin"}
        actual_languages = set(languages.keys())
        assert expected_languages.issubset(actual_languages)

    def test_python_has_expected_fields(self, languages: dict[str, Any]) -> None:
        """Python entry must have required fields."""
        python = languages["Python"]
        assert "type" in python
        assert "extensions" in python or "filenames" in python
        assert python["type"] in ("programming", "markup", "prose", "data")

    def test_each_language_has_type_field(self, languages: dict[str, Any]) -> None:
        """All languages must have a 'type' field."""
        for name, definition in languages.items():
            assert isinstance(definition, dict), f"{name} is not a dict"
            assert "type" in definition, f"{name} missing 'type' field"
            valid_types = ("programming", "markup", "prose", "data")
            assert (
                definition["type"] in valid_types
            ), f"{name} has invalid type: {definition['type']}"

    def test_each_language_has_extensions_or_filenames(
        self, languages: dict[str, Any]
    ) -> None:
        """Most languages must have extensions or filenames."""
        # Some edge case languages (like aliases) may not have extensions/filenames
        # but most should. We verify a high ratio.
        has_content_count = 0
        for _name, definition in languages.items():
            has_extensions = "extensions" in definition and definition["extensions"]
            has_filenames = "filenames" in definition and definition["filenames"]
            is_grouped = "group" in definition
            if has_extensions or has_filenames or is_grouped:
                has_content_count += 1

        ratio = has_content_count / len(languages)
        assert (
            ratio > 0.95
        ), f"Only {ratio:.1%} languages have extensions/filenames/group"

    def test_extensions_format(self, languages: dict[str, Any]) -> None:
        """All extensions must be strings starting with a dot."""
        for name, definition in languages.items():
            extensions = definition.get("extensions", [])
            if extensions:
                assert isinstance(extensions, list), f"{name} extensions is not a list"
                for ext in extensions:
                    assert isinstance(
                        ext, str
                    ), f"{name} extension {ext} is not a string"
                    assert ext.startswith(
                        "."
                    ), f"{name} extension {ext} doesn't start with dot"

    def test_filenames_format(self, languages: dict[str, Any]) -> None:
        """All filenames must be strings."""
        for name, definition in languages.items():
            filenames = definition.get("filenames", [])
            if filenames:
                assert isinstance(filenames, list), f"{name} filenames is not a list"
                for filename in filenames:
                    assert isinstance(
                        filename, str
                    ), f"{name} filename {filename} is not a string"

    def test_extensions_are_unique_across_languages(
        self, languages: dict[str, Any]
    ) -> None:
        """Extension language mapping should be mostly unique."""
        extension_to_languages: dict[str, list[str]] = {}
        for name, definition in languages.items():
            for ext in definition.get("extensions", []):
                if ext not in extension_to_languages:
                    extension_to_languages[ext] = []
                extension_to_languages[ext].append(name)

        # Extensions can have multiple languages, but most should be unique
        multi_language_exts = [
            ext for ext, langs in extension_to_languages.items() if len(langs) > 1
        ]
        total_exts = len(extension_to_languages)
        unique_ratio = (total_exts - len(multi_language_exts)) / total_exts
        # In practice, Linguist has some ambiguous extensions (e.g., .h for C/C++)
        # so we allow up to 15% ambiguity
        assert (
            unique_ratio > 0.85
        ), f"Extension uniqueness ratio {unique_ratio:.2%} is lower than expected"

    def test_ace_mode_present(self, languages: dict[str, Any]) -> None:
        """Most languages should have ace_mode for editor support."""
        languages_with_ace = sum(1 for d in languages.values() if "ace_mode" in d)
        ratio = languages_with_ace / len(languages)
        assert ratio > 0.95, f"Only {ratio:.1%} languages have ace_mode"

    def test_common_extensions_recognized(self, languages: dict[str, Any]) -> None:
        """Common file extensions must be recognized."""
        common_extensions = {".py", ".js", ".java", ".go", ".rs", ".kt"}
        all_extensions = set()
        for definition in languages.values():
            all_extensions.update(definition.get("extensions", []))

        missing = common_extensions - all_extensions
        assert not missing, f"Missing common extensions: {missing}"


class TestHeuristicsYaml:
    """Test heuristics.yml structure and content."""

    @pytest.fixture
    def heuristics(self) -> dict[str, Any]:
        """Load heuristics.yml."""
        with open(LINGUIST_DIR / "heuristics.yml") as f:
            data = yaml.safe_load(f)
        return data or {}

    def test_heuristics_is_valid_yaml(self) -> None:
        """heuristics.yml must be valid YAML."""
        with open(LINGUIST_DIR / "heuristics.yml") as f:
            data = yaml.safe_load(f)
        assert data is not None
        assert isinstance(data, dict)

    def test_heuristics_not_empty(self, heuristics: dict[str, Any]) -> None:
        """heuristics.yml must contain rules."""
        assert len(heuristics) > 0

    def test_heuristics_has_disambiguations(self, heuristics: dict[str, Any]) -> None:
        """heuristics.yml must have disambiguations key."""
        assert "disambiguations" in heuristics

    def test_disambiguations_is_list(self, heuristics: dict[str, Any]) -> None:
        """disambiguations must be a list."""
        disambiguations = heuristics.get("disambiguations", [])
        assert isinstance(disambiguations, list)
        assert len(disambiguations) > 0

    def test_each_disambiguation_has_extensions(
        self, heuristics: dict[str, Any]
    ) -> None:
        """Each disambiguation rule must specify extensions."""
        disambiguations = heuristics.get("disambiguations", [])
        for i, rule in enumerate(disambiguations):
            assert "extensions" in rule, f"Rule {i} missing 'extensions'"
            assert isinstance(
                rule["extensions"], list
            ), f"Rule {i} extensions is not a list"
            assert len(rule["extensions"]) > 0, f"Rule {i} has empty extensions"

    def test_each_disambiguation_has_rules(self, heuristics: dict[str, Any]) -> None:
        """Each disambiguation rule must have matching rules."""
        disambiguations = heuristics.get("disambiguations", [])
        for i, rule in enumerate(disambiguations):
            assert "rules" in rule, f"Rule {i} missing 'rules'"
            assert isinstance(rule["rules"], list), f"Rule {i} rules is not a list"
            assert len(rule["rules"]) > 0, f"Rule {i} has empty rules"

    def test_each_heuristic_rule_has_language(self, heuristics: dict[str, Any]) -> None:
        """Each individual heuristic rule must specify a language."""
        disambiguations = heuristics.get("disambiguations", [])
        for dis_idx, disambiguation in enumerate(disambiguations):
            for rule_idx, rule in enumerate(disambiguation.get("rules", [])):
                assert (
                    "language" in rule
                ), f"Disambiguation {dis_idx} rule {rule_idx} missing 'language'"
                # Language can be a string or list of strings (multi-language rules)
                language = rule["language"]
                if isinstance(language, list):
                    assert all(
                        isinstance(lang, str) for lang in language
                    ), f"Dis {dis_idx} rule {rule_idx} has non-string in language list"
                else:
                    assert isinstance(
                        language, str
                    ), f"Dis {dis_idx} rule {rule_idx} language not string or list"

    def test_heuristic_patterns_are_strings(self, heuristics: dict[str, Any]) -> None:
        """Heuristic patterns/named_patterns should be strings or lists."""
        disambiguations = heuristics.get("disambiguations", [])
        for dis_idx, disambiguation in enumerate(disambiguations):
            for rule_idx, rule in enumerate(disambiguation.get("rules", [])):
                if "pattern" in rule:
                    pattern = rule["pattern"]
                    if isinstance(pattern, list):
                        assert all(
                            isinstance(p, str) for p in pattern
                        ), f"Dis {dis_idx} rule {rule_idx} has non-str in pattern list"
                    else:
                        assert isinstance(
                            pattern, str
                        ), f"Dis {dis_idx} rule {rule_idx} pattern not string or list"
                if "named_pattern" in rule:
                    assert isinstance(
                        rule["named_pattern"], str
                    ), f"Dis {dis_idx} rule {rule_idx} named_pattern not string"

    def test_ambiguous_extension_coverage(self, heuristics: dict[str, Any]) -> None:
        """Heuristics should include rules for commonly ambiguous extensions."""
        disambiguations = heuristics.get("disambiguations", [])
        all_extensions = set()
        for rule in disambiguations:
            all_extensions.update(rule.get("extensions", []))

        # These extensions are known to be ambiguous
        ambiguous_extensions = {".h", ".pl", ".rb"}
        covered = all_extensions & ambiguous_extensions
        assert (
            len(covered) > 0
        ), f"Heuristics don't cover known ambiguous extensions: {ambiguous_extensions}"


class TestVendorYaml:
    """Test vendor.yml structure and content."""

    @pytest.fixture
    def vendor_data(self) -> dict[str, Any]:
        """Load vendor.yml."""
        with open(LINGUIST_DIR / "vendor.yml") as f:
            data = yaml.safe_load(f)
        return data or {}

    def test_vendor_is_valid_yaml(self) -> None:
        """vendor.yml must be valid YAML."""
        with open(LINGUIST_DIR / "vendor.yml") as f:
            data = yaml.safe_load(f)
        assert data is not None

    def test_vendor_not_empty(self, vendor_data: dict[str, Any]) -> None:
        """vendor.yml must contain exclusion patterns."""
        assert len(vendor_data) > 0

    def test_vendor_has_expected_patterns(self, vendor_data: dict[str, Any]) -> None:
        """vendor.yml must contain common exclusions."""
        vendor_str = str(vendor_data)

        # These are commonly excluded patterns in Linguist
        # vendor.yml is a list of regex patterns
        common_patterns = ["node_modules", "vendor"]
        for pattern in common_patterns:
            assert (
                pattern in vendor_str
            ), f"vendor.yml doesn't exclude '{pattern}' pattern"

    def test_vendor_patterns_are_strings(self, vendor_data: dict[str, Any]) -> None:
        """Vendor patterns should be strings (regex patterns)."""
        # vendor.yml is a list of regex patterns
        if isinstance(vendor_data, list):
            for i, pattern in enumerate(vendor_data):
                assert isinstance(
                    pattern, str
                ), f"vendor.yml item {i} is not a string: {type(pattern)}"


class TestLinguistDataIntegration:
    """Integration tests across all data files."""

    def test_all_files_load_together(self) -> None:
        """All three files should load without errors."""
        with open(LINGUIST_DIR / "languages.yml") as f:
            languages = yaml.safe_load(f)
        with open(LINGUIST_DIR / "heuristics.yml") as f:
            heuristics = yaml.safe_load(f)
        with open(LINGUIST_DIR / "vendor.yml") as f:
            _vendor = yaml.safe_load(f)

        assert languages is not None
        assert heuristics is not None
        # vendor can be various formats, just check it loads

    def test_linguist_module_loads(self) -> None:
        """The linguist module should be importable and load all data."""
        # Import directly using sys.path approach for testing
        src_dir = Path(__file__).parent.parent / "src"
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))

        from clauded.linguist import (
            load_heuristics,
            load_languages,
            load_vendor_patterns,
        )

        languages = load_languages()
        assert languages
        assert "Python" in languages

        heuristics = load_heuristics()
        assert heuristics
        assert "disambiguations" in heuristics

        _vendor = load_vendor_patterns()
        # vendor can be various structures

    def test_file_sizes_reasonable(self) -> None:
        """Vendored files should have reasonable sizes."""
        languages_size = (LINGUIST_DIR / "languages.yml").stat().st_size
        heuristics_size = (LINGUIST_DIR / "heuristics.yml").stat().st_size
        vendor_size = (LINGUIST_DIR / "vendor.yml").stat().st_size

        # These files should be reasonably sized (not empty, not corrupted)
        assert languages_size > 100_000, "languages.yml is suspiciously small"
        assert heuristics_size > 10_000, "heuristics.yml is suspiciously small"
        assert vendor_size > 1_000, "vendor.yml is suspiciously small"

        assert languages_size < 1_000_000, "languages.yml is suspiciously large"
        assert heuristics_size < 500_000, "heuristics.yml is suspiciously large"
        assert vendor_size < 100_000, "vendor.yml is suspiciously large"
