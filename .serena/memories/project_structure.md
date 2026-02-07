# Project Structure

## Directory Layout
```
clauded/
├── src/clauded/           # Main package source
│   ├── cli.py             # CLI entry point (Click-based)
│   ├── config.py          # Config management (.clauded.yaml)
│   ├── lima.py            # Lima VM operations
│   ├── provisioner.py     # Ansible integration
│   ├── wizard.py          # Interactive setup wizard
│   ├── downloads.py       # Download and cloud image management
│   ├── downloads.yml      # Cloud image metadata
│   ├── constants.py       # Constants and configuration
│   ├── spinner.py         # CLI spinner utilities
│   ├── detect/            # Project detection module
│   ├── linguist/          # Vendored Linguist data
│   └── roles/             # Ansible roles (21 roles)
├── tests/                 # Test suite (mirrors src structure)
├── docs/                  # Technical documentation
├── specs/                 # Specifications and user stories
├── .githooks/             # Git hooks (pre-commit)
├── .github/               # GitHub workflows
├── Makefile               # Development automation
├── pyproject.toml         # Project metadata and dependencies
├── hatch_build.py         # Custom build hook
├── CHANGELOG.md           # Version history
├── CLAUDE.md              # AI agent instructions
└── README.md              # User documentation
```

## Key Files

### Configuration
- `pyproject.toml`: Project metadata, dependencies, tool configuration
- `.clauded.yaml`: Per-project VM configuration (user-facing)
- `.pre-commit-config.yaml`: Pre-commit hook configuration
- `hatch_build.py`: Custom build hook for including YAML files

### Source Code Entry Points
- `src/clauded/cli.py`: Main CLI entry point (`clauded` command)
- `src/clauded/config.py`: Configuration schema and validation
- `src/clauded/wizard.py`: Interactive configuration wizard

### Build Artifacts (gitignored)
- `dist/`: Built wheels
- `.venv/`: Virtual environment (managed by uv)
- `__pycache__/`: Python bytecode
- `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`: Tool caches
- `htmlcov/`: Coverage HTML reports

## Module Responsibilities

### Core Modules
- **cli.py**: Command-line interface, argument parsing, command routing
- **config.py**: Load/save/validate `.clauded.yaml` configuration
- **lima.py**: Interface to limactl for VM operations
- **provisioner.py**: Generate and run Ansible playbooks
- **wizard.py**: Interactive menu system for configuration
- **downloads.py**: Cloud image download and management

### Supporting Modules
- **detect/**: Auto-detect project languages, versions, frameworks, databases
- **linguist/**: Language detection data (vendored from GitHub Linguist)
- **roles/**: Ansible roles for provisioning (Python, Node, Java, databases, etc.)
- **constants.py**: Shared constants (versions, defaults)
- **spinner.py**: CLI user feedback

## Testing Structure
- Tests in `tests/` mirror structure of `src/clauded/`
- Test files use `test_*.py` naming pattern
- Fixtures defined in individual test files or conftest.py
- Coverage requirement: 80% minimum
