# Acceptance Criteria: Add opencode as a Selectable Harness

Generated: 2026-05-04
Source: spec.md

## Criteria

### AC-001: opencode binary available on PATH after Ubuntu provisioning
- **Description**: After provisioning a VM with `"opencode"` in `config.frameworks`, the `opencode` binary is on PATH for the VM user.
- **Verification**: `which opencode` returns a path under `~/.local/bin`; `opencode --version` succeeds.
- **Type**: integration

### AC-002: opencode role pinned to requested version
- **Description**: When `versions.opencode` is set in `.clauded.yaml`, that exact version is installed; when omitted, the role installs the latest GitHub release.
- **Verification**: Provision with `versions.opencode: 1.14.33`; `opencode --version` reports `1.14.33`. Provision without the pin; `opencode --version` matches `tag_name` of `https://api.github.com/repos/anomalyco/opencode/releases/latest` at the moment of provision.
- **Type**: integration

### AC-003: opencode role does not install Node.js
- **Description**: A VM with `frameworks: [opencode]` (no codex, no playwright, no `node:` runtime) has no `node` binary.
- **Verification**: `which node` returns non-zero; the provisioner role list does not include `node`.
- **Type**: unit + integration

### AC-004: opencode role is idempotent
- **Description**: Running `clauded --reprovision` twice in a row with unchanged config does not reinstall opencode the second time (or completes without error if it does).
- **Verification**: Manual: capture `opencode --version` mtime before and after second reprovision; Ansible task `changed_when` evaluates to false on the second run.
- **Type**: integration

### AC-005: `Config.harness` defaults to `"claude-code"` when absent
- **Description**: Loading a `.clauded.yaml` without a `harness:` line yields `Config.harness == "claude-code"` and emits no warning.
- **Verification**: Unit test loads a fixture YAML lacking `harness:`; assert no warning logged and `config.harness == "claude-code"`.
- **Type**: unit

### AC-006: `Config.load` rejects unknown harness values
- **Description**: A `.clauded.yaml` with `harness: gemini` raises `ConfigValidationError` listing the accepted values.
- **Verification**: Unit test asserts `ConfigValidationError` raised, message contains `"claude-code"`, `"codex"`, and `"opencode"`.
- **Type**: unit

### AC-007: `Config.load` enforces harness ⇒ framework consistency
- **Description**: A `.clauded.yaml` with `harness: opencode` but no `opencode` in `frameworks` raises `ConfigValidationError` with an actionable message that names `clauded --edit`.
- **Verification**: Unit test asserts the error and message content; assert claude-code and codex variants do NOT raise (those frameworks are always present).
- **Type**: unit

### AC-008: `Config.save` persists `harness` field
- **Description**: After `Config.from_wizard({"harness": "opencode", ...}).save()`, the resulting YAML contains a top-level `harness: opencode` line.
- **Verification**: Unit test round-trips through save/load and asserts the field is present in the YAML text.
- **Type**: unit

### AC-009: Wizard exposes harness selection
- **Description**: `wizard.run()` prompts for harness selection after the frameworks step, with `claude-code` as the default cursor position for new configs.
- **Verification**: Unit test mocks `simple_term_menu` calls and asserts the harness menu is shown with the three expected entries; assert default index points at `claude-code`.
- **Type**: unit

### AC-010: Wizard auto-adds opencode to frameworks when chosen as harness
- **Description**: When the user picks `opencode` as harness, the resulting `Config.frameworks` contains `"opencode"` even if the user did not check the opencode box in the frameworks multi-select.
- **Verification**: Unit test simulates wizard answers `{"harness": "opencode", "frameworks": ["playwright"]}`; assert `config.frameworks` contains `"opencode"`.
- **Type**: unit

### AC-011: Wizard preserves harness on `--edit`
- **Description**: `wizard.run_edit()` pre-selects the current harness and saves the (possibly unchanged) value.
- **Verification**: Unit test loads a config with `harness: codex`, runs `run_edit` with no menu changes, asserts saved config still has `harness: codex`.
- **Type**: unit

### AC-012: `--harness` CLI flag overrides config for one invocation
- **Description**: Running `clauded --harness opencode` with a config of `harness: claude-code` (and `opencode` in frameworks) launches opencode this run; the saved `.clauded.yaml` still reads `harness: claude-code`.
- **Verification**: Integration test asserts the launch builder receives `harness="opencode"`; asserts file mtime/content of `.clauded.yaml` unchanged.
- **Type**: integration

### AC-013: `--harness` rejects values outside the accepted set
- **Description**: `clauded --harness gemini` exits with code 2 and prints Click's standard "invalid value" error.
- **Verification**: CLI test using `click.testing.CliRunner` asserts `result.exit_code == 2` and stderr contains `"Invalid value"`.
- **Type**: unit

### AC-014: `--harness` exits 1 when chosen harness is not in frameworks
- **Description**: `clauded --harness opencode` against a config that lacks `opencode` in frameworks exits with code 1 and prints the FR6 error message.
- **Verification**: CLI test asserts exit code 1 and stderr contains the precise message including `"clauded --edit"`.
- **Type**: unit

### AC-015: `--harness` ignored with `--edit`/`--reprovision`/`--stop`/`--destroy`
- **Description**: Combining `--harness` with any of those flags does not affect their behavior. `--harness` with `--edit` emits a one-line warning that the flag is ignored.
- **Verification**: CLI tests for each combination assert behavior matches the version of the workflow without `--harness`, except for the warning line in the `--edit` case.
- **Type**: unit

### AC-016: `lima.py:shell()` dispatches to claude-code by default
- **Description**: When `config.harness == "claude-code"` and no override, the launch command is `claude` with `--dangerously-skip-permissions` appended iff `claude_dangerously_skip_permissions` is true.
- **Verification**: Unit test mocks `subprocess.run`; asserts the constructed argv contains `claude` and (conditionally) the flag; asserts the `USE_BUILTIN_RIPGREP=0` env var is no longer prepended (after Story 04 boy-scout cleanup).
- **Type**: unit

### AC-017: `lima.py:shell()` launches codex correctly
- **Description**: When `config.harness == "codex"` (or override), the launch command is `codex`, with `--dangerously-bypass-approvals-and-sandbox` appended iff `claude_dangerously_skip_permissions` is true.
- **Verification**: Unit test asserts argv content for both true and false permission-skip values.
- **Type**: unit

### AC-018: `lima.py:shell()` launches opencode TUI correctly
- **Description**: When `config.harness == "opencode"` (or override), the launch command is `opencode` (no subcommand, no per-invocation permission flag).
- **Verification**: Unit test asserts argv content; asserts no `--dangerously-*` flag is appended regardless of `claude_dangerously_skip_permissions`.
- **Type**: unit

### AC-019: opencode user state mounted from host
- **Description**: For VMs with `opencode` in frameworks, host paths `~/.config/opencode` and `~/.local/share/opencode` mount into the VM at the same paths. Host directories are auto-created if missing.
- **Verification**: Unit test asserts `lima.py` Lima YAML generation includes both mount entries when `"opencode" in config.frameworks`. Manual: create a new project, run `clauded`, check that `mkdir ~/.config/opencode` and `~/.local/share/opencode` happened on the host.
- **Type**: unit + integration

### AC-020: opencode update check parity
- **Description**: `_check_library_updates()` includes opencode in its comparison loop when `"opencode" in config.frameworks`. Pinned version takes precedence over latest; latest is fetched from the GitHub releases API.
- **Verification**: Unit test mocks the GitHub API and asserts the prompt is built with both installed and target versions; asserts pin overrides latest.
- **Type**: unit

### AC-021: opencode `claude-code`/`codex`/`playwright` orthogonality
- **Description**: A VM can have any subset of `{claude-code, codex, opencode, playwright}` in frameworks; provisioning succeeds for every subset.
- **Verification**: Parametrized unit test over the 16 subsets; asserts `_get_base_roles()` returns a valid role list for each.
- **Type**: unit

### AC-022: Backward compatibility with pre-epic configs
- **Description**: A `.clauded.yaml` written by a pre-epic `clauded` (no `harness:`, no `opencode` framework, no `versions.opencode`) loads cleanly; default workflow enters the claude-code shell as before.
- **Verification**: Unit test loads a pre-epic fixture and asserts `config.harness == "claude-code"`, no errors, no warnings.
- **Type**: unit

### AC-023: Ubuntu-only enforcement (pre-Alpine-removal)
- **Description**: While `epic-remove-alpine-support` has not yet landed, attempting to use `frameworks: [opencode]` with `vm.distro: alpine` raises `ConfigValidationError` whose message points at `--distro ubuntu`.
- **Verification**: Unit test asserts the error and message content. (After Alpine removal, this test is removed alongside the validation.)
- **Type**: unit

### AC-024: All existing tests pass
- **Description**: No regressions introduced by the harness refactor or opencode addition.
- **Verification**: `make check` passes (lint + typecheck + test); coverage threshold (≥ 80 %) maintained.
- **Type**: unit

### AC-025: Documentation updated
- **Description**: README, `specs/spec.md`, `docs/configuration.md`, and `CHANGELOG.md` reflect the new harness concept, the `--harness` flag, the opencode framework, and the harness ⇒ framework rule.
- **Verification**: Manual review; grep for `harness` in those files yields the expected coverage.
- **Type**: documentation

## Verification Plan

1. Unit-test pass: `make check` green for AC-005…AC-018, AC-020…AC-023, AC-024.
2. Integration-test pass: provision a fresh Ubuntu VM with `frameworks: [opencode]` and exercise AC-001…AC-004, AC-012, AC-019.
3. Manual review: AC-025.
4. Grep audit: no Alpine-specific code is added by this epic; `grep -rn 'opencode-alpine' src/` returns no results.

## E2E Test Plan

### Scenario 1: Fresh project with opencode harness

- `cd` into a new project directory.
- Run `clauded`; in the wizard, select `opencode` as a framework AND as the harness.
- Assert: VM is created, opencode is on PATH, `clauded` enters the opencode TUI.

### Scenario 2: Add opencode to existing project

- Start from a project with default config (claude-code harness).
- Run `clauded --edit`; add `opencode` to frameworks; keep harness=claude-code.
- Run `clauded` (default invocation): claude-code TUI as before.
- Run `clauded --harness opencode`: opencode TUI launches; `.clauded.yaml` unchanged.

### Scenario 3: Persist opencode harness via `--edit`

- From Scenario 2's state, run `clauded --edit`; pick `opencode` as harness.
- Run `clauded` (no flag): opencode TUI launches.
- Inspect `.clauded.yaml`: contains `harness: opencode`.

### Scenario 4: Misconfigured harness recovery

- Manually edit `.clauded.yaml` to `harness: opencode` while `frameworks` lacks opencode.
- Run `clauded`: hard error per AC-007 with actionable message.
- Run `clauded --edit`: wizard resolves the inconsistency by auto-adding opencode to frameworks (AC-010); next provision installs it.

### Scenario 5: Version pinning and update prompt

- Set `versions.opencode: 1.14.32` in `.clauded.yaml` (one version behind latest at test time).
- Run `clauded`: update prompt offers to bump to latest (AC-020).
- Decline: opencode stays at 1.14.32.
- Accept: opencode upgrades to latest; `opencode --version` reports the new version.
