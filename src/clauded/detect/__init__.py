"""Project detection - automatic language, version, framework, and database detection.

This module provides automatic detection of project characteristics by analyzing
project files, manifests, and configuration. Detection results can be used to
pre-populate wizard defaults while remaining fully overridable by users.

Usage:
    from clauded.detect import detect

    result = detect(Path("/path/to/project"))

    # Access detected languages
    for lang in result.languages:
        print(f"{lang.name}: {lang.confidence}")

    # Access detected versions
    python_version = result.get_detected_version("python")

    # Check for tools/databases
    has_docker = result.is_tool_detected("docker")
"""

import time
from pathlib import Path

from .database import detect_databases
from .framework import detect_frameworks_and_tools
from .linguist import detect_languages
from .result import DetectionResult, ScanStats
from .version import detect_versions


def detect(project_path: Path, *, no_detect: bool = False) -> DetectionResult:
    """Detect project characteristics from files in project_path.

    Orchestrates all detection strategies and consolidates results.

    CONTRACT:
      Inputs:
        - project_path: directory path to project root, must exist and be readable
        - no_detect: boolean flag, if True returns empty result immediately

      Outputs:
        - DetectionResult: complete detection results including languages, versions,
          frameworks, tools, databases, and scan statistics

      Invariants:
        - Never raises exceptions - all detection failures logged and result partial
        - Empty DetectionResult returned if project_path doesn't exist or is unreadable
        - Scan stats always present if any scanning occurred
        - All file paths in results are absolute paths

      Properties:
        - Idempotent: calling detect() multiple times on same path yields same results
        - Non-destructive: never modifies any project files
        - Deterministic: same project state produces same detection results

      Algorithm:
        1. Validate project_path existence and readability
        2. Start timing for scan_stats
        3. Run detection strategies in parallel conceptually (no dependencies):
           a. Language detection via Linguist data
           b. Version detection via version files and manifests
           c. Framework/tool detection via manifest dependencies
           d. Database detection via docker-compose and env files
        4. Consolidate all results into single DetectionResult
        5. Calculate scan statistics (duration, file counts)
        6. Return complete DetectionResult
    """
    if no_detect:
        return DetectionResult()

    if not project_path.exists() or not project_path.is_dir():
        return DetectionResult()

    start_time = time.perf_counter()

    # Run all detection strategies
    # Language detection also gathers file scan statistics
    file_stats: dict[str, int] = {}
    languages = detect_languages(project_path, scan_stats=file_stats)
    versions = detect_versions(project_path)
    frameworks, tools = detect_frameworks_and_tools(project_path)
    databases = detect_databases(project_path)

    duration_ms = int((time.perf_counter() - start_time) * 1000)

    scan_stats = ScanStats(
        files_scanned=file_stats.get("files_scanned", 0),
        files_excluded=file_stats.get("files_excluded", 0),
        duration_ms=duration_ms,
    )

    return DetectionResult(
        languages=languages,
        versions=versions,
        frameworks=frameworks,
        tools=tools,
        databases=databases,
        scan_stats=scan_stats,
    )


__all__ = ["detect", "DetectionResult"]
