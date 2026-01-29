# SQLite Database Option - Requirements Specification

## Problem Statement

Node.js projects apparently require SQLite support in the clauded VM environment. Currently, only PostgreSQL, Redis, and MySQL are available as database options. Users need the ability to select SQLite as a database option, and it should be the auto-selected default for Node.js runtimes.

## Core Functionality

Add SQLite as a fourth database option in the clauded configuration system:
- Appears in the wizard alongside PostgreSQL, Redis, and MySQL
- Available for selection by any runtime (Python, Node.js, Java, Go, Rust, Kotlin)
- Auto-selected (pre-checked) when Node.js runtime is detected or selected
- Provisions SQLite in the Alpine Linux VM via Ansible role

## Functional Requirements

### FR1: Wizard Selection
- SQLite appears as a checkbox option in the "── Databases ──" section of the wizard
- Any user can manually select SQLite regardless of runtime
- When Node.js runtime is present, SQLite checkbox is pre-checked by default
- Users can deselect SQLite even if auto-selected

**Acceptance Criteria:**
- `clauded init` wizard shows "sqlite" as a database option
- SQLite can be selected alongside PostgreSQL, Redis, and/or MySQL (not mutually exclusive)
- Running wizard in a Node.js project automatically checks the sqlite option

### FR2: Configuration Storage
- Selected databases are stored in `.clauded.yaml` config file
- SQLite is stored as "sqlite" in the `environment.databases` list
- Configuration follows same pattern as existing databases

**Acceptance Criteria:**
- `.clauded.yaml` can contain `databases: ["sqlite"]` or `databases: ["postgresql", "sqlite"]`
- Config loads and saves correctly with sqlite in databases list

### FR3: Auto-Detection
- SQLite usage is auto-detected from project files
- Detection sources: `.db`/`.sqlite`/`.sqlite3` files, Node.js sqlite packages, database URLs

**Acceptance Criteria:**
- Projects with `better-sqlite3` or `sqlite3` in `package.json` auto-detect SQLite
- Projects with `.db` or `.sqlite` files auto-detect SQLite
- Auto-detection pre-checks SQLite in wizard

### FR4: VM Provisioning
- When SQLite is selected, an Ansible role provisions it in the VM
- SQLite installs via Alpine Linux apk package manager
- Unlike PostgreSQL/Redis/MySQL, SQLite requires no service initialization or startup

**Acceptance Criteria:**
- `clauded start` provisions SQLite when selected in config
- `sqlite3` command is available in the VM after provisioning
- SQLite provisioning succeeds without requiring service management

### FR5: Node.js Auto-Selection
- When Node.js runtime is selected (any version), SQLite is automatically pre-checked in wizard
- Auto-selection occurs whether Node.js is auto-detected or manually selected
- User can still deselect SQLite if not needed

**Acceptance Criteria:**
- Wizard pre-checks sqlite when `node` is set in config/answers
- User can manually uncheck sqlite and proceed without it
- SQLite auto-selection only affects wizard defaults, not final config (user choice wins)

## Critical Constraints

### C1: Database Storage Configuration
- Database file location is entirely user-configurable
- Host-mounted paths persist across VM recreations
- VM-local paths are ephemeral (lost on VM destroy)
- System MUST NOT dictate storage location

**Rationale:** User specified: "configuration is entirely up to user and should be host mounted. if a non-mounted path is specified, that will result in VM-local storage. but we don't want to dictate anything, here."

### C2: Coexistence with Other Databases
- SQLite can coexist with PostgreSQL, Redis, and MySQL simultaneously
- Node.js auto-selection does not prevent selecting other databases
- Multiple databases can be selected in any combination

**Rationale:** User specified: "no override. can coexist side by side"

### C3: User Disclaimer
- When SQLite is selected, display a disclaimer about storage location implications
- Disclaimer should explain host-mounted vs VM-local storage trade-offs
- Exact placement and wording to be determined by architect

**Rationale:** User specified: "you may want to display a disclaimer when selecting sqlite."

### C4: Backwards Compatibility
- Existing `.clauded.yaml` configs without SQLite continue to work
- Existing database options (postgresql, redis, mysql) remain unchanged
- No breaking changes to wizard flow or config schema

## Integration Points

### IP1: Wizard Module
- File: `src/clauded/wizard.py`
- Integration: Add "sqlite" to database checkbox options (around line 127)
- Integration: Add "sqlite" to `database_options` set (around line 142)

### IP2: Wizard Integration Module
- File: `src/clauded/detect/wizard_integration.py`
- Integration: Add "sqlite" to database checkbox options (around line 200)
- Integration: Add "sqlite" to `database_options` set (around line 215)
- Integration: Pre-check sqlite when Node.js is selected

### IP3: Database Detection Module
- File: `src/clauded/detect/database.py`
- Integration: Add SQLite detection patterns for:
  - `.db`, `.sqlite`, `.sqlite3` files in project
  - `sqlite3`, `better-sqlite3` in `package.json`
  - `sqlite3` in Python dependencies (optional - might be too noisy)
  - Database URLs starting with `sqlite://`

### IP4: Provisioner Module
- File: `src/clauded/provisioner.py`
- Integration: Add conditional role mapping (around line 118):
  ```python
  if "sqlite" in self.config.databases:
      roles.append("sqlite")
  ```

### IP5: Ansible Role
- New file: `src/clauded/roles/sqlite/tasks/main.yml`
- Integration: Create Ansible playbook to install SQLite via apk
- Note: SQLite is file-based, no service management needed (unlike postgresql/redis/mysql)

## User Preferences

### Architecture Preferences
- Follow existing patterns for database options (minimize deviation)
- Treat SQLite as a first-class database option with same integration as PostgreSQL
- Keep Ansible role simple - SQLite doesn't need service initialization

### Implementation Preferences
- Auto-selection logic should be obvious and maintainable
- Detection patterns should be conservative (avoid false positives)
- Disclaimer placement should be natural (not intrusive)

## Codebase Context

See `.claude/exploration/sqlite-database-option-context.md` for exploration findings.

**Key patterns to follow:**
- Database options are hardcoded in two places: `wizard.py` and `wizard_integration.py`
- Detection returns `DetectedItem` objects with confidence levels (high/medium/low)
- Provisioner uses simple if-in checks to map config to Ansible roles
- Ansible roles follow pattern: install packages → configure → start service (SQLite will be simpler - no service)

**Existing database architecture:**
- PostgreSQL: Server-based, requires initialization and service startup
- Redis: Server-based, requires service startup
- MySQL/MariaDB: Server-based, requires initialization and service startup
- SQLite: File-based, no server process (simpler role)

## Related Artifacts

- **Exploration Context**: `.claude/exploration/sqlite-database-option-context.md`
- **Configuration Schema**: `src/clauded/config.py`
- **Existing Database Roles**: `src/clauded/roles/postgresql/`, `src/clauded/roles/redis/`, `src/clauded/roles/mysql/`

## Out of Scope

The following are explicitly NOT part of this feature:
- SQLite-specific performance tuning or optimization
- Migration tools between PostgreSQL and SQLite
- SQLite version selection (use whatever Alpine Linux provides)
- SQLite GUI tools or management interfaces
- Custom SQLite compilation or configuration
- SQLite-specific documentation beyond basic usage
- ORM-specific SQLite adapters or examples
- Connection pooling for SQLite (file-based, not network-based)

## Open Questions for Architect

1. **Auto-selection timing**: Should Node.js → SQLite auto-selection happen during detection, wizard pre-population, or config generation?

2. **Disclaimer placement**: Where should the storage location disclaimer appear?
   - During wizard when SQLite is checked?
   - In terminal output after provisioning?
   - In documentation only?

3. **Detection sensitivity**: Should we detect `import sqlite3` in Python code?
   - Python includes sqlite3 by default (might cause false positives)
   - Or only detect explicit `.db` files and Node.js packages?

4. **SQLite package verification**: Is SQLite pre-installed in Alpine Linux base image?
   - If yes, role only needs to verify installation
   - If no, role needs to install `sqlite` package

---

**Note**: This is a requirements specification, not an architecture design.
Edge cases, error handling details, and implementation approach will be
determined by the integration-architect during architecture phase.
