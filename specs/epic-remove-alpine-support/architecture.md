# Architecture — Epic: Remove Alpine Linux Support

**Status**: Living document. Updated as cross-story seams are identified.
**Created**: 2026-05-05
**Authoritative for**: all teammates working stories in this epic.

This is the operational architecture document. The spec lives at `spec.md`; the AC list at `acceptance-criteria.md`; codebase exploration at `exploration.json`.

---

## Paradigm

**Modular monolith, package-by-feature** within `src/clauded/`. Plain modules and classes (not hexagonal). Inward-pointing imports: `cli.py` is the top of the graph; `provisioner.py` imports `config`, `lima`, `downloads`; `lima.py` imports `config` and lazily imports `distro`; `config.py` imports `distro`.

A thin `DistroProvider` Protocol exists in `distro.py` but is consulted at one site only (`lima._get_image_config`). The rest of the system passes the distro as `Config.vm_distro: str`.

After this epic completes, the protocol is gone and the distro string is gone. Ubuntu is the implicit and only OS.

---

## Module map

### Modules to remove entirely

| Module | Path | Why |
|---|---|---|
| `distro.py` | `src/clauded/distro.py` | ADR-001: collapse single-element registry. |

### Modules to amend (distro-specific code excised)

| Module | Path | What goes |
|---|---|---|
| `config.py` | `src/clauded/config.py` | `vm_distro` field; `_validate_distro`; `SUPPORTED_DISTROS` import. **Adds**: Alpine-config hard error in `Config.load()`. |
| `cli.py` | `src/clauded/cli.py` | `--distro` Click option (~line 712); `_handle_distro_change` (~line 531); `linux-arm64-musl` branch (~line 254); `distro_override` pass-through (~lines 917, 921); `SUPPORTED_DISTROS` lazy import. |
| `wizard.py` | `src/clauded/wizard.py` | `_select_distro` (~line 116); `distro_override` parameter on `run()` (~line 154); `answers['distro']` assignment (~line 167); lazy distro imports. |
| `lima.py` | `src/clauded/lima.py` | `get_vm_distro` SSH method (~line 360); `_get_image_config` distro branch (~lines 425-437) — replace with direct Ubuntu URL lookup; Alpine comments at lines 229 and 501. |
| `provisioner.py` | `src/clauded/provisioner.py` | `_ROLES_WITH_VARIANTS` frozenset (~line 23); `_apply_distro_suffix` (~line 139); opencode-alpine guard (~lines 179-185); `vm_distro` Ansible variable (~line 381); distro reference in error message (~line 195). Keep `_validate_roles_exist`. |
| `downloads.py` | `src/clauded/downloads.py` | `get_alpine_image()` (~line 64); `alpine_image` key from `get_ansible_download_vars()` (~line 128); simplify `get_cloud_image()` to no-arg or strict ubuntu-only. |
| `downloads.yml` | `src/clauded/downloads.yml` | `alpine_image:` block (~lines 14-17). |
| `detect/wizard_integration.py` | `src/clauded/detect/wizard_integration.py` | `distro_override` param (~line 30); `_select_distro` call (~line 103); `vm_distro` pass-through (~lines 488, 860). **Not in spec FR list — caught by exploration.** |

### Roles directory (`src/clauded/roles/`)

Current state: 24 `*-alpine` + 25 `*-ubuntu` (extra is `opencode-ubuntu`) + 19 stale bare dirs (`aws_cli`, `c`, `dart`, `docker`, `gh`, `go`, `gradle`, `java`, `kotlin`, `maven`, `mongodb`, `mysql`, `playwright`, `poetry`, `postgresql`, `redis`, `rust`, `sqlite`, `uv`).

End state: **25 bare dirs**: `aws_cli`, `c`, `claude_code`, `codex`, `common`, `dart`, `docker`, `gh`, `go`, `gradle`, `java`, `kotlin`, `maven`, `mongodb`, `mysql`, `node`, `opencode`, `playwright`, `poetry`, `postgresql`, `python`, `redis`, `rust`, `sqlite`, `uv`.

Role transition (single Story 04 commit set):
1. `git rm -r src/clauded/roles/{aws_cli,c,dart,docker,gh,go,gradle,java,kotlin,maven,mongodb,mysql,playwright,poetry,postgresql,redis,rust,sqlite,uv}/` (delete 19 stale bare dirs).
2. `git rm -r src/clauded/roles/*-alpine/` (delete 24 alpine variants).
3. `git mv src/clauded/roles/<name>-ubuntu src/clauded/roles/<name>` for all 25 ubuntu variants (incl. `opencode-ubuntu` → `opencode`).

**Note**: AC5 in `acceptance-criteria.md` lists 24 final dir names; the planner must update this to 25 (add `opencode` to the list).

---

## Boundary rules

1. **No direct imports across module boundaries except via the existing inward-pointing graph.** Cross-module access only through declared public symbols. `cli` may import everything; `provisioner` may import `config`/`lima`/`downloads`; lower modules may not import upward.
2. **`config.py` is the single Alpine-detection point at load time.** Per NFR2, every CLI workflow inherits the Alpine rejection by virtue of loading the config first. No code path may bypass `Config.load()` for distro detection. Story 01 establishes this; later stories must not re-introduce parallel detection.
3. **No new abstractions for "Ubuntu-only".** Per ADR-001, the protocol is removed; do not introduce a `UbuntuConfig` class or similar replacement. Ubuntu specifics live inline at their use sites (image URL in `lima._get_image_config`, role names in `provisioner._get_base_roles`, platform string in `_update_claude_code`).
4. **Role names emitted by the provisioner are bare strings.** Per ADR-002 and FR7, no suffix logic remains.
5. **`vm.distro` field in YAML is silently discarded for `ubuntu` (NFR4) and rejected for `alpine` (FR5).** Both behaviours live in `Config.load()` only.
6. **No code path references "alpine" by string after the epic completes**, except: the FR5 error message in `config.py`, `docs/migration-from-alpine.md`, and historical specs/CHANGELOG entries (NFR3).

---

## Cross-story seams

Stories communicate through:

1. **Config.load() Alpine-rejection contract** (introduced by Story 01, consumed by all later stories that load configs in tests):
   - **Owner**: Story 01.
   - **Contract**: `Config.load(path)` raises `ConfigValidationError` with a message containing `"Alpine Linux is no longer supported"` when YAML contains `vm.distro: alpine`. The error is raised before any side-effects.
   - **Consumers**: Stories 02-07 must keep their integration tests using Alpine fixtures pointed at this error path until those fixtures are removed.

2. **Bare role-name contract** (introduced by Story 04, consumed by Stories 05/06/07):
   - **Owner**: Story 04.
   - **Contract**: After Story 04, `provisioner._get_base_roles(config)` returns role names without suffixes. Tests that previously asserted `"common-alpine"` or `"common-ubuntu"` must assert `"common"`.
   - **Consumers**: Story 05 (tests of provisioner), Story 06 (docs that quote provisioner output), Story 07 (E2E provisioning).

3. **No-`vm_distro` Config dataclass** (introduced by Story 03, consumed by Stories 04/05/06/07):
   - **Owner**: Story 03.
   - **Contract**: `Config` no longer has a `vm_distro` attribute. Test fixtures must drop the kwarg.
   - **Consumers**: Stories 04-07.

These seams are file-level contracts only — there is no shared interface module to maintain.

---

## Implementation constraints

From CLAUDE.md (project) and CLAUDE.md (user global):

- **Package management**: `uv` only. No direct `pip`.
- **CHANGELOG**: every story MUST add an `[Unreleased]` entry under the appropriate section.
- **Lint/format/typecheck** verified after each increment: `make lint`, `make format`, `make typecheck`, `make test`.
- **Coverage**: 80% threshold must remain green after deletions (AC14).
- **No production code adaptations for tests.** No test-only branches in production code.
- **No third-party software recommendations.** Project is implementation-agnostic.
- **No `file: state: absent`** in Ansible against Lima mount points (host filesystem mounted into VM).
- **Code is fully responsible for the resulting VM setup.** Do not handle "unexpected configurations" — fail fast on malformed input.
- **Boy-scout rule** for adjacent issues; do not expand scope.
- **No git history rewrite** under any circumstance.

From the spec:

- **NFR1**: never silently auto-recreate a VM. Alpine config → hard error → user manually destroys.
- **NFR2**: `Config.load()` is the only Alpine detection site.
- **NFR3**: post-epic `grep -ri 'alpine' src/ tests/ docs/ specs/` returns only the FR5 error string + migration doc + historical spec dirs + CHANGELOG.
- **NFR4**: `vm.distro: ubuntu` loads silently with INFO log line; no warning, no error.
- **NFR5**: CHANGELOG `Removed` block enumerates Alpine support, `--distro` flag, `vm.distro` config field, `*-alpine` Ansible roles, distro selection wizard step. Plus a `Changed` line stating Ubuntu 24.04 LTS is the sole supported guest OS.

---

## Story order and dependencies

Per `spec.md` "Dependencies and Sequencing":

```
01 (Block Alpine configs)              ← guardrail, must land first
  ├─ 02 (Remove --distro flag + wizard step)   ← parallel-safe with 03
  ├─ 03 (Drop vm.distro from schema + Config)  ← parallel-safe with 02
  │
  └─ 04 (Remove *-alpine roles + drop -ubuntu suffix)  ← needs 02 + 03
       └─ 05 (Remove DistroProvider + Alpine assets)   ← needs 04
            └─ 06 (Documentation, spec, changelog)     ← needs 05
                 └─ 07 (E2E validation + release)       ← needs 06
```

**Single-architect run**: sequential 01 → 02 → 03 → 04 → 05 → 06 → 07.
**Two-architect run** (if scaled up per /base:feature): architect-1 takes 01, 03, 05, 07; architect-2 takes 02, 04, 06. Parallel gate: architect-2 cannot start 02 until 01's `Config.load()` Alpine-rejection contract lands; architect-2 cannot start 04 until 02 and 03 both land. Given the single linear chain after 03, parallelism saves only marginal time. **Recommendation**: single architect, sequential.

---

## Pre-existing patterns to follow

- **Multi-line ConfigValidationError messages**: model on `provisioner.py:181-184` (uses `\n` concatenation with implicit string joining inside the `raise` call).
- **YAML round-trip tests**: model on `tests/test_config.py` patterns (use `pytest.raises(ConfigValidationError, match='<keyword>')`).
- **Role rename pattern**: model on epic-multi-distribution-support story 03 — single-commit `git mv` with simultaneous test updates.
- **CHANGELOG entry style**: bold `**feature name**` followed by an em-dash and prose. See top of `CHANGELOG.md` for existing entries.

---

## Risks specific to this epic's architecture

1. **playwright bare role is Alpine-only** despite not being in `_ROLES_WITH_VARIANTS`. Story 04's stale-bare-dir deletion list must explicitly include `playwright` even though it isn't in the spec's variant registry.
2. **opencode is the new 25th role** (added after the multi-distro epic). FR7 lists 24 ubuntu variants; the planner must extend the list to 25.
3. **detect/wizard_integration.py** holds 4 distro touch-points the spec doesn't enumerate. Stories 02 and 03 must include this file.
4. **`linguist/languages.yml`** mentions "Alpine Linux" as a programming-language entry (linguist data — unrelated to OS choice). NFR3 grep check must filter this hit out OR Story 06 must add an exclusion to the grep one-liner.

---

## Update log

- **2026-05-05**: Initial draft. Synthesized from `exploration.json`. No arch-debate flag in spec frontmatter, so default synthesis path was taken. Cross-story seams declared above; planner may add story-specific contracts when producing `stories.json`.
