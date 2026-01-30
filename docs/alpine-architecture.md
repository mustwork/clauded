# Alpine Linux Architecture Decision

## Decision

clauded uses Alpine Linux 3.21 as the base operating system for all provisioned VMs.

## Context

The initial implementation used Ubuntu Jammy 22.04 LTS. Package installation via apt was identified as a significant bottleneck during VM provisioning, particularly the `common` role that installs base system packages.

Two alternatives were evaluated:

1. **Custom Lima base image**: Pre-bake an Ubuntu image with common packages, cache locally for 28 days
2. **Alpine Linux**: Switch to Alpine Linux for faster package management

## Rationale

Alpine Linux was chosen for the following reasons:

### Performance Benefits

- **Smaller base image**: Alpine cloud image is ~50MB vs ~600MB for Ubuntu
- **Faster package manager**: apk is significantly faster than apt for package installation
- **Reduced download time**: Smaller packages mean faster provisioning
- **Lower memory footprint**: Alpine's minimal design uses less RAM

### Simplicity

- **No cache management**: Unlike the custom image approach, no need to manage image expiry, garbage collection, or storage
- **Single source of truth**: All provisioning logic remains in Ansible roles
- **Transparent updates**: New Alpine releases can be adopted by changing a single URL

## Trade-offs

### Compatibility Considerations

- **musl libc**: Alpine uses musl instead of glibc. This can affect:
  - Some npm packages with native bindings (rare, most work fine)
  - Pre-compiled binaries that assume glibc (mitigated by using `gcompat` where needed)
  - Python packages with C extensions (typically work with proper dev headers)
  - **uv python install**: uv doesn't provide musl Python distributions yet ([#6890](https://github.com/astral-sh/uv/issues/6890)). The uv role falls back to system Python on Alpine with `UV_PYTHON_PREFERENCE=only-system`.

- **BusyBox coreutils**: Alpine ships BusyBox which provides minimal implementations of standard Unix tools. BusyBox's `env` lacks the `-S` (split-string) flag required by Node.js tools and Claude Code internal scripts. The `coreutils` package replaces BusyBox utilities with full GNU implementations.

- **OpenRC vs systemd**: Alpine uses OpenRC for service management instead of systemd
  - Services are managed via `rc-update` and `service` commands
  - All database and Docker roles updated to use OpenRC

- **Package availability**: Some packages have different names or may not exist
  - MySQL is provided via MariaDB (fully compatible)
  - Playwright uses system browsers instead of downloading binaries
  - GitHub CLI available as `github-cli` package

### Mitigation Strategies

1. **GNU coreutils**: Replaces BusyBox utilities with full GNU implementations. Required because BusyBox's `env` lacks the `-S` flag used by Claude Code and Node.js tool shebangs.
2. **Claude Code direct binary download**: The official native installer (`claude.ai/install.sh`) has interactive prompts that hang in automated environments. We download the musl binary directly from the release CDN. Requires `libgcc`, `libstdc++`, system `ripgrep`, and `USE_BUILTIN_RIPGREP=0`. See [claude-code-alpine-troubleshooting.md](claude-code-alpine-troubleshooting.md) for detailed debugging information.
3. **Community repository for Node.js**: Alpine 3.21's main `nodejs` package has SQLite session extension compatibility issues. We install `nodejs-current` from the community repository.
4. **gcompat package**: Installed for bun which requires glibc compatibility.
5. **System browsers for Playwright**: Uses Alpine's Chromium/Firefox packages instead of Playwright's bundled browsers.
6. **Direct downloads**: Go, Rust, Kotlin, and build tools are downloaded directly from official sources, bypassing package manager differences.
7. **pip-based AWS CLI**: AWS CLI v2 binary requires glibc. We install v1 via pip instead.
8. **System Python for uv**: Since uv can't install Python on musl, the uv role detects Alpine and uses system Python (from apk) instead of `uv python install`. Sets `UV_PYTHON_PREFERENCE=only-system` to ensure uv uses the system interpreter.

## Implementation Details

### Base Image

```
https://dl-cdn.alpinelinux.org/alpine/v3.21/releases/cloud/nocloud_alpine-3.21.0-aarch64-uefi-cloudinit-r0.qcow2
```

### Package Manager

All Ansible roles use the `apk` module instead of `apt`:

```yaml
- name: Install packages
  apk:
    name:
      - package1
      - package2
    state: present
    update_cache: yes
```

### Service Management

Services are managed via OpenRC:

```yaml
- name: Add service to boot
  command: rc-update add servicename default

- name: Start service
  service:
    name: servicename
    state: started
```

### Key Package Mappings

| Ubuntu Package | Alpine Package |
|---------------|----------------|
| build-essential | alpine-sdk |
| coreutils | coreutils (replaces BusyBox) |
| libpq-dev | postgresql-dev |
| libmysqlclient-dev | mariadb-dev |
| mysql-server | mariadb |
| redis-server | redis |
| software-properties-common | (not needed) |
| lsb-release | (not needed) |

## Verification

After migration, verify that:

1. All Ansible roles complete successfully
2. All development tools are functional (Python, Node, Java, Go, Rust, Kotlin)
3. All databases start and accept connections (PostgreSQL, Redis, MariaDB)
4. Docker containers run correctly
5. Playwright tests execute with system browsers

## Lima-Specific Considerations

### Home Directory Ownership

Lima creates user home directories with incorrect ownership (root:root). The `common` role fixes this by setting correct ownership on `/home/<user>.linux/`. Note: Don't use recursive chown when `~/.claude` is mounted from host - it will fail on mount points.

### File Mounts vs Copies

Lima can only mount directories, not individual files. For single files like `~/.gitconfig` and `~/.claude.json`, we copy content via provision scripts instead of mounting.

### Username vs Home Directory Mismatch

Lima creates a mismatch between username and home directory:
- **Username**: `mrother` (matches host, no suffix)
- **Home directory**: `/home/mrother.linux` (has `.linux` suffix)

This means you cannot construct the home path from the username. Ansible tasks must:
- Use `whoami` to get the username (for ownership)
- Use `echo $HOME` to get the actual home directory path (for file paths)

**Wrong**: `path: "/home/{{ username }}"`
**Right**: `path: "{{ home_from_echo_HOME }}"`

## Future Considerations

- Monitor Alpine releases for security updates
- Consider Alpine edge branch for bleeding-edge packages if needed
- Track any compatibility issues with native npm/Python packages
