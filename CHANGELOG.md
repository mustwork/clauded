# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **CCR `<think>` reasoning leak on MiniMax providers** — the `minimax` provider in the generated CCR config referenced a `"use": ["extrathinktag"]` transformer that doesn't exist in CCR 1.0.73's built-in registry (the legacy musistudio/llms transformer was dropped during the v1→v2 refactor; unknown names are silently filtered by CCR's loader). As a result, MiniMax M2.x emitted raw `<think>...</think>` blocks in `delta.content` that survived the OpenAI→Anthropic SSE conversion and polluted the harness context window. The role now ships a custom transformer at `/etc/clauded/extra-think-tag.js` (registered via the top-level `transformers: [{ path }]` array in CCR's `config.json`) that strips `<think>...</think>` blocks from both JSON and SSE responses with state preserved across split SSE frames, and drops any parallel `delta.reasoning_content` field. Backed by a host-side `node`-driven pytest at `tests/test_ccr_extrathinktag_transformer.py` exercising single-delta, split-across-deltas, unterminated, and passthrough cases.

## [0.3.3] - 2026-05-08

### Changed

- **claude-code-router (CCR) proxy refinements** — the optional `vm.claude_code_router` proxy gains four behaviours that complete the routing layer:
  - The Anthropic provider sends `Authorization: Bearer <token>` and omits `x-api-key`. Subscription OAuth tokens (`sk-ant-oat01-*`) and conventional API keys (`sk-ant-api03-*`) both authenticate against `api.anthropic.com`. Implemented as a provision-time text patch against the bundled `@musistudio/llms` Anthropic transformer in `cli.js` (flipping the default of `useBearer` from `false` to `true`). The provider config keeps the simple string form `"transformer": { "use": ["Anthropic"] }`. The patch is sentinel-asserted post-edit, syntax-checked with `node --check`, and a host-side pytest at `tests/test_claude_code_router_patch.py` re-runs the role's regex against a checked-in fixture excerpt of the pinned CCR 1.0.73 bundle so a CCR version bump cannot silently no-op the substitution.
  - The custom router at `/etc/clauded/ccr-router.js` inspects `req.body.tools` and pins any request carrying an Anthropic server-side web tool (`web_search_*`, `web_fetch_*`) to the `anthropic` provider. Plain model traffic continues to honor `vm.claude_code_router.overrides`.
  - The `clauded-ccr-with` watcher closes fd 9 (`9>&-`) when launching the CCR daemon, so the lock file's open file description is released as soon as the subshell exits. This lets subsequent watcher iterations re-acquire the lock and rotate `ANTHROPIC_API_KEY` after an OAuth refresh.
  - `vm.claude_code_router.log_level` accepts pino's standard set (`fatal|error|warn|info|debug|trace`, default `warn`) and is rendered into CCR's `config.json` as `LOG_LEVEL`. At `debug` the rotated pino logs in `~/.claude-code-router/logs/ccr-*.log` include `final request` entries that capture each outbound URL plus full request headers and body, which is the most reliable way to inspect what CCR is sending upstream. See [docs/claude-code-router.md](docs/claude-code-router.md#diagnostic-logging).
- **`apply_detection_to_config` preserves the full `claude_code_router` block** through detection-driven reprovisioning (`clauded --reprovision --detect`): `ccr_enabled`, `ccr_providers`, `ccr_overrides`, and `ccr_log_level` round-trip alongside the other persisted Config fields.

## [0.3.2] - 2026-05-07

### Added

- **claude-code-router (CCR) proxy (`vm.claude_code_router`)** — opt-in per-session [claude-code-router](https://github.com/musistudio/claude-code-router) running on `127.0.0.1:3456` inside the VM. When enabled, every `claude-code` session routes through the proxy and gains access to auto-discovered Ollama models on the host, an unconditional Anthropic passthrough, and optionally configured curated OpenAI-compatible providers (MiniMax, Groq, Together AI). Per-model overrides for `haiku`/`sonnet`/`opus` (with `<provider>/<model>` syntax — e.g. `haiku: ollama/qwen3:latest`, `opus: minimax/MiniMax-M2.7`) are supported via a small generated `CUSTOM_ROUTER_PATH` JS file at `/etc/clauded/ccr-router.js`. API keys never pass through provisioning — they live in the proxy's process environment only and are resolved via CCR's `${VAR}` interpolation. Pinned to CCR `1.0.73` (last 1.x release; v2.0.0 has active Ollama-routing regressions). See [docs/claude-code-router.md](docs/claude-code-router.md).

## [0.3.1] - 2026-05-06

### Fixed

- **opencode role `set -o pipefail` under dash** — the "Resolve opencode target version" and "Install opencode (resolved version)" tasks used `set -eo pipefail` but Ansible's `shell` module defaults to `/bin/sh` (dash on Ubuntu), which does not support `pipefail` and aborted the play with `Illegal option -o pipefail`. Both tasks now set `args.executable: /bin/bash`.
- **opencode role install** — the role was passing `OPENCODE_INSTALL_DIR` and `OPENCODE_VERSION` env vars to the upstream installer, but the script honors neither (`INSTALL_DIR` is hardcoded to `~/.opencode/bin`, the version env var is `VERSION`). As a result the binary never landed at `~/.local/bin/opencode` and version pins were ignored, causing provisioning to fail at the `--version` verification step. The role now exports `VERSION` (so pins take effect), installs `tar` (required by the script for Linux extraction), and symlinks `~/.opencode/bin/opencode` into `~/.local/bin/opencode` where the VM entrypoint expects it.
- **`make install` now picks up source-tree edits** — `uv tool install --force .` reuses the cached wheel keyed on path:version, so edits without a version bump silently stayed invisible to the installed tool (most painful when iterating on bundled Ansible role YAMLs). The `install` target now runs `uv cache clean clauded` first and uses `--reinstall`, forcing a rebuild from the working tree.

## [0.3.0] - 2026-05-05

### Added

- **`opencode` framework option** — selecting `opencode` in the wizard's frameworks multi-select (or adding it to `frameworks:` in `.clauded.yaml`) installs the opencode binary into `~/.local/bin` via the official install script. The role resolves the latest GitHub release when `opencode_version` is unset, accepts a pin otherwise, and is idempotent across reruns. No Node.js dependency is added.
- **Wizard harness selection step** — `clauded` and `clauded --edit` now prompt for the active harness (`claude-code` / `codex` / `opencode`) after the frameworks multi-select. New configs default to `claude-code`; `--edit` pre-selects the persisted value. Picking `opencode` auto-adds it to `frameworks` (with an info-level message) so the harness ⇒ framework invariant cannot be violated through the wizard. Detection-driven flows (`run_with_detection` / `run_edit_with_detection`) gain the same step; `apply_detection_to_config` preserves the existing `harness` value through non-interactive merges.
- **opencode user state mounted from host into VM** — when `opencode` is in `frameworks`, the host directories `~/.config/opencode` and `~/.local/share/opencode` are mounted writably into the VM (auto-created if missing). Auth tokens, MCP OAuth state, sessions, and TUI prefs persist across `clauded --destroy && clauded` cycles, matching the existing `~/.claude` / `~/.codex` pattern.
- **opencode version pin (`versions.opencode`) and update-check parity** — `.clauded.yaml` accepts a top-level `versions.opencode` pin (validated identically to `versions.claude-code` / `versions.codex`). The CLI's framework-update prompt now includes opencode when it is in `frameworks`: a pinned version takes precedence; otherwise the latest is fetched from the GitHub releases API on the host (graceful skip on rate limit / network failure, matching the npm-fetch pattern). Confirming the prompt re-runs the official install script inside the VM at the resolved version.
- **`--harness` CLI flag** — `clauded --harness <claude-code|codex|opencode>` overrides the persisted harness for one invocation without touching `.clauded.yaml`. Invalid values exit 2 with Click's standard "Invalid value" error. An override that targets a harness whose framework is not present (e.g. `--harness opencode` against a config without `opencode` in `frameworks`) exits 1 with a message naming `clauded --edit`. The flag is silently ignored with `--reprovision`/`--detect`/`--stop`/`--destroy`/`--reboot`/`--force-stop`; with `--edit` it emits a one-line warning and the wizard runs normally.

### Changed

- **Ubuntu 24.04 LTS is now the sole supported guest OS** — Alpine Linux support is removed. Existing Alpine configs receive an actionable migration error at load time; see `docs/migration-from-alpine.md`.
- **`.clauded.yaml` carries an explicit top-level `harness:` field** — accepted values are `claude-code` (default), `codex`, and `opencode`. Existing configs without the field continue to load and behave identically (default is `claude-code`). Misconfigurations (unknown harness, or `harness: opencode` without `opencode` in `frameworks`) fail fast at load time with an actionable error pointing at `clauded --edit`.
- **VM entrypoint command is now harness-driven** — `LimaVM.shell()` dispatches on the resolved harness (per-invocation override if `--harness` was passed, else `Config.harness`). `claude-code` launches `claude` (with `--dangerously-skip-permissions` iff `claude_dangerously_skip_permissions`); `codex` launches `codex` (with `--dangerously-bypass-approvals-and-sandbox` under the same condition); `opencode` launches the bare `opencode` TUI without any `--dangerously-*` flag regardless of `claude_dangerously_skip_permissions`. Default behaviour for users without `harness:` in their config is unchanged (claude-code).
- **Documentation refreshed for the harness model** — `README.md` gains a "Choosing a harness" subsection plus `codex` and `opencode` rows in the frameworks table; `specs/spec.md` documents the `harness:` field, the `--harness` flag, and the harness ⇒ framework rule (FR4); `docs/configuration.md` adds a "Choosing a harness" section with the dispatcher matrix and a troubleshooting note for the harness ⇒ framework error, and refreshes the frameworks reference to include `codex` and `opencode`.

### Removed

- **Alpine Linux support** — Ubuntu 24.04 LTS is now the sole supported guest OS. Loading a `.clauded.yaml` with `vm.distro: alpine` raises a `ConfigValidationError` with actionable migration steps; see `docs/migration-from-alpine.md`. `SUPPORTED_DISTROS`, `AlpineProvider`, `UbuntuProvider`, `get_distro_provider`, and `src/clauded/distro.py` are deleted (ADR-001).
- **`--distro` CLI flag** — `clauded --distro <name>` is no longer accepted. Ubuntu is the only supported guest OS.
- **`vm.distro` config field** — removed from the Config dataclass and from `.clauded.yaml` output. Loading a config with `distro: ubuntu` succeeds silently (field discarded with INFO log); `distro: alpine` raises `ConfigValidationError`.
- **`*-alpine` Ansible roles** — all 24 `*-alpine` role directories deleted from `src/clauded/roles/`.
- **Distro selection wizard step** — `_select_distro` removed; the wizard now opens directly at the Python version question.
- **`*-ubuntu` role suffix** — 25 `*-ubuntu` role directories renamed to bare names (`common-ubuntu` → `common`, `opencode-ubuntu` → `opencode`, etc.). Provisioning logs now emit `Roles: common, python, docker, ...`. `_ROLES_WITH_VARIANTS` and `_apply_distro_suffix` removed from provisioner.
- **`get_alpine_image()` and `alpine_image` download metadata** — `downloads.get_cloud_image()` is now no-arg and returns the Ubuntu image only.
- **`LimaVM.get_vm_distro()`** — SSH-based distro-read method removed; Alpine configs are rejected at config-load time before any VM operation.
- **`USE_BUILTIN_RIPGREP=0` env var prefix** — dropped from the launch command for all harnesses.

### Fixed

- **Provisioning failed on fresh VMs with undefined Ansible variable `vm_distro`** — the `common` role still rendered `"distro": "{{ vm_distro }}"` into `/etc/clauded.json`, but the playbook variable was removed alongside the `Config.vm_distro` field. The `distro` key is dropped from the metadata file (no consumer reads it after the Alpine removal); legacy VMs that already wrote it on disk are unaffected.
- **`clauded --destroy` and `clauded --stop` errored out on legacy `vm.distro: alpine` configs** — `Config.load` raised the FR5 migration error before either workflow could run, leaving users with the very command the migration message instructs them to use blocked. `Config.load` now accepts `allow_alpine_legacy=True` (used by `--destroy` and `--stop` only) so the migration flow is actually executable.
- **Harness validation now matches provisioner behaviour for every harness, not just `opencode`** — the previous rule only enforced `opencode ⇒ "opencode" in frameworks` on the assumption that `claude-code` and `codex` were unconditional defaults at the provisioner level. They are not: the provisioner only installs frameworks listed in `frameworks:`, so a config with `harness: codex` and `frameworks: []` (or any harness not in the frameworks list) would have validated and then failed at shell-launch time. `Config.load` and the `--harness` override now reject any harness that is missing from `frameworks` with the same actionable `clauded --edit` message. The default `Config.frameworks` is now `["claude-code"]` (matching the default harness) so freshly constructed configs round-trip without manual fixup.
- **opencode update reports failure on silent install errors** — `_update_opencode` previously piped `curl ... | bash` without `pipefail`, so a failed download would still exit 0 and `_check_library_updates` would print "updated successfully" while the binary on disk was unchanged. The pipeline now sets `pipefail` and verifies the result by running `opencode --version` and matching the installed version against the requested one before reporting success.
- **`apply_detection_to_config` silently dropped persisted config fields** — the non-interactive merge used by `clauded --reprovision --detect` reconstructed a fresh `Config` without carrying over `previous_vm_name`, `playwright_browsers`, `claude_code_version`, `codex_version`, or `opencode_version`. Re-saving the merged config would erase those values from `.clauded.yaml`. All five fields are now preserved alongside `harness`.
- **`--harness` override leaked into shell launches under `--edit` / `--reprovision` / `--reboot`** — although the validation gate was correctly skipped (and `--edit` printed the documented warning), the override was still passed into `LimaVM`, so the post-edit/post-reprovision/post-reboot shell silently ran the override harness instead of the persisted one. The flag is now dropped to `None` in those modes per AC-015 / FR6.
- **Detection-based framework preselection wired to the wrong defaults source** — the frameworks multi-select in `run_with_detection` was checking `defaults["tools"]` for `opencode` / `playwright` membership, so framework detection never resulted in pre-checked menu entries. The menu now reads `defaults["frameworks"]` like the other multi-selects read their own keys.

## [0.2.6] - 2026-04-27

### Fixed

- **Ubuntu provisioning fails with `No package matching 'strace'/'unzip' is available` despite correct sources** — cloud-init/apt-daily can leave `/var/lib/apt/lists` with partial `Packages` files; subsequent `apt-get update` runs use pdiffs and report success against a still-broken cache. The common-ubuntu role now wipes `/var/lib/apt/lists` before the first cache refresh to force a clean, full fetch.

## [0.2.5] - 2026-04-27

### Fixed

- **Ubuntu provisioning fails with `No package matching '<pkg>' is available`** — `apt-get update` can return success while individual source fetches silently fail, leaving a partial package index. The common package install task now refreshes the cache and retries up to 5 times.

## [0.2.4] - 2026-04-27

### Fixed

- **Ubuntu provisioning fails when cloud-init reports recoverable warnings** — `cloud-init status --wait` exits 2 on recoverable errors even though `status: done`; the wait task now accepts rc 0 and 2 and only fails on rc 1 (unrecoverable)

## [0.2.3] - 2026-04-27

### Fixed

- **Ubuntu provisioning fails with `No package matching 'unzip' is available`** — common-ubuntu role now waits for `cloud-init status --wait` before the first apt run and drops `cache_valid_time` so a partial apt cache is always refreshed on retry, instead of being treated as still-valid for an hour

## [0.2.2] - 2026-04-27

### Changed

- **Default vCPUs reduced from 4 to 1** — idle VMs with 4 vCPUs caused high CPU load on the host; 1 vCPU is sufficient for most workloads and can be increased in `.clauded.yaml` when needed

### Fixed

- **Maven 3.9.14 removed from Apache mirror**: Bump Maven to 3.9.15 (3.9.14 returns 404 on dlcdn.apache.org)
- **CARGO_HOME writable by non-root users** — The Rust roles now set `CARGO_HOME=$HOME/.cargo` in the shell profile instead of `/usr/local/cargo`, so `cargo build` works without root permissions
- **Claude Code crashes on Alpine with `posix_getdents: symbol not found`** — Alpine 3.21 ships musl 1.2.5 which lacks `posix_getdents` (added in musl 1.2.6). The claude_code-alpine role now compiles a small LD_PRELOAD shim that provides the symbol via the getdents64 syscall

## [0.2.1] - 2026-03-19

### Fixed

- **Security: validate version pins at config load time** — version pins from `.clauded.yaml` are now strictly validated (digits and dots only), preventing shell command injection via crafted version strings
- **Malformed `versions` config produces clear error** — non-mapping `versions` values (e.g. `versions: latest`) now raise `ConfigValidationError` instead of crashing with `AttributeError`
- **Consistent `"latest"` handling** — the `"latest"` sentinel in version pins is now normalized to `None` during config load, ensuring identical behavior across provisioning and startup update paths

### Added

- **User-Configurable Framework Versions**: New `versions` section in `.clauded.yaml` for pinning Claude Code and Codex versions
  - Pin specific versions: `versions: { claude-code: "2.1.62", codex: "1.2.0" }`
  - Omitting a key defaults to "latest" (resolved at provision/check time)
  - Claude Code "latest" resolved via GCS on the host; Codex "latest" resolved via npm in the VM
  - Bidirectional version check at startup: detects both upgrades and downgrades
  - Version pins respected during both provisioning and in-VM update checks
  - Claude Code version no longer hardcoded in `downloads.yml`; user controls via config

### Removed

- **Dead `claude_code` base role**: Removed the unused base role (`roles/claude_code/`) that fetched "latest" dynamically and used an Ansible `creates:` guard preventing updates on reprovision. All provisioning already uses the distro-specific variants (`claude_code-alpine`, `claude_code-ubuntu`) which correctly use the pinned version from `downloads.yml`.

## [0.2.0] - 2026-03-19

### Added

- **Version Bump Targets**: `make bump-major`, `make bump-minor`, `make bump-patch` to automate version bumps with changelog updates and tagged commits

### Added

- **Update Check on VM Startup**: Automatic checks when connecting to an existing VM
  - **clauded version check**: Detects when clauded has been updated since provisioning by comparing git commits; prompts to reprovision (default: No)
  - **Library update check**: When clauded version matches, checks Claude Code (against pinned version in `downloads.yml`) and Codex (against npm latest) for available updates; prompts to update in-VM (default: No)
  - Claude Code updates use atomic download (temp file + validate + move) to prevent corrupting the existing binary on network failures
  - Library checks only run for frameworks listed in config; silently skipped on network/tool failures
  - Both checks skipped when VM is newly created, recreated due to distro change, or `--reprovision` flag is used

### Fixed

- **Codex update fails with EACCES**: Add `sudo` to `npm install -g` in the in-VM Codex update command (provisioning runs as root, but the update command ran as the regular user)
- **Library update offers downgrades**: Version comparison now checks that the target version is actually newer than installed, preventing downgrade offers when the VM has a newer version than the pinned/latest target
- **Maven 3.9.13 removed from Apache mirror**: Bump Maven to 3.9.14 (3.9.13 returns 404 on dlcdn.apache.org)
- **Claude Code `posix_getdents` crash on Alpine**: Pin Claude Code binary to v2.1.62 to avoid musl libc incompatibility introduced in v2.1.63. Binary download now uses pinned version from `downloads.yml` instead of fetching `latest`, and re-downloads on reprovision to pick up version changes.
- **Plugin Path Resolution**: Create symlink from macOS home path (e.g. `/Users/<user>`) to VM home directory so that absolute host paths in mounted Claude Code plugin metadata resolve correctly

### Added

- **Dart + Flutter**: Dart language option now always installs the Flutter SDK alongside the Dart SDK on both Alpine and Ubuntu VMs. Flutter version is aligned to the selected Dart version (Dart 3.7→Flutter 3.29.2, 3.6→3.27.4, 3.5→3.24.5). The `flutter` command is available on the PATH in all new shell sessions.
- **Host Environment Variable Forwarding**: Configurable allowlist of host environment variables forwarded into the VM shell session via Lima's `--preserve-env` mechanism
  - New `vm.forward_env` config field in `.clauded.yaml`
  - Wizard prompts with `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` pre-selected
  - Only forwards variables that are actually set on the host
  - Uses `LIMA_SHELLENV_ALLOW` for precise allowlisting (no full env leakage)
- **OpenAI Codex Framework Support**: Added Codex as a default framework for Ubuntu and Alpine VMs
  - Installed via npm (`npm install -g @openai/codex`) alongside Claude Code
  - Automatically included in all new VM configurations
  - Follows the same npm installation pattern as Playwright framework
- **VM Stop Confirmation Prompt**: Interactive confirmation before stopping VM
  - Prompt appears when exiting last active session with `keep_vm_running: false`
  - User can confirm (Yes/Y/Enter) to stop VM or decline (No/N) to keep it running
  - Ctrl+C or Ctrl+D during prompt cancels stop (VM stays running)
  - Non-interactive mode (piped stdin) stops VM silently without prompts
  - Preserves existing behavior: no prompt when `keep_vm_running: true` or other sessions active

- **CLI Distribution Selection**: `--distro` flag for distro selection at VM creation
  - `--distro alpine` or `--distro ubuntu` to specify distribution
  - Validates against supported distros (alpine, ubuntu)
  - Shows clear error for unsupported distros with list of supported options
  - Conflicts with existing config show helpful error messages
  - Works with both `--detect` and `--no-detect` flags
- **Wizard Distribution Selection**: Interactive distro selection in setup wizard
  - Distro selection shown as FIRST wizard question
  - Defaults to Alpine Linux
  - Respects `--distro` flag pre-selection (skips question if flag provided)
  - Shows "Alpine Linux" and "Ubuntu" as display names
  - Generated config includes selected distro in `vm.distro` field
- **Distribution Change Detection**: Automatic detection and handling of distro changes
  - Reads actual distro from VM via SSH after boot (/etc/clauded.json)
  - Detects mismatches between config and running VM
  - Shows clear warning about VM recreation and data loss
  - User confirmation required (y/N) before VM destruction
  - Automatically recreates VM with new distro on confirmation
  - Exits safely without changes on cancellation
  - Only checks when VM is running and provisioned
- **Distribution Provider Infrastructure**: Foundational support for multi-distribution VMs
  - Added `vm.distro` field to config schema (supports 'alpine', 'ubuntu')
  - Created DistroProvider protocol with AlpineProvider and UbuntuProvider implementations
  - Added Ubuntu 24.04 LTS cloud image metadata to downloads.yml
  - Config defaults to 'alpine' when distro field missing (backward compatibility)
  - VM metadata (/etc/clauded.json) now includes distro field
  - Comprehensive unit tests for distro validation and provider implementations
- **Complete Multi-Distribution Support**: All Ansible roles now have both Alpine and Ubuntu variants
  - 46 total role variants: 23 Alpine + 23 Ubuntu
  - Core roles: common, python, node
  - Language roles: java, kotlin, rust, go, dart, c
  - Tool roles: docker, uv, poetry, maven, gradle, aws_cli, gh
  - Database roles: postgresql, redis, mysql, sqlite, mongodb
  - Framework roles: claude_code, playwright
  - Each variant uses distro-appropriate package managers (apk vs apt) and service managers (OpenRC vs systemd)
  - Strict variant architecture: no distro conditionals in role tasks
  - Provisioner automatically appends -alpine or -ubuntu suffix based on config
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
