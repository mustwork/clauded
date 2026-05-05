# Add opencode as a Selectable Harness

**Created**: 2026-05-04
**Status**: In Progress
**Depends on**: `epic-remove-alpine-support` (Ubuntu-only target — *not yet merged; this epic targets the pre-removal codebase*)
**Related**: `epic-add-codex-framework` (precedent for adding a framework alongside `claude-code`)

## Implementation Decisions (2026-05-04)

Resolved before kickoff:
- **Alpine state**: pre-removal. Role lives at `src/clauded/roles/opencode-ubuntu/tasks/main.yml`; `opencode` is added to `_ROLES_WITH_VARIANTS`; NFR5 distro guard is active and raises `ConfigValidationError` when `distro=alpine` + `opencode` in frameworks. No `opencode-alpine` variant is created.
- **Story 07 deferred**: Migration stops after Story 06 (documentation). The end-to-end VM provisioning validation and release tagging are manual user-driven steps after merge — not part of the agent team's scope.
- **No architecture debate**: spec already contains 4 ADRs covering the load-bearing decisions. Architecture.md is synthesized directly from exploration findings.

## Overview

Add [opencode](https://opencode.ai) as a third AI coding agent that can be installed and launched inside `clauded` VMs, alongside the existing `claude-code` (default) and `codex` frameworks.

In addition, introduce a **harness** abstraction: the AI CLI that becomes the entrypoint shell command when `clauded` enters a VM is now a user choice — `claude-code` (default), `codex`, or `opencode`. The harness is configurable in the wizard, persisted in `.clauded.yaml`, and overridable per invocation via a new `--harness` CLI flag.

The change is Ubuntu-only by design. Alpine is being removed in `epic-remove-alpine-support`; this epic does not introduce an `opencode-alpine` role.

## Background

`clauded` already installs `claude-code` and `codex` in every VM as non-configurable defaults (see `epic-add-codex-framework`). However, the VM entrypoint is hardcoded to `claude` in `src/clauded/lima.py:shell()`:

```python
claude_cmd = "claude"
if self.config.claude_dangerously_skip_permissions:
    claude_cmd += " --dangerously-skip-permissions"
full_cmd = f"USE_BUILTIN_RIPGREP=0 {claude_cmd}"
```

So although `codex` is installed, the user has to invoke it manually from inside the shell. opencode magnifies this gap because its primary value is provider-agnostic LLM access (Anthropic, OpenAI, OpenRouter, local models, GitHub Copilot, etc.) — which is the kind of thing a developer would reasonably want as their default daily driver, not a buried second-class citizen.

The harness abstraction unifies the three options behind a single concept: which agent does `clauded` launch you into? The user picks. The CLI flag `--harness` provides per-session override (e.g. "today I want opencode for this project even though my config says claude-code").

## Motivation

### Why opencode

1. **Provider agnosticism**: opencode supports 75+ model providers via the Vercel AI SDK and `models.dev`. Users with OpenRouter, Bedrock, Vertex, or local Ollama setups can use the same harness. claude-code is locked to Anthropic; codex is locked to OpenAI.
2. **Single static binary**: opencode ships as statically-linked Bun binaries with native `linux-arm64` and `linux-x64` releases. No Node.js runtime requirement; no glibc/musl edge case (although musl variants are published, this epic targets Ubuntu/glibc only).
3. **Standard auto-accept flag**: `opencode run --dangerously-skip-permissions` mirrors `claude --dangerously-skip-permissions`. Behavior parity with the existing harness.
4. **TUI + headless modes**: `opencode` (TUI), `opencode run "<prompt>"` (headless one-shot), `opencode serve` (HTTP API). The TUI is the relevant mode for clauded; the others remain available to the user inside the VM.
5. **Active development**: as of 2026-05-04 the canonical repo is `github.com/anomalyco/opencode` (the previous `github.com/sst/opencode` URL 301-redirects there). Latest stable: v1.14.33, MIT-licensed.

### Why a harness abstraction

1. **No silent winners**: today, "clauded installs codex" is half-true — `codex` is on PATH, but the user has to know that and exit the claude-code session to use it. Making the entrypoint an explicit choice is honest about what `clauded` does.
2. **Per-project preference**: language-server-like tools work because each project picks its own. A Java project might want opencode-with-Anthropic; a TypeScript project might want claude-code; an experimental project might want codex. Harness-per-project removes the "switch globally" friction.
3. **Testing surface**: the existing `lima.py:shell()` hardcodes one path. A harness abstraction forces the launch logic into a small dispatcher that is unit-testable.
4. **Future harnesses are cheap**: adding a fourth (e.g. `aider`, `cursor-agent`, `goose`) becomes "add a role + register a launch builder" rather than "patch `lima.py` again". The cost lands now, once.

### Out-of-scope speculation

This epic does **not**:
- Add provider auth bootstrap (env-var forwarding stays as-is; user supplies API keys).
- Add multi-harness sessions in one VM run (one harness per `clauded` invocation).
- Add an "all harnesses installed but launch nothing" mode — there is always a harness, even if the user picks claude-code.
- Treat the harness as a first-class concept inside the `frameworks` list in any way that breaks existing configs.

## Goals

1. **opencode installed on PATH** in any new Ubuntu VM where the user opts in via the wizard or sets `frameworks: [..., opencode]` in `.clauded.yaml`.
2. **Harness selection** persisted in `.clauded.yaml` as `harness: claude-code | codex | opencode` (default `claude-code` for backward compat).
3. **`--harness <name>` CLI flag** overrides the persisted choice for one invocation.
4. **Wizard adds a harness step** after the frameworks selection. The wizard ensures the chosen harness is also in `frameworks`.
5. **Backward compatibility**: existing `.clauded.yaml` files without `harness` continue to load with default `claude-code`.
6. **No regressions** for users who never touch the harness setting.

## Non-Goals

- Alpine support for opencode (rolled into `epic-remove-alpine-support`).
- Cross-architecture validation beyond what `clauded` already supports (arm64 primary; x64 only inasmuch as it already worked).
- Auto-detecting which harness "fits" a project (no heuristic).
- Bundling opencode auth pre-flight (user logs in via `opencode auth login` inside the VM, same as today's claude-code/codex flows).

## Functional Requirements

### FR1: Add opencode Ansible role (Ubuntu-only)

Create `src/clauded/roles/opencode/tasks/main.yml`. After `epic-remove-alpine-support` lands, role names are bare (no `-ubuntu` suffix). If this epic merges before that one, the role lives at `src/clauded/roles/opencode-ubuntu/tasks/main.yml` and is added to `_ROLES_WITH_VARIANTS`; no `opencode-alpine` variant is created, and selecting `opencode` on an Alpine config raises `ConfigValidationError`.

**Installation method**: official install script, pinned by version. Rationale: matches upstream's documented "preferred on Linux" path, produces a single statically-linked binary, no Node.js dependency. The npm route (`npm install -g opencode-ai`) is a viable alternative (and simpler for version pinning), but pulls per-arch optional dependencies via npm's `optionalDependencies` mechanism, which can mis-resolve in non-standard npm configurations and adds a Node.js requirement we'd otherwise avoid.

The role MUST:

1. Resolve the target version:
   - If `opencode_version != "latest"`: use the value verbatim.
   - Otherwise: fetch `https://api.github.com/repos/anomalyco/opencode/releases/latest` and parse `tag_name` (`vX.Y.Z`).
2. Run the install script as the unprivileged VM user with `OPENCODE_INSTALL_DIR=$HOME/.local/bin` and `--no-modify-path`:
   ```
   curl -fsSL https://opencode.ai/install | bash -s -- --version <version> --no-modify-path
   ```
   - `--no-modify-path` prevents the script from appending its own line to `~/.bashrc` (clauded already manages `$HOME/.local/bin` on PATH via `/etc/profile.d/claude.sh` for Ubuntu; that file or a sibling `/etc/profile.d/opencode.sh` ensures coverage).
   - `OPENCODE_INSTALL_DIR=$HOME/.local/bin` colocates the binary with `claude` for consistency.
3. Verify the install: `opencode --version` returns the requested version.
4. Be idempotent: a re-run with the same version does nothing; a re-run with a different version replaces the binary.

The role MUST NOT:

- Install Node.js (opencode binaries are Bun-static; no runtime needed).
- Run `opencode auth login` or any interactive flow.
- Pre-populate `~/.config/opencode/opencode.json` (project-local `opencode.json` and user-supplied env vars are sufficient).

**Pre-existing-binary cleanup**: opencode README explicitly warns *"Remove versions older than 0.1.x before installing"* (legacy from the abandoned Go `opencode-ai/opencode` rename). The role MUST detect a pre-existing `opencode` binary that does not respond to `opencode --version` with a `1.x.x` or higher value, and replace it. (In practice: install script handles overwrite; we only need to ensure no stale `apt`-installed opencode shadows the new binary on PATH. Document but skip auto-removal — Ubuntu has no opencode in apt.)

### FR2: Add opencode as a configurable framework

- `frameworks` accepts the literal string `opencode`.
- Wizard offers `opencode` in the frameworks multi-select (alongside `playwright`).
- Provisioner (`provisioner.py:_get_base_roles`) appends `opencode` to the role list when `"opencode" in config.frameworks`.
- Unlike `claude-code` and `codex`, opencode is **not** a non-configurable default — installing it costs network and disk and only matters if the user wants the harness or the binary on PATH. It's opt-in.

### FR3: Harness abstraction in Config

- New field on `Config` dataclass: `harness: str = "claude-code"`.
- Allowed values: `"claude-code"`, `"codex"`, `"opencode"`.
- Persisted in `.clauded.yaml` under `harness:` at the top level (sibling of `vm:`, `mount:`, `environment:`).
- `Config.load()` reads the field; missing → default `"claude-code"`; unknown value → `ConfigValidationError` listing accepted values.
- `Config.save()` always emits the field (not omitted-when-default; explicit is friendlier for the human reader of the YAML).

### FR4: Harness ⇒ framework consistency

The harness must be installed. Validation rule applied during config load and after wizard completion:

| harness | required framework |
|---|---|
| `claude-code` | `claude-code` (always present per existing default) |
| `codex` | `codex` (always present per existing default) |
| `opencode` | `opencode` (must be in `frameworks`) |

If `harness == "opencode"` but `"opencode" not in frameworks`, `Config.load()` raises `ConfigValidationError`:

```
harness "opencode" requires "opencode" in frameworks. Add it to .clauded.yaml
under environment.frameworks, or run `clauded --edit` and pick opencode in
both the frameworks selection and the harness selection.
```

The wizard prevents this state by auto-adding `opencode` to `frameworks` when the user selects it as harness, with an info-level message: *"opencode added to frameworks (required by harness selection)."*

### FR5: Wizard harness selection step

After the existing "Select frameworks" multi-select, the wizard prompts:

```
Select harness (the AI agent launched when entering the VM):
  > Claude Code (default)
    Codex
    opencode  [adds opencode to frameworks]
```

- Default cursor on the user's current selection (or `claude-code` for new configs).
- The third entry is shown only if `opencode` is already selected as a framework, OR the entry is selectable and triggers the auto-add described in FR4.
  - **Recommendation**: always show the entry; auto-add on selection. This avoids a "go back and tick the box" loop.
- The wizard stores `answers["harness"] = "<chosen-value>"`; `Config.from_wizard()` reads it.

### FR6: `--harness` CLI flag

- New Click option: `--harness <claude-code|codex|opencode>`.
- Validates against the allowed set; invalid value → exit code 2 with Click's standard error.
- Behavior:
  - **Override-only**: the flag changes the harness for this invocation. It does NOT modify `.clauded.yaml`.
  - **Validation**: if the chosen harness is not in the loaded config's `frameworks`, exit code 1 with a message:
    ```
    Harness "opencode" requires opencode to be installed in this VM, but it is
    not in `frameworks` of .clauded.yaml. Add it via `clauded --edit` and
    reprovision, or pick a different harness.
    ```
- Interaction with `--edit`: the flag is ignored during `--edit` (the wizard step is the canonical place to change the persisted harness). `--harness` with `--edit` produces a one-line warning and the wizard runs normally.
- Interaction with `--reprovision`, `--detect`, `--stop`, `--destroy`: the flag is silently ignored — those workflows do not enter the harness shell.

### FR7: Harness-aware shell launch in `lima.py`

`LimaVM.shell()` is refactored to dispatch on `self.config.harness` (or the per-invocation override; see FR8 for plumbing). The current monolithic implementation becomes a small registry:

| harness | command construction | permission flag |
|---|---|---|
| `claude-code` | `USE_BUILTIN_RIPGREP=0 claude` | append `--dangerously-skip-permissions` if `claude_dangerously_skip_permissions` |
| `codex` | `codex` | append `--dangerously-bypass-approvals-and-sandbox` if `claude_dangerously_skip_permissions` (see FR9 on the rename) |
| `opencode` | `opencode` (TUI by default) | no per-invocation flag — opencode's permission model is config-file-based; document but don't auto-set |

Notes:
- `USE_BUILTIN_RIPGREP=0` is a claude-code-specific workaround for the Alpine/musl bundled-ripgrep issue. After `epic-remove-alpine-support`, this env var becomes unnecessary on Ubuntu and SHOULD be dropped from the claude-code launch builder. (Boy-scout rule: do this in the same PR as the launch refactor; it's a one-line removal.)
- The codex builder is a new code path with this epic; previously codex was only invoked manually inside the shell. Its construction is symmetric with claude-code.
- opencode does not accept a per-invocation `--dangerously-skip-permissions` on the bare TUI launch; that flag is documented for `opencode run`. For TUI-mode auto-accept, opencode reads the user's `~/.config/opencode/opencode.json`. We do not modify that file. If a user wants TUI auto-accept they configure it themselves in opencode.

### FR8: Plumbing the override flag to `LimaVM`

- Add a `harness_override: str | None = None` parameter to `LimaVM.__init__` (or to `LimaVM.shell()` directly — implementation choice). When set, the launch builder uses it instead of `self.config.harness`.
- `cli.py` constructs `LimaVM(config, harness_override=harness)` (or analogous) before calling `vm.shell()`.

### FR9: Permission flag naming

The existing `claude_dangerously_skip_permissions` config field is harness-specific in name but harness-generic in intent. Two options:

1. **Keep the name as-is** (status quo). The flag means "auto-accept tool prompts wherever the harness supports it". claude-code: passes `--dangerously-skip-permissions`. codex: passes `--dangerously-bypass-approvals-and-sandbox`. opencode: not applied to TUI.
2. **Rename to `harness_skip_permissions`**, deprecate the old key with a migration shim.

**Decision**: option 1. Renaming touches every test and the wizard prompt for marginal clarity gain. The wizard prompt is updated to: *"Auto-accept agent permission prompts in VM (where supported)?"* — no longer Claude-specific. Code variable name remains `claude_dangerously_skip_permissions`; this is internal-only and a rename can happen later if it ever justifies the churn.

### FR10: Mount opencode user state from host

Existing `lima.py` already mounts `~/.claude` and `~/.codex` from host into VM (per the `claude_dir` and `codex_dir` blocks around `lima.py:398–415`). Add equivalent mounts for opencode:

- Host `~/.config/opencode` ↔ VM `~/.config/opencode` (config + TUI prefs).
- Host `~/.local/share/opencode` ↔ VM `~/.local/share/opencode` (auth.json, MCP OAuth tokens, sessions).

If the host directories don't exist yet, `lima.py` MUST create them (with `mkdir(exist_ok=True)`) before generating the Lima YAML — same pattern as the existing `claude_dir.mkdir(exist_ok=True)` line.

This makes opencode authentication persistent across `clauded --destroy && clauded` cycles, matching the user expectation set by claude-code and codex.

### FR11: Update check parity for opencode

`cli.py` already implements bidirectional version checks for `claude-code` (via GCS bucket "latest" pointer) and `codex` (via npm registry). Add an opencode equivalent:

- New helper: `_get_latest_opencode_version()` — fetches `https://api.github.com/repos/anomalyco/opencode/releases/latest` and extracts the version from `tag_name`.
- New helper: `_update_opencode(vm, version_str)` — runs the install script inside the VM with `--version <version_str>`.
- `_resolve_framework_versions()` extended: when `"opencode" in config.frameworks`, resolve the desired version (config pin or latest).
- `_check_library_updates()` extended: include opencode in the comparison/prompt loop.
- New `Config.opencode_version: str | None = None` field; serialized under `versions:` alongside the existing `claude-code` and `codex` pins.

### FR12: Documentation

Update:
- `README.md`: frameworks table gains an `opencode` row; add a short "Choosing a harness" subsection with example invocations:
  ```bash
  clauded --harness opencode    # one-off override
  clauded --edit                # persist via wizard
  ```
- `specs/spec.md`: add `opencode` to the runtime/framework list, document the `harness` config field, document `--harness` flag, document the `harness ⇒ framework` validation rule.
- `docs/configuration.md`: section "Choosing a harness" with the matrix in FR7 and the `.clauded.yaml` snippet:
  ```yaml
  harness: opencode
  environment:
    frameworks:
      - claude-code   # always present
      - codex         # always present
      - opencode
  versions:
    opencode: 1.14.33  # optional
  ```
- `CHANGELOG.md`: under `[Unreleased]`:
  - `Added`: opencode framework, `--harness` flag, harness wizard step, opencode mount points, opencode update check.
  - `Changed`: VM entrypoint command is now selected by `harness` (default `claude-code` is unchanged behavior).

### FR13: Tests

- Unit: `Config.load` rejects unknown harness values with `ConfigValidationError`.
- Unit: `Config.load` rejects `harness=opencode` when `opencode` not in `frameworks`.
- Unit: `Config.load` defaults missing `harness` to `claude-code` and emits no warning.
- Unit: `Config.from_wizard` accepts `harness` from answers.
- Unit: wizard auto-adds `opencode` to `frameworks` when harness=opencode is chosen.
- Unit: provisioner includes `opencode` role iff `"opencode" in config.frameworks`.
- Unit: launch builder dispatches to the correct command for each harness (mock subprocess; assert argv).
- Unit: `--harness` CLI flag with invalid value exits 2.
- Unit: `--harness` CLI flag with harness not in `frameworks` exits 1 with the FR6 error.
- Unit: `_get_latest_opencode_version()` parses GitHub API response correctly (mocked).
- Integration / e2e (manual or scripted): provision Ubuntu VM with `frameworks: [opencode]`, verify `opencode --version` succeeds; verify `clauded --harness opencode` enters the opencode TUI.
- Coverage threshold (80 %) must remain satisfied.

## Non-Functional Requirements

### NFR1: Default behavior unchanged

A user who never sets `harness` and never uses `--harness` observes zero behavioral change. `claude` is still the entrypoint. Existing configs do not require migration.

### NFR2: One source of truth for the harness

The harness is set in exactly one place per invocation: the `--harness` flag if present, else `Config.harness`. The launch dispatcher reads from a single attribute. No fallback chains, no env-var precedence.

### NFR3: Error messages cite the next user action

Every harness-related validation error MUST include a concrete CLI command the user can run to fix the state (`clauded --edit`, edit `.clauded.yaml` line N, etc.). See FR4 and FR6 for examples.

### NFR4: Network failure during install is recoverable

The opencode install script writes to a temp location and only moves into place on success. If the role fails halfway, re-running provisioning succeeds. (Native behavior of the official installer; verify and document, do not re-implement.)

### NFR5: Ubuntu-only constraint is enforced, not assumed

If `epic-remove-alpine-support` has not yet landed at merge time, the opencode role exists only as `opencode-ubuntu/`, and `_get_base_roles()` raises `ConfigValidationError` when `vm_distro == "alpine"` and `"opencode" in frameworks`. The error message points at `epic-remove-alpine-support` and suggests `--distro ubuntu`.

After `epic-remove-alpine-support` lands, this guard is unnecessary (Alpine no longer exists) and can be removed.

## Architecture Decisions

### ADR-001: `--harness` is a per-invocation override, not persisted

**Context**: should the flag write back to `.clauded.yaml`?

**Options**:
1. Override only; do not modify config.
2. Override and persist (every `--harness` invocation rewrites `.clauded.yaml`).
3. New flag `--set-harness` for persist; `--harness` is override-only.

**Decision**: option 1. Persisted state changes belong in `--edit`. The flag is a "today I want to try X" lever; the config is the team-shared declaration.

**Pros**: predictable, no surprise rewrites, matches `--distro` flag's prior behavior.
**Cons**: a user who decides "I always want opencode now" must also `clauded --edit`. Acceptable: one explicit step beats silent state drift.

### ADR-002: Install opencode via official script, not npm

**Context**: opencode is distributed both as `opencode-ai` on npm and via `https://opencode.ai/install`.

**Options**:
1. npm — leans on existing Node.js role for codex/playwright users; pins via `npm install -g opencode-ai@<version>`.
2. Official install script — single static binary, no Node.js dependency, baseline/AVX2 detection handled by the script.
3. Direct GitHub release tarball — most control, most code to write.

**Decision**: option 2. The Node.js dependency for opencode would couple it to the `node` role (currently only auto-bundled with `codex` and `playwright`); decoupling is cleaner. The install script handles arch detection (`linux-arm64` vs `linux-x64`, `-baseline` for non-AVX2 CPUs) better than we'd want to hand-roll.

**Pros**: no Node.js coupling, no per-arch logic in the role, official upgrade path.
**Cons**: pulls a shell pipeline into provisioning (`curl | bash`). Pinned version mitigates supply-chain concern; HTTPS transport is the project's existing trust model (see `specs/spec.md` Security Model).

### ADR-003: Harness is independent of frameworks but validated against them

**Context**: should `harness` *be* an entry in `frameworks`, or a separate concept?

**Options**:
1. Single field — `frameworks[0]` is the harness; rest are auxiliary.
2. Separate `harness` field, validated to require its corresponding framework.
3. Reuse `frameworks` order, pick the first one in a known harness set.

**Decision**: option 2. Frameworks are a *set* of installed tools; harness is an *ordering* — exactly one is the launched entrypoint. Conflating them would force ugly invariants (no duplicates, ordering-as-meaning) that YAML doesn't enforce naturally. Two fields, one validation rule, one error path.

**Pros**: easy to reason about; trivial to add a fourth harness later; configs read naturally.
**Cons**: small redundancy (the harness name also appears in `frameworks`). Acceptable.

### ADR-004: opencode is opt-in, not a non-configurable default

**Context**: claude-code and codex are non-configurable defaults (always installed). Should opencode be too?

**Decision**: no. opencode duplicates capability the user may already get from claude-code or codex; installing it unconditionally costs ~30 MB binary + GitHub API request per provision, with low marginal value for users who don't intend to use it. Unlike claude-code/codex (which are *always* useful inside an AI development VM), opencode is a tool the user picks because of its provider-agnosticism.

**Pros**: lighter default install; clearer signal-in-config that opencode is intentional.
**Cons**: users who try `--harness opencode` without first opting in get the FR6 error. The error is descriptive and points at `--edit`.

## Architectural Impact

### Module diff (rough)

| Module | LoC delta | Notes |
|---|---|---|
| `src/clauded/roles/opencode/tasks/main.yml` | +50 (new) | Per FR1 |
| `src/clauded/config.py` | +30 | Harness field, validation, load/save |
| `src/clauded/provisioner.py` | +5 | Add `opencode` to `_ROLES_WITH_VARIANTS` (if pre-Alpine-removal); add framework branch |
| `src/clauded/wizard.py` | +30 | Harness step in `run()` and `run_edit()`; auto-add to frameworks |
| `src/clauded/cli.py` | +60 | `--harness` flag, `_get_latest_opencode_version`, `_update_opencode`, `_resolve_framework_versions` extension, `_check_library_updates` extension |
| `src/clauded/lima.py` | +40 | Harness dispatcher in `shell()`; opencode mount blocks |
| `src/clauded/downloads.yml` | +5 | opencode GitHub API endpoint (optional centralization) |
| `tests/` | +10 files of unit tests, ~+400 LoC | Per FR13 |
| `docs/configuration.md`, `README.md`, `specs/spec.md`, `CHANGELOG.md` | ~+100 LoC | Per FR12 |

Net: ~+700 LoC, ~12 new files.

## User Experience Flow

### Scenario 1: New project, opencode-curious user

```bash
cd ~/myproject
clauded
```

Wizard runs. At "Select frameworks", the user picks `opencode` and `playwright`. At "Select harness", the user picks `opencode` (cursor defaults to `claude-code`). Wizard saves `harness: opencode` and `frameworks: [claude-code, codex, opencode, playwright]`. VM provisions with all four installed. Shell entrypoint is the opencode TUI.

### Scenario 2: Existing claude-code user, one-off opencode test

```bash
cd ~/myproject  # has .clauded.yaml with default harness (claude-code)
clauded --edit  # add opencode to frameworks; keep harness=claude-code
clauded --harness opencode
```

After `--edit`, opencode is installed. The flag override launches opencode for this invocation. Next `clauded` (no flag) returns to claude-code.

### Scenario 3: Existing user, no harness in config

```bash
cd ~/myproject  # legacy .clauded.yaml, no `harness:` field
clauded
```

`Config.load()` defaults `harness` to `claude-code`. Behavior is identical to pre-epic. No warning, no migration prompt.

### Scenario 4: Misconfigured harness

```bash
cd ~/myproject  # .clauded.yaml has `harness: opencode` but `frameworks: [claude-code, codex]`
clauded
```

```
Error: harness "opencode" requires "opencode" in frameworks. Add it to
.clauded.yaml under environment.frameworks, or run `clauded --edit` and pick
opencode in both the frameworks selection and the harness selection.
```

Exit code 1; no VM operations attempted.

### Scenario 5: Invalid `--harness` value

```bash
clauded --harness gemini
```

```
Error: Invalid value for '--harness': 'gemini' is not one of 'claude-code',
'codex', 'opencode'.
```

Exit code 2 (Click's standard for invalid options).

## Acceptance Criteria

See `acceptance-criteria.md` for the full enumerated list.

## Risk Analysis

| Risk | Severity | Mitigation |
|---|---|---|
| `epic-remove-alpine-support` lands after this epic, leaving an awkward "no opencode-alpine variant" state | Low–Medium | NFR5: explicit `ConfigValidationError` on Alpine + opencode. Either order of merge is safe. |
| opencode upstream renames the repo *again* (third time) | Low | Version-pin the install script call; document the source repo in `downloads.yml`. Migration is a one-line URL change. |
| Install script `curl \| bash` flagged by security review | Low | Already the project's pattern (claude-code uses the same approach). Pinned version + HTTPS transport is the documented trust model. |
| TUI rendering breaks under Lima's PTY allocation | Low–Medium | `limactl shell` already works for claude-code's TUI and for codex's; opencode uses the same Bun-driven terminal path that has shipped to thousands of macOS-via-iTerm/wezterm users. Risk mostly theoretical; verify in e2e. |
| User has multiple opencode authentications across projects, mounts conflict | Low | Same pattern as `~/.claude` and `~/.codex` — a global host directory is mounted into every VM. This is the project's stance; document and move on. |
| Adding `--harness` flag confuses users when combined with `--reprovision` etc. | Low | FR6 explicitly defines the no-op interactions; help text mentions "ignored with --reprovision/--edit/etc.". |
| 80 % coverage threshold drops | Medium | Track per-story; FR13 lists targeted unit tests sized to maintain coverage. |
| opencode binary is large (~70 MB) and slows provisioning over slow networks | Low | Single download, cached in the provisioning step. Acceptable. |

## Migration Strategy

Phased delivery; each story leaves the codebase in a working state.

### Story 01 — opencode role and framework opt-in

- Create `src/clauded/roles/opencode-ubuntu/tasks/main.yml` (or `opencode/` if Alpine removal landed).
- Add `opencode` to `_ROLES_WITH_VARIANTS` (pre-Alpine-removal only).
- Add `opencode` to wizard's frameworks multi-select.
- Add `opencode` branch in `provisioner._get_base_roles()`.
- No harness changes yet — opencode is just a framework like playwright.
- **Observable change**: user can pick `opencode` in the wizard; `which opencode` works inside the VM.

### Story 02 — Harness config field

- Add `Config.harness` field with default `"claude-code"`.
- Implement load/save of the field.
- Add validation: harness ⇒ framework rule (FR4).
- Add unit tests.
- **Observable change**: `.clauded.yaml` files can carry a `harness:` line; existing configs default to `claude-code`. No behavior change yet — `lima.py` still hardcodes claude.

### Story 03 — Wizard harness step

- Add "Select harness" prompt in `wizard.run()` and `wizard.run_edit()`.
- Auto-add `opencode` to frameworks when chosen as harness.
- Update `Config.from_wizard()` to accept `harness`.
- **Observable change**: wizard exposes the new step; configs written by the wizard now contain `harness:`. Still no `lima.py` change.

### Story 04 — Harness-aware launch + `--harness` flag

- Refactor `lima.py:shell()` to dispatch on harness.
- Add `--harness` Click option in `cli.py`; plumb override into `LimaVM`.
- Drop the `USE_BUILTIN_RIPGREP=0` env var from the claude-code launch builder (boy-scout).
- **Observable change**: `clauded --harness opencode` enters opencode TUI; default behavior unchanged.

### Story 05 — Mount opencode state + update check

- Add `~/.config/opencode` and `~/.local/share/opencode` mount blocks in `lima.py`.
- Add `_get_latest_opencode_version()`, `_update_opencode()`, extend `_resolve_framework_versions()` and `_check_library_updates()`.
- Add `Config.opencode_version` field.
- **Observable change**: opencode auth persists across VM lifecycle; version-update prompts include opencode.

### Story 06 — Documentation, spec, CHANGELOG

- Update `README.md`, `specs/spec.md`, `docs/configuration.md`, `CHANGELOG.md`.
- **Observable change**: documentation reflects the new harness model.

### Story 07 — End-to-end validation and release (DEFERRED, manual)

Deferred to a manual post-merge step. The agent team stops after Story 06.
The user is responsible for:
- Provisioning a fresh Ubuntu VM with `harness: opencode, frameworks: [..., opencode]`.
- Running `opencode --version`, `clauded --harness opencode`, `clauded` with persisted opencode harness.
- Verifying all three harness paths (claude-code, codex, opencode) launch correctly.
- Tagging the release.

The full pytest + lint + typecheck gate is enforced inside Story 06 by the verifier; e2e VM exercise is the only thing this story would have added beyond what 01–06 already cover.

## Dependencies and Sequencing

- Stories 01 and 02 are independent and can land in either order.
- Story 03 depends on Story 02 (wizard reads/writes Config.harness).
- Story 04 depends on Stories 02 and 03 (override needs the field; flag needs wizard precedence rules).
- Story 05 depends on Story 01 (binary on PATH) and Story 02 (config field for `opencode_version`).
- Story 06 depends on Stories 01–05.
- Story 07 is deferred — manual post-merge step.

## Open Questions

1. **Should the `--harness` flag also accept short aliases (`oc`, `cc`, `cx`)?** Proposed: no. Three explicit strings, documented in `--help`. Aliases create a second naming surface.
2. **Should opencode become a non-configurable default later (matching claude-code/codex)?** Out of scope for this epic. Revisit once opencode usage data exists.
3. **Should we mount the project-local `opencode.json` somewhere special?** No — the project directory is already mounted at the same path host↔VM, so a project-local `opencode.json` is automatically available inside the VM.
4. **Should the harness name in `.clauded.yaml` use a hyphen (`claude-code`) or underscore (`claude_code`)?** Use the hyphen form to match the existing `frameworks` list values and the npm package convention.

## References

- opencode official site: https://opencode.ai
- opencode canonical repo: https://github.com/anomalyco/opencode
- opencode CLI docs: https://opencode.ai/docs/cli
- opencode config docs: https://opencode.ai/docs/config
- opencode providers: https://opencode.ai/docs/providers
- npm package: https://registry.npmjs.org/opencode-ai
- Existing precedent: `specs/epic-add-codex-framework/spec.md`
- Existing dependency: `specs/epic-remove-alpine-support/spec.md`
- Launch hardcoding: `src/clauded/lima.py:202–248`
- Role registry: `src/clauded/provisioner.py:23–55`, `provisioner.py:_get_base_roles` at lines 260–323

## Success Metrics

- A new Ubuntu VM provisioned with `frameworks: [..., opencode]` boots successfully and `opencode --version` returns the pinned (or latest) version.
- `clauded --harness opencode` enters the opencode TUI with no manual user steps inside the VM beyond `opencode auth login` (one-time).
- Existing users with no `harness:` line in `.clauded.yaml` observe zero behavior change.
- `clauded --edit` exposes the harness step and persists the choice.
- Lint, type-check, and test suite (≥ 80 % coverage) all green.
- README and `specs/spec.md` document the harness concept and `--harness` flag.
