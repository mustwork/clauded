"""MCP (Model Context Protocol) configuration detection.

Scans for MCP configuration files and extracts runtime/tool requirements
based on the commands used by MCP servers.

MCP config file locations (in priority order):
  1. .mcp.json (project root)
  2. mcp.json (project root)
  3. mcp.json.example (project root - template)
  4. ~/.claude.json (user config)

Command to requirement mappings:
  - uvx, pipx, python, python3 → python runtime + uv/pipx tool
  - npx, node → node runtime
  - docker → docker tool
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from .result import DetectedItem
from .utils import is_safe_path, safe_read_text

logger = logging.getLogger(__name__)

# MCP config file names to scan (in priority order)
MCP_CONFIG_FILES = [
    ".mcp.json",
    "mcp.json",
    "mcp.json.example",
]

# User-level config location
USER_CLAUDE_CONFIG = Path.home() / ".claude.json"

# Command to runtime/tool mapping
COMMAND_RUNTIME_MAP: dict[str, str] = {
    "uvx": "python",
    "pipx": "python",
    "python": "python",
    "python3": "python",
    "npx": "node",
    "node": "node",
}

COMMAND_TOOL_MAP: dict[str, str] = {
    "uvx": "uv",
    "pipx": "pipx",
    "docker": "docker",
}


@dataclass
class MCPRequirement:
    """A requirement derived from MCP server configuration."""

    runtime: str | None  # "python", "node", or None
    tool: str | None  # "docker", "uv", "pipx", or None
    source_file: str
    command: str
    server_name: str
    confidence: Literal["high", "medium", "low"] = "high"


@dataclass
class MCPDetectionResult:
    """Results from MCP configuration detection."""

    requirements: list[MCPRequirement] = field(default_factory=list)
    source_files: list[str] = field(default_factory=list)

    def get_required_runtimes(self) -> set[str]:
        """Get unique runtimes required by MCP servers."""
        return {req.runtime for req in self.requirements if req.runtime}

    def get_required_tools(self) -> set[str]:
        """Get unique tools required by MCP servers."""
        return {req.tool for req in self.requirements if req.tool}

    def to_detected_items(self) -> list[DetectedItem]:
        """Convert tool requirements to DetectedItem objects for integration."""
        items: list[DetectedItem] = []
        seen_tools: set[str] = set()

        for req in self.requirements:
            if req.tool and req.tool not in seen_tools:
                seen_tools.add(req.tool)
                evidence = f"MCP server '{req.server_name}' uses {req.command}"
                items.append(
                    DetectedItem(
                        name=req.tool,
                        confidence=req.confidence,
                        source_file=req.source_file,
                        source_evidence=evidence,
                    )
                )

        return items


def detect_mcp_requirements(project_path: Path) -> MCPDetectionResult:
    """Detect MCP configuration and extract runtime/tool requirements.

    CONTRACT:
      Inputs:
        - project_path: directory path to project root

      Outputs:
        - MCPDetectionResult containing all detected requirements and source files

      Invariants:
        - Never raises exceptions - logs warnings and returns partial results
        - Checks project-level configs before user-level config
        - Deduplicates requirements by (runtime, tool) pair

      Algorithm:
        1. Scan for MCP config files in project root (priority order)
        2. Optionally check user-level ~/.claude.json
        3. For each config file found:
           a. Parse JSON
           b. Extract mcpServers object
           c. For each server, extract command field
           d. Map command to runtime and tool requirements
        4. Return consolidated MCPDetectionResult
    """
    logger.debug(f"Detecting MCP requirements in {project_path}")

    result = MCPDetectionResult()

    # Scan project-level MCP configs
    for config_name in MCP_CONFIG_FILES:
        config_path = project_path / config_name
        if config_path.exists() and is_safe_path(config_path, project_path):
            logger.debug(f"Found MCP config: {config_path}")
            _parse_mcp_config(config_path, project_path, result)

    # Check user-level config (outside project, so different safety check)
    if USER_CLAUDE_CONFIG.exists():
        logger.debug(f"Checking user config: {USER_CLAUDE_CONFIG}")
        _parse_user_claude_config(USER_CLAUDE_CONFIG, result)

    logger.debug(
        f"MCP detection complete: {len(result.requirements)} requirements, "
        f"runtimes={result.get_required_runtimes()}, "
        f"tools={result.get_required_tools()}"
    )

    return result


def _parse_mcp_config(
    config_path: Path, project_path: Path, result: MCPDetectionResult
) -> None:
    """Parse an MCP config file and extract requirements.

    Args:
        config_path: Path to MCP config file
        project_path: Project root for safe_read_text
        result: MCPDetectionResult to populate
    """
    content = safe_read_text(config_path, project_path)
    if not content:
        return

    try:
        data = json.loads(content)
        _extract_mcp_servers(data, str(config_path), result)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse MCP config {config_path}: {e}")
    except Exception as e:
        logger.warning(f"Error processing MCP config {config_path}: {e}")


def _parse_user_claude_config(config_path: Path, result: MCPDetectionResult) -> None:
    """Parse user-level claude config for MCP servers.

    User config is outside project boundary, so we read it directly
    with standard safety precautions (no symlink following into project).

    Args:
        config_path: Path to ~/.claude.json
        result: MCPDetectionResult to populate
    """
    # Don't follow symlinks for user config
    if config_path.is_symlink():
        logger.debug(f"Skipping symlinked user config: {config_path}")
        return

    try:
        content = config_path.read_text()
        data = json.loads(content)

        # User config may have mcpServers at top level or nested
        _extract_mcp_servers(data, str(config_path), result, confidence="medium")

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse user claude config: {e}")
    except Exception as e:
        logger.debug(f"Could not read user claude config: {e}")


def _extract_mcp_servers(
    data: dict,
    source_file: str,
    result: MCPDetectionResult,
    confidence: Literal["high", "medium", "low"] = "high",
) -> None:
    """Extract MCP server commands from parsed config data.

    Args:
        data: Parsed JSON data
        source_file: Source file path for tracking
        result: MCPDetectionResult to populate
        confidence: Confidence level for detected requirements
    """
    # Look for mcpServers object (standard MCP config structure)
    mcp_servers = data.get("mcpServers", {})

    if not isinstance(mcp_servers, dict):
        logger.debug(f"No valid mcpServers in {source_file}")
        return

    if mcp_servers and source_file not in result.source_files:
        result.source_files.append(source_file)

    for server_name, server_config in mcp_servers.items():
        if not isinstance(server_config, dict):
            continue

        command = server_config.get("command")
        if not command or not isinstance(command, str):
            continue

        # Extract the base command (handle paths like /usr/bin/python)
        base_command = Path(command).name

        logger.debug(f"MCP server '{server_name}': command={base_command}")

        # Map command to runtime
        runtime = COMMAND_RUNTIME_MAP.get(base_command)

        # Map command to tool
        tool = COMMAND_TOOL_MAP.get(base_command)

        # Create requirement if we found any mapping
        if runtime or tool:
            req = MCPRequirement(
                runtime=runtime,
                tool=tool,
                source_file=source_file,
                command=base_command,
                server_name=server_name,
                confidence=confidence,
            )
            result.requirements.append(req)
            logger.debug(f"  -> runtime={runtime}, tool={tool}")
        else:
            logger.debug(f"  -> no mapping for command '{base_command}'")
