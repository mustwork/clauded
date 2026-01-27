"""Tests for clauded.config module."""

from pathlib import Path

import yaml

from clauded.config import Config


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
            "go": "1.25.6",
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
        assert config.go == "1.25.6"
        assert config.tools == ["docker", "git", "aws-cli", "gradle"]
        assert config.databases == ["postgresql", "redis"]
        assert config.frameworks == ["playwright", "claude-code"]
        assert config.cpus == 8
        assert config.memory == "16GiB"
        assert config.disk == "50GiB"
        assert config.mount_host == str(tmp_path)
        assert config.mount_guest == str(tmp_path)

    def test_generates_unique_vm_name_from_path(self, tmp_path: Path) -> None:
        """VM name is generated from path hash."""
        answers = {"cpus": "4", "memory": "8GiB", "disk": "20GiB"}

        config = Config.from_wizard(answers, tmp_path)

        assert config.vm_name.startswith("clauded-")
        assert len(config.vm_name) == len("clauded-") + 8  # 8 char hash

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
            mount_guest="/workspace",
            python="3.12",
            node="20",
            java="21",
            kotlin="2.0",
            rust="stable",
            go="1.25.6",
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
            go="1.25.6",
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
        assert data["environment"]["go"] == "1.25.6"
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
  guest: /workspace
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


class TestConfigDefaults:
    """Tests for Config default values."""

    def test_default_values(self) -> None:
        """Config has sensible defaults."""
        config = Config()

        assert config.version == "1"
        assert config.cpus == 4
        assert config.memory == "8GiB"
        assert config.disk == "20GiB"
        assert config.mount_host == ""
        assert config.mount_guest == ""
        assert config.tools == []
        assert config.databases == []
        assert config.frameworks == []
