# Feature Specification: Detection System Enhancements

## Problem Statement

The current project detection system (implemented in v0.1.0) successfully detects most programming languages, versions, frameworks, and databases from project files. However, four manifest formats explicitly specified in the original feature-project-detection.md remain unimplemented, limiting detection accuracy for certain project types.

## Core Functionality

Extend the existing detection system to support additional manifest formats for version and framework detection.

## Functional Requirements

### FR-1: Python setup.py Version Detection

**Goal:** Parse Python version requirements from setup.py files.

**Detection Logic:**
- Scan for `setup.py` in project root
- Extract `python_requires` parameter using regex
- Parse semver constraints (e.g., `>=3.10`, `~=3.11.0`)
- Return VersionSpec with constraint type

**Priority:** Python projects without pyproject.toml

**Example:**
```python
setup(
    name="myproject",
    python_requires=">=3.10",
    ...
)
```

**Output:** `VersionSpec(version="3.10", source_file="setup.py", constraint_type="minimum")`

---

### FR-2: Kotlin build.gradle.kts Version Detection

**Goal:** Parse Java version from Kotlin DSL Gradle build files.

**Detection Logic:**
- Scan for `build.gradle.kts` in project root
- Extract `sourceCompatibility` or `targetCompatibility` using regex
- Support Kotlin DSL syntax: `JavaVersion.VERSION_17`
- Return VersionSpec for Java version

**Priority:** Kotlin projects using Gradle Kotlin DSL

**Example:**
```kotlin
java {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}
```

**Output:** `VersionSpec(version="17", source_file="build.gradle.kts", constraint_type="exact")`

---

### FR-3: Gradle build.gradle Framework Detection

**Goal:** Detect Java/Kotlin frameworks from Groovy Gradle dependency declarations.

**Detection Logic:**
- Scan for `build.gradle` in project root
- Parse `dependencies` block for known framework packages
- Match against: spring-boot, quarkus, micronaut, ktor
- Return DetectedItem list with confidence scores

**Priority:** Java/Kotlin projects using Groovy Gradle

**Example:**
```groovy
dependencies {
    implementation 'org.springframework.boot:spring-boot-starter-web:3.0.0'
    implementation 'io.ktor:ktor-server-core:2.0.0'
}
```

**Output:**
```
[
    DetectedItem(name="spring-boot", confidence="high", source_file="build.gradle", source_evidence="spring-boot-starter-web"),
    DetectedItem(name="ktor", confidence="high", source_file="build.gradle", source_evidence="ktor-server-core")
]
```

---

### FR-4: MongoDB Database Detection

**Goal:** Detect MongoDB database requirement from project manifests.

**Detection Logic:**
- Check docker-compose for `mongo:` or `mongodb:` images
- Check environment files for `MONGODB_URI` or `MONGO_URL` variables
- Check manifest dependencies: `pymongo`, `mongoose`, `mongodb` driver packages
- Return DetectedItem with confidence based on source

**Priority:** Projects using MongoDB instead of PostgreSQL/MySQL/Redis

**Example Sources:**
```yaml
# docker-compose.yml
services:
  db:
    image: mongo:7.0
```

```bash
# .env.example
MONGODB_URI=mongodb://localhost:27017/mydb
```

```json
// package.json
{
  "dependencies": {
    "mongoose": "^7.0.0"
  }
}
```

**Output:** `DetectedItem(name="mongodb", confidence="high", source_file="docker-compose.yml", source_evidence="image: mongo:7.0")`

---

## Critical Constraints

### Security Requirements

**All new detection code MUST:**
1. Validate file paths are within project boundary (no symlink traversal)
2. Validate extracted version strings match expected patterns (prevent command injection)
3. Limit file reads to first 8KB (prevent resource exhaustion)

**Required Validations:**
```python
# Path validation
if file_path.is_symlink():
    return None

resolved = file_path.resolve()
try:
    resolved.relative_to(project_path.resolve())
except ValueError:
    return None

# Version validation
VERSION_PATTERNS = {
    "java": r"^\d+$",
    "mongodb": r"^[a-zA-Z0-9\.\-]+$",  # Semver or channel
}

if not re.match(VERSION_PATTERNS[runtime], version):
    return None
```

---

## Integration Points

### File Locations
- Add parsers to existing modules:
  - `src/clauded/detect/version.py` - FR-1, FR-2
  - `src/clauded/detect/framework.py` - FR-3
  - `src/clauded/detect/database.py` - FR-4

### Config Integration
- MongoDB → `environment.databases: [mongodb]`
- No changes needed for setup.py/build.gradle.kts (use existing version fields)

---

## Out of Scope

- Transitive dependency resolution
- Multi-module Gradle project support
- MongoDB version detection (only presence/absence)
- Nested setup.py files (only project root)

---

## Acceptance Criteria

### FR-1: setup.py Version Detection
- [ ] Detects `python_requires=">=3.10"` from setup.py
- [ ] Returns VersionSpec with constraint_type="minimum"
- [ ] Returns None for malformed setup.py
- [ ] Validates file is within project boundary

### FR-2: build.gradle.kts Version Detection
- [ ] Detects `JavaVersion.VERSION_17` from build.gradle.kts
- [ ] Returns VersionSpec with constraint_type="exact"
- [ ] Returns None for malformed build.gradle.kts
- [ ] Validates file is within project boundary

### FR-3: build.gradle Framework Detection
- [ ] Detects Spring Boot from build.gradle dependencies
- [ ] Detects Ktor from build.gradle dependencies
- [ ] Returns DetectedItem list with confidence scores
- [ ] Returns empty list for projects without frameworks

### FR-4: MongoDB Detection
- [ ] Detects MongoDB from docker-compose service
- [ ] Detects MongoDB from .env.example MONGODB_URI
- [ ] Detects MongoDB from pymongo/mongoose dependencies
- [ ] Returns DetectedItem with appropriate confidence

### Security
- [ ] All parsers validate file paths (no symlink traversal)
- [ ] All parsers validate extracted version strings
- [ ] All parsers limit file reads to 8KB

---

## Test Coverage Requirements

### Unit Tests
- [ ] setup.py parser with valid/invalid/malformed files
- [ ] build.gradle.kts parser with various Java version formats
- [ ] build.gradle dependency parser with multiple frameworks
- [ ] MongoDB detection from docker-compose/env/manifests

### Property-Based Tests
- [ ] setup.py parser with arbitrary python_requires constraints
- [ ] build.gradle.kts parser with arbitrary Java versions
- [ ] MongoDB detection with arbitrary env var names

### Security Tests
- [ ] Symlink exploitation attempt (should return None)
- [ ] Version injection attempt (should return None)
- [ ] Large file handling (should limit to 8KB)

---

## Implementation Priority

1. **FR-4 (MongoDB)** - Highest impact, reuses existing database.py patterns
2. **FR-1 (setup.py)** - Common format, straightforward regex
3. **FR-2 (build.gradle.kts)** - Medium complexity, Kotlin DSL parsing
4. **FR-3 (build.gradle)** - Most complex, Groovy parsing

---

## References

- Parent Spec: specs/feature-project-detection.md (lines 70-99)
- Remediation Issues: specs/feature-project-detection.md Addendum (SPEC-001)
- Security Requirements: specs/feature-project-detection.md Addendum (SEC-001, SEC-002)
