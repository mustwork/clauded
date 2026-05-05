# Remove Alpine Linux Support

**Created**: 2026-04-28
**Status**: Draft
**Supersedes (partially)**: `epic-multi-distribution-support` — Alpine half is removed; Ubuntu becomes the sole distro.

## Overview

Remove Alpine Linux as a supported base distribution for `clauded` VMs. Ubuntu 24.04 LTS becomes the sole, canonical guest OS. The Alpine cloud image, all `*-alpine` Ansible role variants, the `--distro` CLI flag, the wizard distro-selection step, and the Alpine half of the `DistroProvider` abstraction are removed.

This epic is a deliberate scope reduction: the multi-distro abstraction landed in `epic-multi-distribution-support`, but Alpine has accumulated friction (musl/Python incompatibility for `uv`, custom service management quirks, less familiar to most contributors, marginally more maintenance per role) that does not justify the parallel role tree it requires.

## Motivation

### Why remove Alpine

1. **Maintenance overhead**: Every new role, language, tool, or framework requires *two* implementations (`-alpine` and `-ubuntu`) plus test coverage on both. Twenty-four roles × two variants is a permanent ~2× tax on provisioning work.
2. **musl incompatibility tax**: Several upstream toolchains assume glibc — most visibly `uv python install` (currently bypassed on Alpine via a special-case branch in `roles/uv/tasks/main.yml` that falls back to system Python). Each new tool risks a similar workaround.
3. **Service manager divergence**: Alpine uses OpenRC; Ubuntu uses systemd. Database and Docker roles maintain two service-management code paths for the same outcome.
4. **Image size advantage is marginal in this context**: Alpine's small footprint matters most for container distribution. For Lima VMs with 20 GiB disks and persistent state, the few hundred MB difference is not load-bearing.
5. **Familiarity**: `apt`/`systemctl`/`/etc/os-release`-driven Ubuntu matches what most users already debug daily; Alpine surprises (`apk`, `rc-service`, BusyBox `coreutils`, no `bash` by default) generate support friction.
6. **Claude Code troubleshooting**: A dedicated `docs/claude-code-alpine-troubleshooting.md` exists *only* because the Claude Code native installer is finicky on musl. Removing Alpine eliminates that class of issue entirely.

### What we lose

- ~10–20 % faster boot and ~200–400 MB smaller VM images.
- A second pair of eyes on portability bugs (multi-distro testing sometimes catches bugs that single-distro testing misses).
- Optionality for users with strong Alpine preferences.

### Net assessment

The team-time cost of maintaining Alpine outweighs its ergonomic benefits for a developer-VM tool whose primary value is provisioning speed *of the stack*, not boot speed *of the kernel*. Boot time is amortized — VMs are long-lived per project.

## Goals

1. **Single-distro codebase**: Eliminate the `-alpine`/`-ubuntu` role split. Provisioning code paths are unconditional Ubuntu.
2. **Schema clarity**: Decide whether `vm.distro` remains in `.clauded.yaml` (as a forward extension point) or is removed entirely. **Recommendation: remove** (YAGNI; re-introduce when a second distro is actually planned).
3. **Clear migration for existing users**: Users with `distro: alpine` in their `.clauded.yaml` get a precise, actionable error — never a silent OS swap that loses VM state.
4. **No regressions on Ubuntu**: All Ubuntu-supported features continue to work end-to-end.
5. **Smaller, simpler test suite**: Remove Alpine-only tests; collapse parametrized `(alpine, ubuntu)` tests to Ubuntu-only.

## Non-Goals

- Adding new distros (Debian, Fedora, etc.). The architecture remains extensible-by-refactor, not extensible-by-default.
- Re-architecting Ansible roles beyond removing the distro suffix.
- Changing Ubuntu version or moving off LTS.
- Rewriting `epic-multi-distribution-support/spec.md` retroactively (it stays as historical record; this epic supersedes its Alpine half).

## Functional Requirements

### FR1: Drop Alpine from supported distros

- `SUPPORTED_DISTROS` constant in `src/clauded/distro.py` reduces to `["ubuntu"]`, **or** the constant and `DistroProvider` protocol are removed entirely (see ADR-001 below).
- `AlpineProvider` class deleted.
- Factory `get_distro_provider("alpine")` no longer resolves; raises `ValueError`.
- Any reference to Alpine in user-facing strings, docstrings, or help text is removed.

### FR2: Remove `--distro` CLI flag

- `clauded --distro <name>` is no longer accepted; the option is removed from `cli.py`.
- The flag was the user-facing handle for distro selection; with one distro left, it adds noise without adding value.
- Existing `.clauded.yaml` files written by older clauded versions may still contain `vm.distro: ubuntu` — load successfully (silently ignore the field, see FR4).
- Existing `.clauded.yaml` files with `vm.distro: alpine` — see FR5 (migration error path).

### FR3: Remove distro selection from wizard

- The first wizard step (`_select_distro`) is removed.
- Wizard no longer accepts a `distro_override` parameter.
- The wizard now opens directly with the Python version question (or whichever was previously second).

### FR4: Schema simplification — remove `vm.distro`

**Decision (see ADR-001)**: Drop `vm.distro` from the config schema entirely.

- New `.clauded.yaml` files do not include `vm.distro`.
- Existing files with `vm.distro: ubuntu` load successfully — the field is read and discarded with a one-line `INFO`-level message ("`vm.distro` is no longer used; you can remove it from `.clauded.yaml`"). This is *not* a warning because the user did nothing wrong.
- Existing files with `vm.distro: alpine` trigger a hard error — see FR5.
- `Config.vm_distro` attribute is removed from the dataclass.
- The schema version remains `"1"` (no breaking change to the parts of the schema users wrote intentionally).

### FR5: Migration error for Alpine configs

When `Config.load()` encounters `vm.distro: alpine`, it raises `ConfigValidationError` with a precise multi-line message:

```
Alpine Linux is no longer supported (clauded vX.Y.0). This project's
.clauded.yaml is configured for Alpine, and your existing VM is Alpine-based.

To migrate to Ubuntu (the only supported distro):

  1. Destroy the existing VM:    clauded --destroy
     (Project files are safe — they live on the host filesystem.)
  2. Remove the line `distro: alpine` from .clauded.yaml.
  3. Run `clauded` to provision a fresh Ubuntu VM.

See CHANGELOG.md and docs/migration-from-alpine.md for details.
```

Critically, the error is raised *before* any VM operation, so no destructive action happens automatically. The user opts in by following the migration steps.

### FR6: Remove all `*-alpine` Ansible roles

The following 24 directories are deleted:

```
src/clauded/roles/{aws_cli,c,claude_code,codex,common,dart,docker,gh,go,
  gradle,java,kotlin,maven,mongodb,mysql,node,playwright,poetry,postgresql,
  python,redis,rust,sqlite,uv}-alpine/
```

### FR7: Drop the `-ubuntu` role suffix

**Decision (see ADR-002)**: Rename `*-ubuntu` roles to bare names (`common`, `python`, etc.).

- 24 directories renamed from `<name>-ubuntu/` → `<name>/`.
- The provisioner stops applying a distro suffix; `_apply_distro_suffix()` and `_ROLES_WITH_VARIANTS` are removed.
- The `_validate_roles_exist()` helper is kept (it's a useful sanity check independent of distros) but called against the simplified role list.
- Rationale: with one distro, the suffix is dead weight; bare names are clearer in playbooks, logs, and provisioner output.

### FR8: Clean up stale un-suffixed role directories

Audit reveals that **19 of the 24 base role names also exist as un-suffixed directories** (`roles/aws_cli/`, `roles/rust/`, `roles/uv/`, etc.). These are leftovers from before the variant split — every one of those names is in `_ROLES_WITH_VARIANTS`, so the un-suffixed versions are unreachable from the current provisioner.

However, two of them (`roles/rust/tasks/main.yml`, `roles/uv/tasks/main.yml`, `roles/c/tasks/main.yml`) still contain Alpine-specific code (`alpine-sdk`, `musl-dev`, `/etc/alpine-release` checks). They cannot simply be promoted as-is.

**Resolution**: After FR7 renaming, the renamed `*-ubuntu/` content is what lives at the bare path. Any pre-existing un-suffixed directory that is not the renamed Ubuntu variant is deleted *before* the rename to avoid collisions. (Implementation: `git rm -r` the stale un-suffixed dirs in one commit, `git mv <name>-ubuntu <name>` in the next.)

### FR9: Remove Alpine handling from `lima.py` and `cli.py`

- `cli.py:232` — the `linux-arm64-musl` platform branch (`platform = "linux-arm64-musl" if config.vm_distro == "alpine" else "linux-arm64"`) is replaced with the unconditional `linux-arm64`.
- `lima.py` — the `get_vm_distro()` SSH read of `/etc/clauded.json` is removed *or* repurposed as a sanity check ("is this VM still an Alpine leftover?"). Recommendation: **remove**, since FR5 catches Alpine configs at load time, before SSH is even attempted.
- `_handle_distro_change()` in `cli.py` is removed (no more distro changes possible).
- Comments referring to Alpine quirks (e.g. `lima.py:169` about the `who` command, `lima.py:218` about ripgrep) are removed if the workaround they describe is no longer needed; otherwise the comment is updated to the Ubuntu-only justification.

### FR10: Remove Alpine entries from downloads metadata

- `src/clauded/downloads.yml`: remove the `alpine_image` block.
- `src/clauded/downloads.py`: remove `get_alpine_image()`, remove the `alpine_image` key from `get_ansible_download_vars()`.
- Update `get_cloud_image()` to either accept no arg (Ubuntu-only) or remain distro-keyed but only know about `"ubuntu"`. **Recommendation**: simplify to `get_cloud_image()` (no arg) since callers always pass the same value.

### FR11: Default base image becomes Ubuntu

- `specs/spec.md` "Technology Stack" section updates: `Base OS: Ubuntu 24.04 LTS (cloud image)`.
- All copy referring to "Alpine 3.21 cloud image" updates to "Ubuntu 24.04 minimal cloud image".

### FR12: Documentation cleanup

Delete:
- `docs/alpine-architecture.md`
- `docs/claude-code-alpine-troubleshooting.md`

Update:
- `docs/architecture.md` — remove Alpine paragraphs and dual-distro discussion.
- `docs/configuration.md` — remove Alpine examples and `--distro` flag docs.
- `docs/supply-chain-security.md` — remove Alpine repository signing notes.
- `docs/testing-infrastructure.md` — remove dual-distro test matrix references.
- `README.md` — remove Alpine bullets, the distro selector wizard example, the `clauded --distro alpine` example, and the "change from Alpine to Ubuntu" guidance.
- `CHANGELOG.md` — add a `[Unreleased] / Removed` entry summarizing this epic.
- `user-stories.md` — strike Alpine personas/lines.
- `specs/spec.md` — update base OS, role table, constraints, and assumptions.

Add:
- `docs/migration-from-alpine.md` — a short, AI-agent-readable guide describing the FR5 migration path. (This is the one new doc the project gets — it's the only documentation that's needed for users coming from older clauded versions, and it's referenced from the FR5 error message.)

### FR13: Test suite simplification

- `tests/test_distro.py` — remove (or trim to a single "no-distro field" sanity test if `Config.vm_distro` removal is verified there).
- `tests/test_distro_change.py` — remove (no more distro changes).
- `tests/test_config_distro.py` — remove or fold into `test_config.py` as the FR5 migration-error test.
- `tests/test_wizard_distro.py` — remove.
- `tests/test_cli_distro.py` — remove.
- `tests/test_downloads_distro.py` — remove.
- `tests/test_provisioner.py` — remove parametrization over `(alpine, ubuntu)`; keep the Ubuntu cases.
- `tests/test_lima.py`, `tests/test_database.py`, `tests/test_version_check.py` — strip Alpine-conditional cases.
- Add: a focused unit test that loading a config with `distro: alpine` raises `ConfigValidationError` with the migration message.
- Coverage threshold (80 %) must remain satisfied after removal.

## Non-Functional Requirements

### NFR1: No silent VM swap

The system MUST NOT auto-recreate a VM when an Alpine config is encountered. The user explicitly destroys and re-creates. This is the strongest possible defense against accidental data loss in the migration.

### NFR2: Single error path for Alpine configs

There is exactly one place that detects "this config is for Alpine" — `Config.load()`. Every CLI workflow (`--reprovision`, `--edit`, `--detect`, default) inherits the error by virtue of loading the config first. No workflow may bypass the check.

### NFR3: No code path references "alpine" by string after removal

A grep-level acceptance check: `grep -ri 'alpine' src/ tests/ docs/ specs/` after the epic completes returns only:
- The single `ConfigValidationError` message in `config.py`.
- `CHANGELOG.md` entries (historical).
- `specs/epic-multi-distribution-support/` (historical record, untouched).
- `specs/epic-remove-alpine-support/` (this epic).
- `docs/migration-from-alpine.md` (migration guide).

No live production code path branches on Alpine after the epic completes.

### NFR4: Backward-compatible config loading where possible

A `.clauded.yaml` that uses `distro: ubuntu` (the only legacy value worth preserving) loads without warnings — the field is silently ignored. This is the common case for users who explicitly chose Ubuntu under the old multi-distro support and should not require any user action.

### NFR5: CHANGELOG entry

A `Removed` section under `[Unreleased]` lists:
- Alpine Linux support
- `--distro` CLI flag
- `vm.distro` config field
- `*-alpine` Ansible roles
- Distro selection wizard step

Plus a `Changed` line: "Ubuntu 24.04 LTS is now the sole supported guest OS."

## Architecture Decisions

### ADR-001: Remove the `DistroProvider` abstraction entirely

**Context**: After Alpine removal, only one provider remains. The protocol, factory, and provider class collectively cost ~150 LoC for a one-element registry.

**Options considered**:
1. Keep the abstraction with a single `UbuntuProvider`. Pro: extensible if a third distro arrives. Con: dead weight, misleads readers into thinking distro choice exists.
2. Remove the abstraction; inline Ubuntu-specific calls (cloud image lookup, role names) at their use sites.
3. Replace the abstraction with a simple module-level constant (`UBUNTU_IMAGE = ...`).

**Decision**: Option 2 — remove. YAGNI. If a future epic adds Debian or Fedora, the abstraction can be re-introduced in a focused PR; the historical commit (already on `master`) shows what shape it took. Speculative extensibility is not free.

**Pros**: Smaller surface area, fewer files, fewer concepts to learn.
**Cons**: Re-introducing multi-distro support later costs one focused PR.

### ADR-002: Drop the `-ubuntu` role suffix

**Context**: With one distro, every role name carries `-ubuntu`. Ansible playbooks, provisioner code, and log output all show `Roles: common-ubuntu, python-ubuntu, docker-ubuntu, ...`. The suffix encodes information that is no longer variable.

**Decision**: Rename to bare names (`common`, `python`, `docker`, ...). Update the provisioner to emit `Roles: common, python, docker, ...`.

**Pros**: Cleaner output, simpler provisioner, no apparent meaning in a suffix that never varies.
**Cons**: Slightly more work if a second distro is ever re-introduced (would need to rename back). Considered low-probability per ADR-001.

### ADR-003: Hard error on Alpine configs (no auto-migration)

**Context**: An Alpine config implies an Alpine VM exists locally. Auto-rewriting `distro: alpine` to nothing would leave the user with a Ubuntu config and a still-running Alpine VM — a broken state where `--reprovision` would fail loudly inside Ansible (apt vs apk).

**Options considered**:
1. Hard error with explicit migration steps (FR5).
2. Auto-rewrite config to Ubuntu and trigger `--destroy` flow with confirmation.
3. Auto-rewrite config to Ubuntu silently and let the next provision fail.

**Decision**: Option 1. The user destroys the VM consciously. The error message is precise and actionable.

**Pros**: No accidental destruction. Clear ownership of the migration moment.
**Cons**: A small additional manual step. Worth it given the cost of getting it wrong.

### ADR-004: Keep `_validate_roles_exist()`

**Context**: With one distro, role-existence validation is less critical (no chance of `python-debian` typo). But the helper still catches accidental typos in `_get_base_roles()`.

**Decision**: Keep it. It's ~20 LoC of defensive code that runs in milliseconds and improves error messages.

## Architectural Impact

### Module diff (post-removal)

| Module | LoC delta (rough) | Notes |
|---|---|---|
| `src/clauded/distro.py` | -300 (file deleted) | Per ADR-001 |
| `src/clauded/config.py` | -30 | Drop `vm_distro`, `_validate_distro`, add Alpine-config error path |
| `src/clauded/cli.py` | -80 | Drop `--distro`, `_handle_distro_change`, `linux-arm64-musl` branch |
| `src/clauded/wizard.py` | -50 | Drop `_select_distro`, `distro_override` param |
| `src/clauded/lima.py` | -40 | Drop `get_vm_distro`, Alpine comments |
| `src/clauded/downloads.py` | -10 | Drop alpine helpers |
| `src/clauded/downloads.yml` | -5 | Drop `alpine_image` block |
| `src/clauded/provisioner.py` | -40 | Drop suffix logic, drop `vm_distro` playbook var |
| `src/clauded/roles/` | -24 dirs (plus 19 stale dirs) | Per FR6, FR7, FR8 |
| `tests/` | -8 files, ~-600 LoC | Per FR13 |
| `docs/` | -2 files, -200 LoC, +1 file (~50 LoC migration guide) | Per FR12 |
| `specs/spec.md` | ~-30 lines | Update base OS, role table |

Net: ~−1500 LoC, ~−50 files. The codebase shrinks meaningfully.

### Out-of-scope refactoring

While many roles will be touched (rename), this epic does NOT:
- Restructure role internals.
- Combine roles (e.g., merge `uv` into `python`).
- Pin different Ubuntu package versions.
- Modify the playbook generation contract.

Those changes, if desired, belong in separate epics.

## User Experience Flow

### Scenario 1: New project, fresh install

```bash
cd ~/myproject
clauded
```

Wizard starts at Python (no distro question). VM is Ubuntu 24.04. `.clauded.yaml` contains no `distro` field. Indistinguishable from prior behavior except for the missing first wizard question.

### Scenario 2: Existing Ubuntu user

```bash
cd ~/myproject  # has .clauded.yaml with distro: ubuntu
clauded
```

`.clauded.yaml` is loaded. The `distro: ubuntu` line is silently ignored (NFR4). VM (already Ubuntu) starts, shell opens. No user action required. On the next `clauded --edit`, the config is rewritten without the `distro` line.

### Scenario 3: Existing Alpine user (the migration moment)

```bash
cd ~/myproject  # has .clauded.yaml with distro: alpine
clauded
```

Output:
```
Error: Alpine Linux is no longer supported (clauded vX.Y.0). This project's
.clauded.yaml is configured for Alpine, and your existing VM is Alpine-based.

To migrate to Ubuntu (the only supported distro):

  1. Destroy the existing VM:    clauded --destroy
     (Project files are safe — they live on the host filesystem.)
  2. Remove the line `distro: alpine` from .clauded.yaml.
  3. Run `clauded` to provision a fresh Ubuntu VM.

See CHANGELOG.md and docs/migration-from-alpine.md for details.
```

Exit code: 1. No filesystem changes occur.

### Scenario 4: User who passed `--distro` out of habit

```bash
clauded --distro ubuntu
```

Output (from Click):
```
Error: No such option: --distro
```

Exit code: 2 (Click's default for unknown options). The error is curt; the README and CHANGELOG explain the removal.

## Acceptance Criteria

See `acceptance-criteria.md` for the full enumerated list.

## Risk Analysis

| Risk | Severity | Mitigation |
|---|---|---|
| Existing Alpine users find the migration disruptive | Medium | Clear FR5 error message; `migration-from-alpine.md` doc; CHANGELOG `Removed` callout; project files are mounted from host so data is safe. |
| Hidden Alpine assumption surfaces post-removal (e.g., a hardcoded `apk` somewhere) | Medium | NFR3 grep check; full provisioning run on Ubuntu in CI before merge. |
| Renaming roles breaks user-authored extensions | Low | Roles are an internal contract; users do not author roles in this project. The renaming touches only files inside `src/clauded/roles/`. |
| Lima still runs cached Alpine images on developer machines | Low | Out of scope — the existing VM continues to run until destroyed. The error in FR5 routes the user to destroy it. |
| Test coverage drops below 80 % after deletions | Medium | Track coverage during each story; if it drops, add unit tests for the Alpine-error path and any newly uncovered Ubuntu-only branches. |
| Lima `linux-arm64-musl` platform string was used elsewhere | Low | `grep -rn 'linux-arm64-musl' src/` confirms the single use site at `cli.py:232`. |

## Migration Strategy

Phased delivery; each story leaves the codebase in a working state.

### Story 01 — Block Alpine configs, surface migration message

- Update `_validate_distro()` in `config.py`: when `distro == "alpine"`, raise `ConfigValidationError` with the FR5 message.
- Add the `migration-from-alpine.md` doc.
- Add unit test for the rejection path.
- All other Alpine code remains in place — this is a purely additive guardrail that prevents users from creating new Alpine VMs while the bulk removal proceeds.
- **Observable change**: New `clauded` runs against an Alpine config now error out cleanly. Existing Ubuntu workflows unaffected.

### Story 02 — Remove the `--distro` flag and wizard step

- Delete `--distro` Click option in `cli.py`.
- Delete `_select_distro()` and `distro_override` parameter in `wizard.py`.
- Delete `_handle_distro_change()` in `cli.py`.
- Update tests: `test_cli_distro.py`, `test_wizard_distro.py`, `test_distro_change.py` — delete or trim.
- **Observable change**: Wizard opens at Python; `--distro` is gone from `--help`.

### Story 03 — Drop `vm.distro` from the schema and `Config`

- Remove `vm_distro` field from `Config` dataclass.
- `Config.load()` reads and discards any `distro` field, with the `INFO` log message (NFR4).
- `Config.save()` no longer emits `distro`.
- Update `provisioner.py` to drop the `vm_distro` playbook var.
- Update tests: `test_config.py`, `test_config_distro.py` — delete or fold.
- **Observable change**: New `.clauded.yaml` files have no `distro` line. Old Ubuntu configs continue to work unchanged.

### Story 04 — Remove `*-alpine` roles and the `-ubuntu` suffix

- `git rm -r src/clauded/roles/*-alpine/` (all 24 directories).
- Delete the 19 stale un-suffixed role directories that still contain Alpine code.
- `git mv src/clauded/roles/<name>-ubuntu src/clauded/roles/<name>` for all 24 roles.
- Update `provisioner.py`: drop `_apply_distro_suffix()`, `_ROLES_WITH_VARIANTS`, the suffix application, and the `_get_base_roles()` callers' suffix application. Roles emitted in playbook are bare names.
- Update tests for the new role names.
- **Observable change**: Provisioning logs read `Roles: common, python, docker, ...` instead of `common-ubuntu, python-ubuntu, ...`. Provisioning still works end-to-end.

### Story 05 — Remove `DistroProvider` abstraction and Alpine assets

- Delete `src/clauded/distro.py`.
- Delete `get_alpine_image()` in `downloads.py`; simplify `get_cloud_image()`; drop `alpine_image` from `get_ansible_download_vars()`.
- Delete the `alpine_image` block from `downloads.yml`.
- Delete `lima.get_vm_distro()` and Alpine comments in `lima.py`.
- Delete `linux-arm64-musl` platform branch in `cli.py`.
- Update `provisioner.py` import: `from .distro import ...` line removed.
- Update tests accordingly.
- **Observable change**: No code path references "alpine"; the abstraction is gone. Behavior unchanged for Ubuntu users.

### Story 06 — Documentation, spec, and changelog

- Delete `docs/alpine-architecture.md` and `docs/claude-code-alpine-troubleshooting.md`.
- Update `docs/architecture.md`, `docs/configuration.md`, `docs/supply-chain-security.md`, `docs/testing-infrastructure.md`, `README.md`, `user-stories.md`, `specs/spec.md`.
- Add `[Unreleased] / Removed` and `[Unreleased] / Changed` entries to `CHANGELOG.md`.
- Verify NFR3 grep check passes.
- **Observable change**: Documentation reflects single-distro reality.

### Story 07 — End-to-end validation and release

- Run full Ubuntu provisioning test for: a Python+Node project, a Java+Postgres project, a Rust+Docker project (representative coverage of the role matrix).
- Run lint (`ruff check`), type check (`mypy`), full pytest with `--cov-fail-under=80`.
- Tag a release.
- **Observable change**: A user-installable release where Ubuntu is the sole distro.

## Dependencies and Sequencing

- Story 01 is a precondition for the rest (it makes the migration safe before destructive removals begin).
- Stories 02 and 03 can be done in parallel by independent agents/PRs.
- Story 04 depends on 02 and 03 (those clear references to `vm_distro`).
- Story 05 depends on 04 (role names no longer reference distro).
- Story 06 depends on 05 (documentation matches the final code state).
- Story 07 depends on 06.

## Open Questions

1. **Should `migration-from-alpine.md` be a permanent doc or auto-removed in N+2 versions?**
   - Proposed: keep permanently. It's small, AI-readable, and a migration record is more valuable than the disk space it costs.

2. **Should the FR5 error path also detect leftover Alpine VMs even when the config is already migrated (e.g. user manually edited `.clauded.yaml` to remove `distro: alpine` but did not destroy the VM)?**
   - Proposed: no. If the user edited the config, they took ownership of the migration. The first `--reprovision` will fail at the Ansible layer (apt vs apk) with a clear-enough subprocess error. Adding a second guard adds complexity for a self-inflicted edge case.

3. **CI matrix**: did we ever run CI against a real Alpine VM, or only unit-test Alpine code paths?**
   - From `.github/workflows/test.yml`: unit-test only. There is no end-to-end Alpine VM in CI. Therefore removing Alpine has no CI-runtime impact; only test-file deletions.

## References

- Existing epic: `specs/epic-multi-distribution-support/spec.md` — introduces the multi-distro abstraction this epic partially unwinds.
- `src/clauded/distro.py` — `SUPPORTED_DISTROS`, `DistroProvider`, `AlpineProvider`, `UbuntuProvider`.
- `src/clauded/provisioner.py:_ROLES_WITH_VARIANTS` — current variant registry.
- `src/clauded/cli.py:_handle_distro_change` — distro-change detection that becomes obsolete.
- `roles/uv/tasks/main.yml`, `roles/rust/tasks/main.yml`, `roles/c/tasks/main.yml` — stale un-suffixed roles still containing Alpine conditionals (FR8).

## Success Metrics

- Codebase shrinks by ~1500 LoC and ~50 files.
- `grep -ri 'alpine' src/` returns only the FR5 error message (NFR3).
- Provisioning a fresh Ubuntu project completes successfully end-to-end with no regressions vs. pre-epic Ubuntu behavior.
- Lint, type-check, and test suite (≥ 80 % coverage) all green.
- Existing Ubuntu-config users observe zero forced changes; existing Alpine-config users observe a single, actionable error message.
