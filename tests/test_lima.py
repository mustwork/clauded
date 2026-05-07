"""Tests for clauded.lima module."""

import dataclasses
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from clauded.config import Config
from clauded.lima import LaunchSpec, LimaVM, _build_launch_spec


@pytest.fixture
def sample_config() -> Config:
    """Create a sample config for testing."""
    return Config(
        vm_name="clauded-test1234",
        cpus=1,
        memory="8GiB",
        disk="20GiB",
        mount_host="/path/to/project",
        mount_guest="/path/to/project",
        python="3.12",
        node="20",
        tools=["docker"],
        databases=["postgresql"],
        frameworks=["claude-code"],
    )


class TestLimaVMInit:
    """Tests for LimaVM initialization."""

    def test_sets_name_from_config(self, sample_config: Config) -> None:
        """VM name is taken from config."""
        vm = LimaVM(sample_config)

        assert vm.name == "clauded-test1234"

    def test_stores_config(self, sample_config: Config) -> None:
        """Config is stored for later use."""
        vm = LimaVM(sample_config)

        assert vm.config is sample_config


class TestLimaVMExists:
    """Tests for LimaVM.exists()."""

    def test_returns_true_when_vm_in_list(self, sample_config: Config) -> None:
        """Returns True when VM name appears in limactl list output."""
        vm = LimaVM(sample_config)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="default\nclauded-test1234\nother-vm"
            )

            assert vm.exists() is True

        mock_run.assert_called_once_with(
            ["limactl", "list", "-q"],
            capture_output=True,
            text=True,
        )

    def test_returns_false_when_vm_not_in_list(self, sample_config: Config) -> None:
        """Returns False when VM name not in limactl list output."""
        vm = LimaVM(sample_config)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="default\nother-vm")

            assert vm.exists() is False


class TestLimaVMIsRunning:
    """Tests for LimaVM.is_running()."""

    def test_returns_true_when_status_is_running(self, sample_config: Config) -> None:
        """Returns True when VM status is 'Running'."""
        vm = LimaVM(sample_config)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="Running")

            assert vm.is_running() is True

        mock_run.assert_called_once_with(
            ["limactl", "list", "--format", "{{.Status}}", "clauded-test1234"],
            capture_output=True,
            text=True,
        )

    def test_returns_false_when_status_is_stopped(self, sample_config: Config) -> None:
        """Returns False when VM status is 'Stopped'."""
        vm = LimaVM(sample_config)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="Stopped")

            assert vm.is_running() is False

    def test_returns_false_when_status_has_whitespace(
        self, sample_config: Config
    ) -> None:
        """Handles status output with trailing whitespace."""
        vm = LimaVM(sample_config)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="Running\n")

            assert vm.is_running() is True


class TestLimaVMGetSshConfigPath:
    """Tests for LimaVM.get_ssh_config_path()."""

    def test_returns_correct_path(self, sample_config: Config) -> None:
        """Returns the expected SSH config path."""
        vm = LimaVM(sample_config)

        expected = Path.home() / ".lima" / "clauded-test1234" / "ssh.config"
        assert vm.get_ssh_config_path() == expected


class TestLimaVMGenerateLimaConfig:
    """Tests for LimaVM._generate_lima_config()."""

    def test_generates_correct_structure(self, sample_config: Config) -> None:
        """Generated config has correct structure."""
        vm = LimaVM(sample_config)

        config = vm._generate_lima_config()

        assert config["vmType"] == "vz"
        assert config["os"] == "Linux"
        assert config["arch"] == "aarch64"

    def test_uses_config_resources(self, sample_config: Config) -> None:
        """Generated config uses resource settings from config."""
        vm = LimaVM(sample_config)

        config = vm._generate_lima_config()

        assert config["cpus"] == 1
        assert config["memory"] == "8GiB"
        assert config["disk"] == "20GiB"

    def test_uses_custom_image_when_set(self, sample_config: Config) -> None:
        """Generated config uses custom image URL when vm_image is set."""
        sample_config.vm_image = "https://example.com/custom-image.qcow2"
        vm = LimaVM(sample_config)

        config = vm._generate_lima_config()

        assert len(config["images"]) == 1
        assert (
            config["images"][0]["location"] == "https://example.com/custom-image.qcow2"
        )
        assert config["images"][0]["arch"] == "aarch64"
        # Custom images don't have checksum verification (user's responsibility)
        assert "digest" not in config["images"][0]

    def test_configures_virtiofs_mount(
        self, sample_config: Config, tmp_path: Path
    ) -> None:
        """Generated config has virtiofs mount for project directory."""
        vm = LimaVM(sample_config)

        with (
            patch("clauded.lima.Path.home", return_value=tmp_path),
            patch("clauded.lima.getpass.getuser", return_value="testuser"),
        ):
            config = vm._generate_lima_config()

        assert config["mountType"] == "virtiofs"
        # First mount is always the project directory
        assert config["mounts"][0]["location"] == "/path/to/project"
        assert config["mounts"][0]["mountPoint"] == "/path/to/project"
        assert config["mounts"][0]["writable"] is True

    def test_mounts_home_directories_when_exist(
        self, sample_config: Config, tmp_path: Path
    ) -> None:
        """Mounts ~/.claude and ~/.codex read-write when they exist."""
        vm = LimaVM(sample_config)

        # Create test directories
        claude_dir = tmp_path / ".claude"
        codex_dir = tmp_path / ".codex"
        claude_dir.mkdir()
        codex_dir.mkdir()

        with (
            patch("clauded.lima.Path.home", return_value=tmp_path),
            patch("clauded.lima.getpass.getuser", return_value="testuser"),
        ):
            config = vm._generate_lima_config()

        assert len(config["mounts"]) == 3

        # Check .claude mount
        claude_mount = config["mounts"][1]
        assert claude_mount["location"] == str(claude_dir)
        assert claude_mount["mountPoint"] == "/home/testuser.linux/.claude"
        assert claude_mount["writable"] is True

        # Check .codex mount
        codex_mount = config["mounts"][2]
        assert codex_mount["location"] == str(codex_dir)
        assert codex_mount["mountPoint"] == "/home/testuser.linux/.codex"
        assert codex_mount["writable"] is True

    def test_creates_claude_dir_when_not_exist(
        self, sample_config: Config, tmp_path: Path
    ) -> None:
        """Creates and mounts ~/.claude and ~/.codex when missing on host."""
        vm = LimaVM(sample_config)
        claude_dir = tmp_path / ".claude"
        codex_dir = tmp_path / ".codex"

        assert not claude_dir.exists()
        assert not codex_dir.exists()

        with (
            patch("clauded.lima.Path.home", return_value=tmp_path),
            patch("clauded.lima.getpass.getuser", return_value="testuser"),
        ):
            config = vm._generate_lima_config()

        # Should create the directory
        assert claude_dir.exists()
        assert codex_dir.exists()
        # Should mount both
        assert len(config["mounts"]) == 3
        assert config["mounts"][1]["location"] == str(claude_dir)
        assert config["mounts"][2]["location"] == str(codex_dir)

    def test_mount_points_must_be_absolute_paths(
        self, sample_config: Config, tmp_path: Path
    ) -> None:
        """Lima requires mount points to be absolute paths, not starting with ~."""
        vm = LimaVM(sample_config)

        # Create test directories
        claude_dir = tmp_path / ".claude"
        codex_dir = tmp_path / ".codex"
        claude_dir.mkdir()
        codex_dir.mkdir()

        with (
            patch("clauded.lima.Path.home", return_value=tmp_path),
            patch("clauded.lima.getpass.getuser", return_value="testuser"),
        ):
            config = vm._generate_lima_config()

        # All mount points must be absolute paths (not starting with ~)
        for mount in config["mounts"]:
            mount_point = mount["mountPoint"]
            assert not mount_point.startswith("~"), (
                f"mountPoint '{mount_point}' must not start with '~' - "
                "Lima requires absolute paths"
            )
            assert mount_point.startswith(
                "/"
            ), f"mountPoint '{mount_point}' must be an absolute path"

    def test_mounts_opencode_dirs_when_in_frameworks(self, tmp_path: Path) -> None:
        """AC-019: opencode in frameworks adds two host mounts; mkdir is called."""
        config = Config(
            vm_name="clauded-opencode",
            cpus=2,
            memory="4GiB",
            disk="10GiB",
            mount_host="/path/to/project",
            mount_guest="/path/to/project",
            frameworks=["opencode"],
        )
        vm = LimaVM(config)

        with (
            patch("clauded.lima.Path.home", return_value=tmp_path),
            patch("clauded.lima.getpass.getuser", return_value="testuser"),
        ):
            generated = vm._generate_lima_config()

        config_dir = tmp_path / ".config" / "opencode"
        share_dir = tmp_path / ".local" / "share" / "opencode"
        assert config_dir.exists(), "host ~/.config/opencode must be created"
        assert share_dir.exists(), "host ~/.local/share/opencode must be created"

        mount_locations = {m["location"]: m for m in generated["mounts"]}
        assert str(config_dir) in mount_locations
        assert str(share_dir) in mount_locations

        config_mount = mount_locations[str(config_dir)]
        assert config_mount["mountPoint"] == "/home/testuser.linux/.config/opencode"
        assert config_mount["writable"] is True

        share_mount = mount_locations[str(share_dir)]
        assert share_mount["mountPoint"] == "/home/testuser.linux/.local/share/opencode"
        assert share_mount["writable"] is True

    def test_does_not_mount_opencode_dirs_when_absent(self, tmp_path: Path) -> None:
        """opencode mounts are skipped when 'opencode' is not in frameworks."""
        config = Config(
            vm_name="clauded-no-opencode",
            cpus=2,
            memory="4GiB",
            disk="10GiB",
            mount_host="/path/to/project",
            mount_guest="/path/to/project",
            frameworks=["claude-code", "codex"],
        )
        vm = LimaVM(config)

        with (
            patch("clauded.lima.Path.home", return_value=tmp_path),
            patch("clauded.lima.getpass.getuser", return_value="testuser"),
        ):
            generated = vm._generate_lima_config()

        # No opencode-related mount should appear
        for mount in generated["mounts"]:
            assert not mount["mountPoint"].endswith(
                "/opencode"
            ), f"unexpected opencode mountPoint: {mount}"
            assert (
                "/opencode" not in mount["mountPoint"]
            ), f"unexpected opencode mountPoint: {mount}"

        # Host directories should not be created either
        assert not (tmp_path / ".config" / "opencode").exists()
        assert not (tmp_path / ".local" / "share" / "opencode").exists()

    def test_disables_containerd(self, sample_config: Config) -> None:
        """Generated config disables containerd."""
        vm = LimaVM(sample_config)

        config = vm._generate_lima_config()

        assert config["containerd"]["system"] is False
        assert config["containerd"]["user"] is False

    def test_no_provision_scripts(self, sample_config: Config, tmp_path: Path) -> None:
        """Generated config has no provision scripts (handled by Ansible)."""
        vm = LimaVM(sample_config)

        with (
            patch("clauded.lima.Path.home", return_value=tmp_path),
            patch("clauded.lima.getpass.getuser", return_value="testuser"),
        ):
            config = vm._generate_lima_config()

        # No provision scripts - all configuration handled by Ansible
        assert "provision" not in config


class TestLimaVMCommands:
    """Tests for LimaVM command methods."""

    def test_start_calls_limactl_start(self, sample_config: Config) -> None:
        """start() calls limactl start with VM name."""
        vm = LimaVM(sample_config)

        with patch("subprocess.run") as mock_run:
            vm.start()

        mock_run.assert_called_once_with(
            ["limactl", "start", "--tty=false", "clauded-test1234"],
            check=True,
            stdin=subprocess.DEVNULL,
        )

    def test_stop_calls_limactl_stop(self, sample_config: Config) -> None:
        """stop() calls limactl stop with VM name."""
        vm = LimaVM(sample_config)

        with patch("subprocess.run") as mock_run:
            vm.stop()

        mock_run.assert_called_once_with(
            ["limactl", "stop", "clauded-test1234"],
            check=True,
        )

    def test_destroy_calls_limactl_delete(self, sample_config: Config) -> None:
        """destroy() calls limactl delete with -f flag."""
        vm = LimaVM(sample_config)

        with patch("subprocess.run") as mock_run:
            vm.destroy()

        mock_run.assert_called_once_with(
            ["limactl", "delete", "-f", "clauded-test1234"],
            check=True,
        )

    def test_shell_calls_limactl_shell_with_claude(self, sample_config: Config) -> None:
        """shell() calls limactl shell with claude command and skip permissions flag."""
        vm = LimaVM(sample_config)

        with patch("subprocess.run") as mock_run:
            vm.shell()

        # Last call should be the actual shell command (first call fetches metadata)
        mock_run.assert_called_with(
            [
                "limactl",
                "shell",
                "--workdir",
                "/path/to/project",
                "clauded-test1234",
                "bash",
                "-lic",
                "claude --dangerously-skip-permissions",
            ],
            env=None,
        )

    def test_shell_without_skip_permissions(self, sample_config: Config) -> None:
        """shell() omits skip permissions flag when disabled."""
        sample_config.claude_dangerously_skip_permissions = False
        vm = LimaVM(sample_config)

        with patch("subprocess.run") as mock_run:
            vm.shell()

        # Last call should be the actual shell command (first call fetches metadata)
        mock_run.assert_called_with(
            [
                "limactl",
                "shell",
                "--workdir",
                "/path/to/project",
                "clauded-test1234",
                "bash",
                "-lic",
                "claude",
            ],
            env=None,
        )

    def test_shell_forwards_env_vars_when_configured(
        self, sample_config: Config
    ) -> None:
        """shell() adds --preserve-env and LIMA_SHELLENV_ALLOW for forward_env."""
        sample_config.forward_env = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY"]
        vm = LimaVM(sample_config)

        fake_environ = {
            "PATH": "/usr/bin",
            "ANTHROPIC_API_KEY": "sk-ant-test",
            "OPENAI_API_KEY": "sk-test",
        }
        with (
            patch("subprocess.run") as mock_run,
            patch("clauded.lima.os.environ", fake_environ),
        ):
            vm.shell()

        call_args = mock_run.call_args
        cmd = call_args[0][0]
        env = call_args[1]["env"]
        assert "--preserve-env" in cmd
        assert env["LIMA_SHELLENV_ALLOW"] == "ANTHROPIC_API_KEY,OPENAI_API_KEY"

    def test_shell_skips_missing_env_vars(self, sample_config: Config) -> None:
        """shell() only forwards env vars that are set on the host."""
        sample_config.forward_env = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY"]
        vm = LimaVM(sample_config)

        # Only ANTHROPIC_API_KEY is set
        fake_environ = {"PATH": "/usr/bin", "ANTHROPIC_API_KEY": "sk-ant-test"}
        with (
            patch("subprocess.run") as mock_run,
            patch("clauded.lima.os.environ", fake_environ),
        ):
            vm.shell()

        call_args = mock_run.call_args
        cmd = call_args[0][0]
        env = call_args[1]["env"]
        assert "--preserve-env" in cmd
        assert env["LIMA_SHELLENV_ALLOW"] == "ANTHROPIC_API_KEY"

    def test_shell_no_preserve_env_when_no_vars_present(
        self, sample_config: Config
    ) -> None:
        """shell() omits --preserve-env when no configured vars are set on host."""
        sample_config.forward_env = ["OPENAI_API_KEY"]
        vm = LimaVM(sample_config)

        # OPENAI_API_KEY is not set
        fake_environ = {"PATH": "/usr/bin"}
        with (
            patch("subprocess.run") as mock_run,
            patch("clauded.lima.os.environ", fake_environ),
        ):
            vm.shell()

        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "--preserve-env" not in cmd
        assert call_args[1]["env"] is None


class TestLimaVMCountActiveSessions:
    """Tests for LimaVM.count_active_sessions()."""

    def test_counts_interactive_sessions_from_pts(self, sample_config: Config) -> None:
        """count_active_sessions counts pts devices for interactive sessions."""
        vm = LimaVM(sample_config)

        mock_result = MagicMock()
        mock_result.returncode = 0
        # 3 pts devices (0, 1, 2) means 3 interactive sessions
        mock_result.stdout = "0  1  2  ptmx"

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            count = vm.count_active_sessions()

        assert count == 3
        mock_run.assert_called_once_with(
            ["limactl", "shell", "clauded-test1234", "--", "ls", "/dev/pts"],
            capture_output=True,
            text=True,
            timeout=5,
        )

    def test_single_session_returns_one(self, sample_config: Config) -> None:
        """count_active_sessions returns 1 when one interactive session exists."""
        vm = LimaVM(sample_config)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "0  ptmx"

        with patch("subprocess.run", return_value=mock_result):
            count = vm.count_active_sessions()

        assert count == 1

    def test_returns_zero_when_no_pts_devices(self, sample_config: Config) -> None:
        """count_active_sessions returns 0 when no pts devices exist."""
        vm = LimaVM(sample_config)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "ptmx"  # Only the master device

        with patch("subprocess.run", return_value=mock_result):
            count = vm.count_active_sessions()

        assert count == 0

    def test_returns_zero_on_command_failure(self, sample_config: Config) -> None:
        """count_active_sessions returns 0 on command failure (fail-safe)."""
        vm = LimaVM(sample_config)

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            count = vm.count_active_sessions()

        assert count == 0

    def test_returns_zero_on_timeout(self, sample_config: Config) -> None:
        """count_active_sessions returns 0 on timeout (fail-safe)."""
        vm = LimaVM(sample_config)

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 5)):
            count = vm.count_active_sessions()

        assert count == 0


class TestLimaVMErrorHandling:
    """Tests for LimaVM subprocess error handling."""

    def test_create_handles_lima_not_installed(
        self, sample_config: Config, tmp_path: Path
    ) -> None:
        """create() exits with message when limactl is not found."""
        vm = LimaVM(sample_config)

        with (
            patch("clauded.lima.Path.home", return_value=tmp_path),
            patch("clauded.lima.getpass.getuser", return_value="testuser"),
            patch("subprocess.run", side_effect=FileNotFoundError()),
        ):
            with pytest.raises(SystemExit) as exc_info:
                vm.create()

        assert exc_info.value.code == 1

    def test_create_handles_subprocess_failure(
        self, sample_config: Config, tmp_path: Path
    ) -> None:
        """create() exits with message when limactl start fails."""
        vm = LimaVM(sample_config)

        with (
            patch("clauded.lima.Path.home", return_value=tmp_path),
            patch("clauded.lima.getpass.getuser", return_value="testuser"),
            patch(
                "subprocess.run",
                side_effect=subprocess.CalledProcessError(1, "limactl"),
            ),
        ):
            with pytest.raises(SystemExit) as exc_info:
                vm.create()

        assert exc_info.value.code == 1

    def test_start_handles_lima_not_installed(self, sample_config: Config) -> None:
        """start() exits with message when limactl is not found."""
        vm = LimaVM(sample_config)

        with patch("subprocess.run", side_effect=FileNotFoundError()):
            with pytest.raises(SystemExit) as exc_info:
                vm.start()

        assert exc_info.value.code == 1

    def test_start_handles_subprocess_failure(self, sample_config: Config) -> None:
        """start() exits with message when limactl start fails."""
        vm = LimaVM(sample_config)

        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "limactl"),
        ):
            with pytest.raises(SystemExit) as exc_info:
                vm.start()

        assert exc_info.value.code == 1

    def test_stop_handles_lima_not_installed(self, sample_config: Config) -> None:
        """stop() exits with message when limactl is not found."""
        vm = LimaVM(sample_config)

        with patch("subprocess.run", side_effect=FileNotFoundError()):
            with pytest.raises(SystemExit) as exc_info:
                vm.stop()

        assert exc_info.value.code == 1

    def test_stop_handles_subprocess_failure(self, sample_config: Config) -> None:
        """stop() exits with message when limactl stop fails."""
        vm = LimaVM(sample_config)

        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "limactl"),
        ):
            with pytest.raises(SystemExit) as exc_info:
                vm.stop()

        assert exc_info.value.code == 1

    def test_destroy_handles_lima_not_installed(self, sample_config: Config) -> None:
        """destroy() exits with message when limactl is not found."""
        vm = LimaVM(sample_config)

        with patch("subprocess.run", side_effect=FileNotFoundError()):
            with pytest.raises(SystemExit) as exc_info:
                vm.destroy()

        assert exc_info.value.code == 1

    def test_destroy_handles_subprocess_failure(self, sample_config: Config) -> None:
        """destroy() exits with message when limactl delete fails."""
        vm = LimaVM(sample_config)

        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "limactl"),
        ):
            with pytest.raises(SystemExit) as exc_info:
                vm.destroy()

        assert exc_info.value.code == 1


def _make_config(
    *,
    harness: str = "claude-code",
    skip_permissions: bool = True,
    frameworks: list[str] | None = None,
) -> Config:
    """Build a Config tailored for dispatcher tests."""
    return Config(
        vm_name="clauded-disp",
        cpus=1,
        memory="8GiB",
        disk="20GiB",
        mount_host="/path/to/project",
        mount_guest="/path/to/project",
        frameworks=frameworks or ["claude-code"],
        harness=harness,
        claude_dangerously_skip_permissions=skip_permissions,
    )


class TestLaunchSpec:
    """LaunchSpec dataclass invariants (frozen)."""

    def test_launch_spec_is_frozen(self) -> None:
        """LaunchSpec instances reject attribute reassignment."""
        spec = LaunchSpec(argv=["claude"], env={})
        with pytest.raises(dataclasses.FrozenInstanceError):
            spec.argv = ["codex"]  # type: ignore[misc]


class TestBuildLaunchSpec:
    """Pure dispatcher: branches on harness, applies per-harness flag rules."""

    def test_claude_code_with_skip(self) -> None:
        """AC-016: claude-code argv includes --dangerously-skip-permissions."""
        spec = _build_launch_spec(
            "claude-code",
            _make_config(harness="claude-code", skip_permissions=True),
        )
        assert spec.argv == ["claude", "--dangerously-skip-permissions"]
        assert spec.env == {}

    def test_claude_code_without_skip(self) -> None:
        """AC-016: claude-code omits the flag when skip=False."""
        spec = _build_launch_spec(
            "claude-code",
            _make_config(harness="claude-code", skip_permissions=False),
        )
        assert spec.argv == ["claude"]
        assert spec.env == {}

    def test_codex_with_skip(self) -> None:
        """AC-017: codex argv includes --dangerously-bypass-approvals-and-sandbox."""
        spec = _build_launch_spec(
            "codex",
            _make_config(harness="codex", skip_permissions=True),
        )
        assert spec.argv == ["codex", "--dangerously-bypass-approvals-and-sandbox"]
        assert spec.env == {}

    def test_codex_without_skip(self) -> None:
        """AC-017: codex omits the flag when skip=False."""
        spec = _build_launch_spec(
            "codex",
            _make_config(harness="codex", skip_permissions=False),
        )
        assert spec.argv == ["codex"]
        assert spec.env == {}

    def test_opencode_ignores_skip_true(self) -> None:
        """AC-018, FR7: opencode never gets --dangerously-* even when skip=True."""
        spec = _build_launch_spec(
            "opencode",
            _make_config(
                harness="opencode",
                skip_permissions=True,
                frameworks=["claude-code", "codex", "opencode"],
            ),
        )
        assert spec.argv == ["opencode"]
        assert all("--dangerously" not in tok for tok in spec.argv)
        assert spec.env == {}

    def test_opencode_ignores_skip_false(self) -> None:
        """AC-018: opencode is also flag-free when skip=False."""
        spec = _build_launch_spec(
            "opencode",
            _make_config(
                harness="opencode",
                skip_permissions=False,
                frameworks=["claude-code", "codex", "opencode"],
            ),
        )
        assert spec.argv == ["opencode"]
        assert spec.env == {}

    @pytest.mark.parametrize("harness", ["claude-code", "codex", "opencode"])
    def test_no_use_builtin_ripgrep_for_any_harness(self, harness: str) -> None:
        """Boy-scout: USE_BUILTIN_RIPGREP is never injected for any harness."""
        frameworks = (
            ["claude-code", "codex", "opencode"]
            if harness == "opencode"
            else ["claude-code"]
        )
        spec = _build_launch_spec(
            harness,
            _make_config(harness=harness, frameworks=frameworks),
        )
        assert "USE_BUILTIN_RIPGREP" not in spec.env
        assert all("USE_BUILTIN_RIPGREP" not in tok for tok in spec.argv)

    def test_unknown_harness_raises(self) -> None:
        """Defence-in-depth: dispatcher rejects out-of-allowlist values."""
        with pytest.raises(ValueError, match="harness"):
            _build_launch_spec(
                "gemini",
                _make_config(harness="claude-code"),
            )


class TestLimaVMShellHarnessDispatch:
    """Integration: LimaVM.shell() renders the dispatcher's LaunchSpec correctly."""

    def test_shell_launches_claude_when_harness_is_claude_code(self) -> None:
        """AC-016 integration: claude-code produces 'claude ...' bash-lic arg."""
        vm = LimaVM(_make_config(harness="claude-code", skip_permissions=True))

        with patch("subprocess.run") as mock_run:
            vm.shell()

        cmd_string = mock_run.call_args[0][0][-1]
        assert cmd_string == "claude --dangerously-skip-permissions"
        assert "USE_BUILTIN_RIPGREP" not in cmd_string

    def test_shell_launches_codex_when_harness_is_codex(self) -> None:
        """AC-017 integration: codex harness produces 'codex ...' bash-lic arg."""
        vm = LimaVM(
            _make_config(
                harness="codex",
                skip_permissions=True,
                frameworks=["claude-code", "codex"],
            )
        )

        with patch("subprocess.run") as mock_run:
            vm.shell()

        cmd_string = mock_run.call_args[0][0][-1]
        assert cmd_string == "codex --dangerously-bypass-approvals-and-sandbox"
        assert "USE_BUILTIN_RIPGREP" not in cmd_string

    def test_shell_launches_codex_without_flag_when_skip_disabled(self) -> None:
        """AC-017 integration: codex with skip=False is plain 'codex'."""
        vm = LimaVM(
            _make_config(
                harness="codex",
                skip_permissions=False,
                frameworks=["claude-code", "codex"],
            )
        )

        with patch("subprocess.run") as mock_run:
            vm.shell()

        cmd_string = mock_run.call_args[0][0][-1]
        assert cmd_string == "codex"

    def test_shell_launches_opencode_when_harness_is_opencode(self) -> None:
        """AC-018 integration: opencode is launched flag-free regardless of skip."""
        vm = LimaVM(
            _make_config(
                harness="opencode",
                skip_permissions=True,
                frameworks=["claude-code", "codex", "opencode"],
            )
        )

        with patch("subprocess.run") as mock_run:
            vm.shell()

        cmd_string = mock_run.call_args[0][0][-1]
        assert cmd_string == "opencode"
        assert "--dangerously" not in cmd_string
        assert "USE_BUILTIN_RIPGREP" not in cmd_string

    def test_shell_harness_override_takes_precedence(self) -> None:
        """AC-012 (lima half): per-instance override beats config.harness."""
        config = _make_config(
            harness="claude-code",
            frameworks=["claude-code", "codex", "opencode"],
        )
        vm = LimaVM(config, harness_override="opencode")

        with patch("subprocess.run") as mock_run:
            vm.shell()

        cmd_string = mock_run.call_args[0][0][-1]
        assert cmd_string == "opencode"

    def test_shell_no_use_builtin_ripgrep_in_assembled_command(self) -> None:
        """AC-016 boy-scout (integration): full bash-lic argument is RIPGREP-free."""
        for harness, frameworks in (
            ("claude-code", ["claude-code"]),
            ("codex", ["claude-code", "codex"]),
            ("opencode", ["claude-code", "codex", "opencode"]),
        ):
            vm = LimaVM(_make_config(harness=harness, frameworks=frameworks))
            with patch("subprocess.run") as mock_run:
                vm.shell()
            cmd_string = mock_run.call_args[0][0][-1]
            assert "USE_BUILTIN_RIPGREP" not in cmd_string

    def test_shell_default_harness_override_is_none(self) -> None:
        """LimaVM(config) without harness_override falls back to config.harness."""
        vm = LimaVM(_make_config(harness="codex", frameworks=["claude-code", "codex"]))
        with patch("subprocess.run") as mock_run:
            vm.shell()
        cmd_string = mock_run.call_args[0][0][-1]
        assert cmd_string.startswith("codex")


def _ccr_config(
    *,
    harness: str = "claude-code",
    enabled: bool = True,
    skip_permissions: bool = True,
    frameworks: list[str] | None = None,
) -> Config:
    """Build a Config for claude-code-router tests."""
    return Config(
        vm_name="clauded-ccr",
        cpus=1,
        memory="8GiB",
        disk="20GiB",
        mount_host="/test",
        mount_guest="/test",
        frameworks=frameworks or ["claude-code"],
        harness=harness,
        claude_dangerously_skip_permissions=skip_permissions,
        ccr_enabled=enabled,
    )


class TestCCRLima:
    """LaunchSpec wrapping for the claude-code-router proxy."""

    def test_argv_prepended_when_enabled(self) -> None:
        spec = _build_launch_spec(
            "claude-code", _ccr_config(harness="claude-code", enabled=True)
        )
        assert spec.argv[0] == "clauded-ccr-with"
        assert spec.argv[1] == "claude"

    def test_env_contains_base_url(self) -> None:
        spec = _build_launch_spec(
            "claude-code", _ccr_config(harness="claude-code", enabled=True)
        )
        assert spec.env["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:3456"

    def test_env_no_auth_token_override(self) -> None:
        spec = _build_launch_spec(
            "claude-code", _ccr_config(harness="claude-code", enabled=True)
        )
        assert "ANTHROPIC_AUTH_TOKEN" not in spec.env

    def test_shell_renders_env_and_wrapper(self) -> None:
        config = _ccr_config(harness="claude-code", enabled=True, skip_permissions=True)
        vm = LimaVM(config)
        with patch("subprocess.run") as mock_run:
            vm.shell()
        cmd_string = mock_run.call_args[0][0][-1]
        assert "ANTHROPIC_BASE_URL=http://127.0.0.1:3456" in cmd_string
        assert "clauded-ccr-with" in cmd_string
        assert "claude" in cmd_string

    @pytest.mark.parametrize("harness", ["codex", "opencode"])
    def test_other_harnesses_not_wrapped(self, harness: str) -> None:
        frameworks = (
            ["claude-code", "codex", "opencode"]
            if harness == "opencode"
            else ["claude-code", "codex"]
        )
        spec = _build_launch_spec(
            harness,
            _ccr_config(harness=harness, enabled=True, frameworks=frameworks),
        )
        assert spec.env == {}
        assert "clauded-ccr-with" not in spec.argv

    def test_feature_off_no_env_no_wrapper(self) -> None:
        spec = _build_launch_spec(
            "claude-code", _ccr_config(harness="claude-code", enabled=False)
        )
        assert spec.env == {}
        assert spec.argv[0] != "clauded-ccr-with"
