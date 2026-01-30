# MongoDB Tools Support

## Problem Statement

Developers working with MongoDB need the MongoDB command-line tools (mongodump, mongorestore, mongoexport, mongoimport, etc.) available in their clauded VMs for database operations. While MongoDB detection has been implemented (from docker-compose, environment variables, and ORM dependencies), the actual provisioning of MongoDB tools via Ansible is not yet complete.

Currently, if a user selects MongoDB in the wizard:
- Detection works correctly
- Wizard accepts the selection
- Config saves with `databases: [mongodb]`
- **But**: Provisioning silently skips MongoDB (no Ansible role exists)

**Note**: The full MongoDB server is not available in Alpine Linux repositories (removed after Alpine 3.9 due to licensing). This feature provides the MongoDB CLI tools package (`mongodb-tools`) which includes utilities for working with remote MongoDB instances.

## Core Functionality

Implement MongoDB tools provisioning so that VMs include MongoDB CLI utilities when selected.

## Functional Requirements

### FR-1: Ansible Role
- Create `roles/mongodb/tasks/main.yml` with Alpine apk installation
- Install `mongodb-tools` package via apk (from community repository)
- Verify installation by checking tool availability

### FR-2: Provisioner Integration
- Add role selection logic in `provisioner.py` `_get_roles()` method:
  ```python
  if "mongodb" in self.config.databases:
      roles.append("mongodb")
  ```

## Critical Constraints

### CC-1: Alpine Linux Compatibility
- Must use Alpine-native `mongodb-tools` package from apk community repository
- Must be compatible with ARM64 (Apple Silicon)

### CC-2: Idempotent Provisioning
- Role must be safe to re-run multiple times
- Should not fail if mongodb-tools is already installed

## Integration Points

### Detection System
- Already implemented in `src/clauded/detect/database.py`
- Detects from: docker-compose images, MONGODB_URI env vars, ORM dependencies
- Works across Python, Node.js, Java, and Go ecosystems

### Wizard
- Already implemented in `src/clauded/wizard.py`
- MongoDB appears as database option
- Can be selected/deselected by user

### Configuration
- Already supported in config schema
- `environment.databases: [mongodb]` is valid YAML

## Out of Scope

- MongoDB server installation (not available in Alpine)
- MongoDB authentication configuration
- Replica set configuration
- MongoDB Compass or GUI tools
- Custom MongoDB configuration files

## Acceptance Criteria

- [ ] Ansible role `roles/mongodb/` exists with `tasks/main.yml`
- [ ] `provisioner.py` `_get_roles()` includes mongodb role when selected
- [ ] MongoDB tools (mongodump, etc.) are available after provisioning
- [ ] Provisioning is idempotent (safe to re-run)
- [ ] Tests verify MongoDB role selection
- [ ] Documentation updated to reflect MongoDB tools as implemented
