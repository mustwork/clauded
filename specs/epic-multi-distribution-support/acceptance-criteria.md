# Acceptance Criteria: Multi-Distribution Support

Generated: 2026-02-07T00:00:00Z
Source: spec.md

## Overview

These criteria verify the system can support multiple Linux distributions (Alpine, Ubuntu) through a clean provider abstraction pattern, with safe distro switching via VM recreation, backward compatibility with existing Alpine-only configs, and an extensible architecture for future distributions.

## Criteria

### AC-001: Config schema accepts valid distro field
- **Description**: The `vm.distro` field in `.clauded.yaml` accepts supported distribution names ('alpine', 'ubuntu') and is properly validated during config load
- **Verification**: Load config with `vm.distro: alpine` and `vm.distro: ubuntu` - both should succeed without errors. Check config object has correct distro value.
- **Type**: unit
- **Source**: FR1 - Distribution Configuration (Schema Extension, Validation)

### AC-002: Config schema rejects invalid distro values
- **Description**: Config validation raises `ConfigValidationError` when `vm.distro` contains unsupported distribution name
- **Verification**: Attempt to load config with `vm.distro: fedora` or `vm.distro: invalid` - should raise ConfigValidationError with message listing supported distros
- **Type**: unit
- **Source**: FR1 - Distribution Configuration (Validation)

### AC-003: Missing distro field defaults to Alpine
- **Description**: When loading existing `.clauded.yaml` without `vm.distro` field, system defaults to 'alpine' for backward compatibility
- **Verification**: Load legacy config file without `vm.distro` field - verify config.vm_distro returns 'alpine' and no errors raised
- **Type**: integration
- **Source**: FR1 - Distribution Configuration (Validation); NFR1 - Backward Compatibility

### AC-004: VM metadata includes distro field
- **Description**: The `/etc/clauded.json` file written to VM includes the `distro` field matching the configured distribution
- **Verification**: Provision VM with Alpine, SSH in and verify `/etc/clauded.json` contains `"distro": "alpine"`. Repeat for Ubuntu.
- **Type**: integration
- **Source**: FR5 - Distro Metadata Storage

### AC-005: CLI flag creates VM with specified distro
- **Description**: Using `clauded --distro <name>` creates new VM with the specified distribution when no config exists
- **Verification**: Run `clauded --distro ubuntu` in empty project directory - verify generated `.clauded.yaml` has `vm.distro: ubuntu` and VM is created with Ubuntu image
- **Type**: e2e
- **Source**: FR2 - CLI Flag Support (Behavior)

### AC-006: CLI flag shows error for unsupported distro
- **Description**: Using `--distro` with unsupported value shows error message listing supported distributions
- **Verification**: Run `clauded --distro invalid` - verify error message includes list of supported distros ('alpine', 'ubuntu')
- **Type**: integration
- **Source**: FR2 - CLI Flag Support (Error Handling)

### AC-007: CLI flag conflicts with existing config show clear error
- **Description**: When `.clauded.yaml` exists with different distro than `--distro` flag, system shows clear error with instructions to edit config
- **Verification**: Create config with `vm.distro: alpine`, run `clauded --distro ubuntu` - verify error message explains mismatch and instructs to edit config and use --reprovision
- **Type**: integration
- **Source**: FR2 - CLI Flag Support (Error Handling)

### AC-008: Wizard shows distro selection as first step
- **Description**: Interactive wizard displays distro selection as the first question before Python/Node/etc
- **Verification**: Run `clauded` in empty directory, verify first prompt is "Select Linux distribution" with alpine/ubuntu options
- **Type**: integration
- **Source**: FR3 - Interactive Wizard Integration (First Wizard Step, Position)

### AC-009: Wizard defaults to Alpine selection
- **Description**: Distro selection step in wizard has Alpine pre-selected as default
- **Verification**: Start wizard without --distro flag, verify 'alpine' is the default highlighted option
- **Type**: integration
- **Source**: FR3 - Interactive Wizard Integration (First Wizard Step)

### AC-010: Wizard respects --distro flag pre-selection
- **Description**: When `--distro` flag is used, wizard pre-fills distro selection with specified value
- **Verification**: Run `clauded --distro ubuntu`, verify wizard shows Ubuntu as pre-selected option in distro step
- **Type**: integration
- **Source**: FR3 - Interactive Wizard Integration

### AC-011: Wizard generates config with selected distro
- **Description**: Completed wizard writes `.clauded.yaml` with `vm.distro` field matching user selection
- **Verification**: Complete wizard selecting Ubuntu, verify resulting `.clauded.yaml` contains `vm.distro: ubuntu`
- **Type**: e2e
- **Source**: FR3 - Interactive Wizard Integration

### AC-012: Distro change detection via SSH after boot
- **Description**: System detects distro mismatch by comparing `.clauded.yaml` config with `/etc/clauded.json` in running VM via SSH
- **Verification**: Edit `.clauded.yaml` to change distro from alpine to ubuntu, run `clauded --reprovision` - verify system reads VM metadata via SSH and detects mismatch before prompting
- **Type**: integration
- **Source**: FR4 - Distro Change Detection and VM Recreation (Detection Timing)

### AC-013: Distro change shows recreation warning
- **Description**: When distro mismatch detected, system prompts user with clear warning about VM recreation and data loss
- **Verification**: Change distro in config, run reprovision - verify warning message includes: old distro, new distro, "full VM recreation", "all VM state will be lost", "project files are safe"
- **Type**: e2e
- **Source**: FR4 - Distro Change Detection and VM Recreation (Change Flow)

### AC-014: Distro change allows user to cancel
- **Description**: User can decline distro change recreation prompt, preserving existing VM
- **Verification**: Trigger distro change prompt, answer 'N' - verify VM not destroyed and command exits without changes
- **Type**: e2e
- **Source**: FR4 - Distro Change Detection and VM Recreation (Change Flow)

### AC-015: Distro change recreates VM with new distro
- **Description**: Confirming distro change destroys old VM and creates new VM with new distribution
- **Verification**: Change distro alpine→ubuntu, confirm recreation prompt - verify old VM destroyed, new Ubuntu VM created, and `/etc/clauded.json` shows "distro": "ubuntu"
- **Type**: e2e
- **Source**: FR4 - Distro Change Detection and VM Recreation (Change Flow)

### AC-016: Alpine VM uses Alpine cloud image
- **Description**: Creating VM with Alpine distro uses Alpine cloud image from downloads.yml
- **Verification**: Create Alpine VM, verify Lima config contains Alpine cloud image URL from downloads.yml
- **Type**: integration
- **Source**: Architecture Design (Lima Config Generation, Cloud Image Metadata)

### AC-017: Ubuntu VM uses Ubuntu cloud image
- **Description**: Creating VM with Ubuntu distro uses Ubuntu cloud image from downloads.yml
- **Verification**: Create Ubuntu VM, verify Lima config contains Ubuntu cloud image URL from downloads.yml
- **Type**: integration
- **Source**: Architecture Design (Lima Config Generation, Cloud Image Metadata)

### AC-018: DistroProvider protocol exists with required methods
- **Description**: DistroProvider protocol/interface defines name, display_name, get_cloud_image, get_ansible_role_prefix, and validate_environment methods
- **Verification**: Verify DistroProvider protocol exists with all required methods. Verify AlpineProvider and UbuntuProvider implement protocol.
- **Type**: unit
- **Source**: Architecture Design (Distribution Provider Pattern)

### AC-019: AlpineProvider returns correct metadata
- **Description**: AlpineProvider implementation returns name='alpine', correct cloud image, and role prefix
- **Verification**: Call AlpineProvider().name, .get_cloud_image(), .get_ansible_role_prefix() - verify returns 'alpine', Alpine image metadata, and appropriate prefix
- **Type**: unit
- **Source**: Architecture Design (Distribution Provider Pattern)

### AC-020: UbuntuProvider returns correct metadata
- **Description**: UbuntuProvider implementation returns name='ubuntu', correct cloud image, and role prefix
- **Verification**: Call UbuntuProvider().name, .get_cloud_image(), .get_ansible_role_prefix() - verify returns 'ubuntu', Ubuntu image metadata, and appropriate prefix
- **Type**: unit
- **Source**: Architecture Design (Distribution Provider Pattern)

### AC-021: Provider factory returns correct provider instance
- **Description**: get_distro_provider() factory function returns appropriate provider instance for distro name
- **Verification**: Call get_distro_provider('alpine') and verify returns AlpineProvider. Call get_distro_provider('ubuntu') and verify returns UbuntuProvider. Call with invalid name and verify raises ValueError.
- **Type**: unit
- **Source**: Architecture Design (Distribution Provider Pattern - Factory)

### AC-022: Common role has Alpine and Ubuntu variants
- **Description**: common-alpine and common-ubuntu role directories exist with distro-specific tasks
- **Verification**: Verify roles/common-alpine/tasks/main.yml exists and contains Alpine package manager commands (apk). Verify roles/common-ubuntu/tasks/main.yml exists and contains Ubuntu package manager commands (apt).
- **Type**: integration
- **Source**: Architecture Design (Ansible Role Variant Architecture); AC6

### AC-023: Python role has Alpine and Ubuntu variants
- **Description**: python-alpine and python-ubuntu role directories exist with distro-specific Python installation
- **Verification**: Verify roles/python-alpine/tasks/main.yml and roles/python-ubuntu/tasks/main.yml exist with appropriate package installation for each distro
- **Type**: integration
- **Source**: Architecture Design (Ansible Role Variant Architecture); AC6

### AC-024: Docker role has Alpine and Ubuntu variants
- **Description**: docker-alpine and docker-ubuntu role directories exist with distro-specific Docker installation and service setup
- **Verification**: Verify roles/docker-alpine/tasks/main.yml uses rc-service, roles/docker-ubuntu/tasks/main.yml uses systemctl
- **Type**: integration
- **Source**: Architecture Design (Ansible Role Variant Architecture); AC6

### AC-025: All language roles have both variants
- **Description**: All language roles (node, java, kotlin, rust, go, dart, c) exist with -alpine and -ubuntu variants
- **Verification**: For each language in [node, java, kotlin, rust, go, dart, c], verify both roles/{lang}-alpine/ and roles/{lang}-ubuntu/ directories exist
- **Type**: integration
- **Source**: Architecture Design (Strict Variants for ALL Roles); AC6

### AC-026: All tool roles have both variants
- **Description**: All tool roles (uv, poetry, maven, gradle, aws_cli, gh, claude_code, playwright) exist with -alpine and -ubuntu variants
- **Verification**: For each tool in [uv, poetry, maven, gradle, aws_cli, gh, claude_code, playwright], verify both roles/{tool}-alpine/ and roles/{tool}-ubuntu/ directories exist
- **Type**: integration
- **Source**: Architecture Design (Strict Variants for ALL Roles); AC6

### AC-027: All database roles have both variants
- **Description**: All database roles (postgresql, redis, mysql, sqlite, mongodb) exist with -alpine and -ubuntu variants
- **Verification**: For each db in [postgresql, redis, mysql, sqlite, mongodb], verify both roles/{db}-alpine/ and roles/{db}-ubuntu/ directories exist
- **Type**: integration
- **Source**: Architecture Design (Strict Variants for ALL Roles); AC6

### AC-028: Provisioner selects correct role variants for Alpine
- **Description**: Provisioner generates role list with -alpine suffix for all roles when vm.distro is alpine
- **Verification**: With config vm.distro=alpine and python enabled, verify provisioner generates role list including 'common-alpine' and 'python-alpine'
- **Type**: unit
- **Source**: Architecture Design (Ansible Role Variant Architecture - Role Selection Logic); AC6

### AC-029: Provisioner selects correct role variants for Ubuntu
- **Description**: Provisioner generates role list with -ubuntu suffix for all roles when vm.distro is ubuntu
- **Verification**: With config vm.distro=ubuntu and docker enabled, verify provisioner generates role list including 'common-ubuntu' and 'docker-ubuntu'
- **Type**: unit
- **Source**: Architecture Design (Ansible Role Variant Architecture - Role Selection Logic); AC6

### AC-030: Provisioner validates role existence before running Ansible
- **Description**: Before invoking ansible-playbook, provisioner checks all selected role directories exist
- **Verification**: Configure VM to use missing role variant (e.g., manually delete python-ubuntu), attempt provision - verify error before ansible-playbook runs, listing missing roles
- **Type**: integration
- **Source**: Architecture Design (Strict Variants for ALL Roles - Role Validation); AC6

### AC-031: Role variants contain no distro conditionals
- **Description**: Role task files do not contain when conditionals based on ansible_distribution or os_family
- **Verification**: Grep all role variant task files for 'when:.*ansible_distribution' or 'when:.*os_family' - verify no matches found
- **Type**: integration
- **Source**: Architecture Design (Ansible Role Variant Architecture - Benefits); AC6

### AC-032: Ubuntu cloud image metadata in downloads.yml
- **Description**: downloads.yml contains ubuntu_image entry with url, version, and arch fields
- **Verification**: Load downloads.yml, verify ubuntu_image key exists with url pointing to Ubuntu cloud image, version="24.04", arch="aarch64"
- **Type**: unit
- **Source**: Architecture Design (Cloud Image Metadata)

### AC-033: get_cloud_image function supports ubuntu distro
- **Description**: downloads.py get_cloud_image('ubuntu') returns Ubuntu cloud image metadata
- **Verification**: Call get_cloud_image('ubuntu'), verify returns dict with url, version, arch matching ubuntu_image from downloads.yml
- **Type**: unit
- **Source**: Architecture Design (Cloud Image Metadata)

### AC-034: get_cloud_image raises error for unsupported distro
- **Description**: downloads.py get_cloud_image() raises DownloadMetadataError for distros without metadata
- **Verification**: Call get_cloud_image('fedora'), verify raises DownloadMetadataError with message about missing cloud image
- **Type**: unit
- **Source**: Architecture Design (Cloud Image Metadata)

### AC-035: Alpine VM successfully provisions with basic environment
- **Description**: Complete provisioning flow for Alpine VM results in working VM with common tools
- **Verification**: Create and provision Alpine VM with Python and Docker, SSH in and verify: python3 --version succeeds, docker --version succeeds, apk command available
- **Type**: e2e
- **Source**: AC5 from spec

### AC-036: Ubuntu VM successfully provisions with basic environment
- **Description**: Complete provisioning flow for Ubuntu VM results in working VM with common tools
- **Verification**: Create and provision Ubuntu VM with Python and Docker, SSH in and verify: python3 --version succeeds, docker --version succeeds, apt command available
- **Type**: e2e
- **Source**: AC5 from spec

### AC-037: No hardcoded distro names in config.py
- **Description**: config.py uses constant or enum for supported distros list, not hardcoded strings scattered in logic
- **Verification**: Review config.py source - verify distro validation uses single SUPPORTED_DISTROS constant/list, not inline checks for 'alpine' or 'ubuntu'
- **Type**: manual
- **Source**: NFR2 - Extensibility; AC7 from spec

### AC-038: No hardcoded distro names in lima.py
- **Description**: lima.py uses provider abstraction, not hardcoded distro logic
- **Verification**: Review lima.py source - verify cloud image selection uses get_distro_provider() or similar abstraction, not if/elif chains for specific distros
- **Type**: manual
- **Source**: NFR2 - Extensibility; AC7 from spec

### AC-039: No hardcoded distro names in provisioner.py
- **Description**: provisioner.py uses generic role suffix pattern, not distro-specific logic
- **Verification**: Review provisioner.py source - verify role selection uses f"{role}-{distro}" pattern or equivalent, not separate logic branches per distro
- **Type**: manual
- **Source**: NFR2 - Extensibility; AC7 from spec

### AC-040: Distro detection completes within performance budget
- **Description**: Reading distro from config and VM metadata completes in under 100ms
- **Verification**: Benchmark config load and SSH metadata read - verify total time < 100ms for distro detection
- **Type**: integration
- **Source**: NFR3 - Performance

### AC-041: Legacy config without distro field loads successfully
- **Description**: Existing .clauded.yaml files created before this feature continue to load without errors
- **Verification**: Load pre-existing config file (or create one) without vm.distro field - verify loads successfully with no warnings or errors
- **Type**: integration
- **Source**: NFR1 - Backward Compatibility; AC8 from spec

### AC-042: Legacy VM metadata without distro field assumes Alpine
- **Description**: VMs created before this feature (without distro in /etc/clauded.json) are treated as Alpine
- **Verification**: Create /etc/clauded.json without distro field, verify system reads it as alpine without triggering mismatch warnings
- **Type**: integration
- **Source**: NFR1 - Backward Compatibility; AC8 from spec

### AC-043: --distro flag with legacy config shows conflict error
- **Description**: Using --distro ubuntu with config that has no distro field (implicit alpine) shows error
- **Verification**: Create config without vm.distro field, run clauded --distro ubuntu - verify error message explains implicit Alpine default conflicts with flag
- **Type**: integration
- **Source**: NFR1 - Backward Compatibility (--distro Flag with Legacy Config)

### AC-044: Adding new distro requires only defined components
- **Description**: Extensibility constraint verified - adding Debian would require only: cloud image metadata, role variants, provider implementation, wizard entry
- **Verification**: Manual review of architecture - verify no other code locations would need changes to add Debian support
- **Type**: manual
- **Source**: NFR2 - Extensibility; AC7 from spec

## Verification Plan

### Automated Tests

#### Unit Tests
- AC-001: Config schema accepts valid distro field
- AC-002: Config schema rejects invalid distro values
- AC-003: Missing distro field defaults to Alpine
- AC-018: DistroProvider protocol exists
- AC-019: AlpineProvider returns correct metadata
- AC-020: UbuntuProvider returns correct metadata
- AC-021: Provider factory returns correct provider
- AC-028: Provisioner selects correct Alpine role variants
- AC-029: Provisioner selects correct Ubuntu role variants
- AC-032: Ubuntu metadata in downloads.yml
- AC-033: get_cloud_image supports ubuntu
- AC-034: get_cloud_image raises error for unsupported

#### Integration Tests
- AC-004: VM metadata includes distro field
- AC-006: CLI flag error for unsupported distro
- AC-007: CLI flag conflicts with existing config
- AC-008: Wizard shows distro as first step
- AC-009: Wizard defaults to Alpine
- AC-010: Wizard respects --distro flag
- AC-012: Distro change detection via SSH
- AC-016: Alpine VM uses Alpine cloud image
- AC-017: Ubuntu VM uses Ubuntu cloud image
- AC-022: Common role variants exist
- AC-023: Python role variants exist
- AC-024: Docker role variants exist
- AC-025: All language roles have variants
- AC-026: All tool roles have variants
- AC-027: All database roles have variants
- AC-030: Provisioner validates role existence
- AC-031: Role variants have no conditionals
- AC-040: Distro detection performance
- AC-041: Legacy config loads successfully
- AC-042: Legacy VM metadata assumes Alpine
- AC-043: --distro flag with legacy config conflicts

#### E2E Tests
- AC-005: CLI flag creates VM with specified distro
- AC-011: Wizard generates config with selected distro
- AC-013: Distro change shows recreation warning
- AC-014: Distro change allows cancel
- AC-015: Distro change recreates VM
- AC-035: Alpine VM provisions successfully
- AC-036: Ubuntu VM provisions successfully

### Manual Verification

- AC-037: Review config.py for hardcoded distro names
- AC-038: Review lima.py for hardcoded distro names
- AC-039: Review provisioner.py for hardcoded distro names
- AC-044: Review architecture for extensibility constraints

## Coverage Matrix

| Spec Requirement | Acceptance Criteria |
|------------------|---------------------|
| FR1: Distribution Configuration | AC-001, AC-002, AC-003 |
| FR2: CLI Flag Support | AC-005, AC-006, AC-007, AC-043 |
| FR3: Interactive Wizard Integration | AC-008, AC-009, AC-010, AC-011 |
| FR4: Distro Change Detection and VM Recreation | AC-012, AC-013, AC-014, AC-015 |
| FR5: Distro Metadata Storage | AC-004 |
| NFR1: Backward Compatibility | AC-003, AC-041, AC-042, AC-043 |
| NFR2: Extensibility | AC-037, AC-038, AC-039, AC-044 |
| NFR3: Performance | AC-040 |
| NFR4: Testing | All automated test criteria |
| Architecture: Distribution Provider Pattern | AC-018, AC-019, AC-020, AC-021 |
| Architecture: Ansible Role Variant | AC-022, AC-023, AC-024, AC-025, AC-026, AC-027, AC-028, AC-029, AC-030, AC-031 |
| Architecture: Lima Config Generation | AC-016, AC-017 |
| Architecture: Cloud Image Metadata | AC-032, AC-033, AC-034 |
| AC5 (from spec): VM Creation | AC-016, AC-017, AC-035, AC-036 |
| AC6 (from spec): Ansible Role Variants | AC-022, AC-023, AC-024, AC-025, AC-026, AC-027, AC-028, AC-029, AC-030, AC-031 |
| AC7 (from spec): Extensibility | AC-037, AC-038, AC-039, AC-044 |
| AC8 (from spec): Backward Compatibility | AC-003, AC-041, AC-042 |
