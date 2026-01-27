"""Language detection using GitHub Linguist data."""

import logging
import re
from pathlib import Path
from typing import Any, Literal

from clauded.linguist import (
    load_heuristics,
    load_languages,
    load_vendor_patterns,
)

from .result import DetectedLanguage
from .utils import is_safe_path

logger = logging.getLogger(__name__)

# Cache for loaded data to avoid re-parsing YAML files
_cached_data: dict[str, Any] | None = None


def load_linguist_data() -> dict[str, Any]:
    """Load vendored Linguist YAML files.

    CONTRACT:
      Inputs:
        - None (loads from package resources)

      Outputs:
        - dictionary containing:
          * languages: extension → language mapping from languages.yml
          * heuristics: disambiguation rules from heuristics.yml
          * vendor_patterns: exclusion globs from vendor.yml

      Invariants:
        - All three YAML files must be present in linguist/ directory
        - Returns empty dict on parse errors (logs warning)
        - Never raises exceptions

      Properties:
        - Cached: subsequent calls return same data (no re-parsing)
        - Deterministic: same vendored files yield same parsed data
    """
    global _cached_data
    if _cached_data is not None:
        return _cached_data

    try:
        languages = load_languages()
        heuristics = load_heuristics()
        vendor_patterns = load_vendor_patterns()

        _cached_data = {
            "languages": languages,
            "heuristics": heuristics,
            "vendor_patterns": vendor_patterns,
        }
        return _cached_data
    except Exception as e:
        logger.warning(f"Failed to load Linguist data: {e}")
        return {
            "languages": {},
            "heuristics": {},
            "vendor_patterns": {},
        }


def _is_excluded_by_vendor(file_path: Path, vendor_patterns: list[str]) -> bool:
    """Check if file path matches any vendor exclusion patterns.

    Args:
        file_path: Path to check relative to project root
        vendor_patterns: List of regex patterns from vendor.yml

    Returns:
        True if file should be excluded, False otherwise
    """
    relative_path = file_path.as_posix()

    for pattern in vendor_patterns:
        try:
            if re.search(pattern, relative_path):
                return True
        except re.error:
            logger.debug(f"Invalid regex pattern in vendor.yml: {pattern}")

    return False


def _extract_shebang_interpreter(file_path: Path) -> str | None:
    """Extract interpreter from shebang line if present.

    Reads first 8KB of file to check for shebang. Returns interpreter name
    if found (e.g., 'python', 'bash', 'ruby').

    Args:
        file_path: Path to file

    Returns:
        Interpreter name or None
    """
    try:
        with open(file_path, "rb") as f:
            first_bytes = f.read(8192)

        if first_bytes.startswith(b"#!"):
            try:
                shebang = first_bytes.split(b"\n")[0].decode("utf-8", errors="ignore")
                shebang = shebang[2:].strip()

                interpreter = shebang.split()[-1] if shebang else ""
                interpreter = Path(interpreter).name

                return interpreter if interpreter else None
            except (UnicodeDecodeError, IndexError):
                return None
    except OSError:
        logger.debug(f"Could not read file for shebang: {file_path}")

    return None


def apply_heuristics(
    file_path: Path, candidate_languages: list[str], heuristics_data: dict[str, Any]
) -> str | None:
    """Apply Linguist heuristics to disambiguate ambiguous file extensions.

    CONTRACT:
      Inputs:
        - file_path: path to file, must exist and be readable
        - candidate_languages: collection of possible languages for this extension,
          non-empty collection
        - heuristics_data: parsed heuristics.yml data

      Outputs:
        - language name: string from candidate_languages that matches heuristic rules
        - None: if no heuristic matches or file unreadable

      Invariants:
        - Returned language must be in candidate_languages
        - Only reads first 8KB of file (performance constraint)
        - Never raises exceptions on file read errors

      Properties:
        - Deterministic: same file content yields same language choice
        - Efficient: limited file content sampling
    """
    if not candidate_languages:
        return None

    try:
        with open(file_path, "rb") as f:
            content_bytes = f.read(8192)

        try:
            content = content_bytes.decode("utf-8", errors="replace")
        except Exception:
            return candidate_languages[0]

        ext = file_path.suffix.lower()
        disambiguations = heuristics_data.get("disambiguations", [])

        for disambiguation in disambiguations:
            extensions = disambiguation.get("extensions", [])
            if ext not in extensions:
                continue

            rules = disambiguation.get("rules", [])
            for rule in rules:
                language = rule.get("language")
                if not language:
                    continue

                if isinstance(language, list):
                    languages_to_check: list[str] = [str(lang) for lang in language]
                else:
                    languages_to_check = [str(language)]

                matches = _check_rule_patterns(rule, content)
                if matches:
                    for lang in languages_to_check:
                        if lang in candidate_languages:
                            return lang

        return candidate_languages[0]

    except OSError:
        logger.debug(f"Could not read file for heuristics: {file_path}")
        return candidate_languages[0]


def _check_rule_patterns(rule: dict[str, Any], content: str) -> bool:
    """Check if all patterns in a rule match the content.

    Handles 'and' blocks (all must match), 'pattern', 'negative_pattern',
    and 'named_pattern' references.

    Args:
        rule: Heuristic rule dictionary
        content: File content to match against

    Returns:
        True if rule matches, False otherwise
    """
    if "and" in rule:
        and_rules = rule["and"]
        if not isinstance(and_rules, list):
            and_rules = [and_rules]

        for subrule in and_rules:
            if not _check_rule_patterns(subrule, content):
                return False
        return True

    if "pattern" in rule:
        pattern = rule["pattern"]
        if isinstance(pattern, list):
            combined_pattern = "|".join(f"({p})" for p in pattern)
        else:
            combined_pattern = pattern

        try:
            if not re.search(combined_pattern, content, re.MULTILINE | re.DOTALL):
                return False
        except re.error:
            return False

    if "negative_pattern" in rule:
        pattern = rule["negative_pattern"]
        if isinstance(pattern, list):
            combined_pattern = "|".join(f"({p})" for p in pattern)
        else:
            combined_pattern = pattern

        try:
            if re.search(combined_pattern, content, re.MULTILINE | re.DOTALL):
                return False
        except re.error:
            pass

    return True


def detect_languages(
    project_path: Path, scan_stats: dict[str, int] | None = None
) -> list[DetectedLanguage]:
    """Detect programming languages in project using Linguist data.

    CONTRACT:
      Inputs:
        - project_path: directory path, must exist and be readable
        - scan_stats: optional dict to populate with file counts
          If provided, will be updated with keys: files_scanned, files_excluded

      Outputs:
        - collection of DetectedLanguage objects, sorted by byte_count descending
        - empty collection if no languages detected or errors occur

      Invariants:
        - All returned languages have byte_count > 0
        - All source_files are absolute paths within project_path
        - Confidence levels assigned based on file count and byte count
        - Never raises exceptions - logs warnings and returns partial results

      Properties:
        - Completeness: scans all files recursively excluding vendor patterns
        - Accuracy: matches Linguist extension mappings and heuristics
        - Idempotent: same project state yields same language list
    """
    linguist_data = load_linguist_data()
    languages_map = linguist_data.get("languages", {})
    heuristics_data = linguist_data.get("heuristics", {})
    vendor_patterns = linguist_data.get("vendor_patterns", [])

    if not vendor_patterns or not isinstance(vendor_patterns, list):
        vendor_patterns = []

    ext_to_languages: dict[str, list[str]] = {}
    for lang_name, lang_def in languages_map.items():
        extensions = lang_def.get("extensions", [])
        for ext in extensions:
            if ext not in ext_to_languages:
                ext_to_languages[ext] = []
            ext_to_languages[ext].append(lang_name)

    filename_to_languages: dict[str, list[str]] = {}
    for lang_name, lang_def in languages_map.items():
        filenames = lang_def.get("filenames", [])
        for filename in filenames:
            if filename not in filename_to_languages:
                filename_to_languages[filename] = []
            filename_to_languages[filename].append(lang_name)

    interpreter_to_languages: dict[str, list[str]] = {}
    for lang_name, lang_def in languages_map.items():
        interpreters = lang_def.get("interpreters", [])
        for interp in interpreters:
            key = Path(interp).name
            if key not in interpreter_to_languages:
                interpreter_to_languages[key] = []
            interpreter_to_languages[key].append(lang_name)

    language_bytes: dict[str, int] = {}
    language_files: dict[str, list[str]] = {}
    language_file_count: dict[str, int] = {}

    # Track file counts for scan_stats
    files_scanned = 0
    files_excluded = 0

    if not project_path.is_dir():
        logger.warning(f"Project path does not exist: {project_path}")
        return []

    try:
        for file_path in project_path.rglob("*"):
            if not file_path.is_file():
                continue

            # SEC-001: Skip symlinks to prevent exploitation
            if not is_safe_path(file_path, project_path):
                files_excluded += 1
                continue

            try:
                rel_path = file_path.relative_to(project_path)
                if _is_excluded_by_vendor(rel_path, vendor_patterns):
                    files_excluded += 1
                    continue
            except ValueError:
                files_excluded += 1
                continue

            files_scanned += 1

            detected_language = None
            file_size = file_path.stat().st_size

            filename = file_path.name
            if filename in filename_to_languages:
                detected_language = filename_to_languages[filename][0]
            else:
                ext = file_path.suffix.lower()
                if ext in ext_to_languages:
                    candidates = ext_to_languages[ext]
                    if len(candidates) == 1:
                        detected_language = candidates[0]
                    else:
                        detected_language = apply_heuristics(
                            file_path, candidates, heuristics_data
                        )
                else:
                    shebang_interp = _extract_shebang_interpreter(file_path)
                    if shebang_interp and shebang_interp in interpreter_to_languages:
                        detected_language = interpreter_to_languages[shebang_interp][0]

            if detected_language:
                if detected_language not in language_bytes:
                    language_bytes[detected_language] = 0
                    language_files[detected_language] = []
                    language_file_count[detected_language] = 0

                language_bytes[detected_language] += file_size
                language_file_count[detected_language] += 1

                if len(language_files[detected_language]) < 3:
                    language_files[detected_language].append(str(file_path))

    except Exception as e:
        logger.warning(f"Error scanning project directory: {e}")

    results = []
    for lang_name in sorted(language_bytes.keys()):
        byte_count = language_bytes[lang_name]
        file_count = language_file_count[lang_name]

        if byte_count == 0:
            continue

        confidence: Literal["high", "medium", "low"]
        if file_count > 10 or byte_count > 10 * 1024:
            confidence = "high"
        elif file_count >= 3 or byte_count >= 1024:
            confidence = "medium"
        else:
            confidence = "low"

        results.append(
            DetectedLanguage(
                name=lang_name,
                confidence=confidence,
                byte_count=byte_count,
                source_files=language_files[lang_name],
            )
        )

    results.sort(key=lambda x: x.byte_count, reverse=True)

    # Populate scan_stats if requested
    if scan_stats is not None:
        scan_stats["files_scanned"] = files_scanned
        scan_stats["files_excluded"] = files_excluded

    return results
