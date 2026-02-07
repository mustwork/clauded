# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Multi-Instance Session Detection**: VM shutdown now detects other active sessions
  - VMs only stop when the last session exits, preventing disruption to concurrent users
  - Counts pts devices in `/dev/pts` to detect active SSH sessions
  - `--stop` respects other active sessions (shows message if sessions exist)
  - `--force-stop` flag to stop VM regardless of other active sessions
- **MCP-aware Detection and Reprovisioning**: Detection now picks up runtime requirements from MCP server configurations
  - MCP servers using `uvx` automatically trigger Python runtime requirement
  - `--edit` now runs detection and merges results with existing config (additive)
  - `--reprovision --detect` re-runs detection and updates config without full wizard
  - Detection results are additive: new requirements are added, user choices preserved
- **Keep VM Running Setting**: New `vm.keep_running` option to control VM shutdown behavior
  - Default: `false` (VMs stop on shell exit, freeing resources)
  - Set to `true` to keep VMs running for faster reconnection
  - Configurable via `.clauded.yaml` or interactive wizard
  - Changes take effect on next shell exit (works with running VMs)
- **Dart Language Support**: Dart SDK provisioning with versions 3.5, 3.6, and 3.7
  - Includes dart CLI and pub package manager
  - Official ARM64 binaries from Google storage
- **C/C++ Language Support**: C and C++ development toolchain provisioning
  - GCC toolchain options: gcc14, gcc13
  - Clang/LLVM toolchain options: clang18, clang17
  - Includes build tools: make, cmake, gdb, valgrind
  - Environment variables CC and CXX set based on selected toolchain
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
- MongoDB tools support: installs `mongodb-tools` package (CLI utilities like mongodump, mongorestore) when MongoDB is selected or detected
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

- **Docker provisioning**: Added `docker-cli-compose` plugin for modern `docker compose` command support
- **Playwright browser selection**: New wizard screen allows selecting which browsers to install (Chromium, Firefox, WebKit) when Playwright is chosen
  - All browsers pre-selected by default
  - Selection persisted in `.clauded.yaml` under `environment.playwright_browsers`
  - Reduces provisioning time and disk usage when only specific browsers are needed
- **Playwright provisioning**: Complete rewrite for reliable installation on Alpine
  - Uses `npm install -g` command instead of Ansible npm module (fixes silent failures)
  - Installs both `playwright` and `@playwright/test` packages globally
  - Conditionally installs only selected browsers via `npx playwright install`
  - Added comprehensive system dependencies (mesa, X11 libs, dbus, etc.)
  - Added WebKit-specific dependencies (gstreamer, libsoup3, etc.)
  - Creates `/opt/playwright-browsers/` directory with proper permissions
  - Adds Chrome compatibility symlink at `/opt/google/chrome/chrome` (when Chromium selected)
  - Installs `xvfb` for headless display support
  - Defaults to all browsers for existing configs without explicit browser selection

- **Removed hash verification for all downloads**: Integrity verification now relies on HTTPS transport security only. Upstream providers frequently update artifacts in-place without changing version numbers, breaking checksum verification. This removes SHA256 checksums from `downloads.yml` and all Ansible tasks.
- **Expanded Baseline Tools**: All VMs now include a comprehensive set of common system utilities:
  - HTTP clients: curl, wget
  - Archive/compression: tar, gzip, xz, unzip
  - File sync: rsync
  - SSH: openssh (server + client)
  - JSON: jq
  - Diagnostics: strace, lsof, iproute2, bind-tools (dnsutils), htop

- **Installer Script Hash Verification Removed**: Removed SHA256 checksum verification for installer scripts (uv, bun, rustup) that are updated in-place by upstream providers. These now rely on HTTPS transport security, following the same pattern as Alpine Linux cloud images.
- **Alpine Image Hash Verification Removed**: Alpine Linux cloud images no longer use SHA256 hash verification. Alpine rebuilds images in-place for security patches without changing the version number, which caused tool failures when upstream hashes changed. Integrity now relies on HTTPS transport security and Lima's image caching.

- **Runtime Version Enforcement**: Provisioning now respects user-selected runtime versions
  - Python versions (3.10, 3.11, 3.12) installed via `uv python install` instead of system Python
  - Node.js versions (18, 20, 22) downloaded from official nodejs.org binaries with checksum verification
  - Config validation rejects unsupported runtime versions with clear error messages listing valid options
  - Go versions updated to 1.22.10 and 1.23.5 (aligned with downloads.yml)

### Fixed

- **Docker daemon not starting after installation**: Fixed OpenRC service startup on Alpine Linux
  - Ansible's `service` module doesn't reliably start OpenRC services
  - Now uses `rc-service docker start` directly for reliable daemon startup
  - Added verification step to ensure daemon is actually running
- **Edit/reprovision no longer disrupts other sessions**: `--edit`, `--reprovision`, and `--reboot` now check for other active sessions before performing operations that could disrupt them
  - SSH reconnect (needed for group membership changes) is skipped when other sessions exist
  - `--reboot` refuses to reboot when other sessions are active
  - Users are notified with workaround instructions (e.g., `newgrp docker`)
- **Docker group membership not effective after provisioning**: Fresh VMs with docker enabled now work immediately without requiring a reboot
  - Lima reuses SSH master control sockets, preventing group membership changes from taking effect
  - Shell now uses `--reconnect` flag after provisioning to force a fresh SSH session
  - Docker commands work on first login without needing `newgrp docker` or VM restart
- **VM Cleanup on Exit**: VM now automatically stops when the shell exits (normal or edit mode)
  - Previously, VMs remained running after `exit` or Ctrl+D, consuming system resources
  - Fixed by wrapping vm.shell() in try/finally blocks to ensure cleanup
  - Includes defensive check to avoid stopping already-stopped VMs
  - Shutdown ignores Ctrl+C to ensure cleanup completes
- **Corepack installation for Node.js**: Corepack is now properly installed via npm instead of silently failing. Previously, the installation used `ignore_errors: yes`, causing yarn and pnpm to be unavailable despite being advertised in documentation. Installation is now idempotent with proper path checking (`/usr/bin/corepack` - the Alpine npm global install location).
- **Claude permissions prompt missing in detection wizard**: The "Auto-accept Claude Code permission prompts in VM?" prompt was only shown when using `--no-detect` flag, but not in the default detection-based wizard flow. Users can now configure this setting during initial setup regardless of detection mode.
- **Python installation fails on Alpine/musl systems**: `uv python install` doesn't support musl libc distributions yet. The uv role now detects Alpine and falls back to system Python (installed via apk), with `UV_PYTHON_PREFERENCE=only-system` set to ensure uv uses the system interpreter.

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
