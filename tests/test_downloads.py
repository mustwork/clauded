"""Tests for clauded.downloads module."""

import pytest

from clauded.downloads import (
    DownloadMetadataError,
    get_alpine_image,
    get_downloads,
    get_tool_metadata,
)


class TestGetDownloads:
    """Tests for get_downloads() function."""

    def test_returns_dict(self) -> None:
        """Returns a dictionary of download metadata."""
        downloads = get_downloads()

        assert isinstance(downloads, dict)

    def test_contains_expected_tools(self) -> None:
        """Contains metadata for all expected tools."""
        downloads = get_downloads()

        expected_tools = [
            "alpine_image",
            "go",
            "kotlin",
            "uv",
            "bun",
            "rustup",
            "maven",
            "gradle",
        ]
        for tool in expected_tools:
            assert tool in downloads, f"Missing tool: {tool}"

    def test_caches_result(self) -> None:
        """Returns the same cached dictionary on subsequent calls."""
        downloads1 = get_downloads()
        downloads2 = get_downloads()

        assert downloads1 is downloads2


class TestGetAlpineImage:
    """Tests for get_alpine_image() function."""

    def test_returns_dict_with_required_keys(self) -> None:
        """Returns dict with url, version, arch keys."""
        image = get_alpine_image()

        assert "url" in image
        assert "version" in image
        assert "arch" in image

    def test_url_is_alpine_cdn(self) -> None:
        """URL points to Alpine Linux CDN."""
        image = get_alpine_image()

        assert "dl-cdn.alpinelinux.org" in image["url"]


class TestGetToolMetadata:
    """Tests for get_tool_metadata() function."""

    def test_go_default_version(self) -> None:
        """Returns default Go version when version is None."""
        meta = get_tool_metadata("go")

        assert "version" in meta
        assert "url" in meta
        assert "go.dev/dl" in meta["url"]

    def test_go_specific_version(self) -> None:
        """Returns specific Go version metadata."""
        meta = get_tool_metadata("go", "1.23.5")

        assert meta["version"] == "1.23.5"
        assert "1.23.5" in meta["url"]

    def test_kotlin_default_version(self) -> None:
        """Returns default Kotlin version when version is None."""
        meta = get_tool_metadata("kotlin")

        assert "version" in meta
        assert "url" in meta

    def test_uv_metadata(self) -> None:
        """Returns UV installer metadata."""
        meta = get_tool_metadata("uv")

        assert "version" in meta
        assert "installer_url" in meta

    def test_unknown_tool_raises_error(self) -> None:
        """Raises DownloadMetadataError for unknown tool."""
        with pytest.raises(DownloadMetadataError, match="Unknown tool"):
            get_tool_metadata("unknown_tool")

    def test_unknown_version_raises_error(self) -> None:
        """Raises DownloadMetadataError for unknown version."""
        with pytest.raises(DownloadMetadataError, match="Version .* not found"):
            get_tool_metadata("go", "999.999.999")


class TestDownloadsYamlIntegrity:
    """Tests to verify downloads.yml file has valid structure."""

    def test_all_tools_have_urls(self) -> None:
        """All tools have download URLs defined."""
        downloads = get_downloads()

        # Tools with multiple versions
        for tool in ["go", "kotlin", "maven", "gradle"]:
            for version, meta in downloads[tool]["versions"].items():
                assert "url" in meta, f"{tool} {version} missing url"
                url = meta["url"]
                assert url.startswith("https://"), f"{tool} {version} url not HTTPS"

        # Single-version tools
        assert "installer_url" in downloads["uv"]
        assert downloads["uv"]["installer_url"].startswith("https://")

        # Alpine image
        assert "url" in downloads["alpine_image"]
        assert downloads["alpine_image"]["url"].startswith("https://")

    def test_bun_binary_url(self) -> None:
        """Bun binary has URL defined."""
        downloads = get_downloads()

        assert "binary" in downloads["bun"]
        assert "linux-aarch64" in downloads["bun"]["binary"]
        assert "url" in downloads["bun"]["binary"]["linux-aarch64"]
        assert downloads["bun"]["binary"]["linux-aarch64"]["url"].startswith("https://")
