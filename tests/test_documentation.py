"""Documentation audit tests for the opencode-harness epic.

Locks in AC-025 (each user-facing doc reflects the harness concept, --harness
flag, opencode framework, and harness ⇒ framework rule) and the Story 04
boy-scout invariant (USE_BUILTIN_RIPGREP=0 is gone from user-facing docs).
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

DOC_FILES_REQUIRING_HARNESS_COVERAGE = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "specs" / "spec.md",
    REPO_ROOT / "docs" / "configuration.md",
    REPO_ROOT / "CHANGELOG.md",
]

USER_FACING_DOCS_NO_RIPGREP_FLAG = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "specs" / "spec.md",
    REPO_ROOT / "docs" / "configuration.md",
]


@pytest.mark.parametrize("doc_path", DOC_FILES_REQUIRING_HARNESS_COVERAGE)
def test_doc_mentions_opencode_harness_and_flag(doc_path: Path) -> None:
    """AC-025: each user-facing doc names opencode, harness, and --harness."""
    content = doc_path.read_text().lower()
    assert "opencode" in content, f"{doc_path} does not mention 'opencode'"
    assert "harness" in content, f"{doc_path} does not mention 'harness'"
    assert "--harness" in content, f"{doc_path} does not mention '--harness'"


@pytest.mark.parametrize("doc_path", USER_FACING_DOCS_NO_RIPGREP_FLAG)
def test_no_use_builtin_ripgrep_in_user_facing_docs(doc_path: Path) -> None:
    """Story 04 boy-scout: USE_BUILTIN_RIPGREP=0 is gone from runtime claims.

    CHANGELOG.md is excluded from this check because it correctly records the
    removal under [Unreleased] / Removed.
    """
    content = doc_path.read_text()
    assert (
        "USE_BUILTIN_RIPGREP" not in content
    ), f"{doc_path} still references the removed USE_BUILTIN_RIPGREP env var"


def test_no_opencode_alpine_in_src() -> None:
    """Verification step 4: no Alpine-specific opencode code accidentally landed."""
    src_dir = REPO_ROOT / "src"
    offenders: list[Path] = []
    for path in src_dir.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        if "opencode-alpine" in text:
            offenders.append(path)
    assert not offenders, f"Found opencode-alpine references in: {offenders}"
