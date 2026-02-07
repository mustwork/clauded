# Project Overview

## Purpose
`clauded` is a CLI tool that creates lightweight, isolated Linux VMs for each project using Lima (Linux Machines for macOS). It automatically provisions development environments with exact tools, databases, and frameworks needed through declarative configuration and Ansible.

## Key Features
- Isolated per-project VMs with dedicated resources
- Declarative configuration via `.clauded.yaml`
- Interactive setup wizard
- Automatic project detection (languages, versions, frameworks, databases)
- VM lifecycle management (create, start, stop, destroy, reprovision)
- Multi-instance support (multiple terminals can connect to same VM)
- Crash recovery and atomic config updates

## Target Platform
- macOS with Apple Silicon (ARM64)
- Requires Lima installed (`brew install lima`)
- Python 3.12+

## Tech Stack
- **Language**: Python 3.12+
- **CLI Framework**: Click (8.1.7+)
- **Interactive Menus**: simple-term-menu (1.6+)
- **Configuration**: PyYAML (6.0.2+)
- **Provisioning**: Ansible (11.0, <12.0) - pinned to ansible-core 2.18.x
- **Build System**: hatchling with custom hook
- **Package Manager**: uv (for dependency management and virtual environments)

## Core Modules
- `cli.py`: Click-based CLI entry point and command routing
- `config.py`: Configuration management for `.clauded.yaml` files
- `lima.py`: Lima VM lifecycle operations (create, start, stop, destroy)
- `provisioner.py`: Ansible playbook generation and execution
- `wizard.py`: Interactive menu-based setup wizard
- `detect/`: Project detection module
- `linguist/`: Vendored Linguist data
- `roles/`: Ansible roles (21 roles)
