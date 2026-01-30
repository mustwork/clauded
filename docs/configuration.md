# Configuration Reference

## Overview

`clauded` uses a `.clauded.yaml` file in your project root to define your development environment. This file specifies VM resources, runtime versions, and which tools/databases/frameworks to install.

## Configuration File Location

```
/path/to/your/project/
├── .clauded.yaml      ← Configuration file
├── src/
├── tests/
└── README.md
```

The configuration file must be named `.clauded.yaml` and located at the project root (same directory where you run `clauded`).

## Full Configuration Example

```yaml
version: "1"
vm:
  name: clauded-a1b2c3d4
  cpus: 4
  memory: 8GiB
  disk: 20GiB
mount:
  host: /Users/yourname/projects/myproject
  guest: /Users/yourname/projects/myproject
environment:
  python: "3.12"
  node: "20"
  tools:
    - docker
    - git
    - aws-cli
    - gh
  databases:
    - postgresql
    - redis
    - mysql
  frameworks:
    - claude-code
    - playwright
```

## Configuration Schema

### version

**Type**: String
**Required**: Yes
**Values**: `"1"`

Specifies the configuration file format version. Currently, only version `"1"` is supported.

```yaml
version: "1"
```

---

### vm.name

**Type**: String
**Required**: Yes
**Auto-generated**: Yes

Unique identifier for the VM. Automatically generated from your project path using an MD5 hash.

**Format**: `clauded-{8-character-hash}`

**Example**:
```yaml
vm:
  name: clauded-a1b2c3d4
```

**Note**: You should not manually edit this value. It's generated automatically when creating the config via the wizard or programmatically.

---

### vm.cpus

**Type**: Integer
**Required**: Yes
**Default**: `4`
**Range**: 1-16 (depending on host CPU)

Number of CPU cores allocated to the VM.

```yaml
vm:
  cpus: 4
```

**Recommendations**:
- **Light workloads** (simple scripts): 2 CPUs
- **Standard development** (web apps, APIs): 4 CPUs
- **Heavy workloads** (compilation, builds): 6-8 CPUs

---

### vm.memory

**Type**: String
**Required**: Yes
**Default**: `"8GiB"`
**Format**: `<number>GiB`

Amount of RAM allocated to the VM.

```yaml
vm:
  memory: 8GiB
```

**Common Values**:
- `4GiB`: Minimal setups
- `8GiB`: Standard development (recommended)
- `16GiB`: Heavy workloads, multiple databases
- `32GiB`: Large datasets, memory-intensive applications

**Note**: Ensure your host has sufficient free memory. VM memory is reserved when the VM is running.

---

### vm.disk

**Type**: String
**Required**: Yes
**Default**: `"20GiB"`
**Format**: `<number>GiB`

Disk space allocated to the VM. This is the maximum size; actual usage depends on installed software.

```yaml
vm:
  disk: 20GiB
```

**Common Values**:
- `10GiB`: Minimal setups (Python/Node only)
- `20GiB`: Standard development (recommended)
- `40GiB`: Multiple databases, large dependencies
- `60GiB+`: Docker images, browser binaries, large datasets

**Note**: Disk space is allocated on demand but cannot exceed this limit. Increasing this value requires recreating the VM.

---

### mount.host

**Type**: String
**Required**: Yes
**Auto-generated**: Yes

Absolute path to your project directory on the host machine.

```yaml
mount:
  host: /Users/yourname/projects/myproject
```

**Auto-generated value**: Current working directory when `clauded` is first run.

**Requirements**:
- Must be an absolute path (no relative paths)
- Must be a local filesystem path (not network mount)
- Directory must exist

---

### mount.guest

**Type**: String
**Required**: Yes
**Default**: Same as `mount.host`

Path where your project directory is mounted inside the VM. By default, this matches the host path so that Claude Code sessions are unique per project directory.

```yaml
mount:
  host: /Users/yourname/projects/myapp
  guest: /Users/yourname/projects/myapp
```

**Note**: Using the same path on both host and guest ensures Claude Code's session storage (keyed by project path) is unique per project, avoiding session collisions across VMs.

---

### environment.python

**Type**: String or null
**Required**: No
**Default**: `null`
**Allowed Values**: `"3.10"`, `"3.11"`, `"3.12"`, `null`

Python version to install in the VM. If set to `null`, Python will not be installed.

```yaml
environment:
  python: "3.12"
```

**Installation Details**:
- Installed via Alpine apk
- Set as system default (`python3` command)
- Includes `pip` and `venv`
- Installed packages: `python3`, `python3-dev`, `py3-pip`

**Version Selection**:
- `"3.12"`: Latest stable (recommended for new projects)
- `"3.11"`: Previous stable
- `"3.10"`: Older stable
- `null`: Skip Python installation

---

### environment.node

**Type**: String or null
**Required**: No
**Default**: `null`
**Allowed Values**: `"18"`, `"20"`, `"22"`, `null`

Node.js version to install in the VM. If set to `null`, Node.js will not be installed.

```yaml
environment:
  node: "20"
```

**Installation Details**:
- Installed via Alpine apk from edge/community repository
- Includes `npm` and `npx`
- System-wide installation

**Version Selection**:
- `"22"`: Latest LTS
- `"20"`: Active LTS (recommended)
- `"18"`: Maintenance LTS
- `null`: Skip Node.js installation

---

### environment.tools

**Type**: List of strings
**Required**: No
**Default**: `[]`
**Allowed Values**: `docker`, `git`, `aws-cli`, `gh`

Development tools to install in the VM.

```yaml
environment:
  tools:
    - docker
    - git
    - aws-cli
    - gh
```

**Available Tools**:

#### `docker`
- **Package**: `docker`
- **What it does**: Installs Docker Engine
- **Post-install**: User added to `docker` group (no sudo needed)
- **Service**: Enabled and started automatically
- **Use cases**: Container development, service testing

#### `git`
- **Package**: `git`
- **What it does**: Version control system
- **Installed by**: `common` role (always installed)
- **Use cases**: Cloning repos, version control

#### `aws-cli`
- **Package**: AWS CLI v2 (manual download)
- **What it does**: AWS command-line interface
- **Architecture**: ARM64 (aarch64)
- **Use cases**: AWS resource management, S3 uploads, EC2 control

#### `gh`
- **Package**: GitHub CLI
- **Repository**: Alpine apk (github-cli package)
- **What it does**: GitHub workflow automation
- **Use cases**: PR creation, issue management, GitHub Actions

**Default Selection**: `docker` and `git` are pre-selected in the wizard.

---

### environment.databases

**Type**: List of strings
**Required**: No
**Default**: `[]`
**Allowed Values**: `postgresql`, `redis`, `mysql`, `mongodb`, `sqlite`

Databases to install and configure in the VM.

```yaml
environment:
  databases:
    - postgresql
    - redis
    - mysql
    - mongodb
    - sqlite
```

**Available Databases**:

#### `postgresql`
- **Packages**: `postgresql`, `postgresql-contrib`, `postgresql-dev`
- **Service**: Enabled and started automatically (OpenRC)
- **Port**: 5432
- **Post-install**: Service waits for port 5432 to be ready
- **Use cases**: Relational database, full-text search, JSON storage

#### `redis`
- **Package**: `redis`
- **Service**: Enabled and started automatically (OpenRC)
- **Port**: 6379
- **Post-install**: Service waits for port 6379 to be ready
- **Use cases**: Caching, session storage, pub/sub

#### `mysql`
- **Package**: `mariadb` (MySQL-compatible)
- **Service**: Enabled and started automatically (OpenRC)
- **Port**: 3306
- **Post-install**: Service waits for port 3306 to be ready
- **Use cases**: Relational database, legacy applications

#### `mongodb`
- **Package**: `mongodb`
- **Service**: Enabled and started automatically (OpenRC)
- **Port**: 27017
- **Post-install**: Service waits for port 27017 to be ready
- **Use cases**: Document-oriented NoSQL database, flexible schemas, JSON-like documents
- **Detection**: Automatically detected from docker-compose (mongo/mongodb images), environment variables (MONGODB_URI, MONGO_URL), and ORM dependencies (pymongo, mongoose, motor, mongoengine)

#### `sqlite`
- **Package**: `sqlite`
- **Service**: No service (file-based database)
- **Port**: N/A
- **Use cases**: Embedded database, local storage, testing

**Default Selection**: None (all databases are optional).

---

### environment.frameworks

**Type**: List of strings
**Required**: No
**Default**: `[]`
**Allowed Values**: `claude-code`, `playwright`

Testing and development frameworks to install in the VM.

```yaml
environment:
  frameworks:
    - claude-code
    - playwright
```

**Available Frameworks**:

#### `claude-code`
- **Installation**: Native installer (`claude.ai/install.sh`), auto-updates
- **Binary**: `~/.local/bin/claude`
- **Command**: `claude`
- **What it does**: AI-assisted development CLI
- **Use cases**: Code generation, refactoring, debugging with Claude AI
- **Alpine deps**: `libgcc`, `libstdc++`, `ripgrep`, `USE_BUILTIN_RIPGREP=0`
- **Auto-accept**: See [Claude Code Permissions](#claude-code-permissions) below

#### `playwright`
- **Package**: `playwright` (npm)
- **Installation**: Global npm package + browser binaries
- **Commands**: `playwright`, `playwright test`
- **Browsers**: Chromium, Firefox, WebKit
- **Use cases**: End-to-end testing, browser automation

**Default Selection**: `claude-code` is pre-selected in the wizard.

---

### Claude Code Permissions

When `claude-code` is installed, clauded can configure it to auto-accept all tool permission prompts inside the VM. This is controlled by the `claude.dangerously_skip_permissions` setting.

**Default**: Enabled (`true`) — Claude Code will not prompt for tool permissions inside the VM.

**Configuration**:
```yaml
claude:
  dangerously_skip_permissions: true   # Skip all permission prompts (default)
  # dangerously_skip_permissions: false  # Require manual confirmation
```

#### How clauded Enables Permission Bypass

When `dangerously_skip_permissions` is enabled, clauded uses **two mechanisms** to ensure Claude Code runs without permission prompts:

1. **CLI Flag**: The `--dangerously-skip-permissions` flag is passed directly to Claude Code when starting the shell:
   ```bash
   claude --dangerously-skip-permissions
   ```

2. **Environment Variable**: Creates `/etc/profile.d/claude.sh` in the VM with:
   ```bash
   export CLAUDE_DANGEROUSLY_SKIP_PERMISSIONS=true
   ```

Using both mechanisms provides redundancy, as there are known issues with each method individually (see below).

#### Alternative Configuration Methods

Claude Code supports multiple ways to configure permission bypass. These can be used manually inside the VM if needed:

**Via CLI flag** (most reliable):
```bash
claude --dangerously-skip-permissions
```

**Via settings.json** (persistent):
Add to `~/.claude/settings.json`:
```json
{
  "permissions": {
    "defaultMode": "bypassPermissions"
  }
}
```

**Via permission-mode flag**:
```bash
claude --permission-mode bypassPermissions
```

#### Settings Precedence

Claude Code evaluates permission settings in this order (highest to lowest priority):

1. Managed settings (`/etc/claude-code/managed-settings.json`)
2. CLI flags (`--dangerously-skip-permissions`)
3. Local project settings (`.claude/settings.local.json`)
4. Shared project settings (`.claude/settings.json`)
5. User settings (`~/.claude/settings.json`)
6. Environment variables (`CLAUDE_DANGEROUSLY_SKIP_PERMISSIONS`)

#### Known Issues

There are documented issues with Claude Code's permission bypass:

- **Environment variable alone may not work**: Some users report that `CLAUDE_DANGEROUSLY_SKIP_PERMISSIONS=true` is not sufficient and prompts still appear. The CLI flag is more reliable.

- **Certain tools still prompt**: There's a [known bug](https://github.com/anthropics/claude-code/issues/1498) where `--dangerously-skip-permissions` still prompts for certain tools (particularly `Search()` and `List()`). This is project-specific and persists across versions.

- **Permission mode conflicts**: Using `--permission-mode plan` together with `--dangerously-skip-permissions` can cause unexpected behavior where the permission mode is ignored.

If you experience persistent permission prompts despite this setting, try adding explicit permission rules to `~/.claude/settings.json`:
```json
{
  "permissions": {
    "defaultMode": "bypassPermissions",
    "allow": [
      "Bash(*)",
      "Edit(*)",
      "Read(*)",
      "Write(*)",
      "Search(*)",
      "List(*)"
    ]
  }
}
```

#### Design Decisions

1. **VM-only scope**: The `/etc/profile.d/` directory is part of the VM filesystem (not mounted from host), so this setting only affects Claude Code running inside the VM. The host's Claude Code remains unaffected.

2. **Dual mechanism**: We use both CLI flag and environment variable because neither is 100% reliable on its own due to Claude Code bugs.

3. **Idempotent**: Re-provisioning correctly enables or disables the setting based on current configuration.

**Wizard Option**: The wizard prompts "Auto-accept Claude Code permission prompts in VM?" with default `Yes`. This can also be changed via `clauded --edit`.

---

## Minimal Configuration

The smallest valid configuration (wizard defaults):

```yaml
version: "1"
vm:
  name: clauded-12345678
  cpus: 4
  memory: 8GiB
  disk: 20GiB
mount:
  host: /Users/yourname/projects/myproject
  guest: /Users/yourname/projects/myproject
environment:
  python: null
  node: null
  tools: []
  databases: []
  frameworks: []
```

This creates a bare Alpine VM with only base packages (from the `common` role).

---

## Common Configuration Patterns

### Python Web Application

```yaml
version: "1"
vm:
  name: clauded-webapp01
  cpus: 4
  memory: 8GiB
  disk: 20GiB
mount:
  host: /Users/yourname/projects/flask-app
  guest: /Users/yourname/projects/flask-app
environment:
  python: "3.12"
  node: null
  tools:
    - docker
    - git
  databases:
    - postgresql
    - redis
  frameworks: []
```

**Use case**: Flask/Django app with PostgreSQL and Redis.

---

### Node.js Microservice

```yaml
version: "1"
vm:
  name: clauded-nodeapi
  cpus: 4
  memory: 8GiB
  disk: 20GiB
mount:
  host: /Users/yourname/projects/express-api
  guest: /Users/yourname/projects/express-api
environment:
  python: null
  node: "20"
  tools:
    - docker
    - git
    - aws-cli
  databases:
    - postgresql
  frameworks: []
```

**Use case**: Express.js API with PostgreSQL, deployed to AWS.

---

### Full-Stack Application with Testing

```yaml
version: "1"
vm:
  name: clauded-fullstack
  cpus: 6
  memory: 16GiB
  disk: 40GiB
mount:
  host: /Users/yourname/projects/fullstack-app
  guest: /Users/yourname/projects/fullstack-app
environment:
  python: "3.12"
  node: "20"
  tools:
    - docker
    - git
    - gh
  databases:
    - postgresql
    - redis
  frameworks:
    - playwright
    - claude-code
```

**Use case**: Full-stack app (Python backend, Node frontend) with E2E testing and AI assistance.

---

### Data Science Environment

```yaml
version: "1"
vm:
  name: clauded-datascience
  cpus: 8
  memory: 16GiB
  disk: 60GiB
mount:
  host: /Users/yourname/projects/ml-project
  guest: /Users/yourname/projects/ml-project
environment:
  python: "3.12"
  node: null
  tools:
    - docker
    - git
  databases:
    - postgresql
  frameworks: []
```

**Use case**: Machine learning project with large datasets and heavy computation.

---

## Editing Configuration

### Manual Editing

You can manually edit `.clauded.yaml` to change VM settings or environment selections.

**After editing**:
1. Stop the VM: `clauded --stop`
2. Restart and reprovision: `clauded --reprovision`

**Note**: Changing VM resources (CPU, memory, disk) requires destroying and recreating the VM:
```bash
clauded --destroy
clauded  # Creates new VM with updated config
```

### Regenerating Configuration

To regenerate the configuration from scratch:

```bash
# Backup existing config (optional)
mv .clauded.yaml .clauded.yaml.bak

# Run wizard to create new config
clauded
```

---

## Configuration Validation

`clauded` validates the configuration when loading. Common validation errors:

### Invalid Python Version

```yaml
environment:
  python: "3.9"  # ❌ Not supported
```

**Error**: Invalid Python version. Must be one of: 3.10, 3.11, 3.12, or null.

### Invalid Node.js Version

```yaml
environment:
  node: "16"  # ❌ Not supported
```

**Error**: Invalid Node version. Must be one of: 18, 20, 22, or null.

### Invalid Tool Name

```yaml
environment:
  tools:
    - dockerr  # ❌ Typo
```

**Error**: Invalid tool 'dockerr'. Allowed: docker, git, aws-cli, gh.

### Missing Required Fields

```yaml
version: "1"
vm:
  cpus: 4
  # ❌ Missing name, memory, disk
```

**Error**: Missing required field: vm.name.

---

## Environment Variables

`clauded` does not currently support environment variable substitution in `.clauded.yaml`. All values must be literal strings or numbers.

---

## Version Control

### Recommended: Commit Configuration

```bash
git add .clauded.yaml
git commit -m "Add clauded VM configuration"
```

**Benefits**:
- Team members get identical environments
- Environment changes tracked in git history
- Reproducible across machines

### Optional: Gitignore Configuration

If you want per-developer customization:

```bash
echo ".clauded.yaml" >> .gitignore
```

**Trade-off**: Team members must run wizard individually; environments may differ.

---

## Troubleshooting

### VM Name Mismatch

**Symptom**: VM name in config doesn't match actual VM.

**Cause**: Manually edited `vm.name` or moved project directory.

**Fix**:
```bash
clauded --destroy
rm .clauded.yaml
clauded  # Regenerate config
```

### Resource Allocation Errors

**Symptom**: VM fails to start with resource errors.

**Cause**: Host doesn't have sufficient CPU/memory.

**Fix**: Reduce `vm.cpus` or `vm.memory` in `.clauded.yaml`:
```yaml
vm:
  cpus: 2
  memory: 4GiB
```

Then recreate the VM:
```bash
clauded --destroy
clauded
```

### Mount Path Issues

**Symptom**: Project directory is empty inside VM.

**Cause**: `mount.host` path doesn't exist or is incorrect.

**Fix**: Verify path in `.clauded.yaml`:
```yaml
mount:
  host: /correct/absolute/path/to/project
  guest: /correct/absolute/path/to/project
```

---

## Advanced Configuration

### Custom Roles (Future)

Currently, the Ansible roles are bundled with `clauded`. Future versions may support custom role directories:

```yaml
environment:
  custom_roles:
    - /path/to/custom/role
```

### Cloud VMs (Future)

Future versions may support cloud VM provisioning:

```yaml
provider: aws
vm:
  instance_type: t3.medium
  region: us-west-2
```

---

## Reference Summary

| Field | Type | Required | Default | Allowed Values |
|-------|------|----------|---------|----------------|
| `version` | string | Yes | - | `"1"` |
| `vm.name` | string | Yes | auto-generated | `clauded-{hash}` |
| `vm.cpus` | int | Yes | 4 | 1-16 |
| `vm.memory` | string | Yes | `"8GiB"` | `<N>GiB` |
| `vm.disk` | string | Yes | `"20GiB"` | `<N>GiB` |
| `mount.host` | string | Yes | auto-generated | absolute path |
| `mount.guest` | string | Yes | same as host | absolute path |
| `environment.python` | string\|null | No | `null` | `"3.10"`, `"3.11"`, `"3.12"`, `null` |
| `environment.node` | string\|null | No | `null` | `"18"`, `"20"`, `"22"`, `null` |
| `environment.tools` | list | No | `[]` | `docker`, `git`, `aws-cli`, `gh` |
| `environment.databases` | list | No | `[]` | `postgresql`, `redis`, `mysql` |
| `environment.frameworks` | list | No | `[]` | `claude-code`, `playwright` |
