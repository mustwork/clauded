"""Tests for clauded.config module."""

import logging
from pathlib import Path

import pytest
import yaml

from clauded.config import (
    CURRENT_VERSION,
    Config,
    ConfigValidationError,
    ConfigVersionError,
    _migrate_config,
    _validate_runtime_version,
    _validate_version,
)


class TestConfigFromWizard:
    """Tests for Config.from_wizard()."""

    def test_creates_config_with_all_options(self, tmp_path: Path) -> None:
        """Config is created with all wizard options populated."""
        answers = {
            "python": "3.11",
            "node": "20",
            "java": "21",
            "kotlin": "2.0",
            "rust": "stable",
            "go": "1.23.5",
            "tools": ["docker", "git", "aws-cli", "gradle"],
            "databases": ["postgresql", "redis"],
            "frameworks": ["playwright", "claude-code"],
            "cpus": "8",
            "memory": "16GiB",
            "disk": "50GiB",
        }

        config = Config.from_wizard(answers, tmp_path)

        assert config.python == "3.11"
        assert config.node == "20"
        assert config.java == "21"
        assert config.kotlin == "2.0"
        assert config.rust == "stable"
        assert config.go == "1.23.5"
        assert config.tools == ["docker", "git", "aws-cli", "gradle"]
        assert config.databases == ["postgresql", "redis"]
        assert config.frameworks == ["playwright", "claude-code"]
        assert config.cpus == 8
        assert config.memory == "16GiB"
        assert config.disk == "50GiB"
        assert config.mount_host == str(tmp_path)
        assert config.mount_guest == str(tmp_path)

    def test_generates_unique_vm_name_from_path(self, tmp_path: Path) -> None:
        """VM name includes project name and path hash."""
        answers = {"cpus": "4", "memory": "8GiB", "disk": "20GiB"}

        config = Config.from_wizard(answers, tmp_path)

        # Format: clauded-{project}-{hash}
        assert config.vm_name.startswith("clauded-")
        parts = config.vm_name.split("-")
        assert len(parts) >= 3  # clauded, project name part(s), hash
        assert len(parts[-1]) == 6  # 6 char hash at end

    def test_different_paths_produce_different_vm_names(self) -> None:
        """Different project paths produce different VM names."""
        answers = {"cpus": "4", "memory": "8GiB", "disk": "20GiB"}

        config1 = Config.from_wizard(answers, Path("/project/a"))
        config2 = Config.from_wizard(answers, Path("/project/b"))

        assert config1.vm_name != config2.vm_name

    def test_same_path_produces_same_vm_name(self, tmp_path: Path) -> None:
        """Same project path always produces same VM name."""
        answers = {"cpus": "4", "memory": "8GiB", "disk": "20GiB"}

        config1 = Config.from_wizard(answers, tmp_path)
        config2 = Config.from_wizard(answers, tmp_path)

        assert config1.vm_name == config2.vm_name

    def test_none_python_is_stored_as_none(self, tmp_path: Path) -> None:
        """When Python is 'None', it's stored as None."""
        answers = {"python": "None", "cpus": "4", "memory": "8GiB", "disk": "20GiB"}

        config = Config.from_wizard(answers, tmp_path)

        assert config.python is None

    def test_none_node_is_stored_as_none(self, tmp_path: Path) -> None:
        """When Node is 'None', it's stored as None."""
        answers = {"node": "None", "cpus": "4", "memory": "8GiB", "disk": "20GiB"}

        config = Config.from_wizard(answers, tmp_path)

        assert config.node is None

    def test_none_java_is_stored_as_none(self, tmp_path: Path) -> None:
        """When Java is 'None', it's stored as None."""
        answers = {"java": "None", "cpus": "4", "memory": "8GiB", "disk": "20GiB"}

        config = Config.from_wizard(answers, tmp_path)

        assert config.java is None

    def test_none_kotlin_is_stored_as_none(self, tmp_path: Path) -> None:
        """When Kotlin is 'None', it's stored as None."""
        answers = {"kotlin": "None", "cpus": "4", "memory": "8GiB", "disk": "20GiB"}

        config = Config.from_wizard(answers, tmp_path)

        assert config.kotlin is None

    def test_none_rust_is_stored_as_none(self, tmp_path: Path) -> None:
        """When Rust is 'None', it's stored as None."""
        answers = {"rust": "None", "cpus": "4", "memory": "8GiB", "disk": "20GiB"}

        config = Config.from_wizard(answers, tmp_path)

        assert config.rust is None

    def test_none_go_is_stored_as_none(self, tmp_path: Path) -> None:
        """When Go is 'None', it's stored as None."""
        answers = {"go": "None", "cpus": "4", "memory": "8GiB", "disk": "20GiB"}

        config = Config.from_wizard(answers, tmp_path)

        assert config.go is None

    def test_empty_selections_default_to_empty_lists(self, tmp_path: Path) -> None:
        """Missing selections default to empty lists."""
        answers = {"cpus": "4", "memory": "8GiB", "disk": "20GiB"}

        config = Config.from_wizard(answers, tmp_path)

        assert config.tools == []
        assert config.databases == []
        assert config.frameworks == []

    def test_claude_permissions_defaults_to_true(self, tmp_path: Path) -> None:
        """Missing claude_dangerously_skip_permissions defaults to True."""
        answers = {"cpus": "4", "memory": "8GiB", "disk": "20GiB"}

        config = Config.from_wizard(answers, tmp_path)

        assert config.claude_dangerously_skip_permissions is True

    def test_claude_permissions_explicit_false(self, tmp_path: Path) -> None:
        """Explicit False for claude_dangerously_skip_permissions is honored."""
        answers = {
            "cpus": "4",
            "memory": "8GiB",
            "disk": "20GiB",
            "claude_dangerously_skip_permissions": False,
        }

        config = Config.from_wizard(answers, tmp_path)

        assert config.claude_dangerously_skip_permissions is False


class TestConfigSaveAndLoad:
    """Tests for Config.save() and Config.load()."""

    def test_roundtrip_preserves_all_fields(self, tmp_path: Path) -> None:
        """Saving and loading preserves all config fields."""
        original = Config(
            version="1",
            vm_name="clauded-test123",
            cpus=4,
            memory="8GiB",
            disk="20GiB",
            mount_host="/path/to/project",
            mount_guest="/path/to/project",  # Must match mount_host per spec
            python="3.12",
            node="20",
            java="21",
            kotlin="2.0",
            rust="stable",
            go="1.23.5",
            tools=["docker", "git", "gradle"],
            databases=["postgresql"],
            frameworks=["claude-code"],
        )
        config_path = tmp_path / ".clauded.yaml"

        original.save(config_path)
        loaded = Config.load(config_path)

        assert loaded.version == original.version
        assert loaded.vm_name == original.vm_name
        assert loaded.cpus == original.cpus
        assert loaded.memory == original.memory
        assert loaded.disk == original.disk
        assert loaded.mount_host == original.mount_host
        assert loaded.mount_guest == original.mount_guest
        assert loaded.python == original.python
        assert loaded.node == original.node
        assert loaded.java == original.java
        assert loaded.kotlin == original.kotlin
        assert loaded.rust == original.rust
        assert loaded.go == original.go
        assert loaded.tools == original.tools
        assert loaded.databases == original.databases
        assert loaded.frameworks == original.frameworks

    def test_save_creates_valid_yaml(self, tmp_path: Path) -> None:
        """Saved file is valid YAML with expected structure."""
        config = Config(
            vm_name="clauded-abc12345",
            cpus=4,
            memory="8GiB",
            disk="20GiB",
            mount_host="/test/path",
            mount_guest="/test/path",
            python="3.12",
            node="20",
            java="21",
            kotlin="2.0",
            rust="stable",
            go="1.23.5",
            tools=["docker", "gradle"],
            databases=[],
            frameworks=["claude-code"],
        )
        config_path = tmp_path / ".clauded.yaml"

        config.save(config_path)

        with open(config_path) as f:
            data = yaml.safe_load(f)

        assert data["version"] == "1"
        assert data["vm"]["name"] == "clauded-abc12345"
        assert data["vm"]["cpus"] == 4
        assert data["vm"]["memory"] == "8GiB"
        assert data["vm"]["disk"] == "20GiB"
        assert data["mount"]["host"] == "/test/path"
        assert data["mount"]["guest"] == "/test/path"
        assert data["environment"]["python"] == "3.12"
        assert data["environment"]["node"] == "20"
        assert data["environment"]["java"] == "21"
        assert data["environment"]["kotlin"] == "2.0"
        assert data["environment"]["rust"] == "stable"
        assert data["environment"]["go"] == "1.23.5"
        assert data["environment"]["tools"] == ["docker", "gradle"]
        assert data["environment"]["databases"] == []
        assert data["environment"]["frameworks"] == ["claude-code"]

    def test_load_handles_null_languages(self, tmp_path: Path) -> None:
        """Loading handles null/missing language versions."""
        config_path = tmp_path / ".clauded.yaml"
        config_path.write_text("""
version: "1"
vm:
  name: clauded-test1234
  cpus: 4
  memory: 8GiB
  disk: 20GiB
mount:
  host: /test
  guest: /test
environment:
  python: null
  node: null
  java: null
  kotlin: null
  rust: null
  go: null
  tools: []
  databases: []
  frameworks: []
""")

        config = Config.load(config_path)

        assert config.python is None
        assert config.node is None
        assert config.java is None
        assert config.kotlin is None
        assert config.rust is None
        assert config.go is None

    def test_load_with_custom_image(self, tmp_path: Path) -> None:
        """Loading handles custom vm.image field."""
        config_path = tmp_path / ".clauded.yaml"
        config_path.write_text("""
version: "1"
vm:
  name: clauded-test1234
  cpus: 4
  memory: 8GiB
  disk: 20GiB
  image: https://example.com/custom-alpine.qcow2
mount:
  host: /test
  guest: /test
environment:
  tools: []
  databases: []
  frameworks: []
""")

        config = Config.load(config_path)

        assert config.vm_image == "https://example.com/custom-alpine.qcow2"

    def test_load_without_image_defaults_to_none(self, tmp_path: Path) -> None:
        """Loading config without vm.image field defaults to None."""
        config_path = tmp_path / ".clauded.yaml"
        config_path.write_text("""
version: "1"
vm:
  name: clauded-test1234
  cpus: 4
  memory: 8GiB
  disk: 20GiB
mount:
  host: /test
  guest: /test
environment:
  tools: []
  databases: []
  frameworks: []
""")

        config = Config.load(config_path)

        assert config.vm_image is None

    def test_load_without_claude_section_defaults_permissions_to_true(
        self, tmp_path: Path
    ) -> None:
        """Loading config without claude section defaults permissions to True."""
        config_path = tmp_path / ".clauded.yaml"
        config_path.write_text("""
version: "1"
vm:
  name: clauded-test1234
  cpus: 4
  memory: 8GiB
  disk: 20GiB
mount:
  host: /test
  guest: /test
environment:
  tools: []
  databases: []
  frameworks: []
""")

        config = Config.load(config_path)

        assert config.claude_dangerously_skip_permissions is True

    def test_load_with_claude_permissions_false(self, tmp_path: Path) -> None:
        """Loading config with explicit false permissions is honored."""
        config_path = tmp_path / ".clauded.yaml"
        config_path.write_text("""
version: "1"
vm:
  name: clauded-test1234
  cpus: 4
  memory: 8GiB
  disk: 20GiB
mount:
  host: /test
  guest: /test
environment:
  tools: []
  databases: []
  frameworks: []
claude:
  dangerously_skip_permissions: false
""")

        config = Config.load(config_path)

        assert config.claude_dangerously_skip_permissions is False

    def test_save_with_custom_image(self, tmp_path: Path) -> None:
        """Saving config includes vm.image when set."""
        config = Config(
            vm_name="clauded-test",
            cpus=4,
            memory="8GiB",
            disk="20GiB",
            vm_image="https://example.com/custom.qcow2",
            mount_host="/test",
            mount_guest="/test",
        )
        config_path = tmp_path / ".clauded.yaml"

        config.save(config_path)

        with open(config_path) as f:
            data = yaml.safe_load(f)

        assert data["vm"]["image"] == "https://example.com/custom.qcow2"

    def test_save_without_image_omits_field(self, tmp_path: Path) -> None:
        """Saving config omits vm.image when not set."""
        config = Config(
            vm_name="clauded-test",
            cpus=4,
            memory="8GiB",
            disk="20GiB",
            mount_host="/test",
            mount_guest="/test",
        )
        config_path = tmp_path / ".clauded.yaml"

        config.save(config_path)

        with open(config_path) as f:
            data = yaml.safe_load(f)

        assert "image" not in data["vm"]


class TestConfigDefaults:
    """Tests for Config default values."""

    def test_default_values(self) -> None:
        """Config has sensible defaults."""
        config = Config()

        assert config.version == "1"
        assert config.cpus == 4
        assert config.memory == "8GiB"
        assert config.disk == "20GiB"
        assert config.vm_image is None
        assert config.mount_host == ""
        assert config.mount_guest == ""
        assert config.tools == []
        assert config.databases == []
        assert config.frameworks == []

    def test_claude_dangerously_skip_permissions_defaults_to_true(self) -> None:
        """Claude Code permissions default to skip (auto-accept) for VM convenience."""
        config = Config()

        assert config.claude_dangerously_skip_permissions is True


# Backward compatibility tests for SQLite
class TestSQLiteBackwardCompatibility:
    """Tests ensuring existing configs work without SQLite."""

    def test_config_without_sqlite_loads_correctly(self, tmp_path: Path) -> None:
        """Existing configs without SQLite continue to work."""
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
                "python": "3.12",
                "tools": [],
                "databases": ["postgresql", "redis"],
                "frameworks": ["claude-code"],
            },
        }

        config_file.write_text(yaml.dump(config_data))
        config = Config.load(config_file)

        assert config.databases == ["postgresql", "redis"]
        assert "sqlite" not in config.databases

    def test_config_with_sqlite_loads_correctly(self, tmp_path: Path) -> None:
        """New configs with SQLite load correctly."""
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
                "databases": ["sqlite"],
                "frameworks": ["claude-code"],
            },
        }

        config_file.write_text(yaml.dump(config_data))
        config = Config.load(config_file)

        assert "sqlite" in config.databases

    def test_wizard_answers_without_sqlite(self, tmp_path: Path) -> None:
        """Wizard answers without SQLite produce correct config."""
        answers = {
            "python": "3.12",
            "node": "None",
            "java": "None",
            "kotlin": "None",
            "rust": "None",
            "go": "None",
            "tools": [],
            "databases": ["postgresql"],
            "frameworks": ["claude-code"],
            "cpus": "4",
            "memory": "8GiB",
            "disk": "20GiB",
        }

        config = Config.from_wizard(answers, tmp_path)

        assert config.databases == ["postgresql"]
        assert "sqlite" not in config.databases


class TestConfigVersionValidation:
    """Tests for config version validation."""

    def test_current_version_accepted(self) -> None:
        """Current version '1' is accepted without warnings."""
        result = _validate_version(CURRENT_VERSION)
        assert result == CURRENT_VERSION

    def test_missing_version_defaults_to_current(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Missing version defaults to current with warning."""
        with caplog.at_level(logging.WARNING):
            result = _validate_version(None)

        assert result == CURRENT_VERSION
        assert "missing version field" in caplog.text.lower()

    def test_higher_version_raises_error(self) -> None:
        """Version higher than supported raises ConfigVersionError."""
        future_version = str(int(CURRENT_VERSION) + 1)

        with pytest.raises(ConfigVersionError) as exc_info:
            _validate_version(future_version)

        assert "requires clauded version" in str(exc_info.value)
        assert "upgrade clauded" in str(exc_info.value).lower()

    def test_unrecognized_version_raises_error(self) -> None:
        """Non-numeric version string raises ConfigVersionError."""
        with pytest.raises(ConfigVersionError) as exc_info:
            _validate_version("invalid")

        assert "unrecognized config version" in str(exc_info.value).lower()
        assert "invalid" in str(exc_info.value)

    def test_load_config_with_higher_version_fails(self, tmp_path: Path) -> None:
        """Loading config with future version raises error."""
        config_path = tmp_path / ".clauded.yaml"
        config_path.write_text("""
version: "99"
vm:
  name: clauded-test
  cpus: 4
  memory: 8GiB
  disk: 20GiB
mount:
  host: /test
  guest: /test
environment:
  python: "3.12"
  tools: []
  databases: []
  frameworks: []
""")

        with pytest.raises(ConfigVersionError):
            Config.load(config_path)

    def test_load_config_without_version_warns(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Loading config without version field logs warning."""
        config_path = tmp_path / ".clauded.yaml"
        config_path.write_text("""
vm:
  name: clauded-test
  cpus: 4
  memory: 8GiB
  disk: 20GiB
mount:
  host: /test
  guest: /test
environment:
  python: "3.12"
  tools: []
  databases: []
  frameworks: []
""")

        with caplog.at_level(logging.WARNING):
            config = Config.load(config_path)

        assert config.version == CURRENT_VERSION
        assert "missing version field" in caplog.text.lower()


class TestMountPathValidation:
    """Tests for mount path validation."""

    def test_matching_mount_paths_accepted(self, tmp_path: Path) -> None:
        """Matching mount_host and mount_guest are accepted."""
        config_path = tmp_path / ".clauded.yaml"
        config_path.write_text("""
version: "1"
vm:
  name: clauded-test
  cpus: 4
  memory: 8GiB
  disk: 20GiB
mount:
  host: /project/path
  guest: /project/path
environment:
  tools: []
  databases: []
  frameworks: []
""")

        config = Config.load(config_path)

        assert config.mount_host == "/project/path"
        assert config.mount_guest == "/project/path"

    def test_divergent_mount_paths_auto_corrected(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Divergent mount_guest is auto-corrected to match mount_host."""
        config_path = tmp_path / ".clauded.yaml"
        config_path.write_text("""
version: "1"
vm:
  name: clauded-test
  cpus: 4
  memory: 8GiB
  disk: 20GiB
mount:
  host: /project/path
  guest: /different/path
environment:
  tools: []
  databases: []
  frameworks: []
""")

        with caplog.at_level(logging.WARNING):
            config = Config.load(config_path)

        assert config.mount_host == "/project/path"
        assert config.mount_guest == "/project/path"
        assert "auto-correcting" in caplog.text.lower()
        assert "/different/path" in caplog.text


class TestMigrateConfig:
    """Tests for config migration."""

    def test_migrate_v1_is_noop(self) -> None:
        """Migrating v1 config returns unchanged data."""
        data = {
            "version": "1",
            "vm": {"name": "test", "cpus": 4, "memory": "8GiB", "disk": "20GiB"},
            "mount": {"host": "/test", "guest": "/test"},
            "environment": {"tools": [], "databases": [], "frameworks": []},
        }

        result = _migrate_config(data)

        assert result == data


class TestRuntimeVersionValidation:
    """Tests for runtime version validation."""

    def test_accepts_valid_python_version(self) -> None:
        """Valid Python version is accepted."""
        result = _validate_runtime_version("python", "3.12")
        assert result == "3.12"

    def test_accepts_valid_node_version(self) -> None:
        """Valid Node.js version is accepted."""
        result = _validate_runtime_version("node", "20")
        assert result == "20"

    def test_accepts_valid_go_version(self) -> None:
        """Valid Go version is accepted."""
        result = _validate_runtime_version("go", "1.23.5")
        assert result == "1.23.5"

    def test_accepts_none_version(self) -> None:
        """None version (language not selected) is accepted."""
        result = _validate_runtime_version("python", None)
        assert result is None

    def test_strict_mode_raises_for_invalid_version(self) -> None:
        """Strict mode raises ConfigValidationError for invalid version."""
        with pytest.raises(ConfigValidationError) as exc_info:
            _validate_runtime_version("python", "2.7", strict=True)

        assert "Unsupported Python version '2.7'" in str(exc_info.value)
        assert "Supported versions:" in str(exc_info.value)

    def test_non_strict_mode_warns_for_invalid_version(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Non-strict mode logs warning but returns version."""
        with caplog.at_level(logging.WARNING):
            result = _validate_runtime_version("python", "2.7", strict=False)

        assert result == "2.7"
        assert "Unsupported Python version '2.7'" in caplog.text

    def test_unknown_language_passes_through(self) -> None:
        """Unknown language versions pass through unchanged."""
        result = _validate_runtime_version("unknown", "1.0")
        assert result == "1.0"

    def test_load_config_rejects_invalid_python_version(self, tmp_path: Path) -> None:
        """Loading config with invalid Python version fails."""
        config_path = tmp_path / ".clauded.yaml"
        config_path.write_text("""
version: "1"
vm:
  name: clauded-test
  cpus: 4
  memory: 8GiB
  disk: 20GiB
mount:
  host: /test
  guest: /test
environment:
  python: "2.7"
  tools: []
  databases: []
  frameworks: []
""")

        with pytest.raises(ConfigValidationError) as exc_info:
            Config.load(config_path)

        assert "Unsupported Python version '2.7'" in str(exc_info.value)

    def test_load_config_rejects_invalid_node_version(self, tmp_path: Path) -> None:
        """Loading config with invalid Node.js version fails."""
        config_path = tmp_path / ".clauded.yaml"
        config_path.write_text("""
version: "1"
vm:
  name: clauded-test
  cpus: 4
  memory: 8GiB
  disk: 20GiB
mount:
  host: /test
  guest: /test
environment:
  node: "16"
  tools: []
  databases: []
  frameworks: []
""")

        with pytest.raises(ConfigValidationError) as exc_info:
            Config.load(config_path)

        assert "Unsupported Node.js version '16'" in str(exc_info.value)

    def test_load_config_rejects_invalid_go_version(self, tmp_path: Path) -> None:
        """Loading config with invalid Go version fails."""
        config_path = tmp_path / ".clauded.yaml"
        config_path.write_text("""
version: "1"
vm:
  name: clauded-test
  cpus: 4
  memory: 8GiB
  disk: 20GiB
mount:
  host: /test
  guest: /test
environment:
  go: "1.18"
  tools: []
  databases: []
  frameworks: []
""")

        with pytest.raises(ConfigValidationError) as exc_info:
            Config.load(config_path)

        assert "Unsupported Go version '1.18'" in str(exc_info.value)

    def test_load_config_accepts_valid_versions(self, tmp_path: Path) -> None:
        """Loading config with valid versions succeeds."""
        config_path = tmp_path / ".clauded.yaml"
        config_path.write_text("""
version: "1"
vm:
  name: clauded-test
  cpus: 4
  memory: 8GiB
  disk: 20GiB
mount:
  host: /test
  guest: /test
environment:
  python: "3.12"
  node: "20"
  java: "21"
  kotlin: "2.0"
  rust: "stable"
  go: "1.23.5"
  tools: []
  databases: []
  frameworks: []
""")

        config = Config.load(config_path)

        assert config.python == "3.12"
        assert config.node == "20"
        assert config.java == "21"
        assert config.kotlin == "2.0"
        assert config.rust == "stable"
        assert config.go == "1.23.5"
