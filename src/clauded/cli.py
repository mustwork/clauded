"""Main CLI entry point for clauded."""

import logging
import re
import signal
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import click

from . import __version__, wizard
from .config import HARNESS_NAMES, Config
from .detect import detect
from .detect.cli_integration import display_detection_json
from .detect.wizard_integration import (
    apply_detection_to_config,
    run_edit_with_detection,
    run_with_detection,
)
from .downloads import get_downloads
from .lima import LimaVM, destroy_vm_by_name
from .provisioner import Provisioner, __commit__


def _validate_harness_passthrough(
    extra: tuple[str, ...], argv: list[str] | None = None
) -> None:
    """Enforce that the variadic ``extra`` contains only post-``--`` tokens.

    Two failures are caught here, both produced by ``ignore_unknown_options``
    silently absorbing flags click can't match:

    1. ``clauded --typo`` — extras present, no ``--`` separator. Either a
       typo for a clauded flag or a missing separator; either way refuse.
    2. ``clauded --typo -- --resume x`` — ``--typo`` is an unknown clauded
       flag that leaked into the variadic ahead of the legitimate post-``--``
       tail. Refuse and name the offending token(s).

    ``argv`` is the raw process argv to inspect. Defaults to ``sys.argv``;
    tests pass it explicitly because click's ``CliRunner`` does not mutate
    ``sys.argv`` to match the simulated invocation.
    """
    raw = sys.argv if argv is None else argv
    extras = tuple(extra)

    if "--" in raw:
        idx = raw.index("--")
        after_dd = tuple(raw[idx + 1 :])
        # extras should be exactly the tokens after `--`. Anything else means
        # an unknown flag before `--` was absorbed by ignore_unknown_options.
        if len(extras) >= len(after_dd) and extras[len(extras) - len(after_dd) :] == (
            after_dd
        ):
            unknown = extras[: len(extras) - len(after_dd)]
        else:
            # Defensive: ordering or content diverged from the simple
            # "unknown-prefix + after_dd" model. Treat all extras as suspect.
            unknown = extras
        if unknown:
            click.echo(
                f"Error: unknown option(s): {' '.join(unknown)}. "
                "If you meant to forward to the harness, place them after the "
                "`--` separator.",
                err=True,
            )
            raise SystemExit(2)
        return

    if extras:
        click.echo(
            f"Error: unknown option(s): {' '.join(extras)}. "
            "If you meant to forward to the harness, place them after a `--` "
            "separator. Example: clauded -- --resume <session-id>",
            err=True,
        )
        raise SystemExit(2)


def _info(quiet: bool, message: str = "") -> None:
    """Emit a status message to stdout unless ``quiet`` suppresses it.

    Used for launch-path chatter ("Starting Claude Code...", "Updated
    .clauded.yaml", etc.) that the user can turn off with ``--quiet``. Error
    output (``click.echo(..., err=True)``) is never routed through this helper
    so failures always surface.
    """
    if not quiet:
        click.echo(message)


def _reject_passthrough_on_non_launch(extra: tuple[str, ...], *, mode: str) -> None:
    """Reject forwarded args on subcommands that never launch the harness."""
    if not extra:
        return
    click.echo(
        f"Error: harness passthrough args are not valid with --{mode}.",
        err=True,
    )
    raise SystemExit(2)


def _validate_harness_override(harness: str | None, config: Config) -> None:
    """Reject a --harness override that targets a framework not in the config.

    The provisioner only installs frameworks that are present in
    ``config.frameworks`` — so a harness override naming a framework that is
    absent would launch a binary the VM never received. We refuse the launch
    rather than fail later at exec time.

    Exits 1 with an actionable message naming ``clauded --edit`` per FR6 / AC-014.
    """
    if harness is None:
        return
    if harness not in config.frameworks:
        click.echo(
            f"Error: --harness {harness} requires '{harness}' in frameworks. "
            "Run `clauded --edit` to add it to the frameworks list, "
            "or pick a different harness.",
            err=True,
        )
        raise SystemExit(1)


def _sigint_handler(signum: int, frame: object) -> None:
    """Handle SIGINT (CTRL+C) gracefully.

    Prints a cleanup message and raises KeyboardInterrupt to allow
    context managers and finally blocks to execute properly.
    """
    click.echo("\nInterrupted. Cleaning up...", err=True)
    raise KeyboardInterrupt


def _require_interactive_terminal() -> None:
    """Check that stdin is an interactive terminal.

    The wizard requires an interactive terminal for menu prompts.
    This prevents hangs when running in CI/CD, piped input, or other
    non-interactive contexts.

    Raises:
        SystemExit: If stdin is not a TTY.
    """
    if not sys.stdin.isatty():
        click.echo(
            "Interactive terminal required. "
            "Use an existing .clauded.yaml or create one manually.",
            err=True,
        )
        raise SystemExit(1)


def _reset_terminal() -> None:
    """Reset terminal to a sane state after subprocess calls.

    This ensures the terminal is in the correct mode for interactive
    prompts after running limactl commands that may output
    escape sequences or modify terminal settings.
    """
    if sys.stdin.isatty():
        # Use stty sane for comprehensive terminal reset
        try:
            subprocess.run(["stty", "sane"], check=False, capture_output=True)
        except FileNotFoundError:
            pass

        # Also flush any pending input
        try:
            import termios

            fd = sys.stdin.fileno()
            termios.tcflush(fd, termios.TCIFLUSH)
        except (ImportError, OSError):
            pass


def _stop_vm_if_last_session(
    vm: LimaVM, config_path: Path, *, quiet: bool = False
) -> None:
    """Stop the VM only if this was the last active session.

    Checks for other active SSH sessions in the VM. If other sessions
    exist, skips stopping to avoid disrupting other users.

    Args:
        vm: The LimaVM instance to potentially stop
        config_path: Path to .clauded.yaml for reloading config
        quiet: When True, skip the interactive "stop?" prompt and accept its
            default (stop). Status echoes are also suppressed.
    """
    if not vm.is_running():
        return

    # Reload config to respect changes made while VM was running
    current_config = Config.load(config_path)
    if current_config.keep_vm_running:
        return

    # Check if other sessions are still active
    active_sessions = vm.count_active_sessions()
    if active_sessions > 0:
        _info(
            quiet,
            f"\nVM '{vm.name}' has {active_sessions} other active session(s), "
            "leaving it running.",
        )
        return

    if quiet:
        # --quiet implies "use the default" — same outcome the confirm prompt
        # would produce in a non-TTY context, just without the question.
        should_stop = True
    else:
        # Last session - prompt before stopping
        # Allow Ctrl+C to cancel (treated as "No")
        try:
            # Prompt with default=True (auto-confirms in non-interactive contexts)
            # click.confirm() returns True in non-TTY contexts without blocking
            should_stop = click.confirm(
                f"\nThis is the last active session. Stop VM '{vm.name}'?",
                default=True,
            )
        except (click.Abort, EOFError, KeyboardInterrupt):
            # Ctrl+C, Ctrl+D, or EOF: treat as "No" (leave VM running)
            should_stop = False

    # Only echo in interactive mode (when stdin is a TTY) and not quiet
    is_interactive = sys.stdin.isatty() and not quiet

    if should_stop:
        if is_interactive:
            click.echo(f"Stopping VM '{vm.name}'...")
        # Ignore Ctrl+C during actual stop to ensure cleanup completes
        original_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            vm.stop()
            if is_interactive:
                click.echo(f"VM '{vm.name}' stopped.")
        finally:
            signal.signal(signal.SIGINT, original_handler)
    else:
        if is_interactive:
            click.echo(f"VM '{vm.name}' will continue running.")


def _prompt_vm_deletion(vm_name: str) -> bool:
    """Prompt user to delete a VM and return their decision.

    Args:
        vm_name: Name of VM to delete

    Returns:
        True if user confirmed deletion, False otherwise

    """
    should_delete = click.confirm(f"Delete previous VM '{vm_name}'?", default=False)

    if should_delete:
        destroy_vm_by_name(vm_name)
        return True

    return False


def _get_vm_tool_version(vm: LimaVM, command: str) -> str | None:
    """Run a version command in the VM and extract a semver string.

    Args:
        vm: LimaVM instance
        command: Command to run (e.g. "claude --version")

    Returns:
        Extracted version string (e.g. "2.1.62") or None on failure.
    """
    try:
        result = subprocess.run(
            ["limactl", "shell", vm.name, "--", "bash", "-lc", command],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None
        match = re.search(r"\d+\.\d+\.\d+", result.stdout)
        return match.group(0) if match else None
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        return None


def _get_npm_latest_version(vm: LimaVM, package: str) -> str | None:
    """Query npm registry from inside VM for latest package version.

    Args:
        vm: LimaVM instance
        package: npm package name (e.g. "@anthropic-ai/claude-code")

    Returns:
        Latest version string or None on failure.
    """
    try:
        result = subprocess.run(
            [
                "limactl",
                "shell",
                vm.name,
                "--",
                "bash",
                "-lc",
                f"npm view {package} version",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None
        match = re.search(r"\d+\.\d+\.\d+", result.stdout)
        return match.group(0) if match else None
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        return None


def _update_claude_code(vm: LimaVM, config: Config, version_str: str) -> bool:
    """Download Claude Code binary for the specific version.

    Downloads to a temporary file first, validates the download succeeded,
    then atomically moves into place. This prevents corrupting the existing
    binary on network failures or bad URLs.

    Args:
        vm: LimaVM instance
        config: Config with distro info
        version_str: Version to download (e.g. "2.3.0")

    Returns:
        True if update succeeded, False on failure.
    """
    downloads = get_downloads()
    gcs_bucket = downloads["claude_code"]["gcs_bucket"]
    platform = "linux-arm64"
    url = f"{gcs_bucket}/{version_str}/{platform}/claude"
    # Download to temp file, validate, then atomically move into place
    cmd = (
        "set -e && "
        "tmpfile=$(mktemp ~/.local/bin/.claude-update.XXXXXX) && "
        'trap "rm -f $tmpfile" EXIT && '
        f'curl -fsSL "{url}" -o "$tmpfile" && '
        '[ -s "$tmpfile" ] && '
        'chmod +x "$tmpfile" && '
        'mv -f "$tmpfile" ~/.local/bin/claude && '
        "trap - EXIT"
    )
    result = subprocess.run(
        ["limactl", "shell", vm.name, "--", "bash", "-lc", cmd],
        check=False,
    )
    return result.returncode == 0


def _update_codex(vm: LimaVM, version_str: str) -> bool:
    """Run npm install -g @openai/codex@version in VM.

    Args:
        vm: LimaVM instance
        version_str: Version to install (e.g. "1.2.0")

    Returns:
        True if update succeeded, False on failure.
    """
    result = subprocess.run(
        [
            "limactl",
            "shell",
            vm.name,
            "--",
            "bash",
            "-lc",
            f"sudo npm install -g @openai/codex@{version_str}",
        ],
        check=False,
    )
    return result.returncode == 0


def _handle_version_change(vm: LimaVM) -> bool:
    """Check if clauded has been updated since the VM was provisioned.

    Compares the commit recorded in the VM's /etc/clauded.json with the
    currently running clauded's commit. Prompts the user to reprovision
    if they differ.

    Args:
        vm: LimaVM instance to check

    Returns:
        True if user chose to reprovision, False otherwise.
    """
    metadata = vm.get_vm_metadata()
    if metadata is None:
        return False

    vm_commit = metadata.get("commit")
    vm_version = metadata.get("version", "unknown")
    if not vm_commit or vm_commit == "unknown" or __commit__ == "unknown":
        return False

    if vm_commit == __commit__:
        return False

    click.echo(
        f"\nclauded has been updated since this VM was provisioned.\n\n"
        f"  Provisioned with: v{vm_version} ({vm_commit})\n"
        f"  Installed:        v{__version__} ({__commit__})\n\n"
        f"Reprovisioning updates all VM packages and tools."
    )

    try:
        should_reprovision = click.confirm("Reprovision now?", default=False)
    except (click.Abort, EOFError, KeyboardInterrupt):
        should_reprovision = False

    return should_reprovision


def _get_latest_opencode_version() -> str | None:
    """Resolve the latest opencode version from the GitHub releases API.

    Diverges from _get_npm_latest_version: opencode is not on npm. The query
    runs on the host (curl) rather than in the VM, mirroring the
    _get_latest_claude_code_version host-side pattern. Returns None on every
    recoverable failure (network error, non-200, malformed body, missing
    tag_name) — same skip-on-failure shape as _get_npm_latest_version.

    Returns:
        Latest version string (e.g. "1.14.33") or None on failure.
    """
    url = "https://api.github.com/repos/anomalyco/opencode/releases/latest"
    try:
        result = subprocess.run(
            ["curl", "-fsSL", url],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None
        # Match a tag_name field with an optional leading 'v' prefix.
        match = re.search(r'"tag_name"\s*:\s*"v?(\d+\.\d+\.\d+)"', result.stdout)
        return match.group(1) if match else None
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        return None


def _update_opencode(vm: LimaVM, version_str: str) -> bool:
    """Run the opencode install script inside the VM at a specific version.

    The version flows through the OPENCODE_VERSION env var (not interpolated
    unsafely into a shell command). Installs into $HOME/.local/bin via
    OPENCODE_INSTALL_DIR with --no-modify-path, matching the role's contract.

    Args:
        vm: LimaVM instance
        version_str: Version to install (e.g. "1.14.33")

    Returns:
        True if the install script returned 0 AND the resulting opencode
        binary reports the requested version; False otherwise.
    """
    # `pipefail` ensures a failed `curl` propagates through `| bash`; without
    # it, bash exits 0 on empty stdin and we'd report success for a download
    # that never happened. The post-install version check guards against the
    # install script itself failing silently.
    cmd = (
        "set -eo pipefail && "
        f'export OPENCODE_VERSION="{version_str}" && '
        'export OPENCODE_INSTALL_DIR="$HOME/.local/bin" && '
        "curl -fsSL https://opencode.ai/install | bash -s -- --no-modify-path && "
        '"$OPENCODE_INSTALL_DIR/opencode" --version'
    )
    result = subprocess.run(
        ["limactl", "shell", vm.name, "--", "bash", "-lc", cmd],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return False
    return version_str in result.stdout


def _get_latest_claude_code_version() -> str | None:
    """Resolve the latest Claude Code version from GCS on the host.

    Returns:
        Latest version string (e.g. "2.3.0") or None on failure.
    """
    downloads = get_downloads()
    gcs_bucket = downloads["claude_code"]["gcs_bucket"]
    try:
        result = subprocess.run(
            ["curl", "-fsSL", f"{gcs_bucket}/latest"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None
        match = re.search(r"\d+\.\d+\.\d+", result.stdout)
        return match.group(0) if match else None
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        return None


def _resolve_framework_versions(config: Config, vm: LimaVM) -> dict[str, str | None]:
    """Resolve desired versions for each framework.

    For each framework in config.frameworks:
    - If the user pinned a version in .clauded.yaml → use it
    - Otherwise resolve "latest" (GCS for claude-code, npm for codex)

    Args:
        config: Config with frameworks and version pins
        vm: LimaVM instance (needed for npm queries inside VM)

    Returns:
        Dict mapping framework name to resolved version string (or None on failure).
    """
    resolved: dict[str, str | None] = {}

    if "claude-code" in config.frameworks:
        if config.claude_code_version:
            resolved["claude-code"] = config.claude_code_version
        else:
            resolved["claude-code"] = _get_latest_claude_code_version()

    if "codex" in config.frameworks:
        if config.codex_version:
            resolved["codex"] = config.codex_version
        else:
            resolved["codex"] = _get_npm_latest_version(vm, "@openai/codex")

    if "opencode" in config.frameworks:
        if config.opencode_version:
            resolved["opencode"] = config.opencode_version
        else:
            resolved["opencode"] = _get_latest_opencode_version()

    return resolved


def _check_library_updates(vm: LimaVM, config: Config) -> None:
    """Check for framework version mismatches and prompt user to apply changes.

    Performs bidirectional version comparison (upgrades AND downgrades).
    Version sources are determined by _resolve_framework_versions():
    - User-pinned versions from .clauded.yaml take precedence
    - Otherwise resolves "latest" (GCS for Claude Code, npm for Codex)

    Args:
        vm: LimaVM instance
        config: Config with frameworks and version pins
    """
    desired = _resolve_framework_versions(config, vm)
    # (name, installed, target, kind)
    changes: list[tuple[str, str, str, str]] = []

    if "claude-code" in desired and desired["claude-code"]:
        installed = _get_vm_tool_version(vm, "claude --version")
        target = desired["claude-code"]
        if installed and target and installed != target:
            changes.append(("Claude Code", installed, target, "claude-code"))

    if "codex" in desired and desired["codex"]:
        installed = _get_vm_tool_version(vm, "codex --version")
        target = desired["codex"]
        if installed and target and installed != target:
            changes.append(("Codex", installed, target, "codex"))

    if "opencode" in desired and desired["opencode"]:
        installed = _get_vm_tool_version(vm, "opencode --version")
        target = desired["opencode"]
        if installed and target and installed != target:
            changes.append(("opencode", installed, target, "opencode"))

    if not changes:
        return

    click.echo("\nFramework version changes available:\n")
    for name, installed, target, _ in changes:
        click.echo(f"  {name:<13s}{installed} → {target}")
    click.echo()

    try:
        should_update = click.confirm("Apply version changes?", default=False)
    except (click.Abort, EOFError, KeyboardInterrupt):
        should_update = False

    if not should_update:
        return

    for name, _, target, kind in changes:
        click.echo(f"Updating {name} to {target}...")
        if kind == "claude-code":
            ok = _update_claude_code(vm, config, target)
        elif kind == "codex":
            ok = _update_codex(vm, target)
        elif kind == "opencode":
            ok = _update_opencode(vm, target)
        else:
            ok = False
        if ok:
            click.echo(f"  {name} updated successfully.")
        else:
            click.echo(f"  {name} update failed. Existing version preserved.", err=True)


def _handle_crash_recovery(config: Config, config_path: Path) -> None:
    """Handle incomplete VM update detected on startup.

    CONTRACT:
      Inputs:
        - config: Config object with previous_vm_name potentially set
        - config_path: Path to .clauded.yaml file

      Outputs:
        - None (side effect: may destroy VM, updates config file)

      Invariants:
        - previous_vm_name is always cleared after this function
        - config is saved after any cleanup

      Properties:
        - Idempotent: safe to call multiple times
        - User controlled: respects user decision (prompt with default=False)
        - Exception safe: KeyboardInterrupt handled gracefully

      Algorithm:
        1. If previous_vm_name is None, return immediately
        2. Check if current VM exists
        3. If current VM doesn't exist: rollback vm_name to previous_vm_name
        4. If current VM exists: prompt user to delete previous VM
        5. Clear previous_vm_name and save config
    """
    if config.previous_vm_name is None:
        return

    # Check if current VM exists (the one we tried to create/update to)
    current_vm_exists = subprocess.run(
        ["limactl", "list", "-q"],
        capture_output=True,
        text=True,
    ).returncode == 0 and config.vm_name in subprocess.run(
        ["limactl", "list", "-q"],
        capture_output=True,
        text=True,
    ).stdout.strip().split("\n")

    if not current_vm_exists:
        # Rollback: new VM was never created, restore to previous
        click.echo(
            f"\n⚠️  Incomplete VM update detected. "
            f"Current VM '{config.vm_name}' does not exist. "
            f"Rolling back to '{config.previous_vm_name}'."
        )
        config.vm_name = config.previous_vm_name
        config.previous_vm_name = None
        config.save(config_path)
        return

    # Current VM exists, prompt to delete previous VM
    click.echo(
        f"\n⚠️  Incomplete VM update detected. "
        f"Previous VM was '{config.previous_vm_name}'."
    )

    try:
        _prompt_vm_deletion(config.previous_vm_name)
    except KeyboardInterrupt:
        click.echo("\nSkipping cleanup.")

    # Always clear previous_vm_name after handling
    config.previous_vm_name = None
    config.save(config_path)


@click.command(
    context_settings={"ignore_unknown_options": True},
)
@click.version_option(
    version=version("clauded"),
    prog_name="clauded",
)
@click.option(
    "--destroy", is_flag=True, help="Destroy the VM and optionally remove config"
)
@click.option("--reprovision", is_flag=True, help="Re-run provisioning on the VM")
@click.option("--reboot", is_flag=True, help="Reboot VM after provisioning")
@click.option("--stop", is_flag=True, help="Stop the VM without entering shell")
@click.option(
    "--force-stop",
    is_flag=True,
    help="Force stop the VM even if other sessions are active",
)
@click.option("--edit", is_flag=True, help="Edit VM configuration and reprovision")
@click.option(
    "--detect",
    "detect_only",
    is_flag=True,
    help="Run detection only and output results without starting wizard",
)
@click.option(
    "--no-detect",
    is_flag=True,
    help="Skip auto-detection and use default wizard values",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable verbose output for detection, VM creation, and provisioning",
)
@click.option(
    "--harness",
    type=click.Choice(list(HARNESS_NAMES)),
    default=None,
    help=(
        "Override the active coding harness for this invocation "
        "(claude-code | codex | opencode). Persisted value is unchanged."
    ),
)
@click.option(
    "--no-update",
    is_flag=True,
    help=(
        "Skip the clauded-version and harness-binary update checks for a "
        "faster startup. Ignored when --reprovision is also given."
    ),
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    help=(
        "Suppress setup/provisioning output and auto-accept the end-of-session "
        "stop prompt. Errors still surface on stderr."
    ),
)
@click.argument("extra", nargs=-1, type=click.UNPROCESSED)
def main(
    destroy: bool,
    reprovision: bool,
    reboot: bool,
    stop: bool,
    force_stop: bool,
    edit: bool,
    detect_only: bool = False,
    no_detect: bool = False,
    debug: bool = False,
    harness: str | None = None,
    no_update: bool = False,
    quiet: bool = False,
    extra: tuple[str, ...] = (),
) -> None:
    """clauded - Isolated, per-project Lima VMs.

    Run in any directory to create or connect to a project-specific VM.

    Arguments after a ``--`` separator are forwarded verbatim to the harness
    binary (claude / codex / opencode). Example::

        clauded -- --resume <session-id>
    """
    _validate_harness_passthrough(extra)

    # --quiet is incompatible with paths that require interactive prompts,
    # paths whose stdout is itself the deliverable (--detect emits JSON), and
    # paths that would have to run the Ansible provisioner (which is noisy by
    # nature and whose failures benefit from full diagnostic output). Reject up
    # front so users get a clear signal instead of an inconsistent run.
    if quiet:
        config_path_preview = Path.cwd() / ".clauded.yaml"
        if edit:
            click.echo(
                "Error: --quiet cannot be combined with --edit (the wizard "
                "requires interactive output).",
                err=True,
            )
            raise SystemExit(2)
        if reprovision:
            click.echo(
                "Error: --quiet cannot be combined with --reprovision "
                "(provisioning produces unavoidable diagnostic output).",
                err=True,
            )
            raise SystemExit(2)
        if detect_only and not reprovision:
            click.echo(
                "Error: --quiet cannot be combined with --detect (JSON output "
                "is the deliverable).",
                err=True,
            )
            raise SystemExit(2)
        wizard_path = (
            not config_path_preview.exists()
            and not destroy
            and not stop
            and not force_stop
        )
        if wizard_path:
            click.echo(
                "Error: --quiet requires an existing .clauded.yaml — the "
                "first-run wizard cannot operate silently.",
                err=True,
            )
            raise SystemExit(2)
        # --quiet implies --no-update: a version mismatch would otherwise
        # trigger a silent re-provision, which is exactly what we forbid above.
        no_update = True

    # Register SIGINT handler for graceful cleanup
    signal.signal(signal.SIGINT, _sigint_handler)

    # Configure debug logging for detection
    if debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format="[DEBUG] %(name)s: %(message)s",
        )

    config_path = Path.cwd() / ".clauded.yaml"
    project_path = Path.cwd().resolve()

    # Handle --detect alone (detection-only mode, outputs JSON)
    # Note: --detect with --reprovision is handled separately below
    if detect_only and not reprovision:
        _reject_passthrough_on_non_launch(extra, mode="detect")
        detection_result = detect(project_path, debug=debug)
        display_detection_json(detection_result)
        return

    # Handle --destroy
    if destroy:
        _reject_passthrough_on_non_launch(extra, mode="destroy")
        if not config_path.exists():
            click.echo("No .clauded.yaml found in current directory.")
            raise SystemExit(1)

        # Tolerate legacy vm.distro: alpine so users following the FR5
        # migration message (step 1: clauded --destroy) can actually destroy
        # their existing Alpine VM.
        config = Config.load(config_path, allow_alpine_legacy=True)
        vm = LimaVM(config, harness_override=harness, quiet=quiet)

        if vm.exists():
            vm.destroy()

        if click.confirm("Remove .clauded.yaml?", default=False):
            config_path.unlink()
            click.echo("Removed .clauded.yaml")

        return

    # Handle --stop and --force-stop
    if stop or force_stop:
        _reject_passthrough_on_non_launch(
            extra, mode="force-stop" if force_stop else "stop"
        )
        if not config_path.exists():
            click.echo("No .clauded.yaml found in current directory.")
            raise SystemExit(1)

        # Stopping a legacy Alpine VM should not require pre-emptive config
        # editing — same rationale as --destroy above.
        config = Config.load(config_path, allow_alpine_legacy=True)
        vm = LimaVM(config, harness_override=harness, quiet=quiet)

        if not vm.exists() or not vm.is_running():
            click.echo(f"VM '{vm.name}' is not running.")
            return

        # Check for other active sessions unless --force-stop
        if not force_stop:
            active_sessions = vm.count_active_sessions()
            if active_sessions > 0:
                click.echo(
                    f"VM '{vm.name}' has {active_sessions} active session(s). "
                    "Use --force-stop to stop anyway."
                )
                return

        vm.stop()
        return

    # Handle --edit
    if edit:
        if not config_path.exists():
            click.echo("No .clauded.yaml found. Run 'clauded' to create one.")
            raise SystemExit(1)

        if harness is not None:
            click.echo(
                "--harness is ignored with --edit; "
                "use the wizard step to persist a harness change.",
                err=True,
            )
            # Drop the override so the post-edit shell launch honours the
            # persisted harness (per AC-015 / FR6).
            harness = None

        config = Config.load(config_path)
        _handle_crash_recovery(config, config_path)
        vm = LimaVM(config, harness_override=harness, quiet=quiet)

        if not vm.exists():
            click.echo(f"VM '{vm.name}' does not exist. Run 'clauded' to create it.")
            raise SystemExit(1)

        if not vm.is_running():
            vm.start(debug=debug)

        # Always reset terminal state before running wizard - limactl operations
        # may output escape sequences that interfere with menu prompts
        _reset_terminal()

        # Require interactive terminal for wizard prompts
        _require_interactive_terminal()

        try:
            new_config = run_edit_with_detection(config, project_path, debug=debug)

            # Use atomic_update for transactional config save + provisioning
            with new_config.atomic_update(
                new_config.vm_name, config_path
            ) as old_vm_name:
                click.echo("\nUpdated .clauded.yaml")
                # Re-create LimaVM with new config (name might have changed)
                vm = LimaVM(new_config, harness_override=harness, quiet=quiet)
                provisioner = Provisioner(new_config, vm, debug=debug, quiet=quiet)
                provisioner.run()

                # On success: prompt to delete old VM if name changed
                if old_vm_name and old_vm_name != new_config.vm_name:
                    _require_interactive_terminal()
                    _prompt_vm_deletion(old_vm_name)

        except KeyboardInterrupt:
            click.echo("\nEdit cancelled.")
            raise SystemExit(130) from None

        click.echo(
            f"\nStarting Claude Code in VM '{vm.name}' at {new_config.mount_guest}..."
        )
        try:
            # Reconnect to pick up group membership changes from provisioning
            # BUT: skip reconnect if other sessions are active to avoid disrupting them
            # (--reconnect kills the SSH ControlMaster which other sessions share)
            other_sessions = vm.count_active_sessions()
            if other_sessions > 0:
                click.echo(
                    f"Note: {other_sessions} other session(s) active. "
                    "Skipping SSH reconnect to avoid disruption. "
                    "New group memberships (e.g., docker) may require 'newgrp docker' "
                    "or a new terminal."
                )
            vm.shell(reconnect=(other_sessions == 0), extra_argv=extra)
        finally:
            _stop_vm_if_last_session(vm, config_path, quiet=quiet)
        return

    # No config? Run wizard (with or without detection)
    if not config_path.exists():
        # Require interactive terminal for wizard prompts
        _require_interactive_terminal()

        try:
            if no_detect:
                # Skip detection, use default wizard
                config = wizard.run(project_path)
            else:
                # Run wizard with detection-based defaults
                config = run_with_detection(project_path, debug=debug)
            config.save(config_path)
            click.echo("\nCreated .clauded.yaml")
        except KeyboardInterrupt:
            click.echo("\nSetup cancelled.")
            raise SystemExit(130) from None
    else:
        config = Config.load(config_path)
        _handle_crash_recovery(config, config_path)

    # Validate --harness override against the resolved config — but only on the
    # shell-launch path. With --reprovision or --reboot the harness flag is
    # silently ignored per AC-015 / FR6: drop the override before LimaVM is
    # built so the eventual shell launch honours the persisted harness.
    if reprovision or reboot:
        harness = None
    else:
        _validate_harness_override(harness, config)

    vm = LimaVM(config, harness_override=harness, quiet=quiet)
    provisioned = False  # Track if provisioning ran (need SSH reconnect for groups)

    # VM doesn't exist? Create and provision
    if not vm.exists():
        # --quiet forbids running the provisioner: refuse rather than create
        # silently with output that we'd otherwise have to suppress.
        if quiet:
            click.echo(
                f"Error: VM '{vm.name}' does not exist; --quiet refuses to "
                "create and provision it. Run `clauded` once without --quiet, "
                "or pass --reprovision.",
                err=True,
            )
            raise SystemExit(2)
        # Use atomic_update for crash recovery during VM creation
        with config.atomic_update(config.vm_name, config_path) as old_vm_name:
            vm.create(debug=debug)
            provisioner = Provisioner(config, vm, debug=debug, quiet=quiet)
            provisioner.run()
            provisioned = True

            # Prompt to delete old VM if name changed (unlikely in this flow)
            if old_vm_name and old_vm_name != config.vm_name:
                try:
                    _prompt_vm_deletion(old_vm_name)
                except KeyboardInterrupt:
                    click.echo("\nSkipping VM cleanup.")

    else:
        # VM exists but stopped? Start it
        if not vm.is_running():
            vm.start(debug=debug)

        # Check for clauded version change and library updates
        # --no-update short-circuits both checks for fast startup; an explicit
        # --reprovision still wins because the user asked for it.
        if not reprovision and not no_update:
            if _handle_version_change(vm):
                provisioner = Provisioner(config, vm, debug=debug, quiet=quiet)
                provisioner.run()
                provisioned = True
            else:
                _check_library_updates(vm, config)
        elif no_update and not reprovision:
            _info(quiet, "Skipping update checks (--no-update).")

        # Re-run provisioning if requested (independent of start)
        if reprovision:
            # If --detect flag also provided, run detection and merge with config
            if detect_only:
                updated_config, changes_made = apply_detection_to_config(
                    config, project_path, debug=debug
                )
                if changes_made:
                    click.echo("\nDetection found new requirements:")
                    # Show what changed
                    for runtime in (
                        "python",
                        "node",
                        "java",
                        "kotlin",
                        "rust",
                        "go",
                        "dart",
                        "c",
                    ):
                        old_val = getattr(config, runtime, None)
                        new_val = getattr(updated_config, runtime, None)
                        if old_val != new_val and new_val is not None:
                            click.echo(f"  + {runtime}: {new_val}")
                    for tool in updated_config.tools:
                        if tool not in (config.tools or []):
                            click.echo(f"  + tool: {tool}")
                    for db in updated_config.databases:
                        if db not in (config.databases or []):
                            click.echo(f"  + database: {db}")

                    # Save updated config
                    updated_config.save(config_path)
                    click.echo("\nUpdated .clauded.yaml")
                    config = updated_config
                else:
                    click.echo("\nNo new requirements detected.")

            provisioner = Provisioner(config, vm, debug=debug, quiet=quiet)
            provisioner.run()
            provisioned = True

    # Reboot VM if requested (to apply group membership changes, etc.)
    if reboot:
        # Check for other active sessions before rebooting
        other_sessions = vm.count_active_sessions()
        if other_sessions > 0:
            _info(
                quiet,
                f"Cannot reboot: {other_sessions} other session(s) active. "
                "Use --force-stop first or close other sessions.",
            )
        else:
            _info(quiet, f"\nRebooting VM '{vm.name}'...")
            vm.stop()
            vm.start(debug=debug)

    # Enter Claude Code
    _info(
        quiet,
        f"\nStarting Claude Code in VM '{vm.name}' at {config.mount_guest}...",
    )
    try:
        # Reconnect if provisioning ran (picks up group membership changes)
        # Reboot already creates a fresh session, so no reconnect needed
        # BUT: skip reconnect if other sessions are active to avoid disrupting them
        # (--reconnect kills the SSH ControlMaster which other sessions share)
        needs_reconnect = provisioned and not reboot
        if needs_reconnect:
            other_sessions = vm.count_active_sessions()
            if other_sessions > 0:
                _info(
                    quiet,
                    f"Note: {other_sessions} other session(s) active. "
                    "Skipping SSH reconnect to avoid disruption. "
                    "New group memberships (e.g., docker) may require 'newgrp docker' "
                    "or a new terminal.",
                )
                needs_reconnect = False
        vm.shell(reconnect=needs_reconnect, extra_argv=extra)
    finally:
        _stop_vm_if_last_session(vm, config_path, quiet=quiet)


if __name__ == "__main__":
    main()
