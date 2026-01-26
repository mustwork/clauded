# Makefile for clauded
#
# Development:
#   make install       Install dependencies
#   make dev           Install with dev dependencies
#   make test          Run tests
#   make coverage      Run tests with coverage
#   make lint          Run linter (ruff)
#   make format        Format code (ruff)
#   make typecheck     Run type checker (mypy)
#   make check         Run all checks (lint, typecheck, test)
#   make build         Build wheel
#   make clean         Clean build artifacts
#
# Lima VM (legacy):
#   make bootstrap     Provision Lima VM with Ansible
#   make shell         Shell into Lima VM

.PHONY: install dev test coverage lint format typecheck check build clean bootstrap shell help

# Default target
help:
	@echo "clauded development commands:"
	@echo ""
	@echo "  make install     Install dependencies"
	@echo "  make dev         Install with dev dependencies"
	@echo "  make test        Run tests"
	@echo "  make coverage    Run tests with coverage report"
	@echo "  make lint        Run linter (ruff)"
	@echo "  make format      Format code (ruff)"
	@echo "  make typecheck   Run type checker (mypy)"
	@echo "  make check       Run all checks"
	@echo "  make build       Build wheel"
	@echo "  make clean       Clean build artifacts"
	@echo ""
	@echo "Lima VM commands:"
	@echo "  make bootstrap   Provision Lima VM"
	@echo "  make shell       Shell into Lima VM"

# ----------------------------------------------------------------------------
# Development
# ----------------------------------------------------------------------------

install:
	uv sync

dev:
	uv sync --extra dev

test:
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
	uv build

clean:
	rm -rf build/ dist/ *.egg-info/ htmlcov/ .coverage .pytest_cache/ .mypy_cache/ .ruff_cache/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# ----------------------------------------------------------------------------
# Lima VM (legacy bootstrap)
# ----------------------------------------------------------------------------

INSTANCE ?= claude
HOST_ALIAS := lima-$(INSTANCE)
LIMA_SSHCONF := $(HOME)/.lima/$(INSTANCE)/ssh.config

bootstrap:
	@test -f "$(LIMA_SSHCONF)" || (echo "Missing $(LIMA_SSHCONF). Start the VM first: limactl start $(INSTANCE)"; exit 1)
	@ANSIBLE_SSH_ARGS="-F $(LIMA_SSHCONF)" \
	  uv run ansible-playbook -c ssh -i ansible/inventory.ini ansible/site.yml \
	  -l "$(HOST_ALIAS)"

shell:
	@limactl shell "$(INSTANCE)"
