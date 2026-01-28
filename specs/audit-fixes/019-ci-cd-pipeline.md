# CI/CD Pipeline with Coverage Enforcement

**Audit Reference**: Test Infrastructure #24, #25 | Severity: 6/10
**Source**: `.claude/audit-reports/spec-2026-01-28.md`

## Problem

The project has no CI/CD pipeline. Pre-commit hooks run locally but are:
- Easily bypassed with `--no-verify`
- Not enforced on the remote repository
- Not run for external contributors

There is no automated quality gate for pull requests or pushes. Test coverage is not enforced despite `pytest-cov` being configured.

## Requirements

### FR-1: GitHub Actions Workflow

Create a CI workflow (`.github/workflows/test.yml`) that runs on:
- Push to `master`
- Pull requests targeting `master`

The workflow must:
1. Set up Python 3.12
2. Install uv
3. Install dependencies with `uv sync --extra dev`
4. Run linting: `uv run ruff check src/ tests/`
5. Run type checking: `uv run mypy src/`
6. Run tests with coverage: `uv run pytest tests/ --cov=clauded --cov-report=term-missing --cov-fail-under=80`

### FR-2: Coverage Threshold

Enforce a minimum 80% line coverage via `--cov-fail-under=80`. The CI workflow must fail if coverage drops below this threshold.

Also add the threshold to `pyproject.toml`:
```toml
[tool.coverage.report]
fail_under = 80
```

### FR-3: Status Checks

The GitHub Actions workflow must report status on PRs (pass/fail). Branch protection rules are outside scope of this spec but recommended.

## Affected Files

- `.github/workflows/test.yml` (new)
- `pyproject.toml` (coverage threshold)
