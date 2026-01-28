# User Stories

## Personas

### Backend Developer
Develops backend applications using Python and/or Node.js. Needs isolated development environments per project. Requires databases and development tools without cluttering their local machine. Primary user of core functionality.

### Full-Stack Developer
Works on projects combining multiple technologies (Python, Node.js, databases). Needs end-to-end testing with Playwright. Uses AWS for deployment. Requires consistent, reproducible development environments across team members.

### DevOps/Infrastructure Engineer
Manages VM provisioning and configuration. Uses infrastructure-as-code patterns (Ansible). Needs repeatability and configuration version control. Benefits from simplified VM lifecycle management.

### Solo Developer
Works on side projects locally. Wants quick setup without complex configuration. Appreciates sensible defaults. Values simplicity and guided interactive setup.

### Team Lead
Wants consistent environments across team members. Needs ability to onboard new developers quickly. Benefits from `.clauded.yaml` being committed to version control. Uses reprovision capability to update team environments.

### AI-Assisted Developer
Uses Claude Code within development environments. Needs Claude Code CLI pre-installed and ready to use. Benefits from integrated AI-assisted development workflow.

---

## Epics

### Epic 1: VM Lifecycle Management

Per-project isolated Linux VMs with creation, start/stop, and destruction capabilities.

#### [Implemented] Story: Create Project-Specific VM

**As a** Backend Developer, **I want** to create a project-specific VM by running a single command, **so that** I have an isolated environment without affecting my host machine.

**Acceptance Criteria**:
- [ ] Running `clauded` in a project directory creates a new VM
- [ ] VM name is deterministically generated from project path
- [ ] VM is created with configured resources (CPU, memory, disk)
- [ ] VM is provisioned with selected tools and databases
- [ ] Process completes within 5 minutes on standard network

#### [Implemented] Story: Define VM Resources in Config

**As a** DevOps Engineer, **I want** to define VM resources (CPU, RAM, disk) in a persistent config file, **so that** I can version control and reproduce environments exactly.

**Acceptance Criteria**:
- [ ] `.clauded.yaml` contains VM resource specifications
- [ ] Config can be committed to git
- [ ] Team members get identical environments from same config
- [ ] Resources are applied when VM is created

#### [Implemented] Story: Use Sensible Defaults

**As a** Solo Developer, **I want** sensible defaults (4 CPU, 8GB RAM, 20GB disk), **so that** I can start immediately without configuration complexity.

**Acceptance Criteria**:
- [ ] Default VM config uses 4 CPUs
- [ ] Default VM config uses 8GiB memory
- [ ] Default VM config uses 20GiB disk
- [ ] Defaults can be accepted without customization in wizard

#### [Implemented] Story: Start and Stop VMs

**As a** Solo Developer, **I want** to start/stop VMs without destroying them, **so that** I can pause work and save resources during off-hours.

**Acceptance Criteria**:
- [ ] `clauded --stop` stops running VM
- [ ] `clauded` (default) starts stopped VM
- [ ] VM state persists between stops/starts
- [ ] Start operation completes in <15 seconds

#### [Implemented] Story: Destroy VM and Config

**As a** Backend Developer, **I want** to destroy a VM and optionally remove its config, **so that** I can clean up when a project is complete.

**Acceptance Criteria**:
- [ ] `clauded --destroy` removes the VM
- [ ] User is prompted whether to delete `.clauded.yaml`
- [ ] Both VM and disk are fully removed
- [ ] Command provides confirmation before destruction

---

### Epic 2: Environment-as-Code Configuration

Declarative `.clauded.yaml` configuration for reproducible development environments.

#### [Implemented] Story: Interactive Environment Setup

**As a** Full-Stack Developer, **I want** to answer interactive prompts about my tech stack, **so that** the tool automatically generates an appropriate configuration.

**Acceptance Criteria**:
- [ ] Running `clauded` without config launches wizard
- [ ] Wizard prompts for Python version (3.10/3.11/3.12/None)
- [ ] Wizard prompts for Node.js version (18/20/22/None)
- [ ] Wizard prompts for tools (docker, git, aws-cli, gh)
- [ ] Wizard prompts for databases (postgresql, redis, mysql)
- [ ] Wizard prompts for frameworks (claude-code, playwright)
- [ ] Wizard generates valid `.clauded.yaml`

#### [Implemented] Story: Version Control Configuration

**As a** Team Lead, **I want** to commit `.clauded.yaml` to version control, **so that** all team members get the same environment setup.

**Acceptance Criteria**:
- [ ] `.clauded.yaml` is plain text YAML
- [ ] Config contains no secrets or user-specific paths
- [ ] Config can be committed to git
- [ ] Team members running `clauded` get identical VMs

#### [Implemented] Story: Customize VM Resources

**As a** Backend Developer, **I want** to customize VM resources (CPU, RAM, disk), **so that** I can allocate appropriate resources for my project size.

**Acceptance Criteria**:
- [ ] Wizard offers resource customization option
- [ ] Can specify CPU count
- [ ] Can specify memory in GiB
- [ ] Can specify disk size in GiB
- [ ] Resources are applied to created VM

#### [Implemented] Story: Deterministic VM Naming

**As a** DevOps Engineer, **I want** unique VM names generated from the project path, **so that** I can work on multiple projects without VM name conflicts.

**Acceptance Criteria**:
- [ ] VM name is generated from project path hash
- [ ] Same project path always generates same VM name
- [ ] VM name format is `clauded-{8-char-hash}`
- [ ] Different projects get different VM names

#### [Implemented] Story: Accept Defaults Quickly

**As a** Solo Developer, **I want** the wizard to have sensible defaults (Python 3.12, Node 20, Docker, Git), **so that** I can accept defaults and get started quickly.

**Acceptance Criteria**:
- [ ] Wizard pre-selects Python 3.12
- [ ] Wizard pre-selects Node 20
- [ ] Wizard pre-selects Docker and Git
- [ ] Can proceed with defaults without customization

---

### Epic 3: Runtime Environment Provisioning

Ansible-based installation of tools, databases, and frameworks.

#### [Implemented] Story: Install Python Version

**As a** Python Developer, **I want** my chosen Python version (3.10, 3.11, 3.12) to be installed and set as default, **so that** I can develop without environment mismatch issues.

**Acceptance Criteria**:
- [ ] Selected Python version is installed via apk
- [ ] Python is set as system default (`python3` command)
- [ ] pip is available for the installed version
- [ ] `python3 --version` shows selected version

#### [Implemented] Story: Install Node.js Version

**As a** Node.js Developer, **I want** my chosen Node.js version (18, 20, 22) to be installed, **so that** I have the correct runtime for my project.

**Acceptance Criteria**:
- [ ] Selected Node.js version is installed via apk
- [ ] `node --version` shows selected version
- [ ] npm is available
- [ ] Node.js is accessible system-wide

#### [Implemented] Story: Pre-install Docker

**As a** Backend Developer, **I want** Docker to be pre-installed, **so that** I can containerize and test services immediately.

**Acceptance Criteria**:
- [ ] Docker is installed and running
- [ ] User is added to docker group (no sudo needed)
- [ ] `docker ps` works without errors
- [ ] Docker daemon starts automatically

#### [Implemented] Story: Select Databases

**As a** Full-Stack Developer, **I want** PostgreSQL, Redis, and MySQL available as optional selections, **so that** I can choose the databases my project needs.

**Acceptance Criteria**:
- [ ] Can select PostgreSQL (installs postgresql + contrib + postgresql-dev)
- [ ] Can select Redis (installs redis)
- [ ] Can select MySQL (installs mariadb)
- [ ] Selected databases are running and enabled
- [ ] Database services start automatically on VM boot

#### [Implemented] Story: Install AWS CLI

**As a** DevOps Engineer, **I want** AWS CLI installed when selected, **so that** my team can manage AWS resources from the VM.

**Acceptance Criteria**:
- [ ] AWS CLI v2 is installed for ARM64
- [ ] `aws --version` shows AWS CLI v2
- [ ] AWS CLI is accessible system-wide

#### [Implemented] Story: Install GitHub CLI

**As a** Developer, **I want** GitHub CLI installed when selected, **so that** I can interact with GitHub workflows directly from the VM.

**Acceptance Criteria**:
- [ ] GitHub CLI (`gh`) is installed
- [ ] `gh --version` works
- [ ] GitHub CLI is accessible system-wide

#### [Implemented] Story: Pre-install Playwright

**As a** Testing Developer, **I want** Playwright pre-installed with browser binaries, **so that** I can write and run end-to-end tests immediately.

**Acceptance Criteria**:
- [ ] Playwright is installed globally via npm
- [ ] Browser binaries are downloaded (`playwright install`)
- [ ] Playwright commands are accessible system-wide

#### [Implemented] Story: Pre-install Claude Code

**As an** AI-Assisted Developer, **I want** Claude Code CLI pre-installed, **so that** I can use AI features in my development environment.

**Acceptance Criteria**:
- [ ] Claude Code CLI is installed via native installer
- [ ] `claude` command is available in `~/.local/bin`
- [ ] Login shell sources `/etc/profile.d/claude.sh` for PATH and env vars

#### [Implemented] Story: Install Java Version

**As a** Java Developer, **I want** my chosen Java version (11, 17, 21) to be installed and set as default, **so that** I can develop without environment mismatch issues.

**Acceptance Criteria**:
- [ ] Selected Java version is installed via apk (OpenJDK)
- [ ] `java --version` shows selected version
- [ ] Java is set as system default
- [ ] Maven and Gradle support the installed version

#### [Implemented] Story: Install Kotlin Version

**As a** Kotlin Developer, **I want** my chosen Kotlin version (1.9, 2.0) to be installed, **so that** I have the correct compiler for my project.

**Acceptance Criteria**:
- [ ] Selected Kotlin version is downloaded from GitHub releases
- [ ] `kotlin -version` shows selected version
- [ ] Kotlin compiler is accessible system-wide
- [ ] Works with Gradle and Maven

#### [Implemented] Story: Install Rust Version

**As a** Rust Developer, **I want** my chosen Rust version (stable, nightly) to be installed via rustup, **so that** I have the correct toolchain for my project.

**Acceptance Criteria**:
- [ ] Rustup is installed
- [ ] Selected Rust version/channel is installed
- [ ] `rustc --version` shows selected version
- [ ] Cargo is available for package management

#### [Implemented] Story: Install Go Version

**As a** Go Developer, **I want** my chosen Go version (1.24.12, 1.25.6) to be installed, **so that** I have the correct runtime for my project.

**Acceptance Criteria**:
- [ ] Selected Go version is downloaded from go.dev
- [ ] `go version` shows selected version
- [ ] Go is accessible system-wide
- [ ] Go modules work correctly

---

### Epic 4: Project Onboarding and Initialization

Interactive wizard for quick project setup.

#### [Implemented] Story: Learn Options During Setup

**As a** New User, **I want** to run `clauded` without any config and be prompted with setup questions, **so that** I learn about available options while setting up.

**Acceptance Criteria**:
- [ ] Running `clauded` without `.clauded.yaml` starts wizard
- [ ] Wizard explains each option category
- [ ] Wizard shows available choices (versions, tools, databases)
- [ ] Can navigate through all setup steps

#### [Implemented] Story: Select Tools

**As a** Backend Developer, **I want** to select which tools I need (Docker, AWS CLI, GitHub CLI, Git), **so that** I only install what's necessary.

**Acceptance Criteria**:
- [ ] Wizard presents tools as multi-select
- [ ] Can select docker, git, aws-cli, gh
- [ ] Selected tools are provisioned
- [ ] Unselected tools are not installed

#### [Implemented] Story: Select Databases

**As a** Backend Developer, **I want** to select which databases I need (PostgreSQL, Redis, MySQL), **so that** I can choose the exact stack for my project.

**Acceptance Criteria**:
- [ ] Wizard presents databases as multi-select
- [ ] Can select postgresql, redis, mysql
- [ ] Selected databases are provisioned
- [ ] Unselected databases are not installed

#### [Implemented] Story: Select Frameworks

**As a** Full-Stack Developer, **I want** to select frameworks (Playwright, Claude Code), **so that** my development environment includes everything needed for testing and AI assistance.

**Acceptance Criteria**:
- [ ] Wizard presents frameworks as multi-select
- [ ] Can select playwright, claude-code
- [ ] Selected frameworks are provisioned
- [ ] Unselected frameworks are not installed

#### [Implemented] Story: Bypass Wizard with Existing Config

**As a** Returning User, **I want** to bypass the wizard if `.clauded.yaml` exists, **so that** I can quickly reconnect to an existing project VM.

**Acceptance Criteria**:
- [ ] `clauded` skips wizard when `.clauded.yaml` exists
- [ ] Existing config is loaded automatically
- [ ] VM is created/started based on existing config
- [ ] Can immediately connect to VM

---

### Epic 5: VM Shells and Workspace Integration

Seamless shell access with project directory mounting.

#### [Implemented] Story: Enter VM Shell at Workspace

**As a** Developer, **I want** to enter a shell inside the VM at the project workspace, **so that** I can run commands and work naturally in my environment.

**Acceptance Criteria**:
- [ ] `clauded` (default) enters interactive shell
- [ ] Shell working directory is the project path
- [ ] Can execute commands inside VM
- [ ] Exit command returns to host shell

#### [Implemented] Story: Mount Project Directory

**As a** Developer, **I want** my project directory mounted at the same path inside the VM, **so that** changes I make in the editor are immediately available and Claude Code sessions are unique per project.

**Acceptance Criteria**:
- [ ] Host project directory is mounted at the same path in VM
- [ ] Mount is read-write (bidirectional sync)
- [ ] Files changed on host appear in VM immediately
- [ ] Files changed in VM appear on host immediately

#### [Implemented] Story: Edit Files from Host

**As a** Developer, **I want** to mount my host project directory read-write, **so that** I can edit files from my machine and run them in the VM.

**Acceptance Criteria**:
- [ ] Can edit files in host editor (VS Code, etc.)
- [ ] Edited files immediately available in VM
- [ ] Can execute edited files inside VM
- [ ] No manual sync required

#### [Implemented] Story: Start in Workspace Directory

**As a** Developer, **I want** the shell to start in my project directory, **so that** I can immediately begin working without navigating directories.

**Acceptance Criteria**:
- [ ] Shell starts with pwd=project path
- [ ] Project files are immediately visible (`ls`)
- [ ] Can execute project commands without cd

---

### Epic 6: Reprovisioning and Environment Refresh

Update environments without destroying VMs.

#### [Implemented] Story: Update Environment Without Recreating VM

**As a** Backend Developer, **I want** to re-run provisioning with `--reprovision`, **so that** I can update tools and dependencies without losing my VM or data.

**Acceptance Criteria**:
- [ ] `clauded --reprovision` re-runs Ansible
- [ ] Existing VM is updated (not destroyed)
- [ ] VM disk and data are preserved
- [ ] Updated config is applied

#### [Implemented] Story: Team Config Updates

**As a** Team Lead, **I want** to run `clauded --reprovision` when `.clauded.yaml` changes, **so that** the team can all update to the new configuration.

**Acceptance Criteria**:
- [ ] Changed `.clauded.yaml` can be pulled from git
- [ ] `clauded --reprovision` applies new config
- [ ] All team members can sync to updated environment
- [ ] No manual VM recreation needed

#### [Implemented] Story: Idempotent Provisioning

**As a** DevOps Engineer, **I want** provisioning to be idempotent, **so that** running it multiple times is safe and doesn't duplicate installations.

**Acceptance Criteria**:
- [ ] Re-running provisioning doesn't fail
- [ ] Packages are not reinstalled if already present
- [ ] Configuration is safely reapplied
- [ ] No side effects from multiple runs

---

### Epic 7: Automatic Project Detection

Intelligent detection of languages, versions, frameworks, and databases to pre-populate wizard defaults.

#### [Implemented] Story: Detect Project Languages

**As a** Developer, **I want** my project's programming languages to be automatically detected, **so that** the wizard pre-selects the correct runtimes.

**Acceptance Criteria**:
- [ ] Detects Python from .py files
- [ ] Detects JavaScript/TypeScript from .js/.ts files
- [ ] Detects Java from .java files
- [ ] Detects Kotlin from .kt files
- [ ] Detects Rust from .rs files and Cargo.toml
- [ ] Detects Go from .go files and go.mod
- [ ] Uses GitHub Linguist data for accurate classification

#### [Implemented] Story: Detect Runtime Versions

**As a** Developer, **I want** my project's required runtime versions to be automatically detected from version files, **so that** the wizard pre-fills the correct versions.

**Acceptance Criteria**:
- [ ] Reads Python version from .python-version
- [ ] Reads Node version from .nvmrc
- [ ] Reads Go version from go.mod
- [ ] Reads Rust channel from rust-toolchain.toml
- [ ] Parses .tool-versions for any supported runtime
- [ ] Extracts requires-python from pyproject.toml
- [ ] Extracts engines.node from package.json

#### [Implemented] Story: Detect Frameworks and Tools

**As a** Developer, **I want** my project's frameworks and tools to be automatically detected from dependencies, **so that** the wizard pre-checks relevant options.

**Acceptance Criteria**:
- [ ] Detects Django/Flask/FastAPI from Python dependencies
- [ ] Detects React/Vue/Angular from JavaScript dependencies
- [ ] Detects Playwright from any ecosystem's dependencies
- [ ] Detects Docker from Dockerfile or docker-compose presence
- [ ] Detects AWS CLI from AWS SDK dependencies
- [ ] Detects GitHub CLI from .github/ directory or gh dependencies

#### [Implemented] Story: Detect Databases

**As a** Developer, **I want** my project's required databases to be automatically detected, **so that** the wizard pre-checks the correct databases.

**Acceptance Criteria**:
- [ ] Detects PostgreSQL from docker-compose services
- [ ] Detects Redis from docker-compose services
- [ ] Detects MySQL from docker-compose services
- [ ] Detects databases from ORM adapter dependencies
- [ ] Detects databases from environment variable patterns

#### [Implemented] Story: View Detection Results

**As a** DevOps Engineer, **I want** to use `clauded --detect` to see what was detected without starting the wizard, **so that** I can verify detection accuracy or debug issues.

**Acceptance Criteria**:
- [ ] `clauded --detect` runs detection only
- [ ] Outputs detected languages with confidence scores
- [ ] Outputs detected versions with source files
- [ ] Outputs detected frameworks, tools, and databases
- [ ] Exits without creating VM or running wizard

#### [Implemented] Story: Skip Detection When Needed

**As a** Developer, **I want** to use `--no-detect` to bypass automatic detection, **so that** I can manually configure everything when detection is inaccurate.

**Acceptance Criteria**:
- [ ] `clauded --no-detect` skips detection phase
- [ ] Wizard uses static defaults instead of detected values
- [ ] All wizard options remain fully configurable
- [ ] Works with all other CLI workflows

---

### Epic 8: Detection System Enhancements

Future enhancements to detection system for additional manifest formats.

#### [Planned] Story: Detect Python Version from setup.py

**As a** Python Developer using setup.py, **I want** my Python version requirement to be detected from setup.py, **so that** the wizard defaults match my project constraints.

**Acceptance Criteria**:
- [ ] Detects python_requires from setup.py
- [ ] Parses semver constraints (>=, ~=, ==)
- [ ] Returns VersionSpec with constraint type
- [ ] Links to: specs/detection-enhancements-spec.md (FR-1)

#### [Planned] Story: Detect Java Version from Kotlin DSL

**As a** Kotlin Developer using Gradle Kotlin DSL, **I want** my Java version to be detected from build.gradle.kts, **so that** the wizard defaults match my build configuration.

**Acceptance Criteria**:
- [ ] Detects sourceCompatibility from build.gradle.kts
- [ ] Parses JavaVersion.VERSION_XX syntax
- [ ] Returns VersionSpec with exact version
- [ ] Links to: specs/detection-enhancements-spec.md (FR-2)

#### [Planned] Story: Detect Frameworks from Groovy Gradle

**As a** Java/Kotlin Developer using Groovy Gradle, **I want** my frameworks to be detected from build.gradle, **so that** the wizard suggests relevant tools.

**Acceptance Criteria**:
- [ ] Detects Spring Boot from build.gradle dependencies
- [ ] Detects Ktor from build.gradle dependencies
- [ ] Returns DetectedItem list with confidence scores
- [ ] Links to: specs/detection-enhancements-spec.md (FR-3)

#### [Planned] Story: Detect MongoDB Database

**As a** Developer using MongoDB, **I want** MongoDB to be detected from my project files, **so that** the wizard offers MongoDB installation.

**Acceptance Criteria**:
- [ ] Detects MongoDB from docker-compose
- [ ] Detects MongoDB from .env MONGODB_URI variables
- [ ] Detects MongoDB from pymongo/mongoose dependencies
- [ ] Returns DetectedItem with confidence score
- [ ] Links to: specs/detection-enhancements-spec.md (FR-4)

---

## Feature Implementation Status Summary

- **Total Stories**: 42
- **Implemented**: 36
- **In Progress**: 0
- **Planned**: 6 (Detection Enhancements - Epic 8)

The project is feature-complete for v0.1.0 scope. Epic 8 stories represent planned enhancements documented in specs/detection-enhancements-spec.md.
