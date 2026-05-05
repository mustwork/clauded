# Testing & Conventions Dossier — clauded

_For the opencode harness epic. Read-only exploration, no design recommendations._

---

## 1. Test Framework Setup

### pytest

- **Config location**: `pyproject.toml` lines 79–81
- `testpaths = ["tests"]`
- `addopts = "-ra -q"` (verbose failure summary, quiet pass lines)
- No `pytest.ini` or `setup.cfg` overrides found.

### Coverage

- Threshold configured in `pyproject.toml` lines 84–85:
  ```
  [tool.coverage.report]
  fail_under = 80
  ```
  Confirmed at 80 % — matches the spec claim.
- Coverage invoked via `make coverage`:
  ```
  uv run pytest tests/ --cov=clauded --cov-report=term-missing --cov-report=html
  ```
  (`Makefile` line 80). The `--cov=clauded` flag uses the installed package name,
  not the `src/` path.

### Ruff

- `pyproject.toml` lines 51–64
- `target-version = "py312"`, `line-length = 88`
- Rules: `E`, `W`, `F`, `I`, `B`, `UP`
- Sources: `src`, `tests`

### Mypy

- `pyproject.toml` lines 67–76
- `disallow_untyped_defs = true`, `warn_return_any = true`, `warn_unused_ignores = true`
- `mypy_path = "src"` — runs against `src/` only (not `tests/`)
- `ignore_missing_imports` for `questionary.*` and `ansible.*`

### No conftest.py

There is **no `tests/conftest.py`**. Every fixture is defined locally inside the
test file that uses it. This is the project's deliberate convention; architects
must follow it.

---

## 2. Test File Inventory

### Grouped by target module

**`src/clauded/cli.py`**

| File | Coverage summary |
|---|---|
| `test_cli.py` | CLI help output, `--version`, `--destroy`, `--stop`, `--reprovision` flags, SIGINT handler, session counting, shell entry. Uses `CliRunner`. |
| `test_cli_distro.py` | `--distro` flag acceptance, distro forwarded to config. Uses `CliRunner`. |
| `test_version_check.py` | `_handle_version_change()` and `_check_library_updates()` via CLI integration; Config version round-trips. Uses `CliRunner`. |
| `test_distro_change.py` | VM recreation when distro changes in config. Uses `CliRunner`. |

**`src/clauded/config.py`**

| File | Coverage summary |
|---|---|
| `test_config.py` | `Config.from_wizard()`, `Config.load()`, `Config.save()`, validation, migration, version pins. |
| `test_config_distro.py` | `vm_distro` field: default, load, save, validation. |
| `test_atomic_config_update.py` | `Config.atomic_update()` context manager: success, rollback, `destroy_vm_by_name` call. |
| `test_sqlite_edit_workflow.py` | `--edit` flag preserves SQLite entries in config round-trip. |

**`src/clauded/lima.py`**

| File | Coverage summary |
|---|---|
| `test_lima.py` | `LimaVM.exists()`, `is_running()`, `start()`, `stop()`, `destroy()`, `shell()`, `get_vm_distro()`, `get_vm_metadata()`. All subprocess-mocked. |

**`src/clauded/provisioner.py`**

| File | Coverage summary |
|---|---|
| `test_provisioner.py` | `_get_base_roles()` parametrised by language/tool/framework; `_filter_env()`; Ansible playbook YAML generation validated structurally. |
| `test_mongodb_integration.py` | MongoDB role inclusion end-to-end from `Config` → `Provisioner._get_base_roles()`. |

**`src/clauded/wizard.py`**

| File | Coverage summary |
|---|---|
| `test_wizard.py` | `wizard.run_edit()`: preselection, outdated version fallback, valid default indices. |
| `test_wizard_distro.py` | `wizard.run()`: distro shown first, defaults to Alpine. |

**`src/clauded/downloads.py`**

| File | Coverage summary |
|---|---|
| `test_downloads.py` | `get_downloads()`, `get_alpine_image()`, `get_tool_metadata()`, caching. No HTTP mocking — reads static bundled YAML. |
| `test_downloads_distro.py` | `get_cloud_image()` multi-distro support. |

**`src/clauded/constants.py`**

| File | Coverage summary |
|---|---|
| `test_constants.py` | `LANGUAGE_CONFIG`, `DEFAULT_LANGUAGES`, `get_supported_versions()`, `validate_version()`, `confidence_marker()`. |

**`src/clauded/distro.py`**

| File | Coverage summary |
|---|---|
| `test_distro.py` | `SUPPORTED_DISTROS`, `AlpineProvider`, `UbuntuProvider`, `get_distro_provider()`. |

**`src/clauded/spinner.py`**

| File | Coverage summary |
|---|---|
| `test_spinner.py` | Cursor hide/show, exception path, thread safety. |

**`src/clauded/detect/`**

| File | Coverage summary |
|---|---|
| `test_framework.py` | Property-based + parametrised: `parse_python/node/java/kotlin/rust/go_dependencies`, `detect_docker`, `detect_playwright`, `detect_frameworks_and_tools`. Uses `tmp_path` and `tempfile`. Hypothesis strategies included. |
| `test_version_detection.py` | `detect_versions()`, per-runtime `parse_*_version()` functions. Property-based + parametrised. |
| `test_database.py` | `detect_databases()`, ORM adapters, Docker Compose parsing, env file parsing, deduplication. Property-based. |
| `test_detect_integration.py` | `display_detection_summary()`, `create_wizard_defaults()`, `normalize_version_for_choice()`. Property-based. |
| `test_detect_linguist.py` | Linguist language detection: confidence, byte counts, vendor exclusion, shebang, performance. |
| `test_detection_enhancements_integration.py` | MongoDB + Micronaut full detection pipeline integration tests. |
| `test_detection_properties.py` | Property tests for `setup.py` (FR-1), `build.gradle.kts` (FR-2), `build.gradle` (FR-3) parsers. |
| `test_detection_security.py` | Symlink traversal, version string injection, 8 KB file read limit. |
| `test_mcp.py` | MCP config file detection from `.mcp.json`, `mcp.json`, user-level config. `patch("clauded.detect.mcp.USER_CLAUDE_CONFIG", ...)` used to isolate host env. |

**Other**

| File | Coverage summary |
|---|---|
| `test_linguist.py` | Vendored Linguist YAML files: structure, invariants, required languages. |
| `test_ktor_build_gradle.py` | Ktor detection from `build.gradle` (single regression test). |
| `test_sqlite_e2e.py` | End-to-end SQLite: detection → wizard defaults → config → provisioner roles. |

---

## 3. Mock Patterns

### `subprocess.run`

The dominant pattern is `unittest.mock.patch("clauded.<module>.subprocess.run")` with
`mock_run.side_effect = [result1, result2, ...]` to simulate multiple sequential calls.

Example — `test_version_check.py` line 87:
```python
with patch("clauded.lima.subprocess.run") as mock_run:
    list_result = MagicMock()
    list_result.stdout = "Running"
    cat_result = MagicMock()
    cat_result.returncode = 0
    cat_result.stdout = '{"version": "0.1.0", ...}'
    mock_run.side_effect = [list_result, cat_result]
```

Lima tests (`test_lima.py` line 55) use `patch("subprocess.run")` (no module prefix)
because the `lima` module does a bare `import subprocess`.

### Network calls (HTTP)

`_get_latest_claude_code_version()` calls `subprocess.run(["curl", ...])` on the
**host** — it does **not** use `urllib`, `requests`, or `httpx`. There are therefore
**no HTTP library mocks** for this function; it is patched at the function boundary:

```python
patch("clauded.cli._get_latest_claude_code_version", return_value="2.1.62")
```
(see `test_version_check.py` lines 478, 582, 620, 734, 746)

`_get_npm_latest_version()` runs `limactl shell … npm view` inside the VM; also
patched at the function level:
```python
patch("clauded.cli._get_npm_latest_version", return_value="1.0.5")
```
(see `test_version_check.py` lines 484, 546)

No project-wide `httpx`/`requests`/`urllib` mocking infrastructure exists because
those libraries are not project dependencies.

### YAML I/O

Two patterns in use:

1. **`runner.isolated_filesystem()`** — `CliRunner`'s helper creates a temp CWD so
   `.clauded.yaml` written with `Path(".clauded.yaml").write_text(yaml_str)` is
   isolated. Used extensively in `test_cli.py` and `test_version_check.py`.

2. **`tempfile.NamedTemporaryFile`** (used directly in `TestConfigVersionsPersistence`,
   `test_version_check.py` lines 795–883) for `Config.load()` / `Config.save()` round-trips.

3. **`tmp_path` (pytest built-in fixture)** — used in `test_config.py`, `test_wizard.py`,
   `test_atomic_config_update.py`, `test_sqlite_e2e.py`.

### Default `Config` fixture

Each test file defines its own `Config` fixture. Common shapes:

- `test_version_check.py` lines 14–66: `runner()` + `config_yaml` string fixtures; Config
  is loaded from YAML text inside `isolated_filesystem`.
- `test_provisioner.py` lines 15–54: `full_config` (all options) and `minimal_config`
  (bare minimum) fixtures, constructed with `Config(vm_name=..., ...)`.
- `test_lima.py` line 14: `sample_config` fixture with `Config(vm_name="clauded-test1234", ...)`.
- `test_wizard.py` lines 13–55: `sample_config` and `outdated_config` fixtures.

No shared conftest-level `Config` factory; every file brings its own.

---

## 4. Click CLI Testing

### Representative test shape

From `test_version_check.py` lines 206–239:

```python
def test_version_mismatch_user_declines(
    self, runner: CliRunner, config_yaml: str
) -> None:
    with runner.isolated_filesystem():
        Path(".clauded.yaml").write_text(config_yaml)

        with (
            patch("clauded.cli.LimaVM") as MockVM,
            patch("clauded.cli.Provisioner") as MockProv,
            patch("clauded.cli.__commit__", "def5678"),
            patch("clauded.cli.__version__", "0.2.0"),
            patch("clauded.cli._check_library_updates"),
        ):
            mock_vm = MagicMock()
            mock_vm.exists.return_value = True
            mock_vm.is_running.return_value = True
            ...
            MockVM.return_value = mock_vm

            result = runner.invoke(main, [], input="n\ny\n")

            assert "clauded has been updated" in result.output
            assert "Provisioned with: v0.1.0 (abc1234)" in result.output
            MockProv.return_value.run.assert_not_called()
            mock_vm.shell.assert_called_once()
```

**Key shape**:
1. `runner.isolated_filesystem()` creates temp CWD.
2. `.clauded.yaml` written inline.
3. `LimaVM` and `Provisioner` classes patched at the `clauded.cli` import site (not module-level).
4. `input=` string simulates interactive `y`/`n` prompts in order.
5. Assertions on `result.output` (stdout), `result.exit_code` (when checked), and
   mock call assertions.
6. `result.exit_code` is checked explicitly in some tests (`test_cli.py` line 48),
   omitted in others where only output content matters.

### Fixtures creating `.clauded.yaml`

There is no shared fixture that creates a file on disk. Instead, every CLI test defines
a YAML string fixture (e.g. `config_yaml`, `sample_config_yaml`, `alpine_config_yaml`)
and writes it to disk inside `isolated_filesystem()`. See `test_version_check.py` lines
22–66 for two representative string fixtures covering the unpinned and pinned cases.

---

## 5. Wizard Testing

### `simple_term_menu` mock strategy

`simple_term_menu` is **never imported directly in tests**. Instead, the project wraps
it in two internal helpers (`_menu_select`, `_menu_multi_select`) inside `wizard.py`.
Tests patch those helpers:

```python
patch("clauded.wizard._menu_select") as mock_select
patch("clauded.wizard._menu_multi_select") as mock_multi_select
```
(see `test_wizard.py` lines 66–69, `test_wizard_distro.py` lines 13–15)

### Asserting "wizard offered option X with default index Y"

Tests capture calls by injecting a side-effect that records arguments:

```python
select_calls = []

def track_select(_title, items, default_index):
    select_calls.append((items, default_index))
    return items[default_index][1]

mock_select.side_effect = track_select
```
Then assert against the captured list:
```python
python_call = next(
    (call for call in select_calls
     if [item[0] for item in call[0]] == ["3.12", "3.11", "3.10"]),
    None,
)
assert python_call is not None
assert python_call[1] == 1   # default_index
```
(see `test_wizard.py` lines 113–135 for the outdated-version fallback test,
lines 195–248 for the valid-defaults test)

`_menu_multi_select` is mocked with a side effect that filters `items` by the
`pre` (pre-checked) boolean: `[value for _label, value, pre in items if pre]`.
This pattern appears in `test_wizard.py` lines 72–77 and is reused across all wizard
test methods.

---

## 6. Provisioner / Ansible Testing

### Strategy: pure Python, no `ansible-playbook`

Ansible tasks and roles are **not** tested by running `ansible-playbook`. The
provisioner tests verify only:

1. **Role list composition** — `_get_base_roles()` is called on a real `Provisioner`
   instance constructed with a real `Config` and a real (but uninvoked) `LimaVM`.
   The resulting list is checked with `assert "python" in roles` etc.
   (see `test_provisioner.py` lines 57–280)

2. **Playbook YAML structure** — some tests call internal methods that generate the
   playbook dict and assert structural properties (role order, variable injection,
   env filtering).

3. **No `--check` mode**: No test runs `ansible-playbook --check`. Ansible YAML files
   in `src/clauded/roles/` are entirely uncovered by automated tests.

### `_get_base_roles()` test pattern

`test_provisioner.py` defines two fixtures at lines 15–54:
- `full_config` — all languages, all tools, all supported databases, frameworks `["playwright", "claude-code", "codex"]`
- `minimal_config` — no languages, no tools, no frameworks

Each test is a paired `test_includes_X_when_selected / test_excludes_X_when_none`
method that constructs `Provisioner(config, LimaVM(config))` and calls `._get_base_roles()`.
No parametrisation — individual assertion methods for each role. Tests do **not** use
`pytest.mark.parametrize` for this class.

**Gap noted in memory**: `full_config` fixture at `test_provisioner.py` line 35 lists
`frameworks=["playwright", "claude-code", "codex"]` but the vq-01-investigation memory
(`vq-01-investigation.md` line 10) records that as of the investigation no codex test
existed. Confirm current state before relying on this.

---

## 7. Lint / Type / Hygiene Commands

### Makefile targets

| Target | Command | File:line |
|---|---|---|
| `make lint` | `uv run ruff check src/ tests/` | `Makefile:83` |
| `make format` | `uv run ruff format src/ tests/ && uv run ruff check --fix src/ tests/` | `Makefile:88` |
| `make typecheck` | `uv run mypy src/` | `Makefile:91` |
| `make test` | `uv run pytest tests/ -v` (after `make dev`) | `Makefile:77` |
| `make coverage` | `uv run pytest tests/ --cov=clauded --cov-report=term-missing --cov-report=html` | `Makefile:80` |
| `make check` | `lint typecheck test` (all three in sequence) | `Makefile:93` |

`make test` depends on `dev` (runs `uv sync --extra dev` first). Note: `make coverage`
does **not** include `--cov-fail-under=80`; the threshold is enforced by `pyproject.toml`
`[tool.coverage.report]`.

### Pre-commit hooks

`.pre-commit-config.yaml` lines 5–32:
1. `ruff` (with `--fix`)
2. `ruff-format`
3. `mypy` (runs `uv run mypy src/`)
4. `pytest` (runs `uv run pytest tests/ -v --tb=short`, stage: `pre-commit`)

All four hooks must pass before a commit is allowed.

### Unrelated cleanups in tests

`CLAUDE.md` ("Code hygiene" section) states "Boy-scout rule: fix small adjacent issues
you notice in passing." There is no project rule against touching unrelated lines in the
same PR, so adding opencode test coverage alongside any `USE_BUILTIN_RIPGREP=0` cleanup
(if present) is permitted.

---

## 8. Integration / E2E Infrastructure

### No separate `tests/integration/` or `tests/e2e/` directory

All tests live in `tests/`. Files named `test_*_integration.py` and `test_*_e2e.py`
are collocated there; pytest discovers them normally.

### No Playwright + Docker Compose test infrastructure

No `playwright.config.*` in the test directory. No `docker-compose.yml` for tests.
The optional e2e gate referenced in the verifier does not apply here.

### No VM-provisioning tests calling `limactl`

Zero tests invoke `limactl` for real. Every call is intercepted by `patch("subprocess.run")`.
The project intentionally keeps the test suite host-independent.

---

## 9. Project Conventions

### CLAUDE.md (project-specific, `/Users/mrother/Projects/941design/clauded/CLAUDE.md`)

- Use `uv` for all package management; never `pip`.
- Cleanup all temporary files after implementation (including markdown).
- Never tailor production code towards tests; tests adapt to production.
- All feature work and bug fixes must include a `CHANGELOG.md` entry under `[Unreleased]`.
- Run `make format`, `make lint`, `make typecheck`, `make test` after every increment.
- `specs/spec.md` is the software specification for agents — no concrete implementation advice, no file paths or code snippets.

### Serena memories

| File | Summary |
|---|---|
| `code_style_conventions.md` | Python 3.12, ruff rules, mypy strict, pytest ≥ 8.3, Hypothesis ≥ 6.120, 80 % coverage, src layout, isort via ruff |
| `project_overview.md` | Purpose, tech stack (Click, simple-term-menu, PyYAML, Ansible), core modules |
| `project_structure.md` | Directory layout, key files, module responsibilities, testing mirrors src structure |
| `suggested_commands.md` | All make targets, uv commands, project CLI commands |
| `task_completion_checklist.md` | Ordered: format → lint → typecheck → test → CHANGELOG → cleanup → `make check` |
| `vq-01-investigation.md` | Codex integration gap: `full_config` fixture missing codex, no role-inclusion tests for codex |

### README development section

Standard workflow: `make dev` → `make test` → `make check`. No special flags or
environment variables required for the test suite.

### Forbidden patterns

- No `pip install`; always `uv`.
- No production code adaptations to satisfy tests.
- No `git history rewrite`.
- No `state: absent` on Lima mount paths in Ansible (memory `MEMORY.md`).
- Type hints required everywhere (`disallow_untyped_defs = true`).

---

## 10. Existing Version-Check Tests — Precedent for opencode

### `_get_latest_claude_code_version()`

This function calls `subprocess.run(["curl", ...])` on the host. Tests **do not** test
it in isolation. It is always patched at the call site:

```python
patch("clauded.cli._get_latest_claude_code_version", return_value="2.1.62")
```
(`test_version_check.py` lines 478, 582, 619, 734, 746)

There is no dedicated unit test asserting that the function correctly parses the GCS
response — it is tested only indirectly through the CLI integration tests.

### `_get_npm_latest_version()`

Used for Codex version resolution. Patched at function level:
```python
patch("clauded.cli._get_npm_latest_version", return_value="1.0.5")
patch("clauded.cli._get_npm_latest_version", return_value=None)  # failure case
```
(`test_version_check.py` lines 484, 548, 624)

The `return_value=None` case verifies graceful skip when npm fails
(`test_version_check.py` lines 601–639: `test_npm_failure_gracefully_skipped`).

### `_check_library_updates()` parametrisation

`_check_library_updates` is not parametrised with `pytest.mark.parametrize`. Instead,
`TestLibraryUpdateCheck` class contains individual methods for each scenario:

- `test_claude_code_update_detected` (line 461): uses `side_effect=lambda vm, cmd: "2.0.0" if "claude" in cmd else "1.0.5"` to discriminate between tool commands.
- `test_codex_update_detected` (line 496): mirrors the above with swapped values.
- `test_no_updates_no_prompt` (line 528): both match → no output.
- `test_update_confirmed_runs_commands` (line 559): confirms `_update_claude_code` and `_update_codex` are called with correct version strings.
- `test_update_failure_preserves_existing` (line 751): `_update_claude_code` returns `False` → "update failed" + "Existing version preserved" in output.

The discriminating lambda pattern `side_effect=lambda vm, cmd: "X" if "claude" in cmd else "Y"` is the established idiom for `_get_vm_tool_version` mocking.

### `_resolve_framework_versions()` (called inside `_check_library_updates`)

This is the function that dispatches to `_get_latest_claude_code_version` or
`_get_npm_latest_version` depending on which framework is installed. It is exercised
through CLI integration tests only, never unit-tested directly. For opencode, the
equivalent dispatcher logic (fetching opencode's latest version) would follow the same
pattern and would only need patching at the `_get_*` function boundary.

---

## Recommendations for opencode Story Implementation

These are concrete patterns — with citations — that the architect must reuse:

1. **Patch at the function boundary, not the HTTP library.** `_get_latest_claude_code_version` and `_get_npm_latest_version` are always patched at `clauded.cli._get_*`. An analogous `_get_latest_opencode_version()` helper should be designed to be patchable the same way. (`test_version_check.py` lines 478, 484)

2. **Discriminate tool commands with `side_effect` lambdas.** When `_get_vm_tool_version` needs to return different values for different tools, use `side_effect=lambda vm, cmd: "X" if "opencode" in cmd else "Y"`. (`test_version_check.py` lines 473–475, 508–510)

3. **Use `runner.isolated_filesystem()` + inline YAML fixture.** Every CLI integration test that needs a `.clauded.yaml` on disk writes a string fixture inside `isolated_filesystem()`. Define a `config_yaml_with_opencode` string fixture in the new test file that includes `opencode` in `frameworks`. (`test_version_check.py` lines 22–39, 183–188)

4. **No conftest.py — local fixtures only.** Define `runner`, `config_yaml`, and any `Config` helpers as module-level `@pytest.fixture` functions inside the new `test_*.py` file. Do not add a `conftest.py`. (`test_version_check.py` lines 14–17, `test_lima.py` lines 14–29)

5. **Provision role tests follow `test_includes_X / test_excludes_X` pairing.** Add `test_includes_opencode_when_in_frameworks` and `test_excludes_opencode_when_not_in_frameworks` to `test_provisioner.py`, constructing `Provisioner(config, LimaVM(config))` directly and calling `._get_base_roles()`. (`test_provisioner.py` lines 57–104 for the python/node pattern)

6. **Extend `full_config` fixture to include opencode.** The `full_config` fixture in `test_provisioner.py` (line 35) lists `frameworks=["playwright", "claude-code", "codex"]`. Add `"opencode"` to that list and update `test_full_config_has_all_roles` to expect the new role count. (`test_provisioner.py` lines 15–36)

7. **Wizard mock pattern: capture `_menu_select` calls with a recording side-effect.** To assert opencode is in the frameworks multi-select with correct pre-check state, capture `_menu_multi_select` calls and inspect the `items` list for the frameworks prompt. (`test_wizard.py` lines 146–168)

8. **Test `None` return from version fetcher → graceful skip.** Mirror `test_npm_failure_gracefully_skipped` (`test_version_check.py` lines 601–639): patch `_get_latest_opencode_version` to return `None` and assert opencode is absent from the update prompt but other frameworks are still shown.

9. **Test bidirectional version comparison for opencode pins.** Add a `config_yaml_opencode_pinned` fixture (modelled on `config_yaml_pinned` at line 43) and a `test_downgrade_offered` test for opencode. (`test_version_check.py` lines 689–717)

10. **Run `make check` (lint + typecheck + test) after each increment.** All type annotations are required (`disallow_untyped_defs = true`). New functions — including `_get_latest_opencode_version()`, `_update_opencode()`, any wizard integration — must be fully typed. Mypy runs only on `src/`, so test files are exempt from type checking but must pass ruff. (`task_completion_checklist.md`, `pyproject.toml` lines 67–76)
