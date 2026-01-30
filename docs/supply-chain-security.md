# Supply Chain Security

This document describes how clauded verifies the integrity of external downloads during VM provisioning.

## Overview

All external downloads are defined in a single source of truth (`src/clauded/downloads.yml`) with:
- Pinned versions (no "latest" or dynamic version fetching)
- SHA256 checksums for integrity verification
- Direct download URLs from official sources

## Verified Components

| Component | Source | Verification |
|-----------|--------|--------------|
| Go | go.dev | SHA256 checksum via Ansible get_url |
| Kotlin | JetBrains GitHub releases | SHA256 checksum via Ansible get_url |
| Maven | Apache CDN | SHA256 checksum via Ansible get_url |
| Gradle | Gradle distributions | SHA256 checksum via Ansible get_url |
| Node.js | nodejs.org | SHA256 checksum via Ansible get_url |
| Bun | GitHub releases | Binary SHA256 checksum via Ansible get_url |

## Known Limitations

### Installer Scripts Without Hash Verification

The following tools use installer scripts that are updated in-place by upstream providers without changing version numbers:

- **uv** (astral.sh): Python package manager installer
- **bun** (bun.sh): JavaScript runtime installer
- **rustup** (sh.rustup.rs): Rust toolchain installer

Hash verification is not feasible for these scripts because upstream providers update them in-place for bug fixes and security patches without changing URLs or version numbers. This breaks checksum verification.

**Security Model**: These installer scripts rely on HTTPS transport security rather than checksum verification. This is the same approach used for Alpine Linux cloud images.

**Mitigation**: Version-pinned URLs are still used where available (e.g., uv), and all downloads use HTTPS to prevent tampering in transit.

Note: Binary downloads for bun still use hash verification. Only the installer script lacks hash verification.

### Other Limitations

- **Alpine Linux cloud image**: Alpine rebuilds cloud images in-place for security patches without changing the version number, making hash pinning impractical. Integrity relies on HTTPS transport security. Lima caches the image after first download.
- **Claude Code**: Downloaded from Anthropic's distribution bucket without checksum verification (no official checksums published by Anthropic)
- **Custom VM images**: User-specified images via `vm.image` config bypass checksum verification

## Updating Tool Versions

When a new version of a tool is released, update `src/clauded/downloads.yml`:

### 1. Determine the new download URL

Each tool has a predictable URL pattern:
- Go: `https://go.dev/dl/go{VERSION}.linux-arm64.tar.gz`
- Kotlin: `https://github.com/JetBrains/kotlin/releases/download/v{VERSION}/kotlin-compiler-{VERSION}.zip`
- Maven: `https://dlcdn.apache.org/maven/maven-3/{VERSION}/binaries/apache-maven-{VERSION}-bin.tar.gz`
- Gradle: `https://services.gradle.org/distributions/gradle-{VERSION}-bin.zip`

### 2. Obtain the official checksum

Always use official checksums from the tool maintainers:

**Go**
```bash
curl -sL https://go.dev/dl/?mode=json | jq '.[] | select(.version=="go1.23.5") | .files[] | select(.arch=="arm64" and .os=="linux")'
# Or visit: https://go.dev/dl/
```

**Kotlin**
```bash
# Checksums available on the GitHub releases page
# Or download and compute:
curl -sL https://github.com/JetBrains/kotlin/releases/download/v2.0.21/kotlin-compiler-2.0.21.zip | sha256sum
```

**Maven**
```bash
curl -sL https://dlcdn.apache.org/maven/maven-3/3.9.9/binaries/apache-maven-3.9.9-bin.tar.gz.sha512
# Convert SHA512 to SHA256 by downloading and computing:
curl -sL https://dlcdn.apache.org/maven/maven-3/3.9.9/binaries/apache-maven-3.9.9-bin.tar.gz | sha256sum
```

**Gradle**
```bash
# Checksums available at:
curl -sL https://services.gradle.org/distributions/gradle-8.12-bin.zip.sha256
```

### 3. Update downloads.yml

Add or update the version entry:

```yaml
go:
  default_version: "1.23.5"
  versions:
    "1.23.5":
      url: "https://go.dev/dl/go1.23.5.linux-arm64.tar.gz"
      sha256: "47c84d332d8b26206a7e1e3d7f2aa98fd31c53d9a025e8a7d2d9378c5f168d31"
    # Add new version here
    "1.24.0":
      url: "https://go.dev/dl/go1.24.0.linux-arm64.tar.gz"
      sha256: "<new-checksum>"
```

### 4. Test the update

```bash
# Run tests to verify downloads.yml structure
uv run pytest tests/test_downloads.py -v

# Test provisioning with new version
clauded --destroy && clauded
```

## Security Best Practices

1. **Never use unverified checksums** - Always obtain checksums from official sources
2. **Prefer HTTPS** - All download URLs must use HTTPS
3. **Pin specific versions** - Never use "latest" or version ranges
4. **Review changes** - When updating versions, verify the new release is legitimate
5. **Test after updates** - Always test provisioning after changing download metadata
