# Code Style & Conventions

## Python Version
- Target: Python 3.12
- Type hints: Required for all function signatures (`disallow_untyped_defs = true`)

## Code Quality Tools

### Ruff (Linting & Formatting)
- Line length: 88 characters
- Target version: py312
- Selected rules:
  - E: pycodestyle errors
  - W: pycodestyle warnings
  - F: pyflakes
  - I: isort (import sorting)
  - B: flake8-bugbear
  - UP: pyupgrade

### Mypy (Type Checking)
- Strict mode enabled
- `warn_return_any = true`
- `warn_unused_ignores = true`
- `disallow_untyped_defs = true`
- Ignored modules: `questionary.*`, `ansible.*`

### Testing
- Framework: pytest (8.3+)
- Coverage tracking: pytest-cov (5.0+)
- Minimum coverage: 80%
- Test location: `tests/` directory
- Test files: `test_*.py` pattern
- Property-based testing: Hypothesis (6.120+)

## Code Organization
- Source code: `src/clauded/`
- Tests mirror source structure in `tests/`
- Type stubs: types-pyyaml for YAML support

## Documentation Style
- Module docstrings: Brief description at top of file
- Function docstrings: Standard Python docstring format
- Test fixtures: Documented with brief description

## Import Organization
- Standard library imports first
- Third-party imports second
- Local imports last
- Managed by ruff's isort integration
