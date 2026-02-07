# Task Completion Checklist

When completing a task, ALWAYS perform these steps in order:

## 1. Code Quality Checks
```bash
make format     # Auto-format code
make lint       # Check linting (must pass)
make typecheck  # Check types (must pass)
```

## 2. Run Tests
```bash
make test       # All tests must pass
```

## 3. Update CHANGELOG.md
- ALL feature work and bug fixes MUST include a CHANGELOG.md entry under `[Unreleased]`
- Use appropriate section: `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, or `Security`
- Keep entries concise but descriptive

## 4. Clean Up Temporary Files
- Remove any temporary markdown files
- Remove temporary code backups
- Remove debugging artifacts
- Do NOT create result markdown documents unless absolutely necessary

## 5. Final Verification
```bash
make check      # Run all checks together (lint + typecheck + test)
```

## Pre-commit Hook
If pre-commit hooks are installed, they will automatically run on commit:
- ruff (auto-fix)
- ruff-format
- mypy
- pytest

All must pass before commit is allowed.

## Important Notes
- NEVER rewrite git history
- NEVER tailor production code to tests (tests adapt to production code, not vice versa)
- Always use `uv` for package management
- Type hints are REQUIRED (mypy strict mode)
- Minimum test coverage: 80%
