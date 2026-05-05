# Architecture Dossier — opencode Harness Epic

**Generated**: 2026-05-04
**Focus**: Module map, public surfaces, seam contracts

---

## Paradigm Declaration

The codebase is a **modular monolith** at the package level, with **package-by-feature** sub-organisation inside `detect/`, and **hexagonal seams** at all external boundaries (Lima/`limactl`, Ansible/`ansible-playbook`, GitHub/GCS APIs).

Evidence:
- Single deployable unit, no services, no inter-process messaging (`src/clauded/__init__.py:1`)
- `detect/` is a self-contained sub-package with its own `__init__.py`, `result.py`, `framework.py`, `database.py`, `version.py`, `linguist.py`, `mcp.py` — each file owns one detection concern (`src/clauded/detect/__init__.py:1-165`)
- All Lima calls are isolated behind `limactl` subprocess calls in `lima.py`; Ansible behind `ansible-playbook` subprocess calls in `provisioner.py` — neither external tool type leaks into any other module
- `distro.py` implements the `DistroProvider` **Protocol** (structural subtyping), the one formal port/adapter contract in the codebase (`src/clauded/distro.py:15-114`)

---

## 1. Top-level Package Layout (`src/clauded/`)

| File | Purpose |
|---|---|
| `__init__.py` | Package root; exports only `__version__ = "0.2.6"` |
| `_build_info.py` | Generated at release; exports `__commit__` (git SHA); falls back to runtime `git rev-parse` in dev mode |
| `cli.py` | Click command entry point; owns the full mode-dispatch state machine |
| `config.py` | `Config` dataclass; YAML load/save/validate; `from_wizard` factory; `atomic_update` crash-recovery context manager |
| `constants.py` | `LANGUAGE_CONFIG` dict; `DEFAULT_LANGUAGES`; `confidence_marker` helper |
| `distro.py` | `DistroProvider` protocol; `AlpineProvider`/`UbuntuProvider` implementations; `get_distro_provider` factory |
| `downloads.py` | Lazy-loaded `downloads.yml` cache; `get_downloads()`, `get_cloud_image(distro)`, `get_tool_metadata(tool, version)` |
| `lima.py` | `LimaVM` class wrapping all `limactl` subprocess calls; `destroy_vm_by_name` free function |
| `provisioner.py` | `Provisioner` class; generates and runs Ansible playbooks; `_ROLES_WITH_VARIANTS` registry |
| `spinner.py` | Context manager for console spinner (used in `detect/wizard_integration.py`) |
| `wizard.py` | `run()` / `run_edit()` interactive setup wizards (plain, no detection) |
| `detect/__init__.py` | `detect(project_path)` orchestrator; assembles `DetectionResult` |
| `detect/cli_integration.py` | `create_wizard_defaults()`, `display_detection_summary()`, `display_detection_json()` |
| `detect/wizard_integration.py` | `run_with_detection()`, `run_edit_with_detection()`, `apply_detection_to_config()`, `merge_detection_with_config()` |
| `detect/result.py` | `DetectionResult`, `ScanStats`, `DetectedItem`, `VersionSpec` dataclasses |
| `detect/database.py` | Detects databases from docker-compose and env files |
| `detect/framework.py` | Detects frameworks and tools from manifest dependencies |
| `detect/linguist.py` | Detects languages using GitHub Linguist YAML data |
| `detect/mcp.py` | Detects MCP server runtime requirements |
| `detect/utils.py` | Shared file-scanning utilities for detection |
| `detect/version.py` | Detects runtime versions from version files and manifests |
| `linguist/__init__.py` | Loads and caches Linguist YAML data files |

---

## 2. Config Module (`src/clauded/config.py`)

### `Config` Dataclass — Fields

```
version: str = "1"

# VM settings
vm_name: str = ""
vm_distro: str = "alpine"
cpus: int = 1
memory: str = "8GiB"
disk: str = "20GiB"
vm_image: str | None = None

# Mount settings
mount_host: str = ""
mount_guest: str = ""

# Crash recovery
previous_vm_name: str | None = None

# Runtimes (all optional)
python: str | None = None
node: str | None = None
java: str | None = None
kotlin: str | None = None
rust: str | None = None
go: str | None = None
dart: str | None = None
c: str | None = None

# Collections
tools: list[str] = []                    # e.g. ["docker", "gh"]
databases: list[str] = []               # e.g. ["postgresql", "redis"]
frameworks: list[str] = []              # e.g. ["claude-code", "codex"]
playwright_browsers: list[str] = []     # e.g. ["chromium", "firefox", "webkit"]

# Framework version pins
claude_code_version: str | None = None  # None means "latest"
codex_version: str | None = None        # None means "latest"

# Claude Code settings
claude_dangerously_skip_permissions: bool = True

# SSH
ssh_host_key_checking: bool = True

# Behaviour
keep_vm_running: bool = False
forward_env: list[str] = []
```

Source: `src/clauded/config.py:234-289`

### `Config.load(path: Path) -> "Config"` — `config.py:401`

Reads `.clauded.yaml`, validates schema version, runs `_migrate_config`, auto-corrects `mount_guest != mount_host`, validates distro, validates runtime versions, validates version pins, validates VM names. Raises `ConfigVersionError` or `ConfigValidationError` on failure. All fields except `version` are read from nested YAML keys (`vm.*`, `environment.*`, `claude.*`, `ssh.*`, `versions.*`).

### `Config.save(path: Path) -> None` — `config.py:497`

Serialises to YAML with `fsync`. The `versions` section is omitted when both `claude_code_version` and `codex_version` are `None`. All other top-level sections are always emitted. Round-trip is lossless for all current fields.

### `Config.from_wizard(answers: dict[str, Any], project_path: Path) -> "Config"` — `config.py:292`

Class method. Consumes the flat `answers` dict produced by the wizard. Derives `vm_name` from `_sanitize_vm_name(project_path.name) + sha256(project_path)[:6]`. Normalises the string `"None"` sentinel (from wizard multi-select) to Python `None` for runtime fields. Does not call `save` — caller is responsible.

### `ConfigValidationError` — `config.py:33`

Plain `Exception` subclass. Raised by `_validate_distro`, `_validate_runtime_version`, `_validate_version_pin`. All three are called exclusively from `Config.load`.

### Validation Rules

| Validator | Field(s) | Raise condition | Source |
|---|---|---|---|
| `_validate_distro` | `vm_distro` | not in `SUPPORTED_DISTROS` | `config.py:36` |
| `_validate_runtime_version` | `python`, `node`, `java`, `kotlin`, `rust`, `go`, `dart`, `c` | not in `LANGUAGE_CONFIG[lang]["versions"]` (strict=True) | `config.py:61` |
| `_validate_version_pin` | `claude_code_version`, `codex_version` | not matching `^[0-9]+(\.[0-9]+)*$` (not None, not "latest") | `config.py:141` |
| `_validate_vm_name` | `vm_name`, `previous_vm_name` | empty string, or contains `..`, `/`, `\\` | `config.py:113` |
| `_validate_version` | `version` | integer value > `CURRENT_VERSION` ("1") | `config.py:181` |

### YAML Schema (emitted by `Config.save`)

```yaml
version: "1"
vm:
  name: clauded-myproject-abc123
  distro: ubuntu
  cpus: 2
  memory: 8GiB
  disk: 20GiB
  # optional: image, previous_name, keep_running, forward_env
mount:
  host: /Users/alice/myproject
  guest: /Users/alice/myproject
environment:
  python: "3.12"
  node: null
  java: null
  kotlin: null
  rust: null
  go: null
  dart: null
  c: null
  tools: [docker]
  databases: []
  frameworks: [claude-code, codex]
  playwright_browsers: []
claude:
  dangerously_skip_permissions: true
ssh:
  host_key_checking: true
# versions section only present when at least one is pinned:
versions:
  claude-code: "2.1.62"
  codex: "1.0.0"
```

---

## 3. Provisioner Module (`src/clauded/provisioner.py`)

### Public Surface

- `class Provisioner` — `provisioner.py:129`
  - `__init__(self, config: Config, vm: LimaVM, *, debug: bool = False)`
  - `run(self) -> None` — resolves roles, validates existence, generates playbook, runs ansible-playbook
- `__commit__` — re-exported from `_build_info` or computed from git; consumed by `cli.py`

### `_ROLES_WITH_VARIANTS` — `provisioner.py:23`

A `frozenset[str]` of base role names that have distro-suffixed variants on disk (e.g. `common-alpine`, `common-ubuntu`). Roles absent from this set are passed to Ansible as-is without suffix.

Current members (after Story 06):
```
common, python, node,
java, kotlin, rust, go, dart, c,
docker, uv, poetry, maven, gradle, aws_cli, gh,
postgresql, redis, mysql, sqlite, mongodb,
claude_code, codex, playwright
```

`opencode` is **not yet present** in this set. It must be added as part of this epic.

### `_get_base_roles()` Algorithm — `provisioner.py:257`

Returns a list of base role names (no distro suffix). The algorithm is additive in declaration order:

1. Always starts with `["common"]`
2. If `config.python` → append `python`, `uv`, `poetry`
3. If `config.node` → append `node`
4. If `config.java or config.kotlin` → append `java`; if `config.kotlin` → append `kotlin`; if either → append `maven`, `gradle`
5. If `config.rust/go/dart/c` → append each
6. If `"docker"` in `config.tools` → append `docker`; same for `aws-cli` → `aws_cli`, `gh`
7. Database roles: `postgresql`, `redis`, `mysql`, `sqlite`, `mongodb` by membership in `config.databases`
8. Framework roles:
   - `"codex"` in `config.frameworks` → ensure `node` in roles (insert after `common` if absent), append `codex`
   - `"playwright"` → same node-guard pattern, append `playwright`
   - `"claude-code"` → append `claude_code`

Key pattern: codex and playwright both trigger an implicit `node` role insertion if not already present (`provisioner.py:313, 318`).

### Distro Variant Resolution — `_apply_distro_suffix()` — `provisioner.py:138`

For each base role name: if it is a member of `_ROLES_WITH_VARIANTS`, the resolved name is `f"{role}-{self.config.vm_distro}"`. Otherwise it passes through unchanged. The distro string comes directly from `config.vm_distro`.

---

## 4. Wizard Module (`src/clauded/wizard.py`)

### `run(project_path: Path, *, distro_override: str | None = None) -> Config` — `wizard.py:125`

Fresh wizard for a new config. Steps in order: distro selection (bypassed if `distro_override` set) → language multi-select (DEFAULT_LANGUAGES = `{python, node}` pre-checked) → per-language version single-select → tools multi-select → databases multi-select → frameworks multi-select (only `playwright` shown; `claude-code` and `codex` always appended programmatically) → Playwright browsers (conditional) → env var forwarding → `claude_dangerously_skip_permissions` confirm → `keep_vm_running` confirm → resources (optional). Returns `Config.from_wizard(answers, project_path)`.

### `run_edit(config: Config, project_path: Path) -> Config` — `wizard.py:303`

Re-runs wizard with pre-populated defaults from existing `config`. Distro and VM resources (cpus/memory/disk) are preserved without prompting. Returns `Config.from_wizard(answers, project_path)`.

### Frameworks Multi-Select Step

The user-visible options in `run()` and `run_edit()` are:

```python
[("playwright", "playwright", False)]   # wizard.py:196, 380
```

`claude-code` and `codex` are **not shown to the user** — they are silently prepended in both `run()` and `run_edit()` after the selection:

```python
answers["frameworks"] = ["claude-code", "codex"] + [
    s for s in selections if s not in tool_options and s not in database_options
]
```
Source: `wizard.py:209, 396`

This is the **primary seam** for the harness work. The same pattern is duplicated in `detect/wizard_integration.py:186,396,752` (three copies).

### Wizard → Config Flow

`run()` → populates `answers: dict[str, str | list[str] | bool]` → passes to `Config.from_wizard(answers, project_path)` → returns `Config`. The `from_wizard` classmethod is the sole converter between wizard output and `Config` fields. The `answers` dict is informal (no TypedDict); shape is documented only by convention.

---

## 5. CLI Module (`src/clauded/cli.py`)

### `main()` Click Options — `cli.py:576`

```python
@click.option("--destroy",      is_flag=True)
@click.option("--reprovision",  is_flag=True)
@click.option("--reboot",       is_flag=True)
@click.option("--stop",         is_flag=True)
@click.option("--force-stop",   is_flag=True)
@click.option("--edit",         is_flag=True)
@click.option("--detect",       "detect_only", is_flag=True)
@click.option("--no-detect",    is_flag=True)
@click.option("--debug",        is_flag=True)
@click.option("--distro",       type=str, default=None)
```

### Mode Dispatch — `cli.py:626`

```
if detect_only and not reprovision   → detect-only, print JSON, return
if destroy                           → destroy VM + optionally remove config, return
if stop or force_stop                → stop VM, return
if edit                              → run_edit_with_detection, reprovision, shell, finally stop
if not config_path.exists()          → wizard (run_with_detection or wizard.run), save config
else                                 → Config.load
  if not vm.exists()                 → vm.create, provisioner.run
  else                               → start if needed, handle distro change, handle version
                                       change, handle library updates, handle --reprovision
→ vm.shell(reconnect=needs_reconnect)
→ finally: _stop_vm_if_last_session
```

### Version-Check Helpers

| Function | Signature | Behaviour |
|---|---|---|
| `_get_latest_claude_code_version` | `() -> str | None` | Fetches `{gcs_bucket}/latest` with `curl` on the host; extracts semver. `cli.py:317` |
| `_get_npm_latest_version` | `(vm: LimaVM, package: str) -> str | None` | Runs `npm view <package> version` inside the VM via `limactl shell`; extracts semver. `cli.py:182` |
| `_update_claude_code` | `(vm: LimaVM, config: Config, version_str: str) -> bool` | Downloads Claude Code binary from GCS into VM via atomic `curl → tmp → mv`. Uses `config.vm_distro` to select `linux-arm64-musl` (alpine) vs `linux-arm64` (ubuntu). `cli.py:215` |
| `_update_codex` | `(vm: LimaVM, version_str: str) -> bool` | Runs `sudo npm install -g @openai/codex@{version}` inside VM. `cli.py:252` |
| `_resolve_framework_versions` | `(config: Config, vm: LimaVM) -> dict[str, str | None]` | For each framework in `config.frameworks`: uses pinned version from config or resolves "latest". Returns `{"claude-code": "2.x.y", "codex": "1.x.y"}`. `cli.py:340` |
| `_check_library_updates` | `(vm: LimaVM, config: Config) -> None` | Calls `_resolve_framework_versions`, compares each against installed version, prompts user, calls `_update_*` for each change. `cli.py:371` |

---

## 6. Lima Module (`src/clauded/lima.py`)

### `LimaVM` — Public Interface

```python
class LimaVM:
    def __init__(self, config: Config)         # lima.py:55
    def exists(self) -> bool                   # lima.py:59
    def is_running(self) -> bool               # lima.py:68
    def create(self, *, debug: bool) -> None   # lima.py:77
    def start(self, *, debug: bool) -> None    # lima.py:122
    def stop(self) -> None                     # lima.py:149
    def count_active_sessions(self) -> int     # lima.py:165
    def destroy(self) -> None                  # lima.py:198
    def shell(self, *, reconnect: bool) -> None  # lima.py:202  ← REFACTOR TARGET
    def get_vm_metadata(self) -> dict[str, str] | None  # lima.py:271
    def get_ssh_config_path(self) -> Path      # lima.py:297
    def get_vm_distro(self) -> str | None      # lima.py:301
```

Free function: `destroy_vm_by_name(vm_name: str) -> None` — `lima.py:17`

### `shell()` — Full Body (Refactor Target) — `lima.py:202`

```python
def shell(self, *, reconnect: bool = False) -> None:
    self._print_welcome()

    claude_cmd = "claude"
    if self.config.claude_dangerously_skip_permissions:
        claude_cmd += " --dangerously-skip-permissions"

    # USE_BUILTIN_RIPGREP=0 set for Alpine/musl compatibility
    full_cmd = f"USE_BUILTIN_RIPGREP=0 {claude_cmd}"

    cmd = [
        "limactl", "shell",
        "--workdir", self.config.mount_guest,
    ]
    env = None
    if self.config.forward_env:
        present_vars = [v for v in self.config.forward_env if v in os.environ]
        if present_vars:
            cmd.append("--preserve-env")
            env = os.environ.copy()
            env["LIMA_SHELLENV_ALLOW"] = ",".join(present_vars)
    if reconnect:
        cmd.append("--reconnect")
    cmd.extend([self.name, "bash", "-lic", full_cmd])
    subprocess.run(cmd, env=env)
```

Three hardcoded literals of concern: the string `"claude"` (`lima.py:214`), the flag `"--dangerously-skip-permissions"` (`lima.py:216`), and the env prefix `"USE_BUILTIN_RIPGREP=0"` (`lima.py:220`).

### Mount Block Construction — `_generate_lima_config()` — `lima.py:380`

Three mounts built in order:

1. **Project mount**: `config.mount_host` → `config.mount_guest`, writable. `lima.py:383`
2. **Claude settings**: `~/.claude` → `{guest_home}/.claude`, writable. Created on host if absent. `lima.py:398`
3. **Codex config**: `~/.codex` → `{guest_home}/.codex`, writable. Created on host if absent. `lima.py:411`

`guest_home` is computed as `f"/home/{getpass.getuser()}.linux"` (`lima.py:394`). The `.codex` directory is pre-created on the host (`codex_dir.mkdir(exist_ok=True)`) before being passed to Lima.

### Lima YAML Generation Entry Point

`LimaVM.create()` calls `self._generate_lima_config()` internally, writes the result to a tempfile, and passes it to `limactl start`. `_generate_lima_config` is not called from any other module. `lima.py:79`.

---

## 7. Cross-Module Boundaries (Seams)

### Import Graph

```
cli.py
  → config.py          (Config, ConfigValidationError implied)
  → wizard.py          (__init__ import: `from . import wizard`)
  → detect/__init__.py (detect)
  → detect/cli_integration.py (display_detection_json)
  → detect/wizard_integration.py (apply_detection_to_config, run_edit_with_detection,
                                   run_with_detection)
  → downloads.py       (get_downloads)
  → lima.py            (LimaVM, destroy_vm_by_name)
  → provisioner.py     (Provisioner, __commit__)

provisioner.py
  → config.py          (Config)
  → downloads.py       (get_downloads)
  → lima.py            (LimaVM) — only for get_ssh_config_path()

lima.py
  → config.py          (Config)
  → distro.py          (get_distro_provider) — lazy import inside _get_image_config

wizard.py
  → config.py          (Config)
  → constants.py       (DEFAULT_LANGUAGES, LANGUAGE_CONFIG)

detect/wizard_integration.py
  → config.py          (Config)
  → constants.py       (LANGUAGE_CONFIG)
  → wizard.py          (_menu_multi_select, _menu_select, _select_distro)
  → detect/__init__.py (detect)
  → detect/result.py   (DetectionResult)

detect/cli_integration.py
  → constants.py       (confidence_marker)
  → detect/result.py   (DetectionResult)

config.py
  → constants.py       (LANGUAGE_CONFIG)
  → distro.py          (SUPPORTED_DISTROS)

distro.py
  → downloads.py       (get_cloud_image) — lazy import inside provider methods
```

### Data Shapes Across Boundaries

| Boundary | Data | Shape |
|---|---|---|
| `cli → wizard` | wizard entry call | `project_path: Path`, `distro_override: str | None`; returns `Config` |
| `cli → lima` | VM operations | `LimaVM(config: Config)` — entire `Config` object |
| `cli → provisioner` | provisioning | `Provisioner(config: Config, vm: LimaVM, debug: bool)` |
| `wizard → config` | wizard output | `answers: dict[str, str | list[str] | bool]` (informal); converted by `Config.from_wizard` |
| `provisioner → config` | playbook vars | direct field access on `Config` object |
| `provisioner → lima` | SSH config path | `vm.get_ssh_config_path() -> Path` |
| `detect → wizard_integration` | detection output | `DetectionResult` dataclass |
| `wizard_integration → wizard` | private helpers | imports `_menu_multi_select`, `_menu_select`, `_select_distro` from `wizard.py` — underscore-prefixed |

---

## 8. Existing Patterns the opencode Work Must Follow

### How Codex Launch Works Today (Confirmed)

Codex is installed in the VM but is NOT the entrypoint. `lima.py:214` hardcodes:

```python
claude_cmd = "claude"
if self.config.claude_dangerously_skip_permissions:
    claude_cmd += " --dangerously-skip-permissions"
```

The user must exit the Claude Code TUI and invoke `codex` manually from a shell. The spec describes this exactly: "the user has to invoke `codex` after entering the shell." Code confirms it — there is no dispatch logic, no `config.frameworks` check, no harness selection.

### `claude_dangerously_skip_permissions` — Where Consumed

The field `config.claude_dangerously_skip_permissions` is read in two places:

1. **`lima.py:215`** — controls whether `--dangerously-skip-permissions` is appended to the `claude` command in `shell()`. This is the launch-time consumer.
2. **`provisioner.py:358`** — passed as Ansible variable `claude_dangerously_skip_permissions` into the playbook, where it controls the Ansible role for Claude Code's configuration at provisioning time.

The spec says this field will be reused for opencode/codex dispatch logic. At launch time (`lima.py:shell`), the field currently gates the `--dangerously-skip-permissions` flag only for Claude Code. The dispatcher refactor must decide: does `claude_dangerously_skip_permissions=True` mean "skip permissions on whichever harness is active", or does it remain a Claude-specific field and a new `opencode_dangerously_skip_permissions` field is introduced? The spec (`epic-add-opencode-harness/spec.md`) states to reuse the field name for the dispatch logic.

### `USE_BUILTIN_RIPGREP=0` — Origin and Purpose — `lima.py:220`

Set unconditionally in `shell()` before every session. Comment in code: "The native binary's bundled ripgrep doesn't work on musl." (`lima.py:218-219`). The Claude Code binary ships with a bundled ripgrep that uses glibc. On Alpine Linux (musl libc), the bundled binary fails. Setting `USE_BUILTIN_RIPGREP=0` tells Claude Code to find ripgrep on PATH instead of using its bundled copy. On Ubuntu this variable is harmless — ripgrep is installed via `common-ubuntu` Ansible role and will be found on PATH either way.

This flag is Claude Code-specific. It has no meaning for `codex` or `opencode`. The dispatcher should set it only when the active harness is `claude-code`.

---

## Boundary Risks

### Fragile: `_ROLES_WITH_VARIANTS` vs on-disk roles are out-of-sync by convention

`provisioner.py:23-55` maintains a `frozenset` manually. If a new role is added to `src/clauded/roles/` without updating `_ROLES_WITH_VARIANTS`, the provisioner silently uses the non-suffixed role name and fails at Ansible runtime. There is a `_validate_roles_exist` check (`provisioner.py:158`) that catches this, but only at run time. Adding `opencode` to `_ROLES_WITH_VARIANTS` is mandatory the moment the `opencode-ubuntu` Ansible role is created.

### Fragile: Wizard framework list is not driven by config schema

`wizard.py:196` and all three wizard-integration copies hardcode the user-visible framework list as `[("playwright", "playwright", False)]` with `claude-code` and `codex` appended unconditionally. Adding `opencode` requires touching four files: `wizard.py`, `detect/wizard_integration.py` (three functions: `run_with_detection`, `run_edit_with_detection`, and the `merge_detection_with_config` framework-union logic). There is no single registry; the list is literally repeated.

### Fragile: `_resolve_framework_versions` and `_check_library_updates` hardcode framework names

`cli.py:356-367` and `cli.py:387-397` both pattern-match on the string literals `"claude-code"` and `"codex"`. Adding `opencode` requires extending these two functions to handle its version-resolution and update path.

### Fragile: `answers` dict is untyped

The dict returned by `wizard.run()` and consumed by `Config.from_wizard()` is `dict[str, str | list[str] | bool]` with no TypedDict definition. The key names are magic strings (`"frameworks"`, `"claude_dangerously_skip_permissions"`, etc.) shared between the wizard files and `Config.from_wizard` without compile-time checking. Any new harness-related wizard answer key (e.g. `"harness"`) must be added consistently in all wizard entry points and the `from_wizard` method.

### Stable: `Config` ↔ `LimaVM` and `Config` ↔ `Provisioner`

Both consumers accept the entire `Config` object and read fields directly. This is wide but stable — changes to `Config` fields are immediately visible to both. No adapter layer or DTO in between.

### Stable: `detect/` sub-package boundary

`detect/__init__.py` exports `detect(project_path) -> DetectionResult` as the sole entry point. The rest of `detect/` is internal. `cli.py` and `detect/wizard_integration.py` consume only `DetectionResult`. Adding `opencode` to the detection corpus (e.g. detecting `opencode.json` or `package.json` devDependency) stays inside `detect/framework.py` without touching other modules.
