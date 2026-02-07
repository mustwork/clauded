"""Tests for multi-distro cloud image support in downloads module."""

import pytest

from clauded.downloads import DownloadMetadataError, get_cloud_image


class TestGetCloudImage:
    """Test get_cloud_image() function for multi-distro support."""

    def test_get_alpine_cloud_image(self) -> None:
        """get_cloud_image('alpine') returns Alpine cloud image metadata."""
        cloud_image = get_cloud_image("alpine")

        assert isinstance(cloud_image, dict)
        assert "url" in cloud_image
        assert "version" in cloud_image
        assert "arch" in cloud_image

    def test_alpine_image_url_is_https(self) -> None:
        """Alpine cloud image URL uses HTTPS."""
        cloud_image = get_cloud_image("alpine")
        assert cloud_image["url"].startswith("https://")

    def test_alpine_image_arch_is_aarch64(self) -> None:
        """Alpine cloud image arch is aarch64."""
        cloud_image = get_cloud_image("alpine")
        assert cloud_image["arch"] == "aarch64"

    def test_alpine_image_has_version(self) -> None:
        """Alpine cloud image has version field."""
        cloud_image = get_cloud_image("alpine")
        assert "version" in cloud_image
        assert cloud_image["version"]  # Non-empty

    def test_get_ubuntu_cloud_image(self) -> None:
        """get_cloud_image('ubuntu') returns Ubuntu cloud image metadata."""
        cloud_image = get_cloud_image("ubuntu")

        assert isinstance(cloud_image, dict)
        assert "url" in cloud_image
        assert "version" in cloud_image
        assert "arch" in cloud_image

    def test_ubuntu_image_url_is_https(self) -> None:
        """Ubuntu cloud image URL uses HTTPS."""
        cloud_image = get_cloud_image("ubuntu")
        assert cloud_image["url"].startswith("https://")

    def test_ubuntu_image_version_is_24_04(self) -> None:
        """Ubuntu cloud image version is 24.04 (Noble LTS)."""
        cloud_image = get_cloud_image("ubuntu")
        assert cloud_image["version"] == "24.04"

    def test_ubuntu_image_arch_is_aarch64(self) -> None:
        """Ubuntu cloud image arch is aarch64."""
        cloud_image = get_cloud_image("ubuntu")
        assert cloud_image["arch"] == "aarch64"

    def test_raises_for_unsupported_distro(self) -> None:
        """get_cloud_image raises DownloadMetadataError for unsupported distro."""
        with pytest.raises(DownloadMetadataError, match="No cloud image for distro"):
            get_cloud_image("fedora")

    def test_error_message_includes_distro_name(self) -> None:
        """Error message includes the distro name that was requested."""
        with pytest.raises(DownloadMetadataError, match="fedora"):
            get_cloud_image("fedora")

    def test_alpine_image_different_from_ubuntu(self) -> None:
        """Alpine and Ubuntu cloud images have different URLs."""
        alpine = get_cloud_image("alpine")
        ubuntu = get_cloud_image("ubuntu")

        assert alpine["url"] != ubuntu["url"]
        # Versions will differ
        assert alpine["version"] != ubuntu["version"]

    def test_returns_dict_copy(self) -> None:
        """get_cloud_image returns a copy (not reference to cached data)."""
        image1 = get_cloud_image("alpine")
        image2 = get_cloud_image("alpine")

        # Should have same content
        assert image1 == image2

        # Modifying one shouldn't affect the other
        image1["test_key"] = "test_value"
        assert "test_key" not in image2
