# Multi-Distribution Support

**Created**: 2026-02-07
**Status**: Draft

## Overview

Add support for multiple Linux distributions (Alpine, Ubuntu, and extensible architecture for future distros) via command-line flag and interactive wizard selection. Alpine remains the default. The distribution becomes part of the `.clauded.yaml` config, and changing distro requires full VM recreation with user warning.

## Motivation

Currently, `clauded` is hardcoded to use Alpine Linux. Different projects may benefit from different distributions:
- **Alpine**: Minimal, fast boot, small footprint (current default)
- **Ubuntu**: Broader package availability, familiar to more developers, better compatibility with some tools
- **Future distros**: Debian, Fedora, etc. may be added later

Supporting multiple distros through clean abstraction eliminates branch maintenance overhead and allows users to choose the best fit for their project.

## Goals

1. **Extensible Architecture**: Design system to support 3+ distros without code duplication
2. **User Choice**: Allow distro selection via `--distro` flag and interactive wizard (first wizard step)
3. **Safe Transitions**: Require full VM recreation when distro changes, with clear user warnings
4. **Backward Compatibility**: Existing `.clauded.yaml` files without distro field default to Alpine
5. **Clean Abstraction**: Separate distro-specific logic into provider/variant pattern

## Non-Goals

- In-place distro migration (too complex, error-prone)
- Supporting non-Linux distros (macOS guests, Windows)
- Containerized builds (this is VM-focused)

## Functional Requirements

### FR1: Distribution Configuration

**Schema Extension**:
```yaml
version: "1"
vm:
  name: clauded-a1b2c3d4
  distro: alpine  # NEW: one of 'alpine', 'ubuntu'
  cpus: 4
  memory: 8GiB
  disk: 20GiB
  keep_running: false
mount:
  host: /Users/you/projects/myproject
  guest: /Users/you/projects/myproject
environment:
  # ... existing fields
```

**Validation**:
- `vm.distro` field is required when creating new VMs
- Must be one of supported values: `'alpine'`, `'ubuntu'`
- Invalid distro raises `ConfigValidationError`
- Missing distro on load defaults to `'alpine'` (backward compatibility)

### FR2: CLI Flag Support

**New Flag**: `--distro <name>`
```bash
clauded --distro ubuntu         # Create/connect with Ubuntu
clauded --distro alpine         # Create/connect with Alpine (default)
```

**Behavior**:
- If `.clauded.yaml` doesn't exist: flag sets distro for new config
- If `.clauded.yaml` exists with different distro: error with change instructions
- If flag omitted: use distro from config (or default to Alpine for new VMs)

**Error Handling**:
```bash
# Existing VM is Alpine, user tries:
clauded --distro ubuntu

# Output:
❌ Config distro mismatch: VM uses 'alpine', flag specifies 'ubuntu'
To change distro, edit .clauded.yaml and run 'clauded --reprovision' (will destroy and recreate VM)
```

### FR3: Interactive Wizard Integration

**First Wizard Step** (new):
```
? Select Linux distribution:
  › alpine (recommended - minimal, fast)
    ubuntu (broad compatibility)
```

**Position**:
- First question in wizard (before Python/Node/etc.)
- Default selection: `alpine`
- Arrow keys to navigate, Enter to confirm

**Wizard Flow**:
```
1. Distro selection (NEW)
2. Python version
3. Node.js version
...
```

### FR4: Distro Change Detection and VM Recreation

**Detection Timing**: At VM startup, after boot, via SSH:
1. Start VM (if not running)
2. SSH into VM and read `/etc/clauded.json`
3. Compare `distro` field with `vm.distro` from `.clauded.yaml`
4. If mismatch detected, prompt for recreation

**Rationale**: Checking via SSH after boot is reliable and doesn't require extra metadata files on the host. The VM must be accessible for any operations anyway.

**Change Flow**:
```
1. User edits .clauded.yaml: vm.distro: alpine → ubuntu
2. User runs: clauded --reprovision
3. System detects: config.vm.distro != vm_metadata.distro
4. Prompt user:
   ⚠️  Distribution change detected: alpine → ubuntu
   This requires full VM recreation. All VM state will be lost.
   Project files are safe (mounted from host).

   Continue? (y/N):
5. If yes:
   - Destroy old VM
   - Create new VM with Ubuntu
   - Provision with Ubuntu-specific roles
6. If no:
   - Exit without changes
```

**Alternative**: `clauded --edit` with distro change:
```
# After wizard completes with distro change:
⚠️  You changed distro from 'alpine' to 'ubuntu'
This requires VM recreation. Proceed? (y/N):
```

### FR5: Distro Metadata Storage

**In VM**: Update `/etc/clauded.json` to include distro:
```json
{
  "project_name": "myproject",
  "distro": "alpine",
  "version": "0.13.0",
  "commit": "abc1234",
  "provisioned": "2026-02-07T10:30:00Z"
}
```

**Purpose**:
- Allows detection of distro mismatch
- Useful for debugging and system info display

## Non-Functional Requirements

### NFR1: Backward Compatibility

**Existing Configs**: Any `.clauded.yaml` without `vm.distro` field:
- Loads successfully
- Defaults to `distro: alpine`
- On next `--edit` or `--reprovision`, distro is written to config

**Existing VMs**: Any VM with `/etc/clauded.json` missing the `distro` field:
- Assumes `distro: alpine` (all pre-feature VMs are Alpine)
- No spurious mismatch warnings when upgrading clauded
- On next reprovision, distro field is written to `/etc/clauded.json`

**--distro Flag with Legacy Config**: If `.clauded.yaml` exists without `vm.distro` field:
- Treat missing field as implicit `alpine` (not as "unset")
- `clauded --distro ubuntu` errors: "Config has implicit Alpine default, flag conflicts"
- User must explicitly edit config to change distro

**Migration**: Automatic, no user action required

### NFR2: Extensibility

**Adding New Distro** (e.g., Debian):
1. Add `'debian'` to supported distros constant
2. Create Debian cloud image metadata in `downloads.yml`
3. Create Debian role variants: `common-debian`, etc.
4. Implement `DebianProvider` class (minimal, follows existing pattern)
5. Update wizard options

**Design Constraint**: Adding a new distro should require ONLY:
- Cloud image metadata entry in `downloads.yml`
- New `DistroProvider` implementation (~20 lines)
- New role variants (Ansible files)
- Wizard menu entry

No changes should be required to core logic in `config.py`, `lima.py`, or `provisioner.py` beyond registration/mapping.

### NFR3: Performance

- Distro detection: < 100ms (read from config/metadata)
- VM creation time: comparable to current Alpine (varies by distro)
- Role selection logic: O(1), no conditional tree scanning

### NFR4: Testing

- Unit tests for config validation (valid/invalid distros)
- Integration tests for VM creation with each distro
- Wizard tests for distro selection step
- Distro change flow tests (detection, warning, recreation)

## Architecture Design

### Distribution Provider Pattern

**Abstraction**: Create `DistroProvider` protocol/base class:
```python
# src/clauded/distro.py

from typing import Protocol

class DistroProvider(Protocol):
    """Interface for distro-specific operations."""

    @property
    def name(self) -> str:
        """Distro identifier (alpine, ubuntu)."""
        ...

    @property
    def display_name(self) -> str:
        """Human-readable name for UI."""
        ...

    def get_cloud_image(self) -> dict[str, str]:
        """Return cloud image metadata (url, arch, version)."""
        ...

    def get_ansible_role_prefix(self) -> str:
        """Return prefix for distro-specific roles (e.g., 'alpine-', 'ubuntu-')."""
        ...

    def validate_environment(self, env: dict) -> None:
        """Validate environment config for distro-specific constraints."""
        ...
```

**Implementations**:
- `AlpineProvider`: Alpine-specific logic
- `UbuntuProvider`: Ubuntu-specific logic
- Future: `DebianProvider`, `FedoraProvider`

**Factory**:
```python
def get_distro_provider(distro_name: str) -> DistroProvider:
    """Factory to create appropriate provider."""
    providers = {
        "alpine": AlpineProvider(),
        "ubuntu": UbuntuProvider(),
    }
    if distro_name not in providers:
        raise ValueError(f"Unsupported distro: {distro_name}")
    return providers[distro_name]
```

### Ansible Role Variant Architecture

**Current Structure**:
```
src/clauded/roles/
  ├── common/tasks/main.yml        # Alpine-specific (apk, rc-service)
  ├── python/tasks/main.yml        # Alpine-specific
  ├── docker/tasks/main.yml        # Alpine-specific
  └── ...
```

**New Structure**:
```
src/clauded/roles/
  ├── common-alpine/
  │   └── tasks/main.yml           # Alpine: apk, rc-service, alpine-sdk
  ├── common-ubuntu/
  │   └── tasks/main.yml           # Ubuntu: apt, systemctl, build-essential
  ├── python-alpine/
  │   └── tasks/main.yml           # Alpine: apk add python3
  ├── python-ubuntu/
  │   └── tasks/main.yml           # Ubuntu: apt install python3
  ├── docker-alpine/
  │   └── tasks/main.yml           # Alpine: apk add docker, rc-update add docker
  ├── docker-ubuntu/
  │   └── tasks/main.yml           # Ubuntu: apt install docker.io, systemctl enable docker
  └── ...
```

**Role Selection Logic** (in `provisioner.py`):
```python
def _select_roles(self) -> list[str]:
    """Select Ansible roles based on config and distro."""
    distro = self.config.vm_distro
    roles = [f"common-{distro}"]  # Always include common-{distro}

    if self.config.python_version:
        roles.append(f"python-{distro}")

    if "docker" in self.config.tools:
        roles.append(f"docker-{distro}")

    # ... etc for each language/tool/db

    return roles
```

**Benefits**:
- Clean separation: no conditionals in tasks
- Easy to understand: one role = one distro
- Easy to test: test each role variant independently
- Easy to extend: add new distro = add new role variants

**Drawbacks**:
- More files (mitigated by clear structure)
- Duplication for distro-agnostic roles (acceptable - clarity > DRYness)

### Strict Variants for ALL Roles

**Decision**: All roles use distro-specific variants, even download-based ones.

**Rationale**:
- Consistent mental model: every role has `-alpine` and `-ubuntu` variant
- No conditionals in tasks: cleaner, easier to test
- Future-proof: when adding Debian, just add new variants
- Simpler provisioner: always append `-{distro}` to role name

**Complete Role List** (all need variants):
- `common-alpine`, `common-ubuntu` (base packages, service management)
- `python-alpine`, `python-ubuntu`
- `node-alpine`, `node-ubuntu`
- `java-alpine`, `java-ubuntu`
- `kotlin-alpine`, `kotlin-ubuntu`
- `rust-alpine`, `rust-ubuntu`
- `go-alpine`, `go-ubuntu`
- `dart-alpine`, `dart-ubuntu`
- `c-alpine`, `c-ubuntu`
- `docker-alpine`, `docker-ubuntu`
- `postgresql-alpine`, `postgresql-ubuntu`
- `redis-alpine`, `redis-ubuntu`
- `mysql-alpine`, `mysql-ubuntu`
- `sqlite-alpine`, `sqlite-ubuntu`
- `mongodb-alpine`, `mongodb-ubuntu`
- `uv-alpine`, `uv-ubuntu`
- `poetry-alpine`, `poetry-ubuntu`
- `maven-alpine`, `maven-ubuntu`
- `gradle-alpine`, `gradle-ubuntu`
- `aws_cli-alpine`, `aws_cli-ubuntu`
- `gh-alpine`, `gh-ubuntu`
- `claude_code-alpine`, `claude_code-ubuntu`
- `playwright-alpine`, `playwright-ubuntu`

**Role Validation**: Provisioner MUST validate that all selected role variants exist in `roles/` directory before invoking `ansible-playbook`. If any role is missing, fail with clear error message listing missing roles.

### Lima Config Generation

**Current** (`lima.py`):
```python
def _generate_lima_config(self) -> dict:
    """Generate Lima YAML config for Alpine."""
    alpine_image = get_alpine_image()
    return {
        "images": [{"location": alpine_image["url"], "arch": alpine_image["arch"]}],
        # ...
    }
```

**Updated**:
```python
def _generate_lima_config(self) -> dict:
    """Generate Lima YAML config for configured distro."""
    provider = get_distro_provider(self.config.vm_distro)
    cloud_image = provider.get_cloud_image()

    return {
        "images": [{"location": cloud_image["url"], "arch": cloud_image["arch"]}],
        "cpus": self.config.vm_cpus,
        "memory": self.config.vm_memory,
        "disk": self.config.vm_disk,
        # ... rest of config
    }
```

### Cloud Image Metadata

**Add to `downloads.yml`**:
```yaml
alpine_image:
  url: https://dl-cdn.alpinelinux.org/alpine/v3.21/releases/cloud/alpine-virt-3.21.3-aarch64.iso
  version: "3.21.3"
  arch: aarch64

ubuntu_image:
  url: https://cloud-images.ubuntu.com/minimal/releases/noble/release/ubuntu-24.04-minimal-cloudimg-arm64.img
  version: "24.04"
  arch: aarch64
```

**Update `downloads.py`**:
```python
def get_cloud_image(distro: str) -> dict[str, str]:
    """Get cloud image metadata for specified distro."""
    downloads = get_downloads()
    key = f"{distro}_image"
    if key not in downloads:
        raise DownloadMetadataError(f"No cloud image for distro: {distro}")
    return downloads[key]
```

## User Experience Flow

### Scenario 1: New Project, Default (Alpine)

```bash
cd ~/myproject
clauded

# No .clauded.yaml exists, wizard starts:
? Select Linux distribution: › alpine (recommended - minimal, fast)
? Python version: › 3.12
? Node.js version: › 20
...

# Creates .clauded.yaml with vm.distro: alpine
# Creates Alpine VM
# Provisions with alpine-specific roles
# Drops into shell
```

### Scenario 2: New Project, Ubuntu via Flag

```bash
clauded --distro ubuntu

# Wizard starts with Ubuntu pre-selected:
? Select Linux distribution: › ubuntu (broad compatibility)  [pre-filled]
? Python version: › 3.12
...

# Creates .clauded.yaml with vm.distro: ubuntu
# Creates Ubuntu VM
```

### Scenario 3: Change Distro on Existing Project

```bash
# .clauded.yaml currently has vm.distro: alpine

# User edits .clauded.yaml manually:
vim .clauded.yaml
# Change: vm.distro: alpine → ubuntu

# User reprovisions:
clauded --reprovision

# Output:
⚠️  Distribution change detected: alpine → ubuntu
This requires full VM recreation. All VM state will be lost.
Your project files are safe (mounted from host).

The following will be destroyed:
  - VM 'clauded-a1b2c3d4'
  - All installed packages and databases inside VM

Continue? (y/N): y

Destroying VM 'clauded-a1b2c3d4'... ✓
Creating VM 'clauded-a1b2c3d4' with Ubuntu... ✓
Provisioning Ubuntu environment... ✓

✅ VM recreated with Ubuntu
```

### Scenario 4: Using `--edit` with Distro Change

```bash
clauded --edit

# Wizard shows current values:
? Select Linux distribution: alpine  [current]
  # User changes to: ubuntu

? This will require VM recreation. Continue? (y/N): y

# Same destruction/recreation flow as Scenario 3
```

## Acceptance Criteria

### AC1: Configuration Schema
- [ ] `vm.distro` field is validated on load (must be supported distro or missing)
- [ ] Missing `vm.distro` defaults to `'alpine'`
- [ ] Invalid `vm.distro` raises `ConfigValidationError` with helpful message
- [ ] Updated `.clauded.yaml` written by wizard includes `vm.distro`

### AC2: CLI Flag
- [ ] `clauded --distro alpine` creates Alpine VM
- [ ] `clauded --distro ubuntu` creates Ubuntu VM
- [ ] `clauded --distro invalid` shows error with supported distros
- [ ] `--distro` flag conflicts with existing config show clear error

### AC3: Interactive Wizard
- [ ] Wizard shows distro selection as first question
- [ ] Default selection is `alpine`
- [ ] Selection is pre-filled if `--distro` flag used
- [ ] Generated config includes selected distro

### AC4: Distro Change Detection
- [ ] Changing `vm.distro` in config triggers recreation warning
- [ ] User can confirm or cancel recreation
- [ ] Successful recreation uses new distro
- [ ] `/etc/clauded.json` in VM reflects new distro

### AC5: VM Creation
- [ ] Alpine VM created with Alpine cloud image
- [ ] Ubuntu VM created with Ubuntu cloud image
- [ ] Both distros successfully provision with basic environment
- [ ] `common-alpine` role runs only for Alpine VMs
- [ ] `common-ubuntu` role runs only for Ubuntu VMs

### AC6: Ansible Role Variants
- [ ] ALL roles have distro-specific variants: `common-{distro}`, `python-{distro}`, `docker-{distro}`, etc.
- [ ] No single-variant roles exist (strict variants approach)
- [ ] Provisioner selects correct role variants based on `vm.distro`
- [ ] Provisioner validates all selected roles exist before running Ansible
- [ ] Each role variant is self-contained with no distro conditionals

### AC7: Extensibility
- [ ] Adding new distro requires only: cloud image metadata, role variants, provider implementation
- [ ] No hardcoded distro names in core logic (config.py, lima.py)
- [ ] Distro list defined in single constant/config location

### AC8: Backward Compatibility
- [ ] Existing `.clauded.yaml` files without `vm.distro` load successfully
- [ ] Default to Alpine for legacy configs
- [ ] No breaking changes to existing projects

## Security Considerations

- **Cloud Image Integrity**:
  - Use official Ubuntu/Alpine cloud image URLs
  - Verify HTTPS transport
  - Pin versions in `downloads.yml`

- **Package Manager Security**:
  - Ubuntu: `apt update` requires signature verification
  - Alpine: `apk update` uses signed repositories
  - Both use HTTPS by default

- **Distro Validation**:
  - Allowlist-based (only `'alpine'`, `'ubuntu'`)
  - Reject unknown distros before VM creation

## Migration Strategy

### Phase 1: Infrastructure (Story 1)
1. Add `vm.distro` field to config schema
2. Implement `DistroProvider` protocol and Alpine/Ubuntu implementations
3. Update config validation and defaults
4. Add distro to `/etc/clauded.json` metadata
5. Add Ubuntu cloud image to `downloads.yml`

### Phase 2: CLI and Wizard (Story 2)
1. Add `--distro` flag to CLI
2. Add distro selection as first wizard step
3. Implement distro change detection and warning flow (via SSH after boot)

### Phase 3: Ansible Core Roles (Story 3)
1. Rename existing roles to `-alpine` variants
2. Refactor provisioner to select roles with `-{distro}` suffix
3. Add role existence validation before running Ansible
4. Create `common-ubuntu` role

### Phase 4: Language Role Variants (Story 4)
1. Create Ubuntu variants for: `python`, `node`, `java`, `kotlin`, `rust`, `go`, `dart`, `c`
2. Test language installation on Ubuntu VM

### Phase 5: Tool Role Variants (Story 5)
1. Create Ubuntu variants for: `docker`, `uv`, `poetry`, `maven`, `gradle`, `aws_cli`, `gh`
2. Test tool installation on Ubuntu VM

### Phase 6: Database & Framework Role Variants (Story 6)
1. Create Ubuntu variants for: `postgresql`, `redis`, `mysql`, `sqlite`, `mongodb`
2. Create Ubuntu variants for: `claude_code`, `playwright`
3. Test database services on Ubuntu VM

### Phase 7: Integration and Testing (Story 7)
1. End-to-end tests for both distros
2. Distro change flow tests
3. Documentation updates (README, CHANGELOG)

## Resolved Questions

1. **Ubuntu Version**: Use Ubuntu 24.04 LTS (Noble) or 22.04 LTS (Jammy)?
   - **Decision**: 24.04 LTS (Noble) - longer support until 2029

2. **Role Variant Naming**: Use `common-alpine` or `alpine/common`?
   - **Decision**: `common-alpine` (flat structure, simpler glob patterns)

3. **Distro in VM Name**: Include distro in VM name (e.g., `clauded-ubuntu-a1b2c3d4`)?
   - **Decision**: No (distro stored in metadata, name stability preferred)

4. **Multi-distro Same Project**: Allow switching distro without config change?
   - **Decision**: No (config is source of truth, explicit change required)

5. **Distro Detection Timing**: When to check for distro mismatch?
   - **Decision**: At VM startup, after boot via SSH (read `/etc/clauded.json`)

6. **Role Architecture**: Variants vs conditionals for download-based roles?
   - **Decision**: Strict variants everywhere (no conditionals, all roles have `-alpine`/`-ubuntu`)

7. **Ansible Conditional Pattern**: Which fact to use if conditionals were needed?
   - **Decision**: Use `ansible_distribution` for precise matching (not `os_family`)

8. **Role Validation**: Should provisioner validate role existence?
   - **Decision**: Yes, pre-validate and show clear error if any role variant missing

## References

- [Alpine Linux Cloud Images](https://alpinelinux.org/cloud/)
- [Ubuntu Cloud Images](https://cloud-images.ubuntu.com/)
- [Lima Multi-Arch Support](https://lima-vm.io/docs/config/multi-arch/)
- [Ansible OS Family Facts](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_conditionals.html#ansible-facts-distribution)

## Success Metrics

- Users can successfully create Alpine and Ubuntu VMs
- Distro change flow is clear and prevents accidental data loss
- Adding Debian as 3rd distro validates extensibility (no core logic changes needed)
- No regressions in existing Alpine-only workflows
- All existing tests pass with both distros
