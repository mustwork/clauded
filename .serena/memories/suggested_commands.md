# Suggested Development Commands

## Package Management (uv)
All dependency management uses `uv`:
```bash
uv sync --inexact          # Sync dependencies
uv sync --extra dev        # Install with dev dependencies
uv run <command>           # Run command in virtual environment
```

## Development Setup
```bash
make dev                   # Install with dev dependencies
make hooks                 # Install pre-commit hooks
```

## Testing
```bash
make test                  # Run all tests with pytest
uv run pytest tests/ -v    # Run tests directly
make coverage              # Run tests with coverage report (htmlcov/index.html)
uv run pytest tests/ --cov=clauded --cov-report=term-missing --cov-report=html
```

## Code Quality
```bash
make lint                  # Run ruff linter
uv run ruff check src/ tests/

make format                # Auto-format code with ruff
uv run ruff format src/ tests/
uv run ruff check --fix src/ tests/

make typecheck             # Run mypy type checker
uv run mypy src/

make check                 # Run all checks (lint + typecheck + test)
```

## Build & Installation
```bash
make build                 # Build wheel (outputs to dist/)
uv build --wheel

make install               # Install clauded CLI tool for current user
uv tool uninstall clauded 2>/dev/null || true
uv tool install dist/clauded-*.whl

make clean                 # Clean build artifacts
```

## Pre-commit Hooks
```bash
uv run pre-commit install           # Install hooks
uv run pre-commit run --all-files   # Run manually on all files
```

Hooks run automatically on commit:
- ruff (linting with auto-fix)
- ruff-format (formatting)
- mypy (type checking on src/)
- pytest (tests with short traceback)

## Project Commands
```bash
clauded                    # Create/connect to VM
clauded --stop             # Stop VM
clauded --reprovision      # Update environment after config changes
clauded --edit             # Re-run wizard and reprovision
clauded --detect           # Show detected project technologies
clauded --destroy          # Destroy VM
```

## Common System Commands (Linux)
Standard Linux tools available:
- `git` - version control
- `ls`, `cd`, `pwd` - file navigation
- `grep`, `find` - searching
- `cat`, `less` - file viewing
