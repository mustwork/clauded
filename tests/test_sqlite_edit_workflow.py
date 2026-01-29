"""Tests for SQLite edit workflow.

Verifies that --edit flag preserves SQLite selections correctly.
"""

from pathlib import Path

import yaml

from clauded.config import Config


def test_edit_workflow_preserves_sqlite(tmp_path: Path) -> None:
    """E2E: Edit workflow preserves SQLite when re-editing config."""
    # Step 1: Create initial config with SQLite
    config_file = tmp_path / ".clauded.yaml"
    config_data = {
        "version": "1",
        "vm": {
            "name": "clauded-test",
            "cpus": 4,
            "memory": "8GiB",
            "disk": "20GiB",
        },
        "mount": {
            "host": str(tmp_path),
            "guest": str(tmp_path),
        },
        "environment": {
            "node": "20",
            "tools": [],
            "databases": ["postgresql", "sqlite"],
            "frameworks": ["claude-code"],
        },
    }
    config_file.write_text(yaml.dump(config_data))

    # Step 2: Load config (simulates edit workflow)
    config = Config.load(config_file)
    assert "sqlite" in config.databases
    assert "postgresql" in config.databases

    # Step 3: Simulate user editing config via wizard
    # User keeps existing databases
    answers = {
        "python": "None",
        "node": "20",
        "java": "None",
        "kotlin": "None",
        "rust": "None",
        "go": "None",
        "tools": [],
        "databases": ["postgresql", "sqlite"],  # User keeps both
        "frameworks": ["claude-code"],
        "cpus": "4",
        "memory": "8GiB",
        "disk": "20GiB",
    }

    # Step 4: Create new config from edited answers
    new_config = Config.from_wizard(answers, tmp_path)
    assert "sqlite" in new_config.databases
    assert "postgresql" in new_config.databases


def test_edit_workflow_removes_sqlite(tmp_path: Path) -> None:
    """E2E: Edit workflow allows removing SQLite."""
    # Step 1: Create config with SQLite
    config_file = tmp_path / ".clauded.yaml"
    config_data = {
        "version": "1",
        "vm": {
            "name": "clauded-test",
            "cpus": 4,
            "memory": "8GiB",
            "disk": "20GiB",
        },
        "mount": {
            "host": str(tmp_path),
            "guest": str(tmp_path),
        },
        "environment": {
            "node": "20",
            "databases": ["sqlite"],
            "frameworks": ["claude-code"],
        },
    }
    config_file.write_text(yaml.dump(config_data))

    # Step 2: Load and verify
    config = Config.load(config_file)
    assert "sqlite" in config.databases

    # Step 3: User removes SQLite in edit
    answers = {
        "python": "None",
        "node": "20",
        "java": "None",
        "kotlin": "None",
        "rust": "None",
        "go": "None",
        "tools": [],
        "databases": [],  # User removes all databases
        "frameworks": ["claude-code"],
        "cpus": "4",
        "memory": "8GiB",
        "disk": "20GiB",
    }

    # Step 4: Verify SQLite removed
    new_config = Config.from_wizard(answers, tmp_path)
    assert "sqlite" not in new_config.databases


def test_edit_workflow_adds_sqlite(tmp_path: Path) -> None:
    """E2E: Edit workflow allows adding SQLite to existing config."""
    # Step 1: Create config without SQLite
    config_file = tmp_path / ".clauded.yaml"
    config_data = {
        "version": "1",
        "vm": {
            "name": "clauded-test",
            "cpus": 4,
            "memory": "8GiB",
            "disk": "20GiB",
        },
        "mount": {
            "host": str(tmp_path),
            "guest": str(tmp_path),
        },
        "environment": {
            "node": "20",
            "databases": ["postgresql"],
            "frameworks": ["claude-code"],
        },
    }
    config_file.write_text(yaml.dump(config_data))

    # Step 2: Load and verify no SQLite
    config = Config.load(config_file)
    assert "sqlite" not in config.databases

    # Step 3: User adds SQLite in edit
    answers = {
        "python": "None",
        "node": "20",
        "java": "None",
        "kotlin": "None",
        "rust": "None",
        "go": "None",
        "tools": [],
        "databases": ["postgresql", "sqlite"],  # User adds sqlite
        "frameworks": ["claude-code"],
        "cpus": "4",
        "memory": "8GiB",
        "disk": "20GiB",
    }

    # Step 4: Verify SQLite added
    new_config = Config.from_wizard(answers, tmp_path)
    assert "sqlite" in new_config.databases
    assert "postgresql" in new_config.databases
