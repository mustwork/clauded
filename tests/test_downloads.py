"""Tests for clauded.downloads module - supply chain integrity verification."""

import tempfile
from pathlib import Path

import pytest

from clauded.downloads import (
    DownloadMetadataError,
    IntegrityError,
    get_alpine_image,
    get_downloads,
    get_tool_metadata,
    verify_sha256,
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
        """Returns dict with url, version, arch keys.

        Note: sha256 is intentionally not included because Alpine rebuilds
        images in-place for security patches without changing the version.
        """
        image = get_alpine_image()

        assert "url" in image
        assert "version" in image
        assert "arch" in image
        # sha256 intentionally omitted - Alpine images are rebuilt in-place
        assert "sha256" not in image

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
        assert "sha256" in meta
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
        assert "sha256" in meta

    def test_uv_metadata(self) -> None:
        """Returns UV installer metadata."""
        meta = get_tool_metadata("uv")

        assert "version" in meta
        assert "installer_url" in meta
        assert "installer_sha256" in meta

    def test_unknown_tool_raises_error(self) -> None:
        """Raises DownloadMetadataError for unknown tool."""
        with pytest.raises(DownloadMetadataError, match="Unknown tool"):
            get_tool_metadata("unknown_tool")

    def test_unknown_version_raises_error(self) -> None:
        """Raises DownloadMetadataError for unknown version."""
        with pytest.raises(DownloadMetadataError, match="Version .* not found"):
            get_tool_metadata("go", "999.999.999")


class TestVerifySha256:
    """Tests for verify_sha256() function."""

    def test_valid_checksum_passes(self) -> None:
        """Does not raise when checksum matches."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"hello world\n")
            temp_path = Path(f.name)

        try:
            # SHA256 of "hello world\n"
            expected = (
                "a948904f2f0f479b8f8197694b30184b0d2ed1c1cd2a1ec0fb85d299a192a447"
            )
            verify_sha256(temp_path, expected)  # Should not raise
        finally:
            temp_path.unlink()

    def test_invalid_checksum_raises_error(self) -> None:
        """Raises IntegrityError when checksum does not match."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"hello world\n")
            temp_path = Path(f.name)

        try:
            wrong_checksum = "0" * 64
            with pytest.raises(IntegrityError, match="Checksum verification failed"):
                verify_sha256(temp_path, wrong_checksum)
        finally:
            temp_path.unlink()

    def test_missing_file_raises_error(self) -> None:
        """Raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            verify_sha256(Path("/nonexistent/file.txt"), "0" * 64)

    def test_case_insensitive_comparison(self) -> None:
        """Checksum comparison is case-insensitive."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"hello world\n")
            temp_path = Path(f.name)

        try:
            # Test with uppercase checksum
            expected_upper = (
                "A948904F2F0F479B8F8197694B30184B0D2ED1C1CD2A1EC0FB85D299A192A447"
            )
            verify_sha256(temp_path, expected_upper)  # Should not raise
        finally:
            temp_path.unlink()


class TestDownloadsYamlIntegrity:
    """Tests to verify downloads.yml file has valid structure."""

    def test_all_tools_have_sha256(self) -> None:
        """All tools with immutable releases have SHA256 checksums defined.

        Note: Alpine image intentionally excluded - Alpine rebuilds images
        in-place for security patches without changing the version.
        """
        downloads = get_downloads()

        # Tools with multiple versions (immutable release artifacts)
        for tool in ["go", "kotlin", "maven", "gradle"]:
            assert "versions" in downloads[tool], f"{tool} missing versions"
            for version, meta in downloads[tool]["versions"].items():
                assert "sha256" in meta, f"{tool} {version} missing sha256"
                sha256_len = len(meta["sha256"])
                assert sha256_len == 64, f"{tool} {version} invalid sha256 length"

        # Single-version tools
        assert "installer_sha256" in downloads["uv"]
        assert "installer_sha256" in downloads["rustup"]

        # Alpine image intentionally has no sha256 - rebuilt in-place upstream

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
