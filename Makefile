# Makefile for clauded
#
# Installation:
#   make install         Install clauded for current user (~/.local/bin)
#
# Development:
#   make sync          Sync dependencies
#   make dev           Install with dev dependencies
#   make hooks         Install pre-commit hooks
#   make test          Run tests
#   make coverage      Run tests with coverage
#   make lint          Run linter (ruff)
#   make format        Format code (ruff)
#   make typecheck     Run type checker (mypy)
#   make check         Run all checks (lint, typecheck, test)
#   make build         Build wheel
#   make clean         Clean build artifacts

.PHONY: install sync dev test coverage lint format typecheck check build clean help hooks

# Default target
help:
	@echo "clauded commands:"
	@echo ""
	@echo "Installation:"
	@echo "  make install     Install clauded for current user (~/.local/bin)"
	@echo ""
	@echo "Development:"
	@echo "  make sync        Sync dependencies"
	@echo "  make dev         Install with dev dependencies"
	@echo "  make hooks       Install pre-commit hooks"
	@echo "  make test        Run tests"
	@echo "  make coverage    Run tests with coverage report"
	@echo "  make lint        Run linter (ruff)"
	@echo "  make format      Format code (ruff)"
	@echo "  make typecheck   Run type checker (mypy)"
	@echo "  make check       Run all checks"
	@echo "  make build       Build wheel"
	@echo "  make clean       Clean build artifacts"

# ----------------------------------------------------------------------------
# Installation
# ----------------------------------------------------------------------------

install: build
	uv tool uninstall clauded 2>/dev/null || true
	uv tool install dist/clauded-*.whl

# ----------------------------------------------------------------------------
# Development
# ----------------------------------------------------------------------------

sync:
	uv sync --inexact

dev:
	uv sync --extra dev

hooks:
	uv sync --extra dev
	@mkdir -p .git/hooks
	@ln -sf ../../.githooks/pre-commit .git/hooks/pre-commit
	@chmod +x .githooks/pre-commit
	@echo "Installed pre-commit hook from .githooks/"

test: dev
	uv run pytest tests/ -v

coverage:
	uv run pytest tests/ --cov=clauded --cov-report=term-missing --cov-report=html
	@echo "HTML report: htmlcov/index.html"

lint:
	uv run ruff check src/ tests/

format:
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/

typecheck:
	uv run mypy src/

check: lint typecheck test

build:
	uv build --wheel

clean:
	rm -rf build/ dist/ *.egg-info/ htmlcov/ .coverage .pytest_cache/ .mypy_cache/ .ruff_cache/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
