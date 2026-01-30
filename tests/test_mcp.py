"""Tests for MCP (Model Context Protocol) detection.

Tests verify that:
1. MCP config files are detected from .mcp.json, mcp.json, and mcp.json.example
2. User-level ~/.claude.json is checked for MCP servers
3. Server commands are correctly mapped to runtimes and tools
4. Missing/malformed files are handled gracefully
5. Symlinks are not followed for security
6. MCPDetectionResult correctly aggregates requirements
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from clauded.detect.mcp import (
    COMMAND_RUNTIME_MAP,
    COMMAND_TOOL_MAP,
    MCP_CONFIG_FILES,
    MCPDetectionResult,
    MCPRequirement,
    detect_mcp_requirements,
)


class TestMCPConfigFileDetection:
    """Test detection from various MCP config file locations."""

    @pytest.mark.parametrize(
        "config_name",
        [".mcp.json", "mcp.json", "mcp.json.example"],
    )
    def test_detects_config_from_project_root(self, config_name: str) -> None:
        """Detects MCP servers from config file in project root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            config_path = project_path / config_name
            config_path.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "test-server": {"command": "uvx", "args": ["test-mcp"]}
                        }
                    }
                )
            )

            result = detect_mcp_requirements(project_path)

            assert len(result.requirements) == 1
            assert result.requirements[0].server_name == "test-server"
            assert str(config_path) in result.source_files

    def test_priority_order_respects_mcp_json_variants(self) -> None:
        """Project configs are processed: .mcp.json, mcp.json, mcp.json.example."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)

            # Create all three config files with different servers
            (project_path / ".mcp.json").write_text(
                json.dumps({"mcpServers": {"server-a": {"command": "uvx"}}})
            )
            (project_path / "mcp.json").write_text(
                json.dumps({"mcpServers": {"server-b": {"command": "npx"}}})
            )
            (project_path / "mcp.json.example").write_text(
                json.dumps({"mcpServers": {"server-c": {"command": "docker"}}})
            )

            result = detect_mcp_requirements(project_path)

            # All servers should be detected
            server_names = {req.server_name for req in result.requirements}
            assert server_names == {"server-a", "server-b", "server-c"}
            assert len(result.source_files) == 3


class TestUserClaudeConfigDetection:
    """Test detection from user-level ~/.claude.json."""

    def test_detects_from_user_claude_json(self) -> None:
        """Detects MCP servers from ~/.claude.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            fake_home = Path(tmpdir) / "home"
            fake_home.mkdir()
            fake_claude_json = fake_home / ".claude.json"
            fake_claude_json.write_text(
                json.dumps({"mcpServers": {"user-server": {"command": "npx"}}})
            )

            # Patch USER_CLAUDE_CONFIG to use our test file
            with patch("clauded.detect.mcp.USER_CLAUDE_CONFIG", fake_claude_json):
                result = detect_mcp_requirements(project_path)

            assert len(result.requirements) == 1
            assert result.requirements[0].server_name == "user-server"
            assert result.requirements[0].confidence == "medium"

    def test_skips_symlinked_user_config(self) -> None:
        """Does not follow symlinks for user config (security)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            fake_home = Path(tmpdir) / "home"
            fake_home.mkdir()

            # Create a real config file
            real_config = Path(tmpdir) / "real_config.json"
            real_config.write_text(
                json.dumps({"mcpServers": {"hacked": {"command": "uvx"}}})
            )

            # Create symlink to it
            fake_claude_json = fake_home / ".claude.json"
            fake_claude_json.symlink_to(real_config)

            with patch("clauded.detect.mcp.USER_CLAUDE_CONFIG", fake_claude_json):
                result = detect_mcp_requirements(project_path)

            # Should not detect the symlinked config
            assert len(result.requirements) == 0


class TestCommandMapping:
    """Test server command to runtime/tool mapping."""

    @pytest.mark.parametrize(
        "command,expected_runtime,expected_tool",
        [
            ("uvx", "python", "uv"),
            ("pipx", "python", "pipx"),
            ("python", "python", None),
            ("python3", "python", None),
            ("npx", "node", None),
            ("node", "node", None),
            ("docker", None, "docker"),
        ],
    )
    def test_command_mapping(
        self, command: str, expected_runtime: str | None, expected_tool: str | None
    ) -> None:
        """Commands are correctly mapped to runtimes and tools."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".mcp.json").write_text(
                json.dumps({"mcpServers": {"test": {"command": command}}})
            )

            result = detect_mcp_requirements(project_path)

            assert len(result.requirements) == 1
            req = result.requirements[0]
            assert req.runtime == expected_runtime
            assert req.tool == expected_tool

    def test_handles_full_path_commands(self) -> None:
        """Extracts base command from full paths like /usr/bin/python."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".mcp.json").write_text(
                json.dumps({"mcpServers": {"test": {"command": "/usr/bin/python3"}}})
            )

            result = detect_mcp_requirements(project_path)

            assert len(result.requirements) == 1
            assert result.requirements[0].runtime == "python"

    def test_unknown_command_not_mapped(self) -> None:
        """Unknown commands don't create requirements."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".mcp.json").write_text(
                json.dumps({"mcpServers": {"test": {"command": "unknown-tool"}}})
            )

            result = detect_mcp_requirements(project_path)

            # No requirements for unknown commands
            assert len(result.requirements) == 0


class TestMalformedFileHandling:
    """Test graceful handling of missing/malformed files."""

    def test_returns_empty_when_no_config_files(self) -> None:
        """Returns empty result when no MCP config files exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)

            # Patch out user config check
            with patch(
                "clauded.detect.mcp.USER_CLAUDE_CONFIG",
                Path("/nonexistent/.claude.json"),
            ):
                result = detect_mcp_requirements(project_path)

            assert len(result.requirements) == 0
            assert len(result.source_files) == 0

    def test_handles_invalid_json(self) -> None:
        """Gracefully handles invalid JSON without raising."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".mcp.json").write_text("{invalid json syntax")

            with patch(
                "clauded.detect.mcp.USER_CLAUDE_CONFIG",
                Path("/nonexistent/.claude.json"),
            ):
                result = detect_mcp_requirements(project_path)

            assert len(result.requirements) == 0

    def test_handles_missing_mcp_servers_key(self) -> None:
        """Handles config without mcpServers key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".mcp.json").write_text(json.dumps({"other": "data"}))

            with patch(
                "clauded.detect.mcp.USER_CLAUDE_CONFIG",
                Path("/nonexistent/.claude.json"),
            ):
                result = detect_mcp_requirements(project_path)

            assert len(result.requirements) == 0

    def test_handles_invalid_mcp_servers_type(self) -> None:
        """Handles mcpServers that isn't a dict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".mcp.json").write_text(
                json.dumps({"mcpServers": "not a dict"})
            )

            with patch(
                "clauded.detect.mcp.USER_CLAUDE_CONFIG",
                Path("/nonexistent/.claude.json"),
            ):
                result = detect_mcp_requirements(project_path)

            assert len(result.requirements) == 0

    def test_handles_server_without_command(self) -> None:
        """Handles server config without command field."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            (project_path / ".mcp.json").write_text(
                json.dumps({"mcpServers": {"test": {"args": ["arg1"]}}})
            )

            with patch(
                "clauded.detect.mcp.USER_CLAUDE_CONFIG",
                Path("/nonexistent/.claude.json"),
            ):
                result = detect_mcp_requirements(project_path)

            assert len(result.requirements) == 0


class TestSymlinkProtection:
    """Test symlink protection for project-level configs."""

    def test_skips_symlinked_project_config(self) -> None:
        """Does not follow symlinks in project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)

            # Create a config outside project
            outside_config = Path(tmpdir) / "outside" / "malicious.json"
            outside_config.parent.mkdir()
            outside_config.write_text(
                json.dumps({"mcpServers": {"evil": {"command": "uvx"}}})
            )

            # Create symlink inside project
            symlink_path = project_path / ".mcp.json"
            symlink_path.symlink_to(outside_config)

            with patch(
                "clauded.detect.mcp.USER_CLAUDE_CONFIG",
                Path("/nonexistent/.claude.json"),
            ):
                result = detect_mcp_requirements(project_path)

            # Should not detect through symlink
            assert len(result.requirements) == 0


class TestMCPDetectionResultMethods:
    """Test MCPDetectionResult helper methods."""

    def test_get_required_runtimes(self) -> None:
        """get_required_runtimes returns unique runtimes."""
        result = MCPDetectionResult(
            requirements=[
                MCPRequirement(
                    runtime="python",
                    tool="uv",
                    source_file="test",
                    command="uvx",
                    server_name="a",
                ),
                MCPRequirement(
                    runtime="python",
                    tool=None,
                    source_file="test",
                    command="python",
                    server_name="b",
                ),
                MCPRequirement(
                    runtime="node",
                    tool=None,
                    source_file="test",
                    command="npx",
                    server_name="c",
                ),
            ]
        )

        runtimes = result.get_required_runtimes()

        assert runtimes == {"python", "node"}

    def test_get_required_tools(self) -> None:
        """get_required_tools returns unique tools."""
        result = MCPDetectionResult(
            requirements=[
                MCPRequirement(
                    runtime="python",
                    tool="uv",
                    source_file="test",
                    command="uvx",
                    server_name="a",
                ),
                MCPRequirement(
                    runtime=None,
                    tool="docker",
                    source_file="test",
                    command="docker",
                    server_name="b",
                ),
                MCPRequirement(
                    runtime="python",
                    tool="uv",
                    source_file="test",
                    command="uvx",
                    server_name="c",
                ),
            ]
        )

        tools = result.get_required_tools()

        assert tools == {"uv", "docker"}

    def test_to_detected_items_deduplicates_tools(self) -> None:
        """to_detected_items returns unique tools as DetectedItems."""
        result = MCPDetectionResult(
            requirements=[
                MCPRequirement(
                    runtime="python",
                    tool="uv",
                    source_file="config.json",
                    command="uvx",
                    server_name="server-a",
                ),
                MCPRequirement(
                    runtime="python",
                    tool="uv",
                    source_file="config.json",
                    command="uvx",
                    server_name="server-b",
                ),
            ]
        )

        items = result.to_detected_items()

        assert len(items) == 1
        assert items[0].name == "uv"
        assert "server-a" in items[0].source_evidence


class TestCommandMappingConstants:
    """Test that command mapping constants are complete."""

    def test_runtime_map_covers_expected_commands(self) -> None:
        """COMMAND_RUNTIME_MAP includes expected Python and Node commands."""
        assert "uvx" in COMMAND_RUNTIME_MAP
        assert "pipx" in COMMAND_RUNTIME_MAP
        assert "python" in COMMAND_RUNTIME_MAP
        assert "python3" in COMMAND_RUNTIME_MAP
        assert "npx" in COMMAND_RUNTIME_MAP
        assert "node" in COMMAND_RUNTIME_MAP

    def test_tool_map_covers_expected_commands(self) -> None:
        """COMMAND_TOOL_MAP includes expected tool commands."""
        assert "uvx" in COMMAND_TOOL_MAP
        assert "pipx" in COMMAND_TOOL_MAP
        assert "docker" in COMMAND_TOOL_MAP

    def test_mcp_config_files_list(self) -> None:
        """MCP_CONFIG_FILES includes expected file names."""
        assert ".mcp.json" in MCP_CONFIG_FILES
        assert "mcp.json" in MCP_CONFIG_FILES
        assert "mcp.json.example" in MCP_CONFIG_FILES
