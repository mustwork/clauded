# Epic Architecture: Add opencode as a Selectable Harness

**Epic**: `add-opencode-harness`
**Synthesised**: 2026-05-04 (no arch_debate; ADRs already in spec.md)
**Sources**: `exploration-similar-features.md`, `exploration-architecture.md`, `exploration-testing.md`

This is the operational architecture document the planner and architect read before
splitting and implementing stories. Story decomposition MUST respect the paradigm,
module map, and boundary rules declared here. Cross-story seams are recorded as
typed contracts.

---

## 1. Paradigm

- **Top level**: modular monolith. One Python package (`src/clauded/`) with cross-module
  imports through public functions and a single `Config` dataclass.
- **Within `clauded/detect/`**: package-by-feature (`framework.py`, `database.py`,
  `linguist.py`, `version_detection.py`, `wizard_integration.py` each own a slice).
- **External boundaries**: hexagonal ports. The world outside the Python process
  (Lima VM, Ansible, GitHub API, npm registry, GCS, the host filesystem) is reached
  only through subprocess calls (`limactl shell`, `ansible-playbook`, `curl`).
  No HTTP client library is used directly.

This epic does not change the paradigm. It refactors one fragile seam (the launch
dispatcher in `lima.py:shell()`) and introduces one new external boundary (GitHub
releases API for opencode version resolution, replacing npm-registry-via-VM for
this one harness).

---

## 2. Module Map

Modules this epic touches or creates. Bullets list owned data; cross-cutting types
that travel between modules are described in §4 (Seams).

### `src/clauded/config.py` (modified)
- **Purpose**: dataclass `Config` + load/save/from_wizard logic; emits/consumes
  `.clauded.yaml`.
- **Owns**: every persisted config field.
- **Changes for this epic**:
  - New field `harness: str = "claude-code"` on the dataclass (FR3).
  - New field `opencode_version: str | None = None` (FR11).
  - New validation: harness ⇒ framework rule (FR4).
  - New error message in `ConfigValidationError` for unknown harness values (FR3).
  - `from_wizard` accepts the new `harness` answer key.
  - `save` emits `harness:` always (not omitted-when-default) and `opencode` under
    `versions:` when pinned.

### `src/clauded/provisioner.py` (modified)
- **Purpose**: builds the Ansible role list from `Config`.
- **Owns**: `_ROLES_WITH_VARIANTS`, role ordering, distro-variant resolution.
- **Changes for this epic**:
  - Add `"opencode"` to `_ROLES_WITH_VARIANTS` (FR1; pre-Alpine-removal path).
  - In `_get_base_roles()`, append `"opencode"` to the role list when
    `"opencode" in config.frameworks` (FR2).
  - Raise `ConfigValidationError` when `vm.distro == "alpine"` and
    `"opencode" in config.frameworks` (NFR5).

### `src/clauded/roles/opencode-ubuntu/tasks/main.yml` (new)
- **Purpose**: Ansible tasks that install opencode in an Ubuntu VM.
- **Behaviour**: per FR1 — resolve version (pin or `latest` → GitHub API),
  run the official install script with `OPENCODE_INSTALL_DIR=$HOME/.local/bin`
  and `--no-modify-path`, verify with `opencode --version`, idempotent on rerun.
- **Out of scope**: `opencode auth login` (interactive), `~/.config/opencode/opencode.json`
  pre-population.

### `src/clauded/wizard.py` (modified)
- **Purpose**: interactive wizard for create/edit flows.
- **Owns**: question ordering, menu defaults, the `answers` dict shape.
- **Changes for this epic**:
  - Frameworks multi-select gains `opencode` as an option alongside `playwright`.
  - New `Select harness` step after the frameworks step (FR5). Three entries:
    `claude-code` (default), `codex`, `opencode`. Default cursor pre-selected from
    current config or `claude-code` for new configs.
  - Auto-add: when `harness == "opencode"`, the wizard appends `"opencode"` to
    `answers["frameworks"]` if not already present, with an info message.
  - `run_edit()` pre-selects the persisted harness.

### `src/clauded/detect/wizard_integration.py` (modified)
- **Purpose**: wizard variants that integrate framework detection (used by the
  detect/repair flows).
- **Owns**: 3 functions that each carry their own framework-options list.
- **Changes for this epic**: each of the 3 framework-options lists at
  `wizard_integration.py:186`, `:396`, `:752` adds `opencode`. (See §4 seam
  `framework_options_list`.)

### `src/clauded/cli.py` (modified)
- **Purpose**: Click entrypoint, mode dispatch, version-update prompting.
- **Changes for this epic**:
  - New Click option `--harness <claude-code|codex|opencode>` (FR6).
  - Plumb override into `LimaVM` (FR8).
  - New helper `_get_latest_opencode_version()` — fetches GitHub releases API.
  - New helper `_update_opencode(vm, version_str)` — runs install script in VM.
  - Extend `_resolve_framework_versions` to include opencode when in frameworks.
  - Extend `_check_library_updates` to include opencode.
  - `--harness` is silently ignored with `--reprovision`/`--detect`/`--stop`/`--destroy`;
    emits a warning with `--edit`.

### `src/clauded/lima.py` (modified)
- **Purpose**: VM lifecycle (`limactl` invocations) + Lima YAML construction.
- **Changes for this epic**:
  - Refactor `LimaVM.shell()` (currently `lima.py:202–248`) into a small dispatcher
    on `self.config.harness` (or a per-invocation override). Three branches:
    `claude-code`, `codex`, `opencode`. (FR7.)
  - Drop `USE_BUILTIN_RIPGREP=0` from the `claude-code` branch (boy-scout per spec
    Story 04). The other branches never had it.
  - Add `harness_override: str | None = None` parameter to `__init__` or `shell()`.
  - Add unconditional host mounts for `~/.config/opencode` and `~/.local/share/opencode`
    when `"opencode" in config.frameworks` (FR10). `mkdir(exist_ok=True)` if absent.

### Tests (`tests/`) (modified — many files)
- **Purpose**: unit tests; no integration/e2e in this repo.
- **Changes for this epic**: per FR13 — `test_config.py`, `test_wizard.py`,
  `test_provisioner.py`, `test_lima.py`, `test_cli.py`, `test_version_check.py`
  each gain opencode coverage following the existing patterns
  (`function-boundary-patch`, `recording-select-side-effect`,
  `paired-include-exclude-methods`, `isolated-filesystem-yaml`).

### Documentation (`README.md`, `specs/spec.md`, `docs/configuration.md`, `CHANGELOG.md`) (modified)
- **Purpose**: human-facing description of the harness concept and `--harness` flag.
- **Changes**: per FR12.

---

## 3. Boundary Rules

The following rules are non-negotiable for every story in this epic:

1. **No direct cross-module imports beyond declared public surfaces.** A module
   may import another module's public name (`from clauded.config import Config`)
   but not its internal helpers prefixed with `_`. The exception is the existing
   `cli.py` ↔ `provisioner.py` ↔ `lima.py` ↔ `wizard.py` ↔ `config.py` graph,
   which stays as-is.
2. **`Config` is the single source of truth for persisted state.** Stories MUST NOT
   add fallback chains, env-var precedences, or implicit defaults outside `Config`.
   The harness comes from exactly one place per invocation: the `--harness` flag if
   present, else `Config.harness`. (NFR2.)
3. **No HTTP client library.** External HTTP/HTTPS calls go through `subprocess.run`
   with `curl` (matching existing patterns). The new `_get_latest_opencode_version`
   helper follows this rule.
4. **Production code MUST NOT contain test-only adaptations.** Per project CLAUDE.md;
   reinforced by `task_completion_checklist.md` memory.
5. **Existing fragile seams (§4) require coordinated updates.** A story that
   touches only one location of a duplicated framework list is a defect. The
   planner must scope every framework-options edit story to update all 4 locations
   in lockstep.
6. **NEVER tailor production code towards tests** — the project CLAUDE.md rule.
   This forbids harness-specific `if "test" in env` branches and similar shims.
7. **Boy-scout exception is allowed**: dropping `USE_BUILTIN_RIPGREP=0` happens in
   the same PR as the launch dispatcher refactor (Story 04 per migration strategy).
   No other unrelated cleanups.

---

## 4. Seams (Cross-Story Contracts)

Seams are typed cross-story contracts that must be agreed before producer/consumer
stories begin. Empty contracts here mean "the planner must define this before
splitting stories that depend on it."

### Seam: `HarnessName` (literal type)
- **Defined by**: Story 02 (Config field).
- **Consumed by**: Stories 03 (wizard), 04 (CLI flag + dispatcher), 05 (no direct
  consumer, but the mount block keys off `frameworks` not `harness`).
- **Contract**:
  ```python
  HARNESS_NAMES: tuple[str, ...] = ("claude-code", "codex", "opencode")
  HarnessName = Literal["claude-code", "codex", "opencode"]
  ```
  - Default: `"claude-code"`.
  - Persistence key: top-level `harness:` in `.clauded.yaml`.
  - Wire format on `--harness` CLI flag: same three strings; click `Choice`.
  - Stored on `Config.harness: str` (typed as plain `str` for dataclass
    compatibility; validated against `HARNESS_NAMES` in `Config.load`).
- **Invariants**:
  1. `Config.harness in HARNESS_NAMES` after a successful `Config.load`.
  2. `harness == "opencode"` ⇒ `"opencode" in frameworks`.
  3. `harness in {"claude-code", "codex"}` always passes invariant 2 because
     those frameworks are non-configurable defaults (verified at exploration time).

### Seam: `LaunchSpec` (dispatcher output)
- **Defined by**: Story 04 (lima.py refactor).
- **Consumed by**: only `LimaVM.shell()`'s subprocess call site — this is an
  internal dispatcher seam, not a cross-module one.
- **Contract** (non-binding suggestion; architect finalises in Story 04
  `architecture.json`):
  ```python
  @dataclass
  class LaunchSpec:
      argv: list[str]              # e.g., ["claude", "--dangerously-skip-permissions"]
      env: dict[str, str]          # extra env vars to prepend; empty for opencode/codex
  ```
- **Invariants**:
  1. `argv[0] in {"claude", "codex", "opencode"}` (the binary name).
  2. `env` does NOT contain `USE_BUILTIN_RIPGREP=0` for any harness (boy-scout).
  3. For `harness == "opencode"`, no `--dangerously-*` flag is appended regardless
     of `claude_dangerously_skip_permissions` (FR7, AC-018).

### Seam: `OpencodeMounts` (Lima YAML mount entries)
- **Defined by**: Story 05.
- **Consumed by**: Lima YAML generation in `LimaVM` (internal).
- **Contract**: two unconditional host mounts when `"opencode" in config.frameworks`:
  - host `~/.config/opencode` ↔ guest `~/.config/opencode`
  - host `~/.local/share/opencode` ↔ guest `~/.local/share/opencode`
  - Both auto-created via `mkdir(exist_ok=True)` if absent (matches the
    existing `claude_dir.mkdir(exist_ok=True)` pattern).

### Seam: `OpencodeVersionResolution` (CLI helpers)
- **Defined by**: Story 05.
- **Consumed by**: `_resolve_framework_versions`, `_check_library_updates`, the
  Ansible role.
- **Contract**:
  - `_get_latest_opencode_version() -> str | None`: returns version string parsed
    from `tag_name` of `https://api.github.com/repos/anomalyco/opencode/releases/latest`,
    or `None` on network failure (matching the existing graceful-skip pattern from
    `_get_npm_latest_version`).
  - `_update_opencode(vm, version_str) -> None`: runs the install script inside
    the VM with `--version <version_str>`.
- **Invariants**:
  1. Pinned `Config.opencode_version` overrides "latest" resolution.
  2. `None` return from `_get_latest_opencode_version()` causes opencode to be
     silently skipped from the update prompt (no error to the user).

---

## 5. Implementation Constraints

These constraints apply across all stories and are non-negotiable:

1. **Pre-Alpine-removal targeting**: this epic merges before `epic-remove-alpine-support`.
   The opencode role lives at `src/clauded/roles/opencode-ubuntu/tasks/main.yml`,
   `opencode` is added to `_ROLES_WITH_VARIANTS`, and the NFR5 distro guard is active.
   No `opencode-alpine` variant is created — selecting it on Alpine raises
   `ConfigValidationError` pointing at `--distro ubuntu`.

2. **Coverage threshold ≥ 80 %** must remain satisfied at every story boundary
   (verified via `make check` which runs `pyproject.toml`'s `[tool.coverage.report]
   fail_under = 80`).

3. **CHANGELOG.md** under `[Unreleased]` must be updated in **every** story PR
   (per project CLAUDE.md). Entries go under the appropriate section (Added /
   Changed / Removed / Fixed). The final consolidated entry lives in Story 06.

4. **No interactive opencode flows** are run by Ansible: no `opencode auth login`,
   no opencode config file pre-population. The user authenticates inside the VM
   on first launch (matches the claude-code/codex pattern).

5. **GitHub API call** (in `_get_latest_opencode_version`) MUST handle rate limiting
   gracefully. `None` return is the correct behaviour on a 403/429, mirroring the
   existing `_get_npm_latest_version` skip-on-failure pattern.

6. **FR9 stays as option 1**: keep the config field name `claude_dangerously_skip_permissions`
   even though it is now harness-generic. The wizard prompt label changes; the code
   variable does not. No migration shim. No deprecation warning.

7. **Backward compatibility is a hard requirement** (NFR1, AC-022). A pre-epic
   `.clauded.yaml` with no `harness:` line and no `opencode` in frameworks loads
   cleanly and behaves identically to today.

8. **Each story leaves the codebase green**: `make check` (lint + typecheck +
   pytest with coverage) passes at every story boundary. The verifier runs
   `make check` as the test gate per the integration architect's protocol.

---

## 6. Story Decomposition Guidance

The spec already lays out 6 stories (Story 07 deferred). The planner refines and
records them in `stories.json`. Suggested `owning_module` per story:

| Story | Title | Owning module(s) |
|---|---|---|
| 01 | opencode role and framework opt-in | `provisioner.py`, `roles/opencode-ubuntu/`, `wizard.py` (frameworks-only edit) |
| 02 | Harness config field | `config.py` |
| 03 | Wizard harness step | `wizard.py`, `detect/wizard_integration.py` |
| 04 | Harness-aware launch + `--harness` flag | `lima.py`, `cli.py` |
| 05 | Mount opencode state + update check | `lima.py`, `cli.py` |
| 06 | Documentation, spec, CHANGELOG | `README.md`, `specs/spec.md`, `docs/configuration.md`, `CHANGELOG.md` |

The dependency graph (from spec):
- 01 ⟂ 02 (independent)
- 03 ← 02
- 04 ← 02, 03
- 05 ← 01, 02
- 06 ← 01, 02, 03, 04, 05

---

## 7. References

- `specs/epic-add-opencode-harness/spec.md` — full requirements
- `specs/epic-add-opencode-harness/acceptance-criteria.md` — 25 enumerated ACs
- `specs/epic-add-opencode-harness/exploration-similar-features.md` — codex precedent dossier
- `specs/epic-add-opencode-harness/exploration-architecture.md` — module-boundary dossier
- `specs/epic-add-opencode-harness/exploration-testing.md` — test-pattern dossier
- `specs/epic-add-codex-framework/` — completed precedent epic (full artifact set)
