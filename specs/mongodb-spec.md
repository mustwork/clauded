# MongoDB Database Support

## Problem Statement

Developers using MongoDB need the database automatically provisioned in their clauded VMs. While MongoDB detection has been implemented (from docker-compose, environment variables, and ORM dependencies), the actual provisioning via Ansible is not yet complete.

Currently, if a user selects MongoDB in the wizard:
- Detection works correctly
- Wizard accepts the selection
- Config saves with `databases: [mongodb]`
- **But**: Provisioning silently skips MongoDB (no Ansible role exists)

## Core Functionality

Implement MongoDB database provisioning so that VMs include a running MongoDB instance when selected.

## Functional Requirements

### FR-1: Ansible Role
- Create `roles/mongodb/tasks/main.yml` with Alpine apk installation
- Install `mongodb` package via apk
- Configure and start MongoDB service via OpenRC
- Wait for port 27017 to be ready before completing

### FR-2: Provisioner Integration
- Add role selection logic in `provisioner.py` `_get_roles()` method:
  ```python
  if "mongodb" in self.config.databases:
      roles.append("mongodb")
  ```

### FR-3: Service Configuration
- Enable MongoDB service at boot
- Start service after installation
- Verify service is listening on port 27017

## Critical Constraints

### CC-1: Alpine Linux Compatibility
- Must use Alpine-native `mongodb` package from apk
- Must work with OpenRC init system
- Must be compatible with ARM64 (Apple Silicon)

### CC-2: Idempotent Provisioning
- Role must be safe to re-run multiple times
- Should not fail if MongoDB is already installed
- Should not duplicate configuration

### CC-3: Resource Considerations
- MongoDB can be memory-intensive
- Consider documenting recommended VM resources (16GB+ RAM)

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

- MongoDB authentication configuration
- Replica set configuration
- MongoDB Compass or GUI tools
- Custom MongoDB configuration files
- Sharding or clustering

## Acceptance Criteria

- [ ] Ansible role `roles/mongodb/` exists with `tasks/main.yml`
- [ ] `provisioner.py` `_get_roles()` includes mongodb role when selected
- [ ] MongoDB service starts automatically on VM boot
- [ ] Port 27017 is accessible after provisioning
- [ ] Provisioning is idempotent (safe to re-run)
- [ ] Tests verify MongoDB role selection
- [ ] Documentation updated to reflect MongoDB as fully implemented
