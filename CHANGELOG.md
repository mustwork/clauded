# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Atomic Config Updates with Rollback**: VM configuration changes now use transactional semantics
  - Config updates automatically roll back to previous state if VM creation or provisioning fails
  - Rollback handles all exceptions including KeyboardInterrupt and SystemExit
  - Crash recovery on startup detects incomplete updates and intelligently recovers:
    - If current VM doesn't exist: automatically rolls back to previous VM
    - If current VM exists: prompts user to optionally delete previous VM
  - Previous VM cleanup prompt after successful transitions (with user confirmation)
  - Config file changes are fsynced to disk for durability
  - New `previous_vm_name` field in config for crash recovery (backwards-compatible)
- MIT License file and metadata in pyproject.toml
- MongoDB as selectable database option in wizard (initial setup, edit mode, and detection wizard) regardless of detection status
- **Detection System Enhancements**
  - Python version detection from setup.py (`python_requires` parameter)
  - Java version detection from build.gradle.kts (Kotlin DSL syntax)
  - Framework detection from build.gradle (Groovy DSL) including Micronaut and Ktor
  - MongoDB database detection from docker-compose, environment variables, and ORM dependencies
  - Support for MongoDB across Python (pymongo, motor, mongoengine, beanie), Node.js (mongoose, mongodb), Java, and Go ecosystems
  - Playwright testing framework detection across all project types:
    - Config files: `playwright.config.ts`, `playwright.config.js`, `playwright.config.mjs`
    - Node.js packages: `playwright`, `@playwright/test`
    - Python packages: `playwright`, `pytest-playwright`

### Changed

- **Alpine Image Hash Verification Removed**: Alpine Linux cloud images no longer use SHA256 hash verification. Alpine rebuilds images in-place for security patches without changing the version number, which caused tool failures when upstream hashes changed. Integrity now relies on HTTPS transport security and Lima's image caching.

- **Runtime Version Enforcement**: Provisioning now respects user-selected runtime versions
  - Python versions (3.10, 3.11, 3.12) installed via `uv python install` instead of system Python
  - Node.js versions (18, 20, 22) downloaded from official nodejs.org binaries with checksum verification
  - Config validation rejects unsupported runtime versions with clear error messages listing valid options
  - Go versions updated to 1.22.10 and 1.23.5 (aligned with downloads.yml)

### Fixed

- **Claude permissions prompt missing in detection wizard**: The "Auto-accept Claude Code permission prompts in VM?" prompt was only shown when using `--no-detect` flag, but not in the default detection-based wizard flow. Users can now configure this setting during initial setup regardless of detection mode.

### Security

- **VM Name Path Traversal Protection**: VM names are now validated to prevent path traversal attacks
  - Rejects VM names containing "..", "/", or "\\" characters
  - Validation applied on config load and during atomic updates
  - Protects against malicious configs attempting directory traversal
  - Clear error messages when invalid VM names are detected

- **SSH Host Key Checking Enabled by Default**: Ansible provisioning now verifies SSH host keys by default
  - Strengthens host authenticity guarantees for VM connections
  - Can be disabled via `ssh.host_key_checking: false` in `.clauded.yaml` for local development
  - Previous configs without this setting will use the secure default (enabled)

- **Supply Chain Integrity**: All external downloads now use pinned versions and SHA256 checksum verification where feasible
  - Centralized download metadata in `downloads.yml` for all tools (Go, Kotlin, Maven, Gradle, uv, Bun, Rustup, Node.js)
  - Installer scripts (uv, rustup) downloaded and verified before execution
  - Eliminated `curl | sh` patterns and dynamic "latest" version fetching
  - Maven and Gradle versions pinned instead of fetching from APIs
  - Note: Alpine cloud image relies on HTTPS transport security (see Changed section)

- **Detection System Security Enhancements**
  - Symlink traversal protection for all detection parsers
  - Version string validation to prevent command injection
  - 8KB file read limit enforced across all detection modules (SEC-002)
  - Safe file reading with path validation for all manifest parsers

## [0.1.0] - 2026-01-30

### Added

- **Core VM Management**
  - Lima-based VM lifecycle management (create, start, stop, destroy)
  - Automatic VM naming using SHA256 hashing of project path
  - Configurable VM resources (CPU, memory, disk)
  - Project directory mounted at same path in VM
  - Graceful cleanup on keyboard interrupt (CTRL+C)

- **Interactive Setup Wizard**
  - Guided prompts for selecting languages, databases, and tools
  - Non-interactive terminal detection with graceful fallback
  - Checkbox-based multi-selection for languages
  - Circle indicators for select prompts
  - Spinner and separators for better UX

- **Project Detection**
  - Automatic detection of languages from project files
  - Version detection from configuration files (pyproject.toml, package.json, etc.)
  - Framework detection (Playwright, Claude Code)
  - Database detection from dependencies and config files
  - MCP configuration detection for runtime/tool requirements
  - Bounded file scanning for performance

- **Language Support**
  - Python 3.10, 3.11, 3.12 with pip, pipx, uv, uvx, poetry
  - Node.js 18, 20, 22 with npm, npx, yarn, pnpm, bun (via corepack)
  - Java 11, 17, 21 with Maven, Gradle
  - Kotlin 1.9, 2.0 with Maven, Gradle
  - Rust stable/nightly with Cargo
  - Go 1.22.10, 1.23.5 with built-in modules

- **Database Support**
  - PostgreSQL with contrib and libpq-dev
  - Redis in-memory data store
  - MySQL relational database
  - SQLite file-based database

- **Developer Tools**
  - Docker with user added to docker group
  - Git (always installed via common role)
  - AWS CLI v2 (ARM64)
  - GitHub CLI (`gh` command)
  - Gradle build automation

- **Framework Support**
  - Claude Code AI-assisted development CLI
  - Playwright browser automation with binaries

- **Provisioning**
  - Ansible-based provisioning with 21 roles
  - Alpine Linux 3.21 base image (configurable version)
  - Recoverable provisioning failures
  - Reprovision support for configuration updates
  - Environment variable sanitization for security
  - Thread-safe caching for linguist data loading

- **CLI Features**
  - `clauded` - Create/connect to VM
  - `clauded --stop` - Stop VM
  - `clauded --destroy` - Destroy VM
  - `clauded --reprovision` - Update environment
  - `clauded --edit` - Modify configuration
  - `clauded --detect` - Show detected technologies
  - `clauded --debug` - Verbose Lima and Ansible output
  - `clauded --version` - Show version information

- **Configuration**
  - YAML-based configuration (`.clauded.yaml`)
  - Schema versioning for forward compatibility
  - Config load validation with error reporting
  - Defensive recovery for config files after ungraceful shutdown

- **Development Infrastructure**
  - GitHub Actions CI/CD pipeline with coverage enforcement
  - Pre-commit hooks with uv fallback
  - Ruff for linting and formatting
  - Mypy for strict type checking
  - Pytest with coverage tracking (80% minimum)
  - Hypothesis for property-based testing

### Security

- SHA256 hashing for VM names (upgraded from MD5)
- Environment variable sanitization for Ansible execution
- Bounded file scanning prevents resource exhaustion
- Specific exception handling (no broad catches)
- Gitconfig injection safety validation
