# Architecture Documentation

## Overview

`clauded` is a Python CLI application that orchestrates Lima VM creation and Ansible provisioning to provide isolated, reproducible development environments. The architecture follows a modular design with clear separation of concerns across five core modules.

## System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        Host Machine (macOS)                   │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  clauded CLI (Python 3.12+)                            │  │
│  │                                                         │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐             │  │
│  │  │   cli    │  │  config  │  │  wizard  │             │  │
│  │  │ (Click)  │─>│ (YAML)   │<─│(questio- │             │  │
│  │  │          │  │          │  │  nary)   │             │  │
│  │  └──────────┘  └──────────┘  └──────────┘             │  │
│  │       │             │                                   │  │
│  │       v             v                                   │  │
│  │  ┌──────────┐  ┌──────────┐                            │  │
│  │  │   lima   │  │provision │                            │  │
│  │  │ (limactl)│  │ (Ansible)│                            │  │
│  │  └──────────┘  └──────────┘                            │  │
│  │       │             │                                   │  │
│  └───────┼─────────────┼───────────────────────────────────┘  │
│          │             │                                       │
│          │             │ SSH (Lima's SSH config)               │
│          │             │                                       │
│          v             v                                       │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  Lima VM (Alpine Linux 3.21 / Apple Virtualization)  │    │
│  │                                                       │    │
│  │  <project-path> (virtiofs mount from host)            │    │
│  │                                                       │    │
│  │  Provisioned Software:                                │    │
│  │  - Python 3.x, Node.js                                │    │
│  │  - Docker, PostgreSQL, Redis, MySQL                   │    │
│  │  - AWS CLI, GitHub CLI, Playwright, Claude Code       │    │
│  └───────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

## Module Design

### 1. cli.py - Command Router

**Responsibility**: Parse CLI options and orchestrate workflow

**Dependencies**:
- Click (CLI framework)
- config module (Config class)
- lima module (LimaVM class)
- provisioner module (Provisioner class)

**Key Functions**:
- `main()`: CLI entry point registered in pyproject.toml
- Command option parsing (--destroy, --stop, --reprovision)
- Workflow orchestration based on VM state

**State Transitions**:
```
User runs `clauded` →
  Config missing? → wizard → save config
  VM missing? → create VM → provision
  VM stopped? → start VM
  → enter shell

User runs `clauded --destroy` →
  VM exists? → destroy VM
  → prompt to delete config

User runs `clauded --stop` →
  VM running? → stop VM

User runs `clauded --reprovision` →
  VM stopped? → start VM
  → run provisioner → enter shell
```

**Implementation Pattern**:
```python
@click.command()
@click.option('--destroy', is_flag=True)
@click.option('--stop', is_flag=True)
@click.option('--reprovision', is_flag=True)
def main(destroy: bool, stop: bool, reprovision: bool) -> None:
    # Load or create config
    # Create LimaVM instance
    # Handle destroy/stop/reprovision
    # Default: start VM and enter shell
```

### 2. config.py - Configuration Management

**Responsibility**: Load, save, and generate `.clauded.yaml` configurations

**Dependencies**:
- PyYAML (YAML parsing)
- wizard module (interactive setup)
- hashlib (VM name generation)

**Data Model**:
```python
@dataclass
class Config:
    version: str
    vm_name: str
    vm_cpus: int
    vm_memory: str
    vm_disk: str
    mount_host: str
    mount_guest: str
    python_version: str | None
    node_version: str | None
    tools: list[str]
    databases: list[str]
    frameworks: list[str]
```

**Key Methods**:
- `from_wizard()`: Create config from interactive wizard
- `load(path)`: Parse YAML file into Config object
- `save(path)`: Serialize Config to YAML file
- `_generate_vm_name(project_path)`: MD5 hash-based naming

**VM Naming Logic**:
```python
def _generate_vm_name(project_path: str) -> str:
    hash_obj = hashlib.md5(project_path.encode())
    return f"clauded-{hash_obj.hexdigest()[:8]}"
```

### 3. wizard.py - Interactive Setup

**Responsibility**: Guide users through environment configuration

**Dependencies**:
- questionary (terminal UI)
- config module (Config class)

**Prompt Flow**:
1. Python version: Select from 3.12, 3.11, 3.10, None
2. Node.js version: Select from 22, 20, 18, None
3. Tools: Multi-select from docker, git, aws-cli, gh
4. Databases: Multi-select from postgresql, redis, mysql
5. Frameworks: Multi-select from claude-code, playwright
6. Resources: Optional customization of CPU/memory/disk

**UI Pattern**:
```python
def run() -> Config:
    python_version = questionary.select(
        "Select Python version:",
        choices=["3.12", "3.11", "3.10", "None"]
    ).ask()

    tools = questionary.checkbox(
        "Select tools:",
        choices=["docker", "git", "aws-cli", "gh"],
        default=["docker", "git"]
    ).ask()

    # ... more prompts

    return Config(...)
```

### 4. lima.py - VM Lifecycle Manager

**Responsibility**: Interact with Lima CLI to manage VM lifecycle

**Dependencies**:
- subprocess (execute limactl commands)
- tempfile (Lima config generation)
- PyYAML (Lima config serialization)

**Key Methods**:

**VM State Queries**:
```python
def exists(self) -> bool:
    # Run: limactl list --quiet
    # Parse output for VM name

def is_running(self) -> bool:
    # Run: limactl list --format '{{.Status}}' <vm-name>
    # Check if status is "Running"
```

**VM Operations**:
```python
def create(self) -> None:
    # Generate Lima YAML config
    # Run: limactl start <vm-name> --tty=false <config-path>

def start(self) -> None:
    # Run: limactl start <vm-name>

def stop(self) -> None:
    # Run: limactl stop <vm-name>

def destroy(self) -> None:
    # Run: limactl delete <vm-name> --force

def shell(self) -> None:
    # Run: limactl shell <vm-name> --workdir <project-path>
```

**Lima Config Generation**:
```python
def _generate_lima_config(self) -> dict[str, Any]:
    return {
        "vmType": "vz",  # Apple Virtualization Framework
        "os": "linux",
        "arch": "aarch64",
        "images": [{
            "location": "https://dl-cdn.alpinelinux.org/alpine/v3.21/releases/cloud/nocloud_alpine-3.21.0-aarch64-uefi-cloudinit-r0.qcow2"
        }],
        "cpus": self.config.vm_cpus,
        "memory": self.config.vm_memory,
        "disk": self.config.vm_disk,
        "mountType": "virtiofs",
        "mounts": [{
            "location": self.config.mount_host,
            "mountPoint": self.config.mount_guest,
            "writable": True
        }]
    }
```

### 5. provisioner.py - Ansible Orchestrator

**Responsibility**: Generate and execute Ansible playbooks

**Dependencies**:
- subprocess (execute ansible-playbook)
- tempfile (playbook/inventory generation)
- PyYAML (playbook serialization)

**Provisioning Workflow**:
```
1. Determine roles based on config
2. Generate playbook YAML in temp directory
3. Generate inventory INI in temp directory
4. Generate ansible.cfg in temp directory
5. Execute ansible-playbook with Lima SSH config
6. Cleanup temp files
```

**Role Selection Logic**:
```python
def _get_roles(self) -> list[str]:
    roles = ["common"]  # Always included

    if self.config.python_version:
        roles.append("python")
    if self.config.node_version:
        roles.append("node")
    if "docker" in self.config.tools:
        roles.append("docker")
    if "aws-cli" in self.config.tools:
        roles.append("aws_cli")
    if "gh" in self.config.tools:
        roles.append("gh")
    if "postgresql" in self.config.databases:
        roles.append("postgresql")
    if "redis" in self.config.databases:
        roles.append("redis")
    if "mysql" in self.config.databases:
        roles.append("mysql")
    if "playwright" in self.config.frameworks:
        roles.append("playwright")
    if "claude-code" in self.config.frameworks:
        roles.append("claude_code")

    return roles
```

**Playbook Structure**:
```yaml
- name: Provision clauded VM
  hosts: vm
  become: true
  vars:
    python_version: "{{ config.python_version }}"
    node_version: "{{ config.node_version }}"
  roles:
    - common
    - python
    - node
    # ... conditional roles
```

**Inventory Format**:
```ini
[vm]
{vm-name} ansible_host=lima-{vm-name} ansible_connection=ssh ansible_user={user}
```

**Ansible Config**:
```ini
[defaults]
host_key_checking = False
retry_files_enabled = False
pipelining = True
roles_path = {roles-directory-path}
```

## Data Flow

### 1. VM Creation Flow

```
User runs `clauded`
    ↓
cli.py: Check for .clauded.yaml
    ↓ (missing)
wizard.py: Run interactive prompts
    ↓
config.py: Generate Config object
    ↓
config.py: Save to .clauded.yaml
    ↓
cli.py: Create LimaVM instance
    ↓
lima.py: Generate Lima config YAML
    ↓
lima.py: Execute limactl start
    ↓
provisioner.py: Determine required roles
    ↓
provisioner.py: Generate playbook/inventory/config
    ↓
provisioner.py: Execute ansible-playbook
    ↓
lima.py: Enter shell (limactl shell)
```

### 2. Reprovisioning Flow

```
User runs `clauded --reprovision`
    ↓
cli.py: Load .clauded.yaml
    ↓
cli.py: Check if VM is running
    ↓ (stopped)
lima.py: Start VM
    ↓
provisioner.py: Re-run Ansible with current config
    ↓
lima.py: Enter shell
```

### 3. Config-to-VM Mapping

```
.clauded.yaml
    ↓
Config object (config.py)
    ↓
    ├─> Lima config (lima.py)
    │   - VM resources (CPU, memory, disk)
    │   - Mount configuration
    │
    └─> Ansible playbook (provisioner.py)
        - Role selection
        - Variable passing (python_version, node_version)
```

## Design Patterns

### 1. Separation of Concerns

Each module has a single, well-defined responsibility:
- `cli`: User interaction and workflow orchestration
- `config`: Configuration persistence and generation
- `wizard`: Interactive data collection
- `lima`: VM lifecycle operations
- `provisioner`: Environment provisioning

### 2. Subprocess Execution Pattern

External tools (limactl, ansible-playbook) are invoked via subprocess:
```python
subprocess.run(
    ["limactl", "start", vm_name],
    check=True,
    capture_output=True
)
```

**Rationale**: Lima and Ansible have no Python bindings; subprocess is the standard integration method.

### 3. Temporary File Management

Ansible files (playbook, inventory, config) are generated in temp directories:
```python
with tempfile.TemporaryDirectory() as tmpdir:
    playbook_path = Path(tmpdir) / "playbook.yml"
    # ... generate files
    # ... execute ansible-playbook
    # Automatic cleanup on context exit
```

**Rationale**: Avoid polluting project directory with generated files.

### 4. Idempotent Operations

All Ansible roles are idempotent:
- Package installation checks if already installed
- Service enabling checks if already enabled
- Configuration changes are conditional

**Rationale**: Supports `--reprovision` safely without side effects.

### 5. Deterministic VM Naming

VM names are MD5 hashes of project paths:
```python
vm_name = f"clauded-{md5(project_path)[:8]}"
```

**Rationale**: Prevents naming conflicts across multiple projects while maintaining consistency.

## Component Interactions

### CLI ↔ Config
- CLI loads config via `Config.load()`
- CLI creates config via `Config.from_wizard()`
- CLI saves config via `config.save()`

### CLI ↔ LimaVM
- CLI checks VM state via `vm.exists()` and `vm.is_running()`
- CLI creates VM via `vm.create()`
- CLI manages lifecycle via `vm.start()`, `vm.stop()`, `vm.destroy()`
- CLI enters shell via `vm.shell()`

### CLI ↔ Provisioner
- CLI provisions VM via `provisioner.run()`
- CLI re-provisions via same `provisioner.run()` (idempotent)

### Config ↔ Wizard
- Config delegates to wizard via `Config.from_wizard()`
- Wizard returns populated Config object

### LimaVM ↔ Provisioner
- Provisioner uses `vm.get_ssh_config_path()` for Ansible SSH connection
- Provisioner assumes VM is running (CLI ensures this)

### Provisioner ↔ Ansible Roles
- Provisioner selects roles based on Config
- Provisioner passes variables (python_version, node_version) to roles
- Roles are located in `src/clauded/roles/`

## Testing Architecture

### Test Organization

```
tests/
├── test_cli.py          # CLI option parsing, workflow logic
├── test_config.py       # Config serialization, VM name generation
├── test_lima.py         # Lima config generation, command execution
├── test_provisioner.py  # Role selection, playbook generation
└── __init__.py
```

### Mocking Strategy

**External Dependencies Mocked**:
- `subprocess.run` (limactl, ansible-playbook commands)
- File I/O (`open`, `Path.write_text`)
- `questionary` prompts (return predefined answers)

**Rationale**: Tests run without requiring Lima installation or actual VMs.

**Example**:
```python
@patch('subprocess.run')
def test_create_vm(mock_run):
    vm = LimaVM(config)
    vm.create()
    mock_run.assert_called_once_with(
        ['limactl', 'start', 'clauded-12345678', ...],
        check=True
    )
```

### Test Coverage

- **cli.py**: ~80% (all workflows, error handling)
- **config.py**: ~95% (all methods, edge cases)
- **lima.py**: ~85% (all operations, config generation)
- **provisioner.py**: ~90% (all roles, playbook generation)
- **wizard.py**: ~70% (prompt flow, defaults)

## Deployment Architecture

### Package Structure

```
clauded-0.1.0-py3-none-any.whl
├── clauded/
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py
│   ├── lima.py
│   ├── provisioner.py
│   ├── wizard.py
│   └── roles/
│       ├── common/tasks/main.yml
│       ├── python/tasks/main.yml
│       ├── node/tasks/main.yml
│       └── ... (11 roles total)
└── metadata files
```

### Entry Point

Registered in `pyproject.toml`:
```toml
[project.scripts]
clauded = "clauded.cli:main"
```

After installation, `clauded` command is available system-wide.

### Runtime Dependencies

**Required on Host**:
- Python 3.12+
- Lima (`limactl` in PATH)
- Ansible (installed via uv/pip as dependency)
- Internet connection (for VM image and package downloads)

**Bundled in Wheel**:
- All Python modules
- All Ansible roles
- Python package dependencies (click, questionary, pyyaml, ansible)

## Performance Considerations

### VM Creation (~1-3 minutes)

**Breakdown**:
1. Lima VM initialization: ~30-60 seconds
2. Alpine image download: ~10-30 seconds (first time only, ~50MB)
3. VM boot: ~10-20 seconds
4. Ansible provisioning: ~30-90 seconds (depends on selected roles)

**Optimization**:
- Alpine image cached by Lima after first download
- apk package manager is faster than apt
- Ansible pipelining enabled (reduces SSH round-trips)
- Parallel package installation where possible

### Subsequent Starts (~5-15 seconds)

**Breakdown**:
1. VM start: ~5-10 seconds
2. Shell entry: <1 second

**Optimization**:
- No reprovisioning needed unless explicitly requested
- VM disk persists all installed software

### Provisioning (~30-90 seconds)

**Breakdown**:
- apk package index update: ~5-10 seconds
- Package downloads: ~15-60 seconds (depends on number of packages)
- Installation and configuration: ~10-20 seconds

**Optimization**:
- Idempotent roles skip already-installed packages
- apk cache shared within VM

## Security Considerations

### Trust Model

- **Host trusts VM**: Same user owns both; no sandboxing
- **VM trusts host**: Mounted directory is writable from host
- **SSH is local-only**: Lima SSH config restricts to localhost

### Security Boundaries

**None**:
- VMs run under host user's privileges
- No authentication required (SSH key-based via Lima)
- VMs have full internet access

**Rationale**: Development environment tool; security isolation not a goal.

### Sensitive Data

- `.clauded.yaml` contains no secrets (safe to commit)
- Lima SSH keys stored in `~/.lima/<vm-name>/` (host-only access)
- VM disk is unencrypted (assumed to be on encrypted host filesystem)

## Extension Points

### Adding New Ansible Roles

1. Create `src/clauded/roles/<role-name>/tasks/main.yml`
2. Add role selection logic in `provisioner.py::_get_roles()`
3. Add wizard prompt in `wizard.py::run()`
4. Add config field in `config.py::Config` if needed

**Example** (adding Go support):
```python
# provisioner.py
if "go" in self.config.tools:
    roles.append("golang")

# src/clauded/roles/golang/tasks/main.yml
- name: Install Go
  apk:
    name: go
    state: present
```

### Adding New Provisioners (Beyond Ansible)

Implement alternative provisioner class with `run()` method:
```python
class DockerfileProvisioner:
    def run(self) -> None:
        # Generate Dockerfile
        # Execute docker build inside VM
        pass
```

Update `cli.py` to use new provisioner:
```python
provisioner = DockerfileProvisioner(config, vm)
provisioner.run()
```

### Adding Cloud VM Support

Extend `lima.py` with cloud provider SDK:
```python
class AWSVM(BaseVM):
    def create(self) -> None:
        # Use boto3 to launch EC2 instance
        pass
```

## Troubleshooting

### Common Issues

**Issue**: `limactl: command not found`
- **Cause**: Lima not installed
- **Fix**: `brew install lima`

**Issue**: VM creation hangs
- **Cause**: Network issues downloading Alpine image
- **Fix**: Check internet connection, retry

**Issue**: Ansible provisioning fails
- **Cause**: SSH connection issues or package download failures
- **Fix**: Check VM is running, check internet connection, retry with `--reprovision`

**Issue**: Mount not working
- **Cause**: Host path doesn't exist or not accessible
- **Fix**: Verify host path in `.clauded.yaml`, ensure directory exists

## Future Architecture Improvements

1. **Plugin System**: Allow third-party Ansible roles via plugin directory
2. **Multi-VM Support**: Extend to Docker Compose-like multi-VM setups
3. **Remote Provisioning**: Add support for cloud VMs (AWS, GCP, Azure)
4. **State Management**: Track VM states in a local database (SQLite)
5. **Resource Monitoring**: Add VM health checks and resource usage tracking
