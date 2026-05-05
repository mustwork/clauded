# Acceptance Criteria — Remove Alpine Linux Support

Each criterion maps to a functional/non-functional requirement in `spec.md`.

## AC1: Alpine config rejection (FR5, NFR1)

- [ ] Loading a `.clauded.yaml` with `vm.distro: alpine` raises `ConfigValidationError`.
- [ ] The error message names: (a) the Alpine deprecation, (b) the three migration steps, (c) `docs/migration-from-alpine.md`.
- [ ] No VM, file, or process state changes occur on this error path.
- [ ] CLI workflows that *create* or *reprovision* the VM inherit the rejection by virtue of loading the config first: `clauded` (default), `--edit`, `--reprovision`, `--detect`. `--destroy` and `--stop` deliberately **bypass** the Alpine check (`Config.load(..., allow_alpine_legacy=True)`) so the FR5 migration step 1 (`clauded --destroy`) is actually executable on a legacy Alpine project.

## AC2: `--distro` flag removal (FR2)

- [ ] `clauded --help` does not list `--distro`.
- [ ] `clauded --distro ubuntu` exits with Click's "no such option" error.
- [ ] No code path in `cli.py` references `--distro`, `distro_override`, or `distro` as a CLI parameter.

## AC3: Wizard distro step removal (FR3)

- [ ] Running the wizard from a clean directory shows the Python prompt as the first question.
- [ ] `wizard.run()` accepts no `distro_override` parameter.
- [ ] `_select_distro` is deleted from `wizard.py`.

## AC4: Schema simplification (FR4, NFR4)

- [ ] `Config` dataclass has no `vm_distro` attribute.
- [ ] New `.clauded.yaml` files written by `Config.save()` do not include a `distro` key under `vm`.
- [ ] Loading a config with `vm.distro: ubuntu` succeeds without warnings; an `INFO`-level log line notes the field is no longer used.
- [ ] Loading a config with no `vm.distro` field succeeds without comment.
- [ ] Loading a config with `vm.distro: alpine` triggers AC1.

## AC5: Role removal and rename (FR6, FR7, FR8)

- [ ] `src/clauded/roles/` contains exactly 25 directories: `aws_cli`, `c`, `claude_code`, `codex`, `common`, `dart`, `docker`, `gh`, `go`, `gradle`, `java`, `kotlin`, `maven`, `mongodb`, `mysql`, `node`, `opencode`, `playwright`, `poetry`, `postgresql`, `python`, `redis`, `rust`, `sqlite`, `uv`.
- [ ] No directory ends in `-alpine` or `-ubuntu`.
- [ ] None of the role files contains `apk`, `alpine-sdk`, `musl-dev`, `/etc/alpine-release`, `rc-service`, `rc-update`, or `OpenRC`.
- [ ] `provisioner._apply_distro_suffix` and `_ROLES_WITH_VARIANTS` are removed.
- [ ] Provisioning logs emit bare role names (e.g. `Roles: common, python, docker`).

## AC6: `DistroProvider` abstraction removal (ADR-001, FR1)

- [ ] `src/clauded/distro.py` does not exist.
- [ ] `provisioner.py`, `lima.py`, `wizard.py`, `config.py`, `cli.py` contain no imports from `clauded.distro`.
- [ ] `SUPPORTED_DISTROS`, `DistroProvider`, `AlpineProvider`, `UbuntuProvider`, `get_distro_provider` are not referenced anywhere in `src/`.

## AC7: Lima and CLI Alpine cleanup (FR9)

- [ ] `cli.py` always uses `linux-arm64` for the Claude Code platform string (no `linux-arm64-musl` branch).
- [ ] `lima.get_vm_distro()` is removed.
- [ ] `cli._handle_distro_change()` is removed.
- [ ] No comment in `lima.py` or `cli.py` mentions Alpine, musl, OpenRC, or `apk`.

## AC8: Downloads metadata cleanup (FR10, FR11)

- [ ] `src/clauded/downloads.yml` does not contain an `alpine_image` block.
- [ ] `downloads.py` exports no `get_alpine_image` function.
- [ ] `get_ansible_download_vars()['downloads']` does not contain an `alpine_image` key.
- [ ] `get_cloud_image()` returns the Ubuntu image (signature simplified to take no args, or strictly validates `"ubuntu"`).

## AC9: Documentation cleanup (FR12)

- [ ] `docs/alpine-architecture.md` does not exist.
- [ ] `docs/claude-code-alpine-troubleshooting.md` does not exist.
- [ ] `docs/migration-from-alpine.md` exists and contains the FR5 migration steps in AI-agent-readable form.
- [ ] `docs/architecture.md`, `docs/configuration.md`, `docs/supply-chain-security.md`, `docs/testing-infrastructure.md` contain no live references to Alpine.
- [ ] `README.md` contains no Alpine bullets, no `--distro` flag examples, no "change distro" guidance.
- [ ] `user-stories.md` contains no Alpine-specific lines.
- [ ] `specs/spec.md` lists Ubuntu 24.04 LTS as the base OS, with no dual-distro narrative.

## AC10: Changelog (NFR5)

- [ ] `CHANGELOG.md` `[Unreleased]` section has a `Removed` block listing: Alpine support, `--distro` flag, `vm.distro` config field, `*-alpine` Ansible roles, distro selection wizard step.
- [ ] The same section has a `Changed` line stating Ubuntu 24.04 LTS is now the sole supported guest OS.

## AC11: Test suite (FR13)

- [ ] `tests/test_distro.py`, `test_distro_change.py`, `test_config_distro.py`, `test_wizard_distro.py`, `test_cli_distro.py`, `test_downloads_distro.py` are removed.
- [ ] A test exists in `tests/test_config.py` (or equivalent) verifying that loading `distro: alpine` raises `ConfigValidationError` with the expected message.
- [ ] No test parametrizes on `(alpine, ubuntu)` or imports from `clauded.distro`.
- [ ] `pytest --cov-fail-under=80` passes.

## AC12: NFR3 grep check

- [ ] `grep -ri 'alpine' src/ tests/ docs/ specs/` (case-insensitive) returns only:
  - The single error string in `config.py` (`"Alpine Linux is no longer supported..."`).
  - `docs/migration-from-alpine.md`.
  - `specs/epic-multi-distribution-support/` (historical, untouched).
  - `specs/epic-remove-alpine-support/` (this epic).
  - `CHANGELOG.md` (historical entries plus the `Removed` line).
  - `src/clauded/linguist/languages.yml` — external linguist data with an "Alpine Linux" programming-language entry, unrelated to OS choice. Story 06 documents the exclusion.

## AC13: Functional regression suite (FR4, FR11, plus baseline behavior)

End-to-end smoke tests on a fresh Ubuntu host VM, post-migration:

- [ ] `clauded` on an empty project creates a Ubuntu VM, runs the wizard (no distro question), provisions, and drops into a shell.
- [ ] `clauded --reprovision` on a project with `python: 3.12, node: 22, postgresql, claude-code` re-runs cleanly with no errors.
- [ ] `clauded --edit` walks through the wizard with current values pre-selected, saves, and reprovisions.
- [ ] `clauded --destroy` removes the VM and offers to remove `.clauded.yaml`.
- [ ] `clauded --detect` outputs detection results without VM operations.
- [ ] A project with `dart`, `flutter`, `java`, `kotlin`, `gradle`, `mongodb`, `playwright` provisions successfully (covers heavy roles).

## AC14: Tooling gates

- [ ] `ruff check` passes with no warnings.
- [ ] `mypy` passes with no new errors.
- [ ] `pytest` passes with coverage ≥ 80 %.
- [ ] `make lint` and `make test` (or project equivalents) pass on a clean checkout.
