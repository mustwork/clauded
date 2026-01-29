"""End-to-end integration tests for SQLite database option.

Tests verify:
1. SQLite appears in wizard database options
2. SQLite detection works from multiple sources
3. SQLite auto-selects when Node.js is detected
4. SQLite can coexist with other databases
5. SQLite provisioner mapping works correctly
"""

import json
from pathlib import Path

import yaml

from clauded.config import Config
from clauded.detect import detect
from clauded.detect.cli_integration import create_wizard_defaults
from clauded.provisioner import Provisioner


def test_e2e_sqlite_detection_from_file(tmp_path: Path) -> None:
    """E2E: SQLite file detected → wizard defaults → config → provisioner."""
    # Setup: Create SQLite database file
    db_file = tmp_path / "app.db"
    db_file.write_text("")

    # Step 1: Detection
    detection = detect(tmp_path)
    sqlite_detected = [db for db in detection.databases if db.name == "sqlite"]
    assert len(sqlite_detected) == 1

    # Step 2: Wizard defaults
    defaults = create_wizard_defaults(detection)
    assert "sqlite" in defaults["databases"]

    # Step 3: Config creation
    answers = {
        "python": "None",
        "node": "None",
        "java": "None",
        "kotlin": "None",
        "rust": "None",
        "go": "None",
        "tools": [],
        "databases": ["sqlite"],
        "frameworks": ["claude-code"],
        "cpus": 4,
        "memory": "8GiB",
        "disk": "20GiB",
        "claude_dangerously_skip_permissions": True,
    }
    config = Config.from_wizard(answers, tmp_path)
    assert "sqlite" in config.databases

    # Step 4: Provisioner role mapping (would invoke Ansible in real usage)
    # We can't run actual Ansible here, but we can verify the role mapping
    from unittest.mock import MagicMock

    mock_vm = MagicMock()
    provisioner = Provisioner(config, mock_vm)
    roles = provisioner._get_roles()
    assert "sqlite" in roles


def test_e2e_sqlite_detection_from_package_json(tmp_path: Path) -> None:
    """E2E: SQLite in package.json detected → wizard defaults → config."""
    # Setup: Create package.json with sqlite3
    package_json = tmp_path / "package.json"
    package_json.write_text(json.dumps({"dependencies": {"sqlite3": "^5.1.6"}}))

    # Step 1: Detection
    detection = detect(tmp_path)
    sqlite_detected = [db for db in detection.databases if db.name == "sqlite"]
    assert len(sqlite_detected) == 1

    # Step 2: Wizard defaults
    defaults = create_wizard_defaults(detection)
    assert "sqlite" in defaults["databases"]


def test_e2e_sqlite_auto_selection_with_nodejs(tmp_path: Path) -> None:
    """E2E: Node.js runtime detected → SQLite auto-selected in wizard defaults."""
    # Setup: Create .nvmrc to trigger Node.js version detection
    nvmrc = tmp_path / ".nvmrc"
    nvmrc.write_text("20\n")

    # Also create package.json for language detection
    package_json = tmp_path / "package.json"
    package_json.write_text(
        json.dumps(
            {
                "name": "test-app",
                "version": "1.0.0",
                "dependencies": {"express": "^4.18.0"},
            }
        )
    )

    # Step 1: Detection (detects Node.js from .nvmrc)
    detection = detect(tmp_path)

    # Step 2: Wizard defaults should auto-select SQLite
    defaults = create_wizard_defaults(detection)
    assert defaults.get("node") != "None"  # Node.js detected
    assert "sqlite" in defaults["databases"]  # SQLite auto-selected


def test_e2e_sqlite_coexists_with_other_databases(tmp_path: Path) -> None:
    """E2E: SQLite coexists with PostgreSQL, Redis, MySQL."""
    # Setup: Create docker-compose with multiple databases + SQLite file
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(
        yaml.dump(
            {
                "services": {
                    "postgres": {"image": "postgres:15"},
                    "redis": {"image": "redis:7"},
                    "mysql": {"image": "mysql:8"},
                },
            }
        )
    )
    db_file = tmp_path / "cache.db"
    db_file.write_text("")

    # Step 1: Detection
    detection = detect(tmp_path)
    db_names = {db.name for db in detection.databases}
    assert db_names == {"postgresql", "redis", "mysql", "sqlite"}

    # Step 2: Wizard defaults
    defaults = create_wizard_defaults(detection)
    assert "postgresql" in defaults["databases"]
    assert "redis" in defaults["databases"]
    assert "mysql" in defaults["databases"]
    assert "sqlite" in defaults["databases"]

    # Step 3: Config with all databases
    answers = {
        "python": "None",
        "node": "None",
        "java": "None",
        "kotlin": "None",
        "rust": "None",
        "go": "None",
        "tools": [],
        "databases": ["postgresql", "redis", "mysql", "sqlite"],
        "frameworks": ["claude-code"],
        "cpus": 4,
        "memory": "8GiB",
        "disk": "20GiB",
        "claude_dangerously_skip_permissions": True,
    }
    config = Config.from_wizard(answers, tmp_path)
    assert set(config.databases) == {"postgresql", "redis", "mysql", "sqlite"}

    # Step 4: Provisioner includes all database roles
    from unittest.mock import MagicMock

    mock_vm = MagicMock()
    provisioner = Provisioner(config, mock_vm)
    roles = provisioner._get_roles()
    assert "postgresql" in roles
    assert "redis" in roles
    assert "mysql" in roles
    assert "sqlite" in roles


def test_e2e_sqlite_not_detected_without_indicators(tmp_path: Path) -> None:
    """E2E: SQLite not detected when no indicators present."""
    # Setup: Create project with no SQLite indicators
    readme = tmp_path / "README.md"
    readme.write_text("# Test Project\n")

    # Step 1: Detection
    detection = detect(tmp_path)
    sqlite_detected = [db for db in detection.databases if db.name == "sqlite"]
    assert len(sqlite_detected) == 0

    # Step 2: Wizard defaults should not include SQLite
    defaults = create_wizard_defaults(detection)
    assert "sqlite" not in defaults.get("databases", [])


def test_e2e_sqlite_user_can_deselect(tmp_path: Path) -> None:
    """E2E: User can deselect SQLite even when auto-selected."""
    # Setup: Create Node.js project (triggers SQLite auto-selection)
    nvmrc = tmp_path / ".nvmrc"
    nvmrc.write_text("20\n")

    package_json = tmp_path / "package.json"
    package_json.write_text(
        json.dumps({"name": "test", "dependencies": {"express": "^4.0.0"}})
    )

    # Step 1: Detection
    detection = detect(tmp_path)
    defaults = create_wizard_defaults(detection)
    assert "sqlite" in defaults["databases"]  # Auto-selected

    # Step 2: User deselects SQLite in wizard
    answers = {
        "python": "None",
        "node": defaults["node"],
        "java": "None",
        "kotlin": "None",
        "rust": "None",
        "go": "None",
        "tools": [],
        "databases": [],  # User deselected all databases
        "frameworks": ["claude-code"],
        "cpus": 4,
        "memory": "8GiB",
        "disk": "20GiB",
        "claude_dangerously_skip_permissions": True,
    }
    config = Config.from_wizard(answers, tmp_path)
    assert "sqlite" not in config.databases  # User choice wins

    # Step 3: Provisioner does not include SQLite
    from unittest.mock import MagicMock

    mock_vm = MagicMock()
    provisioner = Provisioner(config, mock_vm)
    roles = provisioner._get_roles()
    assert "sqlite" not in roles
