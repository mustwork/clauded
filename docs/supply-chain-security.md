# Supply Chain Security

This document describes how clauded handles external downloads during VM provisioning.

## Overview

All external downloads are defined in a single source of truth (`src/clauded/downloads.yml`) with:
- Pinned versions (no "latest" or dynamic version fetching)
- Direct download URLs from official sources
- HTTPS-only transport

## Security Model

Integrity verification relies on **HTTPS transport security**. Hash verification is not used because upstream providers frequently update artifacts in-place without changing version numbers, which breaks checksum verification.

This decision was made after encountering repeated hash mismatches caused by:
- Alpine rebuilding cloud images for security patches
- Installer scripts (uv, bun, rustup) being updated in-place
- Binary releases being rebuilt without version changes

## Downloaded Components

| Component | Source | Notes |
|-----------|--------|-------|
| Alpine image | dl-cdn.alpinelinux.org | Cloud image for Lima VMs |
| Go | go.dev | Language runtime |
| Kotlin | JetBrains GitHub releases | Compiler |
| Maven | Apache CDN | Build tool |
| Gradle | Gradle distributions | Build tool |
| Dart | Google Cloud Storage | SDK |
| Node.js | nodejs.org | Runtime (via Alpine packages) |
| Bun | GitHub releases | JavaScript runtime |
| uv | astral.sh | Python package manager installer |
| rustup | sh.rustup.rs | Rust toolchain installer |

## Other Limitations

- **Claude Code**: Downloaded from Anthropic's distribution bucket (no official checksums published)
- **Custom VM images**: User-specified images via `vm.image` config bypass all verification

## Updating Tool Versions

When a new version of a tool is released, update `src/clauded/downloads.yml`:

### 1. Determine the new download URL

Each tool has a predictable URL pattern:
- Go: `https://go.dev/dl/go{VERSION}.linux-arm64.tar.gz`
- Kotlin: `https://github.com/JetBrains/kotlin/releases/download/v{VERSION}/kotlin-compiler-{VERSION}.zip`
- Maven: `https://dlcdn.apache.org/maven/maven-3/{VERSION}/binaries/apache-maven-{VERSION}-bin.tar.gz`
- Gradle: `https://services.gradle.org/distributions/gradle-{VERSION}-bin.zip`

### 2. Update downloads.yml

Update the version entry:

```yaml
go:
  default_version: "1.24.0"
  versions:
    "1.24.0":
      url: "https://go.dev/dl/go1.24.0.linux-arm64.tar.gz"
    "1.23.5":
      url: "https://go.dev/dl/go1.23.5.linux-arm64.tar.gz"
```

### 3. Test the update

```bash
# Run tests to verify downloads.yml structure
uv run pytest tests/test_downloads.py -v

# Test provisioning with new version
clauded --destroy && clauded
```

## Security Best Practices

1. **Prefer HTTPS** - All download URLs must use HTTPS
2. **Pin specific versions** - Never use "latest" or version ranges
3. **Review changes** - When updating versions, verify the new release is legitimate
4. **Test after updates** - Always test provisioning after changing download metadata
