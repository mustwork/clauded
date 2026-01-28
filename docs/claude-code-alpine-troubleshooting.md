# Claude Code on Alpine Linux Troubleshooting

This document details the issues encountered running Claude Code on Alpine Linux (musl libc) and their solutions. These findings emerged from extensive debugging of Claude Code hanging silently on Alpine-based Lima VMs.

## Summary of Issues

Running Claude Code on Alpine Linux requires addressing several compatibility issues:

1. **musl libc compatibility** - Native binary requires specific libraries
2. **Ripgrep compatibility** - Built-in ripgrep doesn't work on musl
3. **Home directory permissions** - Lima creates home directories with wrong ownership
4. **Missing config file** - `~/.claude.json` must exist and be writable
5. **Direct binary download** - Native installer's interactive prompts don't work in automated environments

## Required Dependencies

Install these packages before running Claude Code on Alpine:

```bash
apk add libgcc libstdc++ ripgrep
```

- `libgcc` and `libstdc++`: Required by the native binary
- `ripgrep`: System ripgrep to replace the non-working bundled version

## Environment Variables

### USE_BUILTIN_RIPGREP=0

**Critical**: The native Claude Code binary bundles ripgrep, but it doesn't work on musl. You must set:

```bash
export USE_BUILTIN_RIPGREP=0
```

This tells Claude Code to use the system ripgrep instead.

### DISABLE_AUTOUPDATER=1

Optional but recommended for automated environments:

```bash
export DISABLE_AUTOUPDATER=1
```

## Native Binary Installation

The official installer (`curl -fsSL https://claude.ai/install.sh | bash`) has interactive prompts that hang in automated environments. Instead, download the binary directly:

```bash
GCS_BUCKET="https://storage.googleapis.com/claude-code-dist-86c565f3-f756-42ad-8dfa-d59b1c096819/claude-code-releases"
VERSION=$(curl -fsSL "$GCS_BUCKET/latest")
ARCH=$(uname -m)
case "$ARCH" in
  aarch64|arm64) PLATFORM="linux-arm64-musl" ;;
  x86_64) PLATFORM="linux-x64-musl" ;;
esac
BINARY_URL="$GCS_BUCKET/$VERSION/$PLATFORM/claude"
mkdir -p ~/.local/bin
curl -fsSL "$BINARY_URL" -o ~/.local/bin/claude
chmod +x ~/.local/bin/claude
```

Note: The platform names are `linux-arm64-musl` and `linux-x64-musl`, not the standard Rust target triples.

## Home Directory Permissions (Lima-specific)

Lima VMs may create the user's home directory with root ownership, preventing Claude Code from writing configuration files.

### Symptoms

- Claude Code starts but shows nothing (blank screen)
- Debug logs show: `Error: EACCES: permission denied, open '/home/user/.claude.json'`

### Solution

```bash
sudo chown $(whoami):$(whoami) ~
```

**Note**: Don't use `chown -R` (recursive) if `~/.claude` is mounted from the host - it will fail on the mount point.

## Config File (~/.claude.json)

Claude Code requires `~/.claude.json` to exist and be writable. If it doesn't exist and can't be created, Claude Code hangs silently.

### Create Minimal Config

```bash
echo '{}' > ~/.claude.json
chmod 600 ~/.claude.json
```

### Share OAuth Tokens from Host

For Lima VMs, copy the host's config to share authentication:

```bash
# In Lima provision script
cat > ~/.claude.json << 'EOF'
<contents of host ~/.claude.json>
EOF
chmod 600 ~/.claude.json
```

## Debugging Silent Hangs

When Claude Code hangs with no output, use these techniques:

### 1. Check Debug Logs

Claude Code writes debug logs to `~/.claude/debug/`:

```bash
# Find recent logs
ls -lt ~/.claude/debug/*.txt | head -5

# Check for errors
grep "ERROR" $(ls -t ~/.claude/debug/*.txt | head -1)

# Watch logs in real-time during a run
touch /tmp/marker
claude -p "test" &
sleep 5
find ~/.claude/debug -newer /tmp/marker -exec cat {} \;
kill %1
```

### 2. Use strace

```bash
# See what syscalls are blocking
strace -f ~/.local/bin/claude -p "hello" 2>&1 | head -200

# Focus on network activity
strace -e trace=socket,connect,write -f claude -p "hello" 2>&1 | tail -100

# Check what the process is waiting on
claude &
PID=$!
sleep 2
cat /proc/$PID/wchan  # Shows: do_epoll_wait if waiting for I/O
strace -p $PID        # Attach to see live syscalls
```

### 3. Check File Descriptors

```bash
claude &
PID=$!
sleep 2
ls -la /proc/$PID/fd/  # Shows all open files
```

### 4. Test Specific Functionality

```bash
# Version works (no runtime init)
claude --version

# Headless mode (tests API without TUI)
claude -p "hello"

# With timeout to avoid infinite hang
timeout 10 claude -p "hello"
```

## Common Error Messages in Debug Logs

### Permission Denied on .claude.json

```
[ERROR] Failed to save config with lock: Error: ENOENT: no such file or directory, lstat '/home/user/.claude.json'
[DEBUG] Failed to write file atomically: Error: EACCES: permission denied
```

**Solution**: Fix home directory permissions and create the file.

### enabledPlatforms TypeError

```
[DEBUG] Failed to check enabledPlatforms: TypeError: undefined is not an object (evaluating 'nK.join')
```

This is a non-fatal error that can be ignored.

## Complete Working Setup

```bash
# Install dependencies
apk add libgcc libstdc++ ripgrep

# Fix home directory
sudo chown $(whoami):$(whoami) ~

# Create config
echo '{}' > ~/.claude.json
chmod 600 ~/.claude.json

# Download binary
mkdir -p ~/.local/bin
GCS_BUCKET="https://storage.googleapis.com/claude-code-dist-86c565f3-f756-42ad-8dfa-d59b1c096819/claude-code-releases"
VERSION=$(curl -fsSL "$GCS_BUCKET/latest")
PLATFORM="linux-arm64-musl"  # or linux-x64-musl
curl -fsSL "$GCS_BUCKET/$VERSION/$PLATFORM/claude" -o ~/.local/bin/claude
chmod +x ~/.local/bin/claude

# Run with required env var
USE_BUILTIN_RIPGREP=0 ~/.local/bin/claude
```

## Ansible Provisioning

See `src/clauded/roles/claude_code/tasks/main.yml` for the complete Ansible role that handles all of the above automatically.

Key tasks:
1. Install musl dependencies (libgcc, libstdc++, ripgrep)
2. Get remote username and home directory
3. Create `.local/bin` directory with correct ownership
4. Download Claude Code binary directly (bypassing interactive installer)
5. Create `~/.claude.json` if it doesn't exist
6. Configure environment variables in `/etc/profile.d/claude.sh`

## Lima VM Configuration

See `src/clauded/lima.py` for Lima-specific handling:

1. Mount `~/.claude` directory from host (settings, skills, commands)
2. Copy `~/.claude.json` from host if it exists (OAuth tokens)
3. Set `USE_BUILTIN_RIPGREP=0` when invoking claude shell
