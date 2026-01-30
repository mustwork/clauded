"""Shared utility functions for project detection.

This module provides common utility functions used across detection modules,
including security-related path validation and package name extraction.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def is_safe_path(file_path: Path, project_root: Path) -> bool:
    """Check if file path is safe to read (SEC-001: Symlink protection).

    Validates that:
    1. The file is not a symbolic link
    2. The resolved path is within the project boundary

    Args:
        file_path: Path to validate
        project_root: Project root directory

    Returns:
        True if path is safe to read, False otherwise
    """
    # Check if path is a symlink
    if file_path.is_symlink():
        logger.debug(f"Skipping symlinked file: {file_path}")
        return False

    # Check if resolved path is within project boundary
    try:
        resolved = file_path.resolve()
        project_resolved = project_root.resolve()
        resolved.relative_to(project_resolved)
        return True
    except ValueError:
        logger.warning(f"File outside project boundary: {file_path}")
        return False


def safe_read_text(
    file_path: Path, project_root: Path, limit: int = 8192
) -> str | None:
    """Safely read text file with symlink protection and size limit.

    Args:
        file_path: Path to read
        project_root: Project root directory
        limit: Maximum bytes to read (default: 8192 = 8KB per SEC-002)

    Returns:
        File content as string (limited to first `limit` bytes),
        or None if file is unsafe or unreadable
    """
    if not is_safe_path(file_path, project_root):
        return None

    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read(limit)
        return content
    except Exception as e:
        logger.warning(f"Failed to read {file_path}: {e}")
        return None


def safe_read_bytes(
    file_path: Path, project_root: Path, limit: int = 0
) -> bytes | None:
    """Safely read binary file with symlink protection.

    Args:
        file_path: Path to read
        project_root: Project root directory
        limit: Maximum bytes to read (0 for unlimited)

    Returns:
        File content as bytes, or None if file is unsafe or unreadable
    """
    if not is_safe_path(file_path, project_root):
        return None

    try:
        with open(file_path, "rb") as f:
            if limit > 0:
                return f.read(limit)
            return f.read()
    except Exception as e:
        logger.warning(f"Failed to read {file_path}: {e}")
        return None


def extract_package_name(dep_spec: str, normalize_case: bool = False) -> str:
    """Extract package name from dependency specification string.

    Handles common dependency specification formats:
    - "django>=4.0" -> "django"
    - "flask==2.0.0" -> "flask"
    - "pytest" -> "pytest"
    - "redis[hiredis]>=4.0" -> "redis"

    Args:
        dep_spec: Dependency specification string
        normalize_case: If True, convert to lowercase

    Returns:
        Package name without version specifiers
    """
    # Split on common version specifiers and extras
    for sep in (">=", "<=", "==", "!=", ">", "<", "~=", "["):
        if sep in dep_spec:
            name = dep_spec.split(sep)[0].strip()
            return name.lower() if normalize_case else name

    name = dep_spec.strip()
    return name.lower() if normalize_case else name
