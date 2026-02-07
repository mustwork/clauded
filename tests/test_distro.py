"""Tests for distro provider infrastructure."""

import pytest

from clauded.distro import (
    SUPPORTED_DISTROS,
    AlpineProvider,
    UbuntuProvider,
    get_distro_provider,
)


class TestSupportedDistros:
    """Test SUPPORTED_DISTROS constant."""

    def test_contains_alpine(self) -> None:
        """Alpine is in supported distros."""
        assert "alpine" in SUPPORTED_DISTROS

    def test_contains_ubuntu(self) -> None:
        """Ubuntu is in supported distros."""
        assert "ubuntu" in SUPPORTED_DISTROS

    def test_is_list_of_strings(self) -> None:
        """SUPPORTED_DISTROS is a list of strings."""
        assert isinstance(SUPPORTED_DISTROS, list)
        assert all(isinstance(d, str) for d in SUPPORTED_DISTROS)


class TestAlpineProvider:
    """Test AlpineProvider implementation."""

    def test_name_returns_alpine(self) -> None:
        """AlpineProvider.name returns 'alpine'."""
        provider = AlpineProvider()
        assert provider.name == "alpine"

    def test_display_name_returns_alpine_linux(self) -> None:
        """AlpineProvider.display_name returns 'Alpine Linux'."""
        provider = AlpineProvider()
        assert provider.display_name == "Alpine Linux"

    def test_get_cloud_image_returns_dict(self) -> None:
        """AlpineProvider.get_cloud_image() returns dict with required keys."""
        provider = AlpineProvider()
        cloud_image = provider.get_cloud_image()

        assert isinstance(cloud_image, dict)
        assert "url" in cloud_image
        assert "version" in cloud_image
        assert "arch" in cloud_image

    def test_get_cloud_image_url_is_https(self) -> None:
        """AlpineProvider cloud image URL uses HTTPS."""
        provider = AlpineProvider()
        cloud_image = provider.get_cloud_image()

        assert cloud_image["url"].startswith("https://")

    def test_get_cloud_image_arch_is_aarch64(self) -> None:
        """AlpineProvider cloud image arch is aarch64."""
        provider = AlpineProvider()
        cloud_image = provider.get_cloud_image()

        assert cloud_image["arch"] == "aarch64"

    def test_get_ansible_role_prefix_returns_empty(self) -> None:
        """AlpineProvider.get_ansible_role_prefix() returns empty string."""
        provider = AlpineProvider()
        assert provider.get_ansible_role_prefix() == ""

    def test_validate_environment_accepts_any_env(self) -> None:
        """AlpineProvider.validate_environment() accepts any environment."""
        provider = AlpineProvider()
        # Should not raise for any env dict
        provider.validate_environment({"python": "3.12", "node": "20"})
        provider.validate_environment({})
        provider.validate_environment({"databases": ["postgresql"]})


class TestUbuntuProvider:
    """Test UbuntuProvider implementation."""

    def test_name_returns_ubuntu(self) -> None:
        """UbuntuProvider.name returns 'ubuntu'."""
        provider = UbuntuProvider()
        assert provider.name == "ubuntu"

    def test_display_name_returns_ubuntu(self) -> None:
        """UbuntuProvider.display_name returns 'Ubuntu'."""
        provider = UbuntuProvider()
        assert provider.display_name == "Ubuntu"

    def test_get_cloud_image_returns_dict(self) -> None:
        """UbuntuProvider.get_cloud_image() returns dict with required keys."""
        provider = UbuntuProvider()
        cloud_image = provider.get_cloud_image()

        assert isinstance(cloud_image, dict)
        assert "url" in cloud_image
        assert "version" in cloud_image
        assert "arch" in cloud_image

    def test_get_cloud_image_url_is_https(self) -> None:
        """UbuntuProvider cloud image URL uses HTTPS."""
        provider = UbuntuProvider()
        cloud_image = provider.get_cloud_image()

        assert cloud_image["url"].startswith("https://")

    def test_get_cloud_image_version_is_24_04(self) -> None:
        """UbuntuProvider cloud image version is 24.04."""
        provider = UbuntuProvider()
        cloud_image = provider.get_cloud_image()

        assert cloud_image["version"] == "24.04"

    def test_get_cloud_image_arch_is_aarch64(self) -> None:
        """UbuntuProvider cloud image arch is aarch64."""
        provider = UbuntuProvider()
        cloud_image = provider.get_cloud_image()

        assert cloud_image["arch"] == "aarch64"

    def test_get_ansible_role_prefix_returns_empty(self) -> None:
        """UbuntuProvider.get_ansible_role_prefix() returns empty string."""
        provider = UbuntuProvider()
        assert provider.get_ansible_role_prefix() == ""

    def test_validate_environment_accepts_any_env(self) -> None:
        """UbuntuProvider.validate_environment() accepts any environment."""
        provider = UbuntuProvider()
        # Should not raise for any env dict
        provider.validate_environment({"python": "3.12", "node": "20"})
        provider.validate_environment({})
        provider.validate_environment({"databases": ["postgresql"]})


class TestGetDistroProvider:
    """Test get_distro_provider() factory function."""

    def test_returns_alpine_provider_for_alpine(self) -> None:
        """get_distro_provider('alpine') returns AlpineProvider."""
        provider = get_distro_provider("alpine")

        assert isinstance(provider, AlpineProvider)
        assert provider.name == "alpine"

    def test_returns_ubuntu_provider_for_ubuntu(self) -> None:
        """get_distro_provider('ubuntu') returns UbuntuProvider."""
        provider = get_distro_provider("ubuntu")

        assert isinstance(provider, UbuntuProvider)
        assert provider.name == "ubuntu"

    def test_raises_for_unsupported_distro(self) -> None:
        """get_distro_provider raises ValueError for unsupported distro."""
        with pytest.raises(ValueError, match="Unsupported distro: fedora"):
            get_distro_provider("fedora")

    def test_error_message_lists_supported_distros(self) -> None:
        """Error message includes list of supported distros."""
        with pytest.raises(ValueError, match="alpine.*ubuntu"):
            get_distro_provider("invalid")

    def test_is_deterministic(self) -> None:
        """Same distro string returns same provider type."""
        provider1 = get_distro_provider("alpine")
        provider2 = get_distro_provider("alpine")

        # Should return same type (though different instances is fine)
        assert isinstance(provider1, type(provider2))
        assert provider1.name == provider2.name
