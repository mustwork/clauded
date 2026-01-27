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

import logging
import time
from pathlib import Path

from .database import detect_databases
from .framework import detect_frameworks_and_tools
from .linguist import detect_languages
from .mcp import MCPDetectionResult, detect_mcp_requirements
from .result import DetectionResult, ScanStats
from .version import detect_versions

logger = logging.getLogger(__name__)


def detect(
    project_path: Path, *, no_detect: bool = False, debug: bool = False
) -> DetectionResult:
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
        logger.debug("Detection skipped (no_detect=True)")
        return DetectionResult()

    if not project_path.exists() or not project_path.is_dir():
        logger.debug(f"Project path invalid: {project_path}")
        return DetectionResult()

    logger.debug(f"Starting detection in {project_path}")
    start_time = time.perf_counter()

    # Run all detection strategies
    # Language detection also gathers file scan statistics
    logger.debug("Running language detection...")
    file_stats: dict[str, int] = {}
    languages = detect_languages(project_path, scan_stats=file_stats)
    logger.debug(
        f"Language detection complete: {len(languages)} languages found "
        f"({file_stats.get('files_scanned', 0)} files scanned, "
        f"{file_stats.get('files_excluded', 0)} excluded)"
    )
    for lang in languages:
        logger.debug(f"  - {lang.name}: {lang.confidence} ({lang.byte_count} bytes)")

    logger.debug("Running version detection...")
    versions = detect_versions(project_path)
    logger.debug(f"Version detection complete: {len(versions)} versions found")
    for runtime, spec in versions.items():
        logger.debug(f"  - {runtime}: {spec.version} (from {spec.source_file})")

    logger.debug("Running framework and tool detection...")
    frameworks, tools = detect_frameworks_and_tools(project_path)
    logger.debug(
        f"Framework/tool detection complete: "
        f"{len(frameworks)} frameworks, {len(tools)} tools"
    )
    for fw in frameworks:
        logger.debug(f"  - Framework: {fw.name} ({fw.confidence})")
    for tool in tools:
        logger.debug(f"  - Tool: {tool.name} ({tool.confidence})")

    logger.debug("Running database detection...")
    databases = detect_databases(project_path)
    logger.debug(f"Database detection complete: {len(databases)} databases found")
    for db in databases:
        logger.debug(f"  - {db.name}: {db.confidence} (from {db.source_file})")

    logger.debug("Running MCP configuration detection...")
    mcp_result = detect_mcp_requirements(project_path)
    mcp_runtimes = mcp_result.get_required_runtimes()
    mcp_tools = mcp_result.to_detected_items()
    logger.debug(
        f"MCP detection complete: runtimes={mcp_runtimes}, "
        f"{len(mcp_tools)} tools from {len(mcp_result.source_files)} config files"
    )
    for req in mcp_result.requirements:
        logger.debug(
            f"  - Server '{req.server_name}': {req.command} -> "
            f"runtime={req.runtime}, tool={req.tool}"
        )

    # Merge MCP tools into tools list (avoid duplicates by name)
    existing_tool_names = {t.name for t in tools}
    for mcp_tool in mcp_tools:
        if mcp_tool.name not in existing_tool_names:
            tools.append(mcp_tool)
            existing_tool_names.add(mcp_tool.name)

    duration_ms = int((time.perf_counter() - start_time) * 1000)
    logger.debug(f"Detection completed in {duration_ms}ms")

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
        mcp_runtimes=mcp_runtimes,
        scan_stats=scan_stats,
    )


__all__ = ["detect", "DetectionResult", "MCPDetectionResult", "detect_mcp_requirements"]
