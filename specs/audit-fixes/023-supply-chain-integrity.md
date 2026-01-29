# Supply Chain Integrity for Downloads

**Audit Reference**: Supply Chain #1 | Severity: 9/10
**Source**: internal audit (2026-01-29)

## Problem

Provisioning roles download and execute remote binaries/scripts without version pinning,
checksums, or signature verification. This is non-reproducible and exposes the VM
build to upstream compromise or MITM attacks.

Observed patterns:
- `curl | sh` installs (uv, bun, rustup)
- `get_url` downloads without checksum (Go tarball, Kotlin zip)
- Claude Code binary fetched from a public bucket using a mutable "latest" pointer
- Lima base image URL is hardcoded with no checksum verification

## Requirements

### FR-1: Pin Versions for All External Downloads
Every externally downloaded tool must be pinned to an explicit version string in
configuration or role defaults. Avoid "latest".

### FR-2: Verify Integrity (Checksum or Signature)
For each download, validate an official SHA256 checksum or signature.
- If upstream provides signatures, verify with known public keys.
- If upstream only provides checksums, validate SHA256 against an expected value.

### FR-3: Centralize Download Metadata
Create a single source of truth for download URLs, versions, and checksums
(e.g., `roles/common/defaults/main.yml` or a dedicated YAML file) to avoid
hardcoding across roles.

### FR-4: Lima Image Verification
Add checksum verification or use a Lima image entry that includes `digest` or
checksum metadata. If Lima does not support it directly, verify the downloaded
image prior to use and fail provisioning on mismatch.

### FR-5: Document Security Posture
Document the integrity verification approach and how to update versions and
checksums when releases change.

## Affected Files

- `src/clauded/roles/node/tasks/main.yml`
- `src/clauded/roles/uv/tasks/main.yml`
- `src/clauded/roles/rust/tasks/main.yml`
- `src/clauded/roles/go/tasks/main.yml`
- `src/clauded/roles/kotlin/tasks/main.yml`
- `src/clauded/roles/claude_code/tasks/main.yml`
- `src/clauded/lima.py`
- `docs/` (update documentation)
