"""Hatch build hook to embed git commit hash."""

import subprocess
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


def get_git_commit() -> str:
    """Get the current git commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


class BuildInfoHook(BuildHookInterface):
    """Build hook that generates _build_info.py with git commit."""

    PLUGIN_NAME = "build-info"

    def initialize(self, version: str, build_data: dict) -> None:
        """Generate _build_info.py before build."""
        commit = get_git_commit()
        build_info_path = Path(self.root) / "src" / "clauded" / "_build_info.py"
        build_info_path.write_text(f'__commit__ = "{commit}"\n')

        # Explicitly include the generated file in the build
        if "force_include" not in build_data:
            build_data["force_include"] = {}
        build_data["force_include"][str(build_info_path)] = "clauded/_build_info.py"
