# clauded Specification

## Purpose & Scope

`clauded` is a CLI tool for macOS that creates isolated, per-project Linux VMs using Lima (Linux Machines) with automatic environment provisioning via Ansible. It enables developers to define their development stack declaratively in a `.clauded.yaml` configuration file, ensuring reproducible and isolated environments across team members.

**In Scope:**
- Per-project VM lifecycle management (create, start, stop, destroy)
- Interactive wizard-based environment configuration
- Automatic project detection (languages, versions, frameworks, databases)
- Declarative configuration via `.clauded.yaml`
- Automatic provisioning of Python, Node.js, Java, Kotlin, Rust, Go, databases, and developer tools
- Project directory mounting at matching path in VMs
- Reprovisionable environments for stack updates
- Customizable VM resources (CPU, memory, disk)

**Out of Scope:**
- Remote VM provisioning (cloud providers)
- Multi-VM orchestration
- Non-macOS host support
- x86_64 architecture support
- Container orchestration beyond Docker installation
- VM snapshots or backups
- GUI interfaces

## Architecture Overview

### Component Model

```
┌─────────────────────────────────────────────────────┐
│  CLI (Click Framework)                              │
│  - Command routing (default, --stop, --destroy,    │
│    --reprovision)                                   │
│  - Entry point: clauded.cli:main                    │
└────────────────┬────────────────────────────────────┘
                 │
                 ├─→ Config Module
                 │   ├─ Load/save .clauded.yaml (YAML)
                 │   ├─ Interactive wizard (questionary)
                 │   └─ VM name generation (MD5 hash)
                 │
                 ├─→ LimaVM Module
                 │   ├─ Check VM existence (limactl list)
                 │   ├─ Create VM (generate Lima YAML, limactl start)
                 │   ├─ Lifecycle: start/stop/destroy
                 │   └─ Shell access (limactl shell)
                 │
                 └─→ Provisioner Module
                     ├─ Dynamic role selection based on config
                     ├─ Generate Ansible playbook YAML
                     ├─ Generate Ansible inventory INI
                     ├─ Generate ansible.cfg
                     └─ Execute ansible-playbook via SSH
```

### Technology Stack

- **Language**: Python 3.12+
- **CLI Framework**: Click 8.1+
- **Interactive UI**: Questionary 2.0+
- **Configuration**: PyYAML 6.0+
- **VM Management**: Lima (limactl commands via subprocess)
- **Provisioning**: Ansible 13.2+ (ansible-playbook via subprocess)
- **Base OS**: Alpine Linux 3.21 (cloud image)
- **Hypervisor**: Apple Virtualization Framework (vz)
- **Filesystem**: virtiofs for host-guest mounting

### Module Responsibilities

**`cli.py`**
- Parse command-line options
- Orchestrate workflow based on flags (--destroy, --stop, --reprovision)
- Handle VM state transitions (missing → create, stopped → start, running → shell)

**`config.py`**
- Define `Config` dataclass with VM settings and environment selections
- Load/save `.clauded.yaml` using PyYAML
- Run interactive wizard via `wizard.py` when config missing
- Generate unique VM names from project path (MD5 hash, first 8 chars)
- Validate config schema version on load; reject incompatible versions
- Validate mount_guest matches mount_host; auto-correct with warning if different
- Support config migration for future schema versions

**`lima.py`**
- Manage Lima VM lifecycle via `limactl` subprocess calls
- Generate Lima YAML configuration with VM resources, Alpine image, and mounts
- Check VM existence and running status
- Provide SSH config path for Ansible connectivity

**`provisioner.py`**
- Select Ansible roles based on config environment selections
- Generate dynamic Ansible playbook YAML with role list and variables
- Generate Ansible inventory INI with Lima SSH connection details
- Generate ansible.cfg with host_key_checking=False and pipelining=True
- Execute ansible-playbook with generated files in temp directory

**`constants.py`**
- Shared configuration constants (language versions, display names, package manager labels)
- `confidence_marker()` helper for consistent confidence level display across CLI output

**`wizard.py`**
- Interactive questionary prompts for Python/Node.js/Java/Kotlin/Rust/Go versions
- Multi-select for tools (docker, git, aws-cli, gh, gradle)
- Multi-select for databases (postgresql, redis, mysql, sqlite)
- Multi-select for frameworks (claude-code, playwright)
- Optional VM resource customization
- Return populated `Config` object
- Non-interactive terminal detection: Exit with error if stdin is not a TTY
- Keyboard interrupt handling: Clean exit with "Setup cancelled." message
- Questionary None handling: Treat None returns as user cancellation

**`detect/` module**
- Automatic language detection using GitHub Linguist data
- Version detection from manifest files (.python-version, package.json, go.mod, etc.)
- Framework and tool detection from dependency manifests
- Database detection from docker-compose, environment files, and project manifests (package.json, database files)
- Pre-population of wizard defaults based on detection results
- Bounded file scanning: Limit file scanning to 50,000 files maximum to prevent memory/time issues on monorepos. When limit reached, continue with partial results and display warning

## Core Functionality

### 1. VM Lifecycle Management

**VM Creation**
- Input: `Config` object with VM settings and environment selections
- Process:
  1. Generate Lima YAML config with vmType=vz, Alpine Linux image, CPU/memory/disk settings
  2. Configure virtiofs mount: host project path → same path in guest
  3. Execute `limactl start <vm-name> --tty=false <lima-config-path>`
- Output: Running Lima VM with project directory mounted

**VM Starting**
- Input: VM name
- Process: Execute `limactl start <vm-name>`
- Output: Running VM

**VM Stopping**
- Input: VM name
- Process: Execute `limactl stop <vm-name>`
- Output: Stopped VM (persistent disk preserved)

**VM Destruction**
- Input: VM name
- Process: Execute `limactl delete <vm-name> --force`
- Output: VM and disk removed

**Shell Access**
- Input: VM name
- Process: Execute `limactl shell <vm-name> --workdir <project-path>`
- Output: Interactive shell session at project directory

### 2. Configuration Management

**Config Schema (.clauded.yaml)**
```yaml
version: "1"
vm:
  name: clauded-{8-char-hash}
  cpus: <int>
  memory: <size>GiB
  disk: <size>GiB
  image: <url>  # optional, defaults to Alpine 3.21 cloud image
mount:
  host: <absolute-path>
  guest: <absolute-path>  # same as host
environment:
  python: "<version>|null"
  node: "<version>|null"
  java: "<version>|null"
  kotlin: "<version>|null"
  rust: "<version>|null"
  go: "<version>|null"
  tools:
    - docker
    - git
    - aws-cli  # optional
    - gh       # optional
    - gradle   # optional
  databases:
    - postgresql  # optional
    - redis       # optional
    - mysql       # optional
  frameworks:
    - claude-code  # optional
    - playwright   # optional
```

**Config Generation**
- Wizard prompts or programmatic creation
- VM name: SHA256(project_path)[:6] prefixed with "clauded-{sanitized_project_name}-"
- Defaults: 4 CPUs, 8GiB memory, 20GiB disk
- Host mount: absolute path to current project directory
- Guest mount: same as host mount (ensures unique Claude Code sessions per project)

**Config Persistence**
- Save: YAML serialization to `.clauded.yaml` in project root
- Load: YAML deserialization from `.clauded.yaml`

**Config Validation**
- Schema version validation on load:
  - Version "1" (current): proceed normally
  - Missing version: treat as "1", log warning
  - Higher version than supported: exit with error indicating upgrade needed
  - Unrecognized version format: exit with error
- Mount path validation on load:
  - If mount_guest differs from mount_host: log warning, auto-correct mount_guest to match mount_host
  - Ensures consistent path mapping between host and VM
- Config migration support for future schema upgrades (currently no-op for v1)

### 3. Provisioning System

**Role Selection Logic**
- Always include: `common` role (base packages)
- Conditional roles based on config:
  - `python` if config.environment.python is set
  - `node` if config.environment.node is set
  - `java` if config.environment.java is set
  - `kotlin` if config.environment.kotlin is set
  - `rust` if config.environment.rust is set
  - `go` if config.environment.go is set
  - `docker` if "docker" in config.environment.tools
  - `aws_cli` if "aws-cli" in config.environment.tools
  - `gh` if "gh" in config.environment.tools
  - `postgresql` if "postgresql" in config.environment.databases
  - `redis` if "redis" in config.environment.databases
  - `mysql` if "mysql" in config.environment.databases
  - `sqlite` if "sqlite" in config.environment.databases
  - `playwright` if "playwright" in config.environment.frameworks
  - `claude_code` if "claude-code" in config.environment.frameworks

**Auto-bundled Roles**
- When `python` is selected: `uv` and `poetry` are automatically included
- When `java` or `kotlin` is selected: `maven` and `gradle` are automatically included
- When `playwright` is selected: `node` is automatically included (npm dependency)

**Ansible Roles**

| Role | Purpose | Key Tasks |
|------|---------|-----------|
| `common` | Base system packages | ca-certificates, coreutils, curl, git, gnupg, alpine-sdk, bash |
| `python` | Python version installation | apk python3, python3-dev, py3-pip |
| `uv` | Python package manager | uv installation via pipx (auto-bundled with Python) |
| `poetry` | Python dependency manager | poetry installation via pipx (auto-bundled with Python) |
| `node` | Node.js installation | apk nodejs-current/npm from community repository |
| `java` | Java version installation | apk openjdk{{ java_version }} |
| `kotlin` | Kotlin compiler installation | Download from GitHub releases, kotlin{{ kotlin_version }} |
| `maven` | Java/Kotlin build tool | Maven binary installation (auto-bundled with Java/Kotlin) |
| `rust` | Rust toolchain installation | rustup, rustc/cargo {{ rust_version }} |
| `go` | Go version installation | Download from go.dev, go{{ go_version }} |
| `docker` | Docker setup | apk docker, OpenRC service, user group |
| `postgresql` | PostgreSQL installation | postgresql, postgresql-contrib, postgresql-dev, OpenRC service |
| `redis` | Redis installation | redis, OpenRC service, port 6379 |
| `mysql` | MySQL installation | mariadb (MySQL-compatible), OpenRC service, port 3306 |
| `sqlite` | SQLite installation | sqlite package via apk, no service management (file-based) |
| `aws_cli` | AWS CLI v2 | Download aarch64 zip, unzip, install |
| `gh` | GitHub CLI | apk package installation |
| `gradle` | Gradle build tool | Download latest, install to /opt/gradle (auto-bundled with Java/Kotlin) |
| `playwright` | Playwright testing | npm install -g playwright, playwright install |
| `claude_code` | Claude Code CLI | Native installer (claude.ai/install.sh), musl deps |

**Playbook Generation**
```yaml
- name: Provision clauded VM
  hosts: all
  become: true
  vars:
    python_version: "{{ config.environment.python }}"
    node_version: "{{ config.environment.node }}"
    java_version: "{{ config.environment.java }}"
    kotlin_version: "{{ config.environment.kotlin }}"
    rust_version: "{{ config.environment.rust }}"
    go_version: "{{ config.environment.go }}"
  roles:
    - common
    - python  # conditional
    - node    # conditional
    - java    # conditional
    - kotlin  # conditional
    - rust    # conditional
    - go      # conditional
    # ... other roles based on config
```

**Inventory Generation**
```ini
[lima]
lima-{vm-name} ansible_connection=ssh ansible_user={user}

[all:vars]
ansible_ssh_common_args=-F {lima-ssh-config-path}
```

**Provisioning Execution**
- Generate playbook, inventory, and ansible.cfg in temp directory
- Execute: `ansible-playbook -i <inventory> <playbook> --limit lima-{vm-name}`
- Cleanup temp files after execution

### 4. CLI Workflows

**Default Workflow (no flags)**
1. Run project detection (unless `--no-detect` flag provided)
2. Check if `.clauded.yaml` exists
   - If missing: Run wizard with detection results, generate config, save to `.clauded.yaml`
3. Check if VM exists (via `limactl list`)
   - If missing: Create VM, provision with Ansible
4. Check if VM is running
   - If stopped: Start VM
5. Enter shell at project directory

**--destroy Workflow**
1. Check if VM exists
   - If exists: Execute `limactl delete <vm-name> --force`
2. Prompt user: "Remove .clauded.yaml?"
   - If yes: Delete `.clauded.yaml`

**--stop Workflow**
1. Check if VM is running
   - If running: Execute `limactl stop <vm-name>`
2. Exit (do not enter shell)

**--reprovision Workflow**
1. Ensure VM is running
   - If stopped: Start VM first
2. Load `.clauded.yaml`
3. Re-run Ansible provisioning with current config
4. Enter shell

**--edit Workflow**
1. Load existing `.clauded.yaml`
2. Run wizard with current config values pre-selected
3. Save updated config
4. Re-run Ansible provisioning
5. Enter shell

**--detect Workflow**
1. Run project detection
2. Output detection results (languages, versions, frameworks, databases)
3. Exit without creating VM or running wizard

**--no-detect Flag**
- Skip automatic project detection
- Use static defaults in wizard
- Can be combined with other workflows

## Security Model

### Trust Boundaries

1. **Host ↔ VM**: Host trusts VM (same user owns both)
2. **Ansible Connection**: SSH-based, using Lima's generated SSH config
3. **VM Internet Access**: VM has full internet access via Lima networking

### Security Constraints

- VMs run under host user's privileges (not root on host)
- Ansible playbooks run with `become: true` (root inside VM)
- SSH host key checking disabled for Lima VMs (ansible.cfg)
- No authentication required for VM access (SSH key-based via Lima)
- VMs are local-only (not exposed to network)
- Environment variable sanitization: The provisioner passes only allowlisted environment variables to `ansible-playbook`, preventing leakage of sensitive variables (AWS credentials, API keys, database passwords) into logs or the VM. Allowlisted variables include: PATH, HOME, USER, LOGNAME, locale settings (LANG, LC_*), TERM, SSH_AUTH_SOCK, temp directories (TMPDIR, TEMP, TMP), and XDG directories.

### Sensitive Data Handling

- `.clauded.yaml` may be committed to version control (no secrets)
- VM disk is local and persists between starts
- Lima SSH keys stored in `~/.lima/<vm-name>/`

## Non-Functional Requirements

### Performance

- VM creation: ~1-3 minutes (Alpine image download + provisioning)
- VM start: ~5-15 seconds
- VM stop: ~2-5 seconds
- Shell entry: <1 second for running VM

### Reliability

- Idempotent Ansible playbooks (safe to re-run)
- VM name determinism (same project → same VM name)
- Non-interactive terminal detection: CLI refuses to launch wizard when stdin is not a TTY, preventing hangs in CI/CD or piped input contexts
- Wizard cancellation handling: KeyboardInterrupt (CTRL+C) cleanly exits without leaving partial config files
- Specific exception handling: Use specific exception types (OSError, YAMLError, JSONDecodeError, etc.) instead of broad catches. Critical exceptions (KeyboardInterrupt, SystemExit) always propagate. Caught exceptions logged at DEBUG level for diagnosis with `--debug` flag.
- Graceful error handling for missing dependencies and subprocess failures:
  - Lima not installed → "Lima is not installed. Install with: brew install lima"
  - VM creation failure → "VM creation failed (exit code N). Check Lima logs: ~/.lima/{vm-name}/ha.stderr.log"
  - VM start failure → "Failed to start VM. Is it in a valid state? Try: clauded --destroy"
  - VM stop failure → "Failed to stop VM. VM may not be running."
  - Provisioning failure → Multi-line message with exit code and three recovery options:
    - Retry provisioning: `clauded --reprovision`
    - Debug in the VM: `limactl shell {vm-name}`
    - Start fresh: `clauded --destroy && clauded`
    Note: VM remains running after provisioning failure to preserve partial state
- All errors exit with code 1 and output to stderr

### Compatibility

- **OS**: macOS (Lima requirement)
- **Architecture**: ARM64/aarch64 (Apple Silicon)
- **Python**: 3.12+
- **Lima**: Compatible with latest Lima releases
- **Ansible**: 13.2+

### Usability

- Interactive wizard for new users
- Sensible defaults (4 CPU, 8GB RAM, Python 3.12, Node 20)
- Clear error messages for missing prerequisites
- Help text via `make help` and CLI `--help`

## Data & Interfaces

### Configuration File Format

**File**: `.clauded.yaml` (YAML format)
**Location**: Project root directory
**Schema**: See Configuration Management section

### CLI Interface

**Command**: `clauded`
**Options**:
- `--version`: Display version and exit
- `--destroy`: Destroy VM and optionally remove config
- `--stop`: Stop VM without entering shell
- `--reprovision`: Re-run Ansible provisioning
- `--edit`: Edit configuration and reprovision
- `--detect`: Run detection only and output results
- `--no-detect`: Skip automatic project detection
- `--debug`: Enable debug logging for detection

**Exit Codes**:
- 0: Success
- Non-zero: Error (subprocess failure, missing config, etc.)

### External Dependencies

**Required**:
- Lima (`limactl` in PATH)
- Ansible (`ansible-playbook` in PATH via uv)
- Internet connection (for Alpine image download and package installation)

**Optional**:
- Git (for version control of `.clauded.yaml`)
- uv package manager (for development)

## State Machine

### VM States

```
[Non-existent] --create--> [Running] --provision--> [Provisioned]
                              |
                              ├--stop--> [Stopped]
                              |
                              └--destroy--> [Non-existent]

[Stopped] --start--> [Running]
[Running] --reprovision--> [Provisioned]
```

### Config States

```
[Missing] --wizard--> [Exists]
[Exists] --edit--> [Modified]
[Modified] --reprovision--> [Applied to VM]
```

## Constraints & Assumptions

### Constraints

1. **Single VM per project**: One `.clauded.yaml` → one VM
2. **macOS-only**: Lima is macOS-specific
3. **ARM64-only**: Hardcoded architecture in Lima config
4. **Local VMs only**: No remote provisioning
5. **Alpine Linux**: Hardcoded base image
6. **No VM migration**: VMs are tied to host machine

### Assumptions

1. Lima is installed and functional
2. User has sufficient disk space for VMs (20GB+ per VM)
3. User has internet access for image downloads and package installation
4. Project directory is on local filesystem (not network mount)
5. User has permissions to execute `limactl` and `ansible-playbook`

## Acceptance Criteria

### Functional

- ✓ Create VM from wizard-generated config
- ✓ Create VM from existing `.clauded.yaml`
- ✓ Start stopped VM
- ✓ Stop running VM
- ✓ Destroy VM and optionally remove config
- ✓ Provision VM with selected tools/databases/frameworks
- ✓ Reprovision existing VM after config changes
- ✓ Enter interactive shell at project directory
- ✓ Mount project directory read-write in VM
- ✓ Install Python version specified in config
- ✓ Install Node.js version specified in config
- ✓ Install Java version specified in config
- ✓ Install Kotlin version specified in config
- ✓ Install Rust version specified in config
- ✓ Install Go version specified in config
- ✓ Support all 21 Ansible roles
- ✓ Detect project languages and versions from files
- ✓ Pre-populate wizard defaults based on detection

### Non-Functional

- ✓ VM creation completes within 5 minutes on standard network
- ✓ Ansible provisioning is idempotent (re-running safe)
- ✓ Config file is valid YAML and human-readable
- ✓ CLI provides clear error messages for common failures
- ✓ Test coverage >80% for core modules
- ✓ Type checking passes with strict mypy
- ✓ Linting passes with ruff

## Extension Points

Future enhancements may include:

1. **Cloud VM Support**: Extend provisioning to AWS/GCP/Azure
2. **Multi-VM Orchestration**: Docker Compose-like multi-VM setups
3. **VM Snapshots**: Save/restore VM states
4. **Template Library**: Pre-configured stacks (Django, Express, Rails)
5. **Team Sharing**: Remote VM provisioning for distributed teams
6. **Resource Monitoring**: Track CPU/memory usage per VM
7. **x86_64 Support**: Cross-architecture compatibility
8. **Non-interactive Mode**: CI/CD integration for automated testing
