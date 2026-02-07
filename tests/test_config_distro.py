"""Tests for config distro field support."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import yaml

from clauded.config import Config, ConfigValidationError


class TestConfigDistroField:
    """Test vm_distro field in Config."""

    def test_default_distro_is_alpine(self) -> None:
        """Config default distro is 'alpine'."""
        config = Config(vm_name="test-vm", mount_host="/test", mount_guest="/test")
        assert config.vm_distro == "alpine"

    def test_can_create_with_alpine_distro(self) -> None:
        """Config can be created with distro='alpine'."""
        config = Config(
            vm_name="test-vm",
            vm_distro="alpine",
            mount_host="/test",
            mount_guest="/test",
        )
        assert config.vm_distro == "alpine"

    def test_can_create_with_ubuntu_distro(self) -> None:
        """Config can be created with distro='ubuntu'."""
        config = Config(
            vm_name="test-vm",
            vm_distro="ubuntu",
            mount_host="/test",
            mount_guest="/test",
        )
        assert config.vm_distro == "ubuntu"


class TestConfigSaveDistro:
    """Test saving config with distro field."""

    def test_save_includes_distro_field(self) -> None:
        """Config.save() includes vm.distro field in YAML."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".clauded.yaml"
            config = Config(
                vm_name="test-vm",
                vm_distro="ubuntu",
                mount_host="/test/project",
                mount_guest="/test/project",
            )

            config.save(config_path)

            with open(config_path) as f:
                data = yaml.safe_load(f)

            assert "vm" in data
            assert "distro" in data["vm"]
            assert data["vm"]["distro"] == "ubuntu"

    def test_save_distro_before_cpus(self) -> None:
        """vm.distro appears in saved YAML after name."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".clauded.yaml"
            config = Config(
                vm_name="test-vm",
                vm_distro="alpine",
                mount_host="/test/project",
                mount_guest="/test/project",
            )

            config.save(config_path)

            # Read as text to check ordering
            with open(config_path) as f:
                content = f.read()

            # vm.distro should appear after vm.name but before cpus
            name_pos = content.find("name:")
            distro_pos = content.find("distro:")
            cpus_pos = content.find("cpus:")

            assert name_pos < distro_pos < cpus_pos


class TestConfigLoadDistro:
    """Test loading config with distro field."""

    def test_load_with_alpine_distro(self) -> None:
        """Config.load() correctly loads distro='alpine'."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".clauded.yaml"

            # Create config file with alpine distro
            data = {
                "version": "1",
                "vm": {
                    "name": "test-vm",
                    "distro": "alpine",
                    "cpus": 4,
                    "memory": "8GiB",
                    "disk": "20GiB",
                },
                "mount": {"host": "/test/project", "guest": "/test/project"},
                "environment": {},
            }

            with open(config_path, "w") as f:
                yaml.dump(data, f)

            config = Config.load(config_path)

            assert config.vm_distro == "alpine"

    def test_load_with_ubuntu_distro(self) -> None:
        """Config.load() correctly loads distro='ubuntu'."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".clauded.yaml"

            data = {
                "version": "1",
                "vm": {
                    "name": "test-vm",
                    "distro": "ubuntu",
                    "cpus": 4,
                    "memory": "8GiB",
                    "disk": "20GiB",
                },
                "mount": {"host": "/test/project", "guest": "/test/project"},
                "environment": {},
            }

            with open(config_path, "w") as f:
                yaml.dump(data, f)

            config = Config.load(config_path)

            assert config.vm_distro == "ubuntu"

    def test_load_missing_distro_defaults_to_alpine(self) -> None:
        """Config.load() defaults to alpine when distro missing (compat)."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".clauded.yaml"

            # Legacy config without distro field
            data = {
                "version": "1",
                "vm": {
                    "name": "test-vm",
                    "cpus": 4,
                    "memory": "8GiB",
                    "disk": "20GiB",
                },
                "mount": {"host": "/test/project", "guest": "/test/project"},
                "environment": {},
            }

            with open(config_path, "w") as f:
                yaml.dump(data, f)

            config = Config.load(config_path)

            assert config.vm_distro == "alpine"

    def test_load_invalid_distro_raises_error(self) -> None:
        """Config.load() raises ConfigValidationError for invalid distro."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".clauded.yaml"

            data = {
                "version": "1",
                "vm": {
                    "name": "test-vm",
                    "distro": "fedora",  # Invalid
                    "cpus": 4,
                    "memory": "8GiB",
                    "disk": "20GiB",
                },
                "mount": {"host": "/test/project", "guest": "/test/project"},
                "environment": {},
            }

            with open(config_path, "w") as f:
                yaml.dump(data, f)

            with pytest.raises(ConfigValidationError, match="Unsupported distro"):
                Config.load(config_path)

    def test_error_message_lists_supported_distros(self) -> None:
        """Invalid distro error includes list of supported distros."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".clauded.yaml"

            data = {
                "version": "1",
                "vm": {
                    "name": "test-vm",
                    "distro": "invalid",
                    "cpus": 4,
                    "memory": "8GiB",
                    "disk": "20GiB",
                },
                "mount": {"host": "/test/project", "guest": "/test/project"},
                "environment": {},
            }

            with open(config_path, "w") as f:
                yaml.dump(data, f)

            with pytest.raises(ConfigValidationError, match="alpine.*ubuntu"):
                Config.load(config_path)


class TestConfigDistroRoundTrip:
    """Test save/load round-trip preserves distro field."""

    def test_alpine_round_trip(self) -> None:
        """Saving and loading config preserves alpine distro."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".clauded.yaml"

            original = Config(
                vm_name="test-vm",
                vm_distro="alpine",
                mount_host="/test/project",
                mount_guest="/test/project",
                python="3.12",
            )

            original.save(config_path)
            loaded = Config.load(config_path)

            assert loaded.vm_distro == "alpine"

    def test_ubuntu_round_trip(self) -> None:
        """Saving and loading config preserves ubuntu distro."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".clauded.yaml"

            original = Config(
                vm_name="test-vm",
                vm_distro="ubuntu",
                mount_host="/test/project",
                mount_guest="/test/project",
                python="3.12",
                node="20",
            )

            original.save(config_path)
            loaded = Config.load(config_path)

            assert loaded.vm_distro == "ubuntu"

    def test_round_trip_preserves_other_fields(self) -> None:
        """Distro field doesn't interfere with other config fields."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".clauded.yaml"

            original = Config(
                vm_name="test-vm",
                vm_distro="ubuntu",
                cpus=8,
                memory="16GiB",
                disk="40GiB",
                mount_host="/test/project",
                mount_guest="/test/project",
                python="3.11",
                node="22",
                tools=["docker", "git"],
                databases=["postgresql"],
            )

            original.save(config_path)
            loaded = Config.load(config_path)

            assert loaded.vm_distro == "ubuntu"
            assert loaded.cpus == 8
            assert loaded.memory == "16GiB"
            assert loaded.python == "3.11"
            assert loaded.node == "22"
            assert loaded.tools == ["docker", "git"]
