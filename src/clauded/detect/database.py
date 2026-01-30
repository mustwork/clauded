"""Database detection from docker-compose and environment files."""

import json
import logging
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore

import yaml

from .result import DetectedItem
from .utils import extract_package_name, is_safe_path, safe_read_text

logger = logging.getLogger(__name__)

# Database detection patterns
POSTGRES_IMAGES = {"postgres", "postgresql"}
REDIS_IMAGES = {"redis"}
MYSQL_IMAGES = {"mysql", "mariadb"}

POSTGRES_ORM_ADAPTERS = {"psycopg2", "psycopg2-binary", "asyncpg", "pg", "postgres"}
REDIS_ORM_ADAPTERS = {"redis", "redis-py", "ioredis", "jedis", "lettuce"}
MYSQL_ORM_ADAPTERS = {
    "mysql-connector-python",
    "mysqlclient",
    "mysql",
    "mysql2",
    "mysql-connector-java",
}
SQLITE_ORM_ADAPTERS = {"sqlite3", "better-sqlite3"}
MONGODB_IMAGES = {"mongo", "mongodb"}
MONGODB_ORM_ADAPTERS = {
    "pymongo",  # Python official driver
    "motor",  # Python async driver
    "mongoengine",  # Python ODM
    "beanie",  # Python async ODM
    "mongoose",  # Node.js ODM
    "mongodb",  # Node.js official driver
    "mongo",  # Generic Node package
    "mongo-driver",  # Go driver
    "mgo",  # Legacy Go driver
}

ENV_VAR_PATTERNS = {
    "postgresql": {"DATABASE_URL", "POSTGRES_URL", "POSTGRESQL_URL"},
    "redis": {"REDIS_URL", "REDIS_HOST"},
    "mysql": {"MYSQL_URL", "DB_HOST"},
    "sqlite": {"SQLITE_URL"},
    "mongodb": {
        "MONGODB_URI",
        "MONGO_URL",
        "MONGODB_URL",
        "MONGODB_HOST",
        "MONGO_HOST",
    },
}


def detect_databases(project_path: Path) -> list[DetectedItem]:
    """Detect database requirements from docker-compose and configuration files.

    CONTRACT:
      Inputs:
        - project_path: directory path, must exist and be readable

      Outputs:
        - collection of DetectedItem objects for detected databases
        - empty collection if no database indicators found

      Invariants:
        - Supported databases: postgresql, redis, mysql, sqlite, mongodb
        - All source_file paths are absolute paths within project_path
        - Confidence: high (docker-compose service, SQLite files),
          medium (ORM dependency), low (env variable pattern)
        - Never raises exceptions - logs warnings and returns partial results

      Properties:
        - Multi-source detection: combines docker-compose, env files, and ORM deps
        - No duplicates: each database appears at most once (highest confidence wins)

      Algorithm:
        1. Initialize empty database list
        2. Check docker-compose files (docker-compose.yml, compose.yml):
           a. Parse YAML
           b. Extract services section
           c. Match service image names against database patterns
           d. Add DetectedItem with high confidence
        3. Check environment files (.env.example, .env.sample):
           a. Read line by line
           b. Match variable names against database URL patterns
           c. Add DetectedItem with low confidence
        4. Check ORM configuration and dependencies:
           a. Detect psycopg2/asyncpg for PostgreSQL
           b. Detect redis-py/ioredis for Redis
           c. Detect mysql-connector for MySQL
           d. Detect sqlite3/better-sqlite3 for SQLite
           e. Detect pymongo/mongoose for MongoDB
           f. Add DetectedItem with medium confidence
        5. Check for SQLite database files:
           a. Scan project root for .db, .sqlite, .sqlite3 files
           b. Add DetectedItem with high confidence
        6. Deduplicate: keep highest confidence for each database
        7. Return collection of DetectedItem objects

      Database Detection Patterns:
        PostgreSQL: postgres/postgresql image, psycopg2/asyncpg deps,
                    DATABASE_URL with postgres://
        Redis: redis image, redis-py/ioredis deps, REDIS_URL
        MySQL: mysql/mariadb image, mysql-connector deps,
               DATABASE_URL with mysql://
        SQLite: .db/.sqlite/.sqlite3 files, sqlite3/better-sqlite3 deps,
                SQLITE_URL with sqlite://
        MongoDB: mongo/mongodb image, pymongo/mongoose deps,
                 MONGODB_URI, DATABASE_URL with mongodb://
    """
    logger.debug(f"Detecting databases in {project_path}")
    databases = []

    try:
        logger.debug("  Parsing docker-compose files...")
        compose_dbs = parse_docker_compose(project_path)
        logger.debug(f"    Found {len(compose_dbs)} databases from docker-compose")
        databases.extend(compose_dbs)
    except (KeyboardInterrupt, SystemExit):
        raise
    except (OSError, yaml.YAMLError) as e:
        logger.debug(f"Error parsing docker-compose files: {e}")

    try:
        logger.debug("  Parsing environment files...")
        env_dbs = parse_env_files(project_path)
        logger.debug(f"    Found {len(env_dbs)} databases from env files")
        databases.extend(env_dbs)
    except (KeyboardInterrupt, SystemExit):
        raise
    except OSError as e:
        logger.debug(f"Error parsing environment files: {e}")

    try:
        logger.debug("  Detecting ORM adapters...")
        orm_dbs = detect_orm_adapters(project_path)
        logger.debug(f"    Found {len(orm_dbs)} databases from ORM adapters")
        databases.extend(orm_dbs)
    except (KeyboardInterrupt, SystemExit):
        raise
    except (OSError, tomllib.TOMLDecodeError, json.JSONDecodeError) as e:
        logger.debug(f"Error detecting ORM adapters: {e}")

    try:
        logger.debug("  Detecting SQLite files...")
        sqlite_dbs = detect_sqlite_files(project_path)
        logger.debug(f"    Found {len(sqlite_dbs)} SQLite databases from files")
        databases.extend(sqlite_dbs)
    except (KeyboardInterrupt, SystemExit):
        raise
    except OSError as e:
        logger.debug(f"Error detecting SQLite files: {e}")

    logger.debug(f"Detected {len(databases)} database items before deduplication")
    result = deduplicate_databases(databases)
    logger.debug(f"Detected {len(result)} unique databases after deduplication")
    return result


def parse_docker_compose(project_path: Path) -> list[DetectedItem]:
    """Parse docker-compose files for database services.

    CONTRACT:
      Inputs:
        - project_path: directory path containing docker-compose files

      Outputs:
        - collection of DetectedItem objects for detected databases
        - empty collection if no compose files found or no database services

      Invariants:
        - Checks docker-compose.yml and compose.yml
        - High confidence for detected databases
        - Never raises exceptions

      Algorithm:
        1. Check for docker-compose.yml or compose.yml
        2. Parse YAML
        3. Extract services section
        4. For each service:
           a. Get image name
           b. Match against database image patterns:
              - postgres, postgresql → PostgreSQL
              - redis → Redis
              - mysql, mariadb → MySQL
           c. Create DetectedItem with service name as source_evidence
        5. Return collection of DetectedItem objects
    """
    databases = []
    compose_files = [
        project_path / "docker-compose.yml",
        project_path / "compose.yml",
    ]

    for compose_file in compose_files:
        if not compose_file.exists():
            continue
        if not is_safe_path(compose_file, project_path):
            continue

        content = safe_read_text(compose_file, project_path)
        if not content:
            continue

        try:
            compose_data = yaml.safe_load(content)

            if not compose_data or not isinstance(compose_data, dict):
                continue

            services = compose_data.get("services", {})
            if not isinstance(services, dict):
                continue

            for service_name, service_config in services.items():
                if not isinstance(service_config, dict):
                    continue

                image = service_config.get("image", "")
                if not isinstance(image, str):
                    continue

                # Extract image base name (before any colon for tags)
                image_base = image.split(":")[0].lower()

                db_name = None
                if any(pattern in image_base for pattern in POSTGRES_IMAGES):
                    db_name = "postgresql"
                elif any(pattern in image_base for pattern in REDIS_IMAGES):
                    db_name = "redis"
                elif any(pattern in image_base for pattern in MYSQL_IMAGES):
                    db_name = "mysql"
                elif any(pattern in image_base for pattern in MONGODB_IMAGES):
                    db_name = "mongodb"

                if db_name:
                    databases.append(
                        DetectedItem(
                            name=db_name,
                            confidence="high",
                            source_file=str(compose_file.absolute()),
                            source_evidence=service_name,
                        )
                    )

        except yaml.YAMLError as e:
            logger.debug(f"Error parsing {compose_file}: {e}")

    return databases


def parse_env_files(project_path: Path) -> list[DetectedItem]:
    """Parse environment example files for database URL patterns.

    CONTRACT:
      Inputs:
        - project_path: directory path containing env files

      Outputs:
        - collection of DetectedItem objects for detected databases
        - empty collection if no env files found or no database URLs

      Invariants:
        - Checks .env.example, .env.sample (not .env itself for security)
        - Low confidence for detected databases
        - Never raises exceptions

      Algorithm:
        1. Check for .env.example and .env.sample files
        2. Read line by line
        3. For each line:
           a. Parse variable name and value
           b. Match against database URL patterns:
              - postgres:// or postgresql:// → PostgreSQL
              - redis:// → Redis
              - mysql:// → MySQL
           c. Create DetectedItem with variable name as source_evidence
        4. Return collection of DetectedItem objects
    """
    databases = []
    env_files = [
        project_path / ".env.example",
        project_path / ".env.sample",
    ]

    for env_file in env_files:
        if not env_file.exists():
            continue
        if not is_safe_path(env_file, project_path):
            continue

        content = safe_read_text(env_file, project_path)
        if not content:
            continue

        try:
            for line in content.splitlines():
                line = line.strip()

                # Skip comments and empty lines
                if not line or line.startswith("#"):
                    continue

                # Parse variable name and value
                if "=" not in line:
                    continue

                var_name, var_value = line.split("=", 1)
                var_name = var_name.strip().upper()
                var_value = var_value.strip()

                # Check for database patterns
                db_name = None

                # For DATABASE_URL, check protocol first
                if var_name == "DATABASE_URL" and var_value:
                    var_value_lower = var_value.lower()
                    if (
                        "postgres://" in var_value_lower
                        or "postgresql://" in var_value_lower
                    ):
                        db_name = "postgresql"
                    elif "redis://" in var_value_lower:
                        db_name = "redis"
                    elif "mysql://" in var_value_lower:
                        db_name = "mysql"
                    elif "sqlite://" in var_value_lower:
                        db_name = "sqlite"
                    elif (
                        "mongodb://" in var_value_lower
                        or "mongodb+srv://" in var_value_lower
                    ):
                        db_name = "mongodb"

                # Check variable name patterns
                if not db_name:
                    if var_name in ENV_VAR_PATTERNS["postgresql"]:
                        db_name = "postgresql"
                    elif var_name in ENV_VAR_PATTERNS["redis"]:
                        db_name = "redis"
                    elif var_name in ENV_VAR_PATTERNS["mysql"]:
                        db_name = "mysql"
                    elif var_name in ENV_VAR_PATTERNS["sqlite"]:
                        db_name = "sqlite"
                    elif var_name in ENV_VAR_PATTERNS["mongodb"]:
                        db_name = "mongodb"

                # Check URL schemes in other values
                if not db_name and var_value:
                    var_value_lower = var_value.lower()
                    if (
                        "postgres://" in var_value_lower
                        or "postgresql://" in var_value_lower
                    ):
                        db_name = "postgresql"
                    elif "redis://" in var_value_lower:
                        db_name = "redis"
                    elif "mysql://" in var_value_lower:
                        db_name = "mysql"
                    elif "sqlite://" in var_value_lower:
                        db_name = "sqlite"
                    elif (
                        "mongodb://" in var_value_lower
                        or "mongodb+srv://" in var_value_lower
                    ):
                        db_name = "mongodb"

                if db_name:
                    databases.append(
                        DetectedItem(
                            name=db_name,
                            confidence="low",
                            source_file=str(env_file.absolute()),
                            source_evidence=var_name,
                        )
                    )

        except (ValueError, UnicodeDecodeError) as e:
            logger.debug(f"Error parsing {env_file}: {e}")

    return databases


def detect_orm_adapters(project_path: Path) -> list[DetectedItem]:
    """Detect databases from ORM adapter dependencies.

    CONTRACT:
      Inputs:
        - project_path: directory path containing manifest files

      Outputs:
        - collection of DetectedItem objects for detected databases
        - empty collection if no ORM adapter dependencies found

      Invariants:
        - Medium confidence for detected databases
        - Checks Python, Node, Java manifests
        - Never raises exceptions

      Algorithm:
        1. Check Python dependencies for:
           - psycopg2, psycopg2-binary, asyncpg → PostgreSQL
           - redis, redis-py → Redis
           - mysql-connector-python, mysqlclient → MySQL
        2. Check Node dependencies for:
           - pg, postgres → PostgreSQL
           - redis, ioredis → Redis
           - mysql, mysql2 → MySQL
        3. Check Java dependencies for:
           - postgresql driver → PostgreSQL
           - jedis, lettuce → Redis
           - mysql-connector-java → MySQL
        4. Return collection of DetectedItem objects
    """
    databases = []

    # Check Python dependencies
    pyproject_file = project_path / "pyproject.toml"
    if pyproject_file.exists() and is_safe_path(pyproject_file, project_path):
        try:
            with open(pyproject_file, "rb") as f:
                pyproject_data = tomllib.load(f)

            all_deps = set()

            # Get regular dependencies
            project_data = pyproject_data.get("project", {})
            if "dependencies" in project_data:
                deps = project_data["dependencies"]
                if isinstance(deps, list):
                    for dep in deps:
                        # Extract package name (before version specifiers)
                        pkg_name = extract_package_name(dep, normalize_case=True)
                        all_deps.add(pkg_name)

            # Get optional dependencies
            if "optional-dependencies" in project_data:
                opt_deps = project_data["optional-dependencies"]
                if isinstance(opt_deps, dict):
                    for dep_list in opt_deps.values():
                        if isinstance(dep_list, list):
                            for dep in dep_list:
                                pkg_name = extract_package_name(
                                    dep, normalize_case=True
                                )
                                all_deps.add(pkg_name)

            # Check for database adapters
            for adapter in all_deps:
                if adapter in POSTGRES_ORM_ADAPTERS:
                    databases.append(
                        DetectedItem(
                            name="postgresql",
                            confidence="medium",
                            source_file=str(pyproject_file.absolute()),
                            source_evidence=adapter,
                        )
                    )
                elif adapter in REDIS_ORM_ADAPTERS:
                    databases.append(
                        DetectedItem(
                            name="redis",
                            confidence="medium",
                            source_file=str(pyproject_file.absolute()),
                            source_evidence=adapter,
                        )
                    )
                elif adapter in MYSQL_ORM_ADAPTERS:
                    databases.append(
                        DetectedItem(
                            name="mysql",
                            confidence="medium",
                            source_file=str(pyproject_file.absolute()),
                            source_evidence=adapter,
                        )
                    )
                elif adapter in MONGODB_ORM_ADAPTERS:
                    databases.append(
                        DetectedItem(
                            name="mongodb",
                            confidence="medium",
                            source_file=str(pyproject_file.absolute()),
                            source_evidence=adapter,
                        )
                    )

        except tomllib.TOMLDecodeError as e:
            logger.debug(f"Error parsing {pyproject_file}: {e}")

    # Check Node dependencies
    package_json_file = project_path / "package.json"
    if package_json_file.exists() and is_safe_path(package_json_file, project_path):
        content = safe_read_text(package_json_file, project_path)
        if content:
            try:
                package_data = json.loads(content)

                all_deps = set()

                # Get regular and dev dependencies
                for dep_section in ["dependencies", "devDependencies"]:
                    if dep_section in package_data and isinstance(
                        package_data[dep_section], dict
                    ):
                        all_deps.update(
                            pkg.lower() for pkg in package_data[dep_section].keys()
                        )

                # Check for database adapters
                for adapter in all_deps:
                    if adapter in POSTGRES_ORM_ADAPTERS:
                        databases.append(
                            DetectedItem(
                                name="postgresql",
                                confidence="medium",
                                source_file=str(package_json_file.absolute()),
                                source_evidence=adapter,
                            )
                        )
                    elif adapter in REDIS_ORM_ADAPTERS:
                        databases.append(
                            DetectedItem(
                                name="redis",
                                confidence="medium",
                                source_file=str(package_json_file.absolute()),
                                source_evidence=adapter,
                            )
                        )
                    elif adapter in MYSQL_ORM_ADAPTERS:
                        databases.append(
                            DetectedItem(
                                name="mysql",
                                confidence="medium",
                                source_file=str(package_json_file.absolute()),
                                source_evidence=adapter,
                            )
                        )
                    elif adapter in SQLITE_ORM_ADAPTERS:
                        databases.append(
                            DetectedItem(
                                name="sqlite",
                                confidence="medium",
                                source_file=str(package_json_file.absolute()),
                                source_evidence=adapter,
                            )
                        )
                    elif adapter in MONGODB_ORM_ADAPTERS:
                        databases.append(
                            DetectedItem(
                                name="mongodb",
                                confidence="medium",
                                source_file=str(package_json_file.absolute()),
                                source_evidence=adapter,
                            )
                        )

            except json.JSONDecodeError as e:
                logger.debug(f"Error parsing {package_json_file}: {e}")

    # Check pom.xml for Java dependencies
    pom_file = project_path / "pom.xml"
    if pom_file.exists() and is_safe_path(pom_file, project_path):
        content = safe_read_text(pom_file, project_path)
        if content:
            try:
                root = ET.fromstring(content)
                # Handle Maven namespace
                ns = {"mvn": "http://maven.apache.org/POM/4.0.0"}

                # Get all dependencies
                for dep in root.findall(".//mvn:dependency", ns):
                    artifact_id_elem = dep.find("mvn:artifactId", ns)
                    if artifact_id_elem is not None and artifact_id_elem.text:
                        artifact_id = artifact_id_elem.text.lower()

                        if "postgresql" in artifact_id:
                            databases.append(
                                DetectedItem(
                                    name="postgresql",
                                    confidence="medium",
                                    source_file=str(pom_file.absolute()),
                                    source_evidence=artifact_id,
                                )
                            )
                        elif any(
                            adapter in artifact_id for adapter in REDIS_ORM_ADAPTERS
                        ):
                            databases.append(
                                DetectedItem(
                                    name="redis",
                                    confidence="medium",
                                    source_file=str(pom_file.absolute()),
                                    source_evidence=artifact_id,
                                )
                            )
                        elif "mysql" in artifact_id:
                            databases.append(
                                DetectedItem(
                                    name="mysql",
                                    confidence="medium",
                                    source_file=str(pom_file.absolute()),
                                    source_evidence=artifact_id,
                                )
                            )
                        elif "mongo" in artifact_id:
                            databases.append(
                                DetectedItem(
                                    name="mongodb",
                                    confidence="medium",
                                    source_file=str(pom_file.absolute()),
                                    source_evidence=artifact_id,
                                )
                            )

            except ET.ParseError as e:
                logger.debug(f"Error parsing {pom_file}: {e}")

    return databases


def detect_sqlite_files(project_path: Path) -> list[DetectedItem]:
    """Detect SQLite from database files in project.

    CONTRACT:
      Inputs:
        - project_path: directory path containing potential SQLite files

      Outputs:
        - collection of DetectedItem objects for detected SQLite
        - empty collection if no SQLite files found

      Invariants:
        - High confidence for detected SQLite files
        - Only checks project root (not recursive to avoid false positives)
        - Never raises exceptions

      Algorithm:
        1. Check for .db, .sqlite, .sqlite3 files in project root
        2. For each matching file:
           a. Create DetectedItem with high confidence
           b. Use filename as source_evidence
        3. Return collection of DetectedItem objects
    """
    databases = []
    sqlite_extensions = [".db", ".sqlite", ".sqlite3"]

    try:
        # Only check project root, not recursive (avoid false positives)
        for file_path in project_path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in sqlite_extensions:
                if is_safe_path(file_path, project_path):
                    databases.append(
                        DetectedItem(
                            name="sqlite",
                            confidence="high",
                            source_file=str(file_path.absolute()),
                            source_evidence=file_path.name,
                        )
                    )
    except OSError as e:
        logger.debug(f"Error detecting SQLite files: {e}")

    return databases


def deduplicate_databases(databases: list[DetectedItem]) -> list[DetectedItem]:
    """Deduplicate databases, keeping highest confidence for each.

    CONTRACT:
      Inputs:
        - databases: collection of DetectedItem objects, may contain duplicates

      Outputs:
        - collection of DetectedItem objects with unique database names
        - for each database name, only the DetectedItem with highest confidence

      Invariants:
        - Confidence ordering: high > medium > low
        - Preserves source_file and source_evidence from highest confidence match
        - Never raises exceptions

      Algorithm:
        1. Group databases by name
        2. For each group:
           a. Sort by confidence (high > medium > low)
           b. Select first item (highest confidence)
        3. Return collection of deduplicated items
    """
    if not databases:
        return []

    confidence_order = {"high": 3, "medium": 2, "low": 1}
    seen: dict[str, DetectedItem] = {}

    for db in databases:
        if db.name not in seen:
            seen[db.name] = db
        else:
            current_score = confidence_order[seen[db.name].confidence]
            new_score = confidence_order[db.confidence]
            if new_score > current_score:
                seen[db.name] = db

    return list(seen.values())
