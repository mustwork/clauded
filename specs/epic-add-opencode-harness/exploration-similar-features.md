# Precedent Dossier: Adding opencode as a Third AI Coding Harness

Exploration focus: similar-features (codex as the reference implementation)

---

## 1. Codex Ansible Roles

Both Alpine and Ubuntu roles are structurally identical — the only difference is the comment header.

**`src/clauded/roles/codex-alpine/tasks/main.yml`** and **`src/clauded/roles/codex-ubuntu/tasks/main.yml`** (lines 1–18, both files):

- **Install method**: `npm install -g @openai/codex` (or `@openai/codex@{{ codex_version }}` when pinned). Uses Ansible `command:` module, not `npm:` module.
- **Version resolution**: Jinja2 inline conditional: `{% if codex_version != 'latest' %}@openai/codex@{{ codex_version }}{% else %}@openai/codex{% endif %}`. The variable `codex_version` is passed from the playbook vars (see provisioner.py:375).
- **Idempotency strategy**: `changed_when: "'added' in codex_npm_install.stdout or 'up to date' not in codex_npm_install.stdout"` — inspects npm output text rather than using `creates:`. The `codex_npm_install` register captures stdout.
- **PATH handling**: npm's global bin directory is used implicitly; no explicit PATH manipulation in the role. Node.js is guaranteed to be installed before this role runs (see provisioner.py:311–314).
- **Verification step**: `codex --version` is run after install; `changed_when: false` so it never marks the task changed.
- **No distro-specific differences**: The two files are character-for-character identical in task content.

---

## 2. Role Registration in `provisioner.py`

### `_ROLES_WITH_VARIANTS` (lines 23–55)

A `frozenset` of base role names that have distro-specific variants (e.g., `codex-alpine`, `codex-ubuntu`). When `_apply_distro_suffix()` processes a base role list, any role whose name is in this set gets a `-{distro}` suffix appended (line 153). Roles absent from the set keep their original name.

`"codex"` is registered at line 52 alongside `"claude_code"` and `"playwright"` in the "Framework roles (Story 06)" comment block.

Shape of entries: plain strings — e.g., `"codex"`, `"claude_code"`.

### `_get_base_roles()` (lines 257–323)

Returns a flat list of base role name strings (no suffix). The codex block is at lines 310–314:

```python
if "codex" in self.config.frameworks:
    # Codex requires npm for installation
    if "node" not in roles:
        roles.insert(roles.index("common") + 1, "node")
    roles.append("codex")
```

Key behaviours:
- Guard: only adds `codex` when `"codex"` is in `config.frameworks`.
- Node auto-dependency: if `node` is not already in the role list, it is inserted immediately after `common` (not appended) to preserve correct dependency order.
- Role ordering: `codex` is appended after all language/tool/database roles.

The identical pattern is used for playwright at lines 315–319.

### Other occurrences of `"codex"` in `provisioner.py`

- Line 375 (inside `_generate_playbook`): `"codex_version": self.config.codex_version or "latest"` — passes the version pin (or sentinel `"latest"`) into Ansible vars.

---

## 3. Config Wiring (`src/clauded/config.py`)

### `Config` dataclass field signatures (lines 234–290)

```python
frameworks: list[str] = field(default_factory=list)      # line 272
codex_version: str | None = None                          # line 277
claude_code_version: str | None = None                    # line 276
```

`frameworks` defaults to an empty list. There is no hard-coded default; the wizard always injects `"claude-code"` and `"codex"` (see Section 4).

### `versions` block in `Config.load()` (lines 446–456)

```python
raw_versions = data.get("versions", {})
codex_pin = _validate_version_pin("codex", raw_versions.get("codex"))
```

The YAML key is `"codex"` (not `"codex_version"`). `_validate_version_pin()` (lines 141–178) normalises `"latest"` → `None`, accepts `None` as-is, rejects non-digit-and-dot strings, and rejects non-string types. The result is stored as `codex_version` on the `Config` instance (line 487).

### `Config.save()` (lines 497–558)

The `versions` section is only emitted when at least one version is pinned (lines 546–553):

```python
versions: dict[str, str] = {}
if self.claude_code_version:
    versions["claude-code"] = self.claude_code_version
if self.codex_version:
    versions["codex"] = self.codex_version
if versions:
    data["versions"] = versions
```

If `codex_version` is `None` (i.e., "latest"), the `versions` section is omitted entirely from the YAML file.

### `Config.from_wizard()` (lines 292–324)

Constructs a `Config` from a wizard `answers` dict. The `frameworks` key is consumed directly via `answers.get("frameworks", [])` at line 316. Note: `codex_version` and `claude_code_version` are **not** set here — they are left as `None` (meaning "latest"). Version pins are only written by the CLI's `_check_library_updates()` path (indirectly, by the user pinning versions in the YAML manually).

### `Config.load()` summary (lines 401–495)

Validates version, migrates config, validates distro and runtime versions, reads and validates version pins from `data["versions"]`, validates VM names, returns a fully populated `Config` instance.

### `Config.save()` summary (lines 497–558)

Serialises all fields to YAML. `versions` section is conditionally included (only when at least one framework version is pinned). Uses `fsync` for durability.

---

## 4. Wizard Wiring (`src/clauded/wizard.py`)

### Framework multi-select

In `run()` (line 125), the framework menu (lines 192–197) shows only **`"playwright"`** as a selectable option. `"claude-code"` and `"codex"` are **not shown** — they are hardcoded as always-included defaults.

After the menu (lines 208–211):
```python
answers["frameworks"] = ["claude-code", "codex"] + [
    s for s in selections if s not in tool_options and s not in database_options
]
```

The same pattern appears in `run_edit()` at lines 395–398.

### `OPENAI_API_KEY` forward-env pre-selection

In `run()` at lines 238–244, the forward-env menu pre-selects `"OPENAI_API_KEY"` when `"codex"` is in the resolved `frameworks` list. The identical pre-selection logic appears in `run_edit()` at lines 421–436.

### `wizard.run()` signature (line 125)

```python
def run(project_path: Path, *, distro_override: str | None = None) -> Config
```

Runs the full setup wizard from scratch; returns a `Config` built via `Config.from_wizard()`.

### `wizard.run_edit()` signature (line 303)

```python
def run_edit(config: Config, project_path: Path) -> Config
```

Re-runs wizard with current config values pre-selected; preserves VM resources (cpus/memory/disk); returns a new `Config` via `Config.from_wizard()`.

---

## 5. CLI Wiring (`src/clauded/cli.py`)

### `main()` command (lines 576–937)

Click command with options: `--destroy`, `--reprovision`, `--reboot`, `--stop`, `--force-stop`, `--edit`, `--detect`, `--no-detect`, `--debug`, `--distro`. No framework-specific CLI flags.

### `_get_npm_latest_version(vm, package)` (lines 182–212)

```python
def _get_npm_latest_version(vm: LimaVM, package: str) -> str | None
```

Runs `npm view {package} version` inside the VM via `limactl shell` with a 10-second timeout. Extracts a semver string via `r"\d+\.\d+\.\d+"`. Returns `None` on any failure. The **npm-registry call pattern** for codex: called from `_resolve_framework_versions()` with `package="@openai/codex"` (line 366).

### `_update_codex(vm, version_str)` (lines 252–274)

```python
def _update_codex(vm: LimaVM, version_str: str) -> bool
```

Runs `sudo npm install -g @openai/codex@{version_str}` inside the VM via `limactl shell`. Returns `True` on `returncode == 0`, `False` otherwise. No atomic download pattern (unlike `_update_claude_code` which downloads to a temp file first).

### `_resolve_framework_versions(config, vm)` (lines 340–368)

```python
def _resolve_framework_versions(config: Config, vm: LimaVM) -> dict[str, str | None]
```

For codex (lines 362–366):
```python
if "codex" in config.frameworks:
    if config.codex_version:
        resolved["codex"] = config.codex_version
    else:
        resolved["codex"] = _get_npm_latest_version(vm, "@openai/codex")
```

Pinned version takes precedence; falls back to live npm-registry query inside VM.

### `_check_library_updates(vm, config)` (lines 371–426)

Codex check at lines 393–397:
```python
if "codex" in desired and desired["codex"]:
    installed = _get_vm_tool_version(vm, "codex --version")
    target = desired["codex"]
    if installed and target and installed != target:
        changes.append(("Codex", installed, target, "codex"))
```

Dispatches to `_update_codex()` when the user confirms the update (line 419).

---

## 6. Lima Shell Launch (`src/clauded/lima.py`)

### `LimaVM.__init__` (lines 55–57)

```python
def __init__(self, config: Config):
    self.config = config
    self.name = config.vm_name
```

### `LimaVM.shell()` (lines 202–248)

The shell method **always launches `claude`** as the entry point (line 214):
```python
claude_cmd = "claude"
if self.config.claude_dangerously_skip_permissions:
    claude_cmd += " --dangerously-skip-permissions"
full_cmd = f"USE_BUILTIN_RIPGREP=0 {claude_cmd}"
```

There is no framework dispatch — `codex` and `opencode` are available in the VM's PATH but `shell()` always launches claude. The shell is a `bash -lic` invocation so the user could type `codex` manually.

### `~/.claude` and `~/.codex` mount blocks (lines 393–418 in `_generate_lima_config`)

```python
# ~/.claude mount (lines 393–406)
claude_dir = home / ".claude"
claude_dir.mkdir(exist_ok=True)
mounts.append({"location": str(claude_dir),
               "mountPoint": f"{guest_home}/.claude",
               "writable": True})

# ~/.codex mount (lines 407–418)
codex_dir = home / ".codex"
codex_dir.mkdir(exist_ok=True)
mounts.append({"location": str(codex_dir),
               "mountPoint": f"{guest_home}/.codex",
               "writable": True})
```

Both dirs are created on the host if absent (`mkdir(exist_ok=True)`). Mounts are always added unconditionally (not gated on whether codex is in `config.frameworks`). This means the mount is present even for VMs that don't have codex installed.

### `claude_dangerously_skip_permissions` consumption (lines 214–216)

Read from `self.config.claude_dangerously_skip_permissions` (a bool). If `True`, appends `--dangerously-skip-permissions` to the claude launch command. This flag is exclusive to claude; codex has no equivalent flag wired here.

---

## 7. Codex Epic Spec (`specs/epic-add-codex-framework/spec.md`)

Status: **COMPLETE** (both stories done, per `epic-state.json`)

**Structure**: Single spec.md with 5 requirements sections (R1–R5) and 5 acceptance criteria (AC-1 through AC-5).

**Stories** (from `stories.json`):
- Story 01 `core-codex-integration`: Ansible roles, provisioner, wizard, detect integration, tests. Complexity: medium.
- Story 02 `documentation-changelog`: README.md frameworks table, CHANGELOG.md entry. Complexity: low.

**Key decisions captured in spec**:
- npm-based install chosen over binary download to avoid glibc/musl Alpine compatibility issues.
- Codex is a non-configurable default (not shown in wizard UI, always in frameworks list).
- Backward compat: old `.clauded.yaml` files without `"codex"` in frameworks load fine; codex is re-inserted on next wizard run.
- Node.js auto-dependency injected by provisioner (same as playwright pattern).

**Additional files in epic directory**: `acceptance-criteria.md`, `epic-state.json`, `exploration.json`, `integration-result.json`, `mocks-registry.json`.

---

## 8. Tests for Codex

**`tests/test_provisioner.py`**
- Line 372: `test_includes_codex_when_in_frameworks` — asserts `"codex"` appears in `_get_base_roles()` output when frameworks contains `"codex"`.
- Line 381: `test_codex_auto_includes_node` — asserts that with `node=None` and `frameworks=["codex"]`, both `"node"` and `"codex"` appear in roles, and `roles.index("node") < roles.index("codex")`.
- Line 431: `"codex"` included in the full-config roles assertion list.

**`tests/test_config.py`**
- Lines 1039–1080: Multiple `_validate_version_pin` assertions for `"codex"` key — `"latest"` normalises to `None`, concrete version accepted, invalid types raise `ConfigValidationError`.
- Lines 1104–1113: Full YAML round-trip test loading `codex: "1.2.0"` from `versions` block, asserting `config.codex_version == "1.2.0"`.
- Lines 1158–1160: Security test — injection attempt `"1.2.3; touch /tmp/pwn"` is rejected by `_validate_version_pin`.
- Line 1247–1255: `Config.save()` / `Config.load()` round-trip with `codex_version="1.2.0"` preserves the value.
- Line 1235: Asserts `codex_version is None` when `versions` section is absent.

**`tests/test_wizard.py`**
- Lines 30 and 53: Fixture configs include `frameworks=["claude-code", "codex"]` — test setups verify codex is always present in default framework lists.

**`tests/test_lima.py`**
- Line 206 (`test_mounts_home_directories_when_exist`): Asserts `~/.codex` is mounted at `{guest_home}/.codex` with `writable=True` as the third mount entry.
- Line 238 (`test_creates_claude_dir_when_not_exist`): Asserts `~/.codex` is created on the host and mounted even when it doesn't pre-exist.
- Line 260 (`test_mount_points_must_be_absolute_paths`): Includes `codex_dir` setup in the test.

**`tests/test_version_check.py`**
- Line 496: `test_codex_update_detected` — asserts the version-check prompt fires when installed codex version differs from desired.
- Lines 588–599: `_update_codex` mock called once with the correct target version string.
- Line 716: Asserts `"1.5.0"` (installed codex version string) appears in CLI output during version-check flow.
- Lines 802–836: Config save/load round-trips asserting `codex_version` survives serialisation.

**`tests/test_detect_integration.py`**
- Line 313: `test_defaults_frameworks_always_include_codex` — property-based test asserting `"codex"` is always in `frameworks`.
- Lines 369, 464, 490, 517, 544: Multiple fixture/assertion sites asserting `"codex"` in `frameworks` for detection integration flows.

---

## Summary of Reusable Patterns for opencode

| Concern | Codex pattern | File:line |
|---|---|---|
| Ansible role (install) | `npm install -g <package>[@version]` via `command:` module | `roles/codex-ubuntu/tasks/main.yml:4` |
| Ansible role (idempotency) | `changed_when` inspects npm stdout | `roles/codex-ubuntu/tasks/main.yml:9` |
| Role variant registration | Add name to `_ROLES_WITH_VARIANTS` frozenset | `provisioner.py:52` |
| Role inclusion gate | `if "X" in self.config.frameworks` block in `_get_base_roles()` | `provisioner.py:310` |
| Node.js auto-dependency | Insert `"node"` after `"common"` if not already present | `provisioner.py:312–313` |
| Playbook variable passing | `"X_version": self.config.X_version or "latest"` | `provisioner.py:375` |
| Config field (version pin) | `X_version: str \| None = None` on `Config` dataclass | `config.py:277` |
| Config load (version pin) | `_validate_version_pin("x", raw_versions.get("x"))` | `config.py:456` |
| Config save (version pin) | Conditional emit under `versions:` key | `config.py:550–551` |
| Wizard default inclusion | Hardcode in `answers["frameworks"]` list construction | `wizard.py:209` |
| Wizard env-var pre-selection | Pre-select `X_API_KEY` when `"X"` in frameworks | `wizard.py:238–244` |
| Latest version resolution | `_get_npm_latest_version(vm, "@scope/package")` | `cli.py:366` |
| In-VM update | `sudo npm install -g @scope/package@{version}` via `limactl shell` | `cli.py:252–274` |
| Version mismatch check | `_get_vm_tool_version(vm, "X --version")` pattern | `cli.py:393–397` |
| Host config dir mount | `mkdir(exist_ok=True)` + unconditional Lima mount entry | `lima.py:407–418` |
