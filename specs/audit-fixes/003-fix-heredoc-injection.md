# Fix Heredoc Injection in gitconfig Copy

**Audit Reference**: Critical #3 | Severity: 5/10
**Source**: `.claude/audit-reports/spec-2026-01-28.md`

## Problem

The Lima VM provision script copies the host `.gitconfig` into the VM using a shell heredoc with delimiter `GITCONFIG_EOF` (`lima.py:161-162`). If the user's `.gitconfig` file contains the exact string `GITCONFIG_EOF` on its own line, the heredoc terminates prematurely, producing a malformed provision script that fails silently or with a cryptic error.

## Requirements

### FR-1: Safe Heredoc Delimiter

Replace the `GITCONFIG_EOF` delimiter with a unique string that cannot reasonably appear in a `.gitconfig` file. The delimiter must be sufficiently unique to avoid accidental collisions.

### FR-2: Alternative - Base64 Encoding

As an alternative approach, the gitconfig content could be base64-encoded and decoded in the provision script, avoiding heredoc parsing entirely:

```
echo '<base64>' | base64 -d > ~/.gitconfig
```

Either approach is acceptable. Choose whichever is simpler.

## Affected Files

- `src/clauded/lima.py:161-162`
- `tests/test_lima.py` (add test with adversarial gitconfig content)
