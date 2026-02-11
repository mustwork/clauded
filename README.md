# clauded

Isolated, per-project Lima VMs (MacOS) with automatic environment provisioning that feel just like `claude`.

## Overview

`clauded` is a CLI tool that creates lightweight, isolated Linux VMs for each of your projects using [Lima](https://github.com/lima-vm/lima) (Linux Machines for macOS). It provisions your development environment with the tools, and frameworks you need through declarative configuration and Ansible.

**Supported Distributions:**
- **Alpine Linux** (default) - Minimal footprint, fast boot
- **Ubuntu 24.04 LTS** - Broader package ecosystem, glibc-based

**Why clauded?**

- **Sandboxing**: Peace of mind when skipping confirmation prompts by claude-code
- **Isolated Environments**: Each project gets its own VM with dedicated resources
- **Declarative Configuration**: Define your stack in `.clauded.yaml` and commit it to version control
- **Zero Setup Friction**: Interactive wizard guides you through environment creation
- **Reproducible Across Teams**: Team members get identical environments from the same config
- **No Local Pollution**: Keep your host machine clean while running complex stacks
- **Exchangeable Usage**: `clauded` and `claude` share the same configuration and history

## Features

- **Interactive Setup Wizard**: Guided prompts for languages, databases, and tools
- **Automatic Project Detection**: Intelligently detects languages, versions, frameworks, and databases from your project files
  - Detects Python versions from setup.py, pyproject.toml, and version files
  - Detects Java versions from build.gradle, build.gradle.kts, and pom.xml
  - Detects frameworks from Gradle, Maven, and package managers
  - Detects databases from docker-compose, environment files, and ORM dependencies
- **Multiple Runtime Versions**: Choose Python 3.10/3.11/3.12, Node.js 18/20/22, Java 11/17/21, Kotlin 1.9/2.0, Rust stable/nightly, Go 1.22.10/1.23.5, Dart 3.5/3.6/3.7, and C/C++ toolchains (gcc13/gcc14, clang17/clang18)
- **Database Support**: PostgreSQL, Redis, MySQL, SQLite, and MongoDB CLI tools with automatic installation
- **Developer Tools**: Docker, AWS CLI, GitHub CLI, Git pre-installed
- **Testing Frameworks**: Playwright with browser binaries ready to use
- **VM Lifecycle Management**: Create, start, stop, destroy, and reprovision VMs
- **Multi-Instance Support**: Multiple terminals can connect to the same VM; VM only stops when the last session exits
- **Atomic Config Updates**: Automatic rollback on failure ensures config never references broken VMs
- **Crash Recovery**: Detects and recovers from interrupted operations on startup
- **Customizable Resources**: Configure CPU, memory, and disk allocation per project
- **Workspace Mounting**: Your project and claude config directories are mounted at the same path in the VM

## Supported Environments

### Languages & Runtimes

| Language | Versions | Package Managers (auto-installed) |
|----------|----------|-----------------------------------|
| Python | 3.10, 3.11, 3.12 | pip, pipx, uv, uvx, poetry |
| Node.js | 18, 20, 22 | npm, npx, corepack, yarn, pnpm, bun |
| Java | 11, 17, 21 | maven, gradle |
| Kotlin | 1.9, 2.0 | maven, gradle |
| Rust | stable, nightly | cargo |
| Go | 1.22.10, 1.23.5 | go modules (built-in) |
| Dart | 3.5, 3.6, 3.7 | dart, pub |
| C/C++ | gcc13, gcc14, clang17, clang18 | gcc, g++, clang, make, cmake |

### Developer Tools

| Tool | Description |
|------|-------------|
| Docker | Container runtime (user added to docker group) |
| Git | Version control (always installed via common role) |
| AWS CLI | AWS command-line interface (v2, ARM64) |
| GitHub CLI | GitHub workflow automation (`gh` command) |
| Gradle | Build automation tool for Java/Kotlin projects |

### Databases

| Database | Port | Notes |
|----------|------|-------|
| PostgreSQL | 5432 | Includes contrib and libpq-dev |
| Redis | 6379 | In-memory data store |
| MySQL | 3306 | Relational database |
| SQLite | N/A | File-based database, no service management required |
| MongoDB | N/A | CLI tools only (mongodump, mongorestore, etc.) for working with remote MongoDB instances |

### Frameworks & Tools

| Framework | Description | Requires |
|-----------|-------------|----------|
| Claude Code | AI-assisted development CLI | Node.js |
| Playwright | Browser automation and E2E testing | Node.js |

## Requirements

- macOS with Apple Silicon (ARM64)
- [Lima](https://github.com/lima-vm/lima) installed (`brew install lima`)
- Python 3.12+

## Installation

```bash
git clone https://github.com/mustwork/clauded.git
# or: git clone git@github.com:mustwork/clauded.git
cd clauded
make install
```

This builds and installs the `clauded` command via `uv tool`.

## Quick Start

### 1. Create a New Project VM

Navigate to your project directory and run:

```bash
clauded
```

If no `.clauded.yaml` exists, the interactive wizard will guide you through setup:

```
? Select distribution: Alpine Linux
? Python version: 3.12
? Node.js version: 20
? Java version: 21
? Kotlin version: 2.0
? Rust version: stable
? Go version: 1.23.5
? Select tools (space to select): docker, git
? Select databases: postgresql, redis, mongodb, sqlite
? Select frameworks: claude-code, playwright
? Customize VM resources? No
```

You can also specify the distribution directly with the `--distro` flag:

```bash
clauded --distro ubuntu  # Create Ubuntu-based VM
clauded --distro alpine  # Create Alpine-based VM (default)
```

This generates `.clauded.yaml`, creates the VM, provisions it with Ansible, and drops you into a shell.

### 2. Reconnect to Existing VM

If `.clauded.yaml` exists:

```bash
clauded
```

This starts the VM (if stopped) and enters the shell immediately.

### 3. Stop the VM

```bash
clauded --stop
```

If other sessions are connected, you'll see a message and the VM won't stop. Use `--force-stop` to stop regardless:

```bash
clauded --force-stop
```

### 4. Reprovision (Update Environment)

After modifying `.clauded.yaml`:

```bash
clauded --reprovision
```

### 5. Edit Configuration

```bash
clauded --edit
```

Re-run the wizard to modify your configuration, then automatically reprovision the VM.

### 6. Detect Project Technologies

```bash
clauded --detect
```

Show detected languages, versions, frameworks, and databases without creating a VM.

### 7. Change Distribution

To change from Alpine to Ubuntu (or vice versa), edit `.clauded.yaml` and change `vm.distro`:

```yaml
vm:
  distro: ubuntu  # Change from alpine to ubuntu
```

Then run `clauded`. You'll be prompted to confirm VM recreation since the distribution change requires a new VM:

```
⚠️  Distribution mismatch detected!
Current VM uses: alpine
Config specifies: ubuntu

Changing distribution requires destroying and recreating the VM.
All VM data will be lost. Your project files are safe (mounted from host).

Recreate VM with ubuntu? [y/N]:
```

### 8. Destroy the VM

```bash
clauded --destroy
```

You'll be prompted whether to also remove `.clauded.yaml`.

### 9. Automatic Crash Recovery

If a VM operation is interrupted (power loss, Ctrl+C, system crash), `clauded` automatically detects the incomplete state on next startup:

```bash
clauded

# Output if crash detected:
⚠️  Incomplete VM update detected. Current VM 'new-vm' does not exist.
Rolling back to 'previous-vm'.
```

The system intelligently handles recovery:
- **Current VM missing**: Automatically rolls back config to previous working VM
- **Current VM exists**: Prompts you to optionally delete the previous VM
- **Config always consistent**: Never left pointing to non-existent VMs

This ensures your development environment remains reliable even after unexpected interruptions.

## Configuration

Create or edit `.clauded.yaml` in your project root:

```yaml
version: "1"
vm:
  name: clauded-a1b2c3d4  # Auto-generated from project path
  distro: alpine         # Distribution: alpine (default) or ubuntu
  cpus: 4
  memory: 8GiB
  disk: 20GiB
  keep_running: false    # Keep VM running after shell exit (see below)
mount:
  host: /Users/you/projects/myproject
  guest: /Users/you/projects/myproject
environment:
  python: "3.12"
  node: "20"
  java: "21"
  kotlin: "2.0"
  rust: "stable"
  go: "1.23.5"
  tools:
    - docker
    - git
    - aws-cli
    - gh
    - gradle
  databases:
    - postgresql
    - redis
    - mysql
    - mongodb
    - sqlite
  frameworks:
    - claude-code
    - playwright
```

See [docs/configuration.md](docs/configuration.md) for full configuration reference.

### Keep VM Running

By default, VMs automatically shut down when you exit the shell. This frees system resources but means the VM must boot again on next connection.

Set `vm.keep_running: true` to keep VMs running after exit:

- **Pros**: Faster reconnection (no boot delay), preserves running processes
- **Cons**: Consumes CPU/memory while idle, must manually stop with `clauded --stop`

This setting can be changed while a VM is running - the new value takes effect on the next shell exit.

## Development

### Setup

```bash
make dev          # Install with dev dependencies
make hooks        # Install pre-commit hooks
```

### Common Commands

```bash
make sync         # Sync dependencies
make test         # Run tests
make coverage     # Run tests with coverage report
make lint         # Run linter (ruff)
make format       # Auto-format code
make typecheck    # Run type checker (mypy)
make check        # Run all checks (lint + typecheck + test)
make build        # Build wheel
make clean        # Remove build artifacts
```

### Running Tests

```bash
# Run all tests
make test

# Run with coverage
make coverage
# Open htmlcov/index.html for detailed coverage report
```

### Code Quality

This project uses:
- **ruff** for linting and formatting
- **mypy** for strict type checking
- **pytest** for testing with coverage tracking

All checks must pass before committing:

```bash
make check
```

## Architecture

`clauded` consists of five core Python modules:

- `cli.py`: Click-based CLI entry point and command routing
- `config.py`: Configuration management for `.clauded.yaml` files
- `lima.py`: Lima VM lifecycle operations (create, start, stop, destroy)
- `provisioner.py`: Ansible playbook generation and execution
- `wizard.py`: Interactive menu-based setup wizard (simple-term-menu)

See [docs/architecture.md](docs/architecture.md) for detailed architecture documentation.

## How It Works

1. **Configuration**: Load `.clauded.yaml` or run wizard to create it
2. **VM Creation**: Generate Lima YAML config and create VM via `limactl`
3. **Provisioning**: Dynamically select Ansible roles based on config and provision via SSH
4. **Shell Access**: Enter interactive shell at your project directory

### Provisioning Architecture

All package installation is handled by Ansible, not Lima boot scripts. This design choice provides:

- **Recoverable failures**: If provisioning fails, the VM still exists and is SSH-accessible. You can debug issues and re-run `clauded --reprovision`
- **Faster VM boot**: Lima doesn't wait for package manager operations during boot
- **Single source of truth**: All environment setup logic lives in Ansible roles, not split between Lima and Ansible

Alpine Linux cloud images include Python by default, allowing Ansible to connect immediately after VM boot without any Lima-side provisioning.

## Project Structure

```
clauded/
├── src/clauded/           # Main package source
│   ├── cli.py             # CLI entry point
│   ├── config.py          # Config management
│   ├── lima.py            # Lima VM operations
│   ├── provisioner.py     # Ansible integration
│   ├── wizard.py          # Interactive setup
│   ├── detect/            # Project detection module
│   ├── linguist/          # Vendored Linguist data
│   └── roles/             # Ansible roles (21 roles)
├── tests/                 # Test suite
├── docs/                  # Technical documentation
├── specs/                 # Specifications
├── Makefile               # Development automation
└── pyproject.toml         # Project metadata
```

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run `make check` to ensure all checks pass
5. Submit a pull request

## License

This project is licensed under the [MIT License](LICENSE).

## Support

- Report issues: [GitHub Issues](https://github.com/mustwork/clauded/issues)
- Documentation: [docs/](docs/)
- Specifications: [specs/spec.md](specs/spec.md)
