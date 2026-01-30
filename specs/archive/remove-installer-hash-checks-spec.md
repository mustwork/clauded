# Remove Installer Hash Verification - Requirements Specification

## Problem Statement

Installer scripts for uv, bun, and rustup are updated in-place by upstream providers without changing version numbers, causing hash mismatches that break provisioning. This is the same problem encountered with Alpine Linux cloud images.

Recent example: uv 0.5.24 installer hash changed from `60da9fa...` to `f476e44...` despite the URL being version-pinned to `/uv/0.5.24/install.sh`.

This makes hash pinning impractical for these installer scripts. We need to remove hash verification for these tools and rely on HTTPS transport security instead, following the same pattern used for Alpine images.

## Core Functionality

Remove SHA256 checksum verification for installer scripts that are updated in-place:
- uv installer script (astral.sh)
- bun installer script (bun.sh)
- rustup installer script (sh.rustup.rs)

The system should continue downloading and executing these installer scripts, but without hash verification.

## Functional Requirements

### FR1: Remove checksums from downloads.yml
- Remove `installer_sha256` field for uv, bun, and rustup from `src/clauded/downloads.yml`
- Add explanatory comments explaining why hash verification is not feasible (similar to Alpine)
- Retain version pinning and URLs

**Acceptance Criteria:**
- downloads.yml no longer contains installer_sha256 for uv, bun, rustup
- Comment explains reliance on HTTPS transport security
- Version and URL fields remain unchanged

### FR2: Update Ansible tasks to remove checksum parameter
- Remove `checksum: "sha256:{{ ... }}"` parameter from get_url tasks in:
  - `roles/uv/tasks/main.yml`
  - `roles/rust/tasks/main.yml`
  - `roles/node/tasks/main.yml` (bun section)
- Do not use conditional logic - simply omit the parameter entirely
- Installer download and execution flow remains otherwise unchanged

**Acceptance Criteria:**
- get_url tasks no longer include checksum parameter for these tools
- Tasks continue to download and execute installer scripts successfully
- No warnings or errors from Ansible about missing variables

### FR3: Update test expectations
- Update `tests/test_downloads.py` to reflect that uv, bun, rustup no longer have checksums
- Remove or modify tests that assert presence of installer_sha256 for these tools
- Add tests that assert absence of checksums (similar to Alpine pattern)
- Ensure remaining checksum tests still validate tools with immutable releases (Go, Kotlin, etc.)

**Acceptance Criteria:**
- All tests pass with new downloads.yml structure
- Tests explicitly verify that uv, bun, rustup lack checksums
- Tests continue to verify checksums for tools with immutable releases

### FR4: Update documentation
- Update `docs/supply-chain-security.md`:
  - Move uv, bun, rustup to "Known Limitations" section
  - Explain why hash verification is not feasible for these tools
  - Document reliance on HTTPS transport security
- Update `specs/spec.md`:
  - Modify security model section to reflect changes
  - Document which tools use hash verification vs. HTTPS-only
- Update `CHANGELOG.md`:
  - Add entry under `[Unreleased]` > `Changed` section
  - Explain removal of hash verification for installer scripts

**Acceptance Criteria:**
- Documentation accurately reflects new verification policy
- Known Limitations section includes uv, bun, rustup with clear rationale
- CHANGELOG entry follows project conventions

## Critical Constraints

1. **No binary download changes**: Only remove verification for installer scripts, not for binary downloads (e.g., Go, Kotlin archives still use checksums)
2. **Follow Alpine pattern**: Use the same approach/style as commit 4163131 for Alpine image
3. **HTTPS enforcement**: URLs must remain HTTPS (already enforced, no changes needed)
4. **Version pinning**: Keep version pinning in downloads.yml (only remove checksums)

## Integration Points

- **downloads.yml**: Central metadata file read by Ansible playbooks
- **Ansible roles**: uv, rust, and node roles use downloads metadata
- **Test suite**: test_downloads.py validates downloads.yml structure
- **Documentation**: specs/spec.md and docs/ reference verification policies

## User Preferences

- **Remove checksum parameter entirely** rather than using conditional logic in Ansible tasks
- **Include all three tools** (uv, bun, rustup) for consistency, even though only uv has been observed failing so far
- **Follow Alpine pattern** established in commit 4163131

## Codebase Context

See `.claude/exploration/remove-installer-hash-checks-context.md` for exploration findings.

## Related Artifacts

- **Exploration Context**: `.claude/exploration/remove-installer-hash-checks-context.md`
- **Reference Commit**: 4163131 (Alpine image hash removal)

## Out of Scope

- Removing verification for binary downloads (Go, Kotlin, Maven, Gradle, Node.js remain unchanged)
- Adding checksum verification for Claude Code installer
- Implementing alternative integrity verification methods (signatures, etc.)
- Changing download URLs or version pinning strategy

---

**Note**: This is a requirements specification, not an architecture design.
Edge cases, error handling details, and implementation approach will be
determined by the integration-architect during Phase 2.
