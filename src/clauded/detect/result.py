"""Data classes for project detection results."""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class DetectedLanguage:
    """A detected programming language with confidence and evidence."""

    name: str
    confidence: Literal["high", "medium", "low"]
    byte_count: int
    file_count: int
    source_files: list[str] = field(default_factory=list)


@dataclass
class VersionSpec:
    """A detected runtime version specification."""

    version: str
    source_file: str
    constraint_type: Literal["exact", "minimum", "range"]


@dataclass
class DetectedItem:
    """A detected framework, tool, or database."""

    name: str
    confidence: Literal["high", "medium", "low"]
    source_file: str
    source_evidence: str


@dataclass
class ScanStats:
    """Statistics from the detection scan."""

    files_scanned: int
    files_excluded: int
    duration_ms: int


@dataclass
class DetectionResult:
    """Complete detection results for a project."""

    languages: list[DetectedLanguage] = field(default_factory=list)
    versions: dict[str, VersionSpec] = field(default_factory=dict)
    frameworks: list[DetectedItem] = field(default_factory=list)
    tools: list[DetectedItem] = field(default_factory=list)
    databases: list[DetectedItem] = field(default_factory=list)
    mcp_runtimes: set[str] = field(default_factory=set)
    scan_stats: ScanStats | None = None

    def get_primary_language(self) -> str | None:
        """Return the primary language (highest byte count, excluding markup/config)."""
        markup_config = {
            "HTML",
            "XML",
            "JSON",
            "YAML",
            "Markdown",
            "CSS",
            "SCSS",
            "SASS",
        }
        code_languages = [
            lang for lang in self.languages if lang.name not in markup_config
        ]
        if not code_languages:
            return None
        return max(code_languages, key=lambda lang: lang.byte_count).name

    def get_detected_version(self, runtime: str) -> str | None:
        """Get detected version for a runtime (python, node, java, etc.)."""
        version_spec = self.versions.get(runtime)
        return version_spec.version if version_spec else None

    def is_tool_detected(self, tool: str) -> bool:
        """Check if a tool was detected."""
        return any(item.name == tool for item in self.tools)

    def is_database_detected(self, database: str) -> bool:
        """Check if a database was detected."""
        return any(item.name == database for item in self.databases)

    def is_framework_detected(self, framework: str) -> bool:
        """Check if a framework was detected."""
        return any(item.name == framework for item in self.frameworks)

    def is_mcp_runtime_required(self, runtime: str) -> bool:
        """Check if a runtime is required by MCP configuration."""
        return runtime in self.mcp_runtimes
