# Migration from Alpine Linux

Alpine Linux is no longer supported as a guest OS for `clauded` VMs. Ubuntu 24.04 LTS is now the sole supported distribution.

## Who needs to migrate

You need to migrate if your project's `.clauded.yaml` contains:

```yaml
vm:
  distro: alpine
```

When this is detected, `clauded` exits immediately with an error and migration instructions. No VM, file, or process changes occur automatically.

## Migration steps

1. **Destroy the existing Alpine VM:**

   ```
   clauded --destroy
   ```

   Project files are safe — they live on the host filesystem and are mounted into the VM. Destroying the VM only removes the VM itself.

2. **Remove the `distro: alpine` line from `.clauded.yaml`:**

   Open `.clauded.yaml` and delete the line `distro: alpine` under the `vm:` section.

3. **Provision a fresh Ubuntu VM:**

   ```
   clauded
   ```

   The wizard opens at the Python version question (the distro question no longer exists). Your existing tool selections, language versions, and project settings are preserved in `.clauded.yaml`.

## What changes after migration

- The VM runs Ubuntu 24.04 LTS instead of Alpine Linux 3.x.
- Package installation uses `apt` instead of `apk`.
- Service management uses `systemd` instead of OpenRC.
- The `--distro` CLI flag is removed; it is no longer accepted.
- The `vm.distro` config field is no longer emitted by `clauded`; existing `distro: ubuntu` lines are silently ignored.

## Why Alpine support was removed

See `CHANGELOG.md` for the full rationale. The short version: maintaining two role trees (alpine + ubuntu variants) for every tool and language imposed a ~2x maintenance cost with diminishing returns in a VM context where boot-time and image-size differences are not load-bearing.
