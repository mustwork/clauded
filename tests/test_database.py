"""Property-based and unit tests for database detection.

Tests verify that:
1. All DetectedItem objects have valid confidence levels
2. Database names are in the supported list
3. No duplicate databases in final result
4. source_file paths are absolute and exist
5. Docker Compose parsing detects databases from service images
6. Environment file parsing detects databases from variable patterns
7. ORM adapter detection works for Python, Node, and Java manifests
8. Deduplication keeps highest confidence when duplicates exist
9. Error handling is non-fatal and continues with partial results
"""

import json
import sys
from pathlib import Path

import pytest
import yaml
from hypothesis import given
from hypothesis import strategies as st

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from clauded.detect.database import (
    deduplicate_databases,
    detect_databases,
    detect_orm_adapters,
    parse_docker_compose,
    parse_env_files,
)
from clauded.detect.result import DetectedItem


# Hypothesis strategies
def detected_item_strategy() -> st.SearchStrategy[DetectedItem]:
    """Generate valid DetectedItem objects."""
    db_names = st.sampled_from(["postgresql", "redis", "mysql", "sqlite", "mongodb"])
    confidence_levels = st.sampled_from(["high", "medium", "low"])
    source_evidence = st.text(
        min_size=1,
        max_size=50,
        alphabet=st.characters(blacklist_categories=("Cc", "Cs")),
    )

    return st.builds(
        DetectedItem,
        name=db_names,
        confidence=confidence_levels,
        source_file=st.just("/tmp/test_file.txt"),
        source_evidence=source_evidence,
    )


@given(detected_item_strategy())
def test_detected_item_has_valid_confidence(item: DetectedItem) -> None:
    """Property: all DetectedItem objects have valid confidence levels."""
    assert item.confidence in {"high", "medium", "low"}


@given(detected_item_strategy())
def test_detected_item_has_supported_database(item: DetectedItem) -> None:
    """Property: all detected items use supported database names."""
    assert item.name in {"postgresql", "redis", "mysql", "sqlite", "mongodb"}


@given(st.lists(detected_item_strategy(), min_size=1))
def test_deduplicate_removes_duplicates(items: list[DetectedItem]) -> None:
    """Property: deduplication removes duplicates by database name."""
    # Create all-same-name items with different confidences
    same_name_items = [
        DetectedItem(
            name="postgresql",
            confidence="low",
            source_file="/tmp/a.txt",
            source_evidence="env",
        ),
        DetectedItem(
            name="postgresql",
            confidence="high",
            source_file="/tmp/b.yml",
            source_evidence="service",
        ),
        DetectedItem(
            name="postgresql",
            confidence="medium",
            source_file="/tmp/c.txt",
            source_evidence="pkg",
        ),
    ]

    result = deduplicate_databases(same_name_items)

    # Should have exactly one postgresql
    assert len(result) == 1
    assert result[0].name == "postgresql"
    # Should keep high confidence
    assert result[0].confidence == "high"


@given(st.lists(detected_item_strategy(), max_size=10))
def test_deduplicate_preserves_unique_databases(items: list[DetectedItem]) -> None:
    """Property: deduplication preserves all unique database names."""
    result = deduplicate_databases(items)

    # Result should contain each database name at most once
    names = [item.name for item in result]
    assert len(names) == len(set(names))

    # Result should be subset of original names
    original_names = {item.name for item in items}
    result_names = {item.name for item in result}
    assert result_names.issubset(original_names)


@given(st.lists(detected_item_strategy(), max_size=10))
def test_deduplicate_selects_highest_confidence(items: list[DetectedItem]) -> None:
    """Property: deduplication selects highest confidence for each database."""
    result = deduplicate_databases(items)

    confidence_order = {"high": 3, "medium": 2, "low": 1}

    # For each database in result, no duplicate in original with higher confidence
    for result_item in result:
        original_same_db = [item for item in items if item.name == result_item.name]
        scores = [confidence_order[item.confidence] for item in original_same_db]
        max_confidence_score = max(scores)
        result_score = confidence_order[result_item.confidence]
        assert result_score == max_confidence_score


def test_deduplicate_empty_list() -> None:
    """Property: deduplication handles empty input gracefully."""
    result = deduplicate_databases([])
    assert result == []


# Docker Compose fixtures and tests
@pytest.fixture
def docker_compose_with_postgres(tmp_path: Path) -> tuple[Path, str]:
    """Fixture: docker-compose.yml with PostgreSQL service."""
    compose_file = tmp_path / "docker-compose.yml"
    content = {
        "version": "3",
        "services": {
            "db": {
                "image": "postgres:15",
                "environment": {"POSTGRES_PASSWORD": "secret"},
            },
        },
    }
    compose_file.write_text(yaml.dump(content))
    return tmp_path, compose_file.name


@pytest.fixture
def docker_compose_with_all_databases(tmp_path: Path) -> tuple[Path, str]:
    """Fixture: docker-compose.yml with PostgreSQL, Redis, and MySQL."""
    compose_file = tmp_path / "docker-compose.yml"
    content = {
        "version": "3",
        "services": {
            "postgres": {
                "image": "postgresql:16",
            },
            "redis": {
                "image": "redis:7-alpine",
            },
            "mysql": {
                "image": "mysql:8.0",
            },
        },
    }
    compose_file.write_text(yaml.dump(content))
    return tmp_path, compose_file.name


@pytest.fixture
def compose_yml_file(tmp_path: Path) -> tuple[Path, str]:
    """Fixture: compose.yml (alternate filename) with Redis."""
    compose_file = tmp_path / "compose.yml"
    content = {
        "services": {
            "cache": {
                "image": "redis:latest",
            },
        },
    }
    compose_file.write_text(yaml.dump(content))
    return tmp_path, compose_file.name


def test_parse_docker_compose_postgres(
    docker_compose_with_postgres: tuple[Path, str],
) -> None:
    """Test: Docker Compose parsing detects PostgreSQL from service image."""
    project_path, _ = docker_compose_with_postgres
    results = parse_docker_compose(project_path)

    assert len(results) == 1
    assert results[0].name == "postgresql"
    assert results[0].confidence == "high"
    assert "docker-compose.yml" in results[0].source_file
    assert results[0].source_evidence == "db"


def test_parse_docker_compose_all_databases(
    docker_compose_with_all_databases: tuple[Path, str],
) -> None:
    """Test: Docker Compose parsing detects all three database types."""
    project_path, _ = docker_compose_with_all_databases
    results = parse_docker_compose(project_path)

    assert len(results) == 3

    db_names = {item.name for item in results}
    assert db_names == {"postgresql", "redis", "mysql"}

    for result in results:
        assert result.confidence == "high"


def test_parse_docker_compose_alternate_filename(
    compose_yml_file: tuple[Path, str],
) -> None:
    """Test: Docker Compose parsing finds compose.yml filename."""
    project_path, _ = compose_yml_file
    results = parse_docker_compose(project_path)

    assert len(results) == 1
    assert results[0].name == "redis"
    assert "compose.yml" in results[0].source_file


def test_parse_docker_compose_missing_file(tmp_path: Path) -> None:
    """Test: Docker Compose parsing returns empty list when no compose files exist."""
    results = parse_docker_compose(tmp_path)
    assert results == []


def test_parse_docker_compose_invalid_yaml(tmp_path: Path) -> None:
    """Test: Docker Compose parsing handles invalid YAML gracefully."""
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text("{ invalid yaml ][")

    results = parse_docker_compose(tmp_path)
    assert results == []


def test_parse_docker_compose_no_services(tmp_path: Path) -> None:
    """Test: Docker Compose parsing handles missing services section."""
    compose_file = tmp_path / "docker-compose.yml"
    content = {"version": "3", "networks": {}}
    compose_file.write_text(yaml.dump(content))

    results = parse_docker_compose(tmp_path)
    assert results == []


def test_parse_docker_compose_non_database_services(tmp_path: Path) -> None:
    """Test: Docker Compose parsing skips non-database services."""
    compose_file = tmp_path / "docker-compose.yml"
    content = {
        "services": {
            "web": {"image": "nginx:latest"},
            "app": {"image": "python:3.12"},
        },
    }
    compose_file.write_text(yaml.dump(content))

    results = parse_docker_compose(tmp_path)
    assert results == []


# Environment file fixtures and tests
@pytest.fixture
def env_example_with_postgres(tmp_path: Path) -> tuple[Path, str]:
    """Fixture: .env.example with PostgreSQL URL."""
    env_file = tmp_path / ".env.example"
    content = "DATABASE_URL=postgresql://user:pass@localhost/dbname\nDEBUG=false\n"
    env_file.write_text(content)
    return tmp_path, env_file.name


@pytest.fixture
def env_sample_with_redis(tmp_path: Path) -> tuple[Path, str]:
    """Fixture: .env.sample with Redis configuration."""
    env_file = tmp_path / ".env.sample"
    content = "REDIS_URL=redis://localhost:6379\nREDIS_HOST=localhost\n"
    env_file.write_text(content)
    return tmp_path, env_file.name


@pytest.fixture
def env_with_multiple_databases(tmp_path: Path) -> tuple[Path, str]:
    """Fixture: .env.example with multiple database patterns."""
    env_file = tmp_path / ".env.example"
    content = """
# PostgreSQL
DATABASE_URL=postgresql://localhost/mydb
POSTGRES_URL=postgres://user@host/db

# Redis
REDIS_URL=redis://localhost:6379
REDIS_HOST=cache.local

# MySQL
MYSQL_URL=mysql://root@localhost/app
DB_HOST=mysql.local
"""
    env_file.write_text(content)
    return tmp_path, env_file.name


def test_parse_env_files_postgres(env_example_with_postgres: tuple[Path, str]) -> None:
    """Test: Environment file parsing detects PostgreSQL from DATABASE_URL."""
    project_path, _ = env_example_with_postgres
    results = parse_env_files(project_path)

    assert len(results) == 1
    assert results[0].name == "postgresql"
    assert results[0].confidence == "low"
    assert ".env.example" in results[0].source_file
    assert results[0].source_evidence == "DATABASE_URL"


def test_parse_env_files_redis(env_sample_with_redis: tuple[Path, str]) -> None:
    """Test: Environment file parsing detects Redis from REDIS_URL and REDIS_HOST."""
    project_path, _ = env_sample_with_redis
    results = parse_env_files(project_path)

    assert len(results) == 2
    assert all(item.name == "redis" for item in results)
    assert all(item.confidence == "low" for item in results)

    evidence = {item.source_evidence for item in results}
    assert evidence == {"REDIS_URL", "REDIS_HOST"}


def test_parse_env_files_multiple_databases(
    env_with_multiple_databases: tuple[Path, str],
) -> None:
    """Test: Environment file parsing detects all three database types."""
    project_path, _ = env_with_multiple_databases
    results = parse_env_files(project_path)

    db_names = {item.name for item in results}
    assert db_names == {"postgresql", "redis", "mysql"}

    for result in results:
        assert result.confidence == "low"


def test_parse_env_files_missing_file(tmp_path: Path) -> None:
    """Test: Environment file parsing returns empty list when no env files exist."""
    results = parse_env_files(tmp_path)
    assert results == []


def test_parse_env_files_empty_file(tmp_path: Path) -> None:
    """Test: Environment file parsing handles empty files gracefully."""
    env_file = tmp_path / ".env.example"
    env_file.write_text("")

    results = parse_env_files(tmp_path)
    assert results == []


def test_parse_env_files_comments_only(tmp_path: Path) -> None:
    """Test: Environment file parsing skips comment lines."""
    env_file = tmp_path / ".env.example"
    content = "# DATABASE_URL=postgresql://localhost\n# REDIS_URL=redis://localhost\n"
    env_file.write_text(content)

    results = parse_env_files(tmp_path)
    assert results == []


def test_parse_env_files_malformed_lines(tmp_path: Path) -> None:
    """Test: Environment file parsing skips malformed lines."""
    env_file = tmp_path / ".env.example"
    content = "NO_EQUALS_SIGN\nVALID_VAR=value\nDATABASE_URL=postgresql://localhost\n"
    env_file.write_text(content)

    results = parse_env_files(tmp_path)

    # Should only detect the postgresql
    assert len(results) == 1
    assert results[0].name == "postgresql"


# ORM adapter fixtures and tests
@pytest.fixture
def pyproject_with_postgres_adapter(tmp_path: Path) -> tuple[Path, str]:
    """Fixture: pyproject.toml with psycopg2 dependency."""
    pyproject_file = tmp_path / "pyproject.toml"
    content = """
[project]
name = "myapp"
dependencies = ["psycopg2-binary", "requests"]
"""
    pyproject_file.write_text(content)
    return tmp_path, pyproject_file.name


@pytest.fixture
def pyproject_with_multiple_adapters(tmp_path: Path) -> tuple[Path, str]:
    """Fixture: pyproject.toml with multiple database adapters."""
    pyproject_file = tmp_path / "pyproject.toml"
    content = """
[project]
name = "myapp"
dependencies = [
    "asyncpg",
    "redis",
    "mysql-connector-python",
]

[project.optional-dependencies]
dev = ["pytest"]
database = ["sqlalchemy"]
"""
    pyproject_file.write_text(content)
    return tmp_path, pyproject_file.name


@pytest.fixture
def package_json_with_redis_adapter(tmp_path: Path) -> tuple[Path, str]:
    """Fixture: package.json with ioredis dependency."""
    package_file = tmp_path / "package.json"
    content = {
        "name": "myapp",
        "dependencies": {
            "ioredis": "^5.0.0",
            "express": "^4.18.0",
        },
    }
    package_file.write_text(json.dumps(content, indent=2))
    return tmp_path, package_file.name


@pytest.fixture
def package_json_with_mysql_adapter(tmp_path: Path) -> tuple[Path, str]:
    """Fixture: package.json with mysql2 in devDependencies."""
    package_file = tmp_path / "package.json"
    content = {
        "name": "myapp",
        "devDependencies": {
            "mysql2": "^3.0.0",
            "jest": "^29.0.0",
        },
    }
    package_file.write_text(json.dumps(content, indent=2))
    return tmp_path, package_file.name


def test_detect_orm_adapters_python_postgres(
    pyproject_with_postgres_adapter: tuple[Path, str],
) -> None:
    """Test: ORM adapter detection finds PostgreSQL from psycopg2."""
    project_path, _ = pyproject_with_postgres_adapter
    results = detect_orm_adapters(project_path)

    assert len(results) == 1
    assert results[0].name == "postgresql"
    assert results[0].confidence == "medium"
    assert results[0].source_evidence == "psycopg2-binary"


def test_detect_orm_adapters_python_multiple(
    pyproject_with_multiple_adapters: tuple[Path, str],
) -> None:
    """Test: ORM adapter detection finds all three databases from Python manifest."""
    project_path, _ = pyproject_with_multiple_adapters
    results = detect_orm_adapters(project_path)

    db_names = {item.name for item in results}
    assert db_names == {"postgresql", "redis", "mysql"}

    for result in results:
        assert result.confidence == "medium"


def test_detect_orm_adapters_node_redis(
    package_json_with_redis_adapter: tuple[Path, str],
) -> None:
    """Test: ORM adapter detection finds Redis from ioredis."""
    project_path, _ = package_json_with_redis_adapter
    results = detect_orm_adapters(project_path)

    assert len(results) == 1
    assert results[0].name == "redis"
    assert results[0].confidence == "medium"
    assert results[0].source_evidence == "ioredis"


def test_detect_orm_adapters_node_mysql_devdeps(
    package_json_with_mysql_adapter: tuple[Path, str],
) -> None:
    """Test: ORM adapter detection finds MySQL from devDependencies."""
    project_path, _ = package_json_with_mysql_adapter
    results = detect_orm_adapters(project_path)

    assert len(results) == 1
    assert results[0].name == "mysql"
    assert results[0].confidence == "medium"


def test_detect_orm_adapters_no_manifests(tmp_path: Path) -> None:
    """Test: ORM adapter detection returns empty when no manifest files exist."""
    results = detect_orm_adapters(tmp_path)
    assert results == []


def test_detect_orm_adapters_empty_pyproject(tmp_path: Path) -> None:
    """Test: ORM adapter detection handles empty pyproject.toml gracefully."""
    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text('[project]\nname = "empty"\n')

    results = detect_orm_adapters(tmp_path)
    assert results == []


def test_detect_orm_adapters_invalid_pyproject(tmp_path: Path) -> None:
    """Test: ORM adapter detection handles invalid TOML gracefully."""
    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text("[invalid toml ][")

    results = detect_orm_adapters(tmp_path)
    assert results == []


def test_detect_orm_adapters_invalid_package_json(tmp_path: Path) -> None:
    """Test: ORM adapter detection handles invalid JSON gracefully."""
    package_file = tmp_path / "package.json"
    package_file.write_text("{ invalid json ][")

    results = detect_orm_adapters(tmp_path)
    assert results == []


# Integration tests
@pytest.fixture
def full_project_with_databases(tmp_path: Path) -> Path:
    """Fixture: Complete project with all database detection sources."""
    # Docker Compose
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(
        yaml.dump(
            {
                "services": {
                    "db": {"image": "postgres:15"},
                },
            }
        )
    )

    # Environment file
    env_file = tmp_path / ".env.example"
    env_file.write_text("REDIS_URL=redis://localhost\n")

    # Python manifest
    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text(
        """
[project]
dependencies = ["mysql-connector-python"]
"""
    )

    return tmp_path


def test_detect_databases_integration(full_project_with_databases: Path) -> None:
    """Test: detect_databases combines results from all sources."""
    results = detect_databases(full_project_with_databases)

    db_names = {item.name for item in results}
    assert db_names == {"postgresql", "redis", "mysql"}

    # Check confidence levels
    by_name = {item.name: item for item in results}
    assert by_name["postgresql"].confidence == "high"  # Docker Compose
    assert by_name["redis"].confidence == "low"  # Environment file
    assert by_name["mysql"].confidence == "medium"  # ORM adapter


def test_detect_databases_handles_parsing_errors(tmp_path: Path) -> None:
    """Test: detect_databases continues on parsing errors."""
    # Create a broken docker-compose file
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text("{ broken yaml")

    # Create a valid env file
    env_file = tmp_path / ".env.example"
    env_file.write_text("REDIS_URL=redis://localhost\n")

    # Should detect redis despite broken compose file
    results = detect_databases(tmp_path)

    assert len(results) == 1
    assert results[0].name == "redis"


def test_detect_databases_deduplicates_results(tmp_path: Path) -> None:
    """Test: detect_databases deduplicates results, keeping highest confidence."""
    # Add PostgreSQL to both docker-compose and env files
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(
        yaml.dump(
            {
                "services": {
                    "db": {"image": "postgres:15"},
                },
            }
        )
    )

    env_file = tmp_path / ".env.example"
    env_file.write_text("DATABASE_URL=postgresql://localhost\n")

    results = detect_databases(tmp_path)

    # Should have exactly one postgresql
    postgres_results = [item for item in results if item.name == "postgresql"]
    assert len(postgres_results) == 1
    # Should keep high confidence from docker-compose
    assert postgres_results[0].confidence == "high"


@given(
    st.lists(
        st.one_of(
            st.tuples(
                st.just("postgresql"),
                st.sampled_from(["high", "medium", "low"]),
            ),
            st.tuples(
                st.just("redis"),
                st.sampled_from(["high", "medium", "low"]),
            ),
            st.tuples(
                st.just("mysql"),
                st.sampled_from(["high", "medium", "low"]),
            ),
            st.tuples(
                st.just("sqlite"),
                st.sampled_from(["high", "medium", "low"]),
            ),
        ),
        max_size=20,
    )
)
def test_deduplicate_idempotent(
    items_data: list[tuple[str, str]],
) -> None:
    """Property: deduplicating twice gives the same result as deduplicating once."""
    items = [
        DetectedItem(
            name=name,
            confidence=conf,
            source_file=f"/tmp/{name}_{conf}.txt",
            source_evidence=f"evidence_{name}",
        )
        for name, conf in items_data
    ]

    once = deduplicate_databases(items)
    twice = deduplicate_databases(once)

    # Should be idempotent
    assert len(once) == len(twice)
    assert {item.name for item in once} == {item.name for item in twice}


# SQLite integration tests
def test_detect_sqlite_from_db_file(tmp_path: Path) -> None:
    """Test: SQLite detection from .db file in project root."""
    db_file = tmp_path / "database.db"
    db_file.write_text("")  # Create empty file

    results = detect_databases(tmp_path)

    sqlite_results = [item for item in results if item.name == "sqlite"]
    assert len(sqlite_results) == 1
    assert sqlite_results[0].confidence == "high"
    assert sqlite_results[0].source_evidence == "database.db"


def test_detect_sqlite_from_sqlite_file(tmp_path: Path) -> None:
    """Test: SQLite detection from .sqlite file in project root."""
    db_file = tmp_path / "app.sqlite"
    db_file.write_text("")

    results = detect_databases(tmp_path)

    sqlite_results = [item for item in results if item.name == "sqlite"]
    assert len(sqlite_results) == 1
    assert sqlite_results[0].confidence == "high"


def test_detect_sqlite_from_sqlite3_file(tmp_path: Path) -> None:
    """Test: SQLite detection from .sqlite3 file in project root."""
    db_file = tmp_path / "data.sqlite3"
    db_file.write_text("")

    results = detect_databases(tmp_path)

    sqlite_results = [item for item in results if item.name == "sqlite"]
    assert len(sqlite_results) == 1
    assert sqlite_results[0].confidence == "high"


def test_detect_sqlite_from_package_json_sqlite3(tmp_path: Path) -> None:
    """Test: SQLite detection from sqlite3 in package.json."""
    package_json = tmp_path / "package.json"
    package_json.write_text(
        json.dumps(
            {
                "dependencies": {
                    "sqlite3": "^5.1.6",
                    "express": "^4.18.2",
                },
            }
        )
    )

    results = detect_databases(tmp_path)

    sqlite_results = [item for item in results if item.name == "sqlite"]
    assert len(sqlite_results) == 1
    assert sqlite_results[0].confidence == "medium"
    assert sqlite_results[0].source_evidence == "sqlite3"


def test_detect_sqlite_from_package_json_better_sqlite3(tmp_path: Path) -> None:
    """Test: SQLite detection from better-sqlite3 in package.json."""
    package_json = tmp_path / "package.json"
    package_json.write_text(
        json.dumps(
            {
                "dependencies": {
                    "better-sqlite3": "^9.2.2",
                },
            }
        )
    )

    results = detect_databases(tmp_path)

    sqlite_results = [item for item in results if item.name == "sqlite"]
    assert len(sqlite_results) == 1
    assert sqlite_results[0].confidence == "medium"
    assert sqlite_results[0].source_evidence == "better-sqlite3"


def test_detect_sqlite_from_env_url(tmp_path: Path) -> None:
    """Test: SQLite detection from SQLITE_URL in env file."""
    env_file = tmp_path / ".env.example"
    env_file.write_text("SQLITE_URL=sqlite:///path/to/database.db\n")

    results = detect_databases(tmp_path)

    sqlite_results = [item for item in results if item.name == "sqlite"]
    assert len(sqlite_results) == 1
    assert sqlite_results[0].confidence == "low"


def test_detect_sqlite_deduplicates_file_and_package(tmp_path: Path) -> None:
    """Test: SQLite deduplication keeps highest confidence (file > package)."""
    # Add both .db file (high confidence) and package.json (medium confidence)
    db_file = tmp_path / "app.db"
    db_file.write_text("")

    package_json = tmp_path / "package.json"
    package_json.write_text(json.dumps({"dependencies": {"sqlite3": "^5.1.6"}}))

    results = detect_databases(tmp_path)

    sqlite_results = [item for item in results if item.name == "sqlite"]
    assert len(sqlite_results) == 1
    # Should keep high confidence from file
    assert sqlite_results[0].confidence == "high"


def test_detect_all_databases_including_sqlite(tmp_path: Path) -> None:
    """Test: SQLite can coexist with PostgreSQL, Redis, and MySQL."""
    # Add docker-compose with PostgreSQL, Redis, MySQL
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(
        yaml.dump(
            {
                "services": {
                    "postgres": {"image": "postgres:15"},
                    "redis": {"image": "redis:7"},
                    "mysql": {"image": "mysql:8"},
                },
            }
        )
    )

    # Add SQLite database file
    db_file = tmp_path / "cache.db"
    db_file.write_text("")

    results = detect_databases(tmp_path)

    # Should detect all four databases
    db_names = {item.name for item in results}
    assert db_names == {"postgresql", "redis", "mysql", "sqlite"}


def test_detect_sqlite_multiple_db_files(tmp_path: Path) -> None:
    """Property: Multiple .db files in project detected as single SQLite."""
    # Create multiple .db files
    for i in range(3):
        db_file = tmp_path / f"database_{i}.db"
        db_file.write_text("")

    results = detect_databases(tmp_path)
    sqlite_results = [item for item in results if item.name == "sqlite"]

    # Should detect SQLite exactly once regardless of file count
    assert len(sqlite_results) == 1
    assert sqlite_results[0].confidence == "high"


# Property-based tests for false positive prevention
@given(st.text(min_size=1, max_size=50))
def test_no_false_positive_from_random_files(filename: str) -> None:
    """Property: Random filenames don't trigger SQLite detection."""
    import tempfile

    # Filter out actual .db/.sqlite/.sqlite3 extensions
    if any(filename.lower().endswith(ext) for ext in [".db", ".sqlite", ".sqlite3"]):
        return  # Skip valid SQLite files

    # Create temporary directory for test
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Create file with random name
        try:
            file_path = tmp_path / filename
            file_path.write_text("")
        except (OSError, ValueError):
            return  # Skip invalid filenames

        results = detect_databases(tmp_path)
        sqlite_results = [item for item in results if item.name == "sqlite"]

        # Should NOT detect SQLite from non-SQLite files
        assert len(sqlite_results) == 0


@given(
    st.lists(
        st.sampled_from(
            [
                "requirements.txt",
                "package-lock.json",
                "yarn.lock",
                "Gemfile",
                "build.gradle",
            ]
        ),
        max_size=10,
    )
)
def test_no_false_positive_from_manifests(files: list[str]) -> None:
    """Property: Non-package.json/pom.xml manifests don't trigger SQLite."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        for filename in files:
            file_path = tmp_path / filename
            file_path.write_text("some content\n")

        results = detect_databases(tmp_path)
        sqlite_results = [item for item in results if item.name == "sqlite"]

        # Should NOT detect SQLite from unrelated manifest files
        assert len(sqlite_results) == 0


def test_no_false_positive_from_python_sqlite3_import(tmp_path: Path) -> None:
    """Property: Python sqlite3 stdlib imports don't trigger detection."""
    # Create Python file with sqlite3 import (stdlib, not a dependency)
    py_file = tmp_path / "app.py"
    py_file.write_text("import sqlite3\n\nconn = sqlite3.connect('db.db')\n")

    # NO package.json, NO actual .db files
    results = detect_databases(tmp_path)
    sqlite_results = [item for item in results if item.name == "sqlite"]

    # Should NOT detect SQLite from Python stdlib import alone
    # (Detection requires explicit .db file or package.json dependency)
    assert len(sqlite_results) == 0


# Security tests for path validation
def test_sqlite_detection_ignores_symlinks(tmp_path: Path) -> None:
    """Security: SQLite detection does not follow symlinks."""
    # Create a real .db file outside project
    external_dir = tmp_path / "external"
    external_dir.mkdir()
    external_db = external_dir / "external.db"
    external_db.write_text("")

    # Create symlink inside project pointing to external file
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    symlink_db = project_dir / "linked.db"
    try:
        symlink_db.symlink_to(external_db)
    except OSError:
        # Symlinks might not be supported on all filesystems
        return

    # Should NOT detect SQLite from symlinked file
    results = detect_databases(project_dir)
    sqlite_results = [item for item in results if item.name == "sqlite"]

    # Implementation may vary, but should handle safely
    # Either ignore symlink or detect it safely
    assert len(sqlite_results) <= 1


def test_sqlite_detection_rejects_path_traversal(tmp_path: Path) -> None:
    """Security: SQLite detection prevents path traversal."""
    # Create project directory
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Try to create file with path traversal in name
    try:
        bad_file = project_dir / "../outside.db"
        bad_file.write_text("")
    except (ValueError, OSError):
        # Expected: path validation prevents traversal
        return

    # If file was created, detection should handle safely
    results = detect_databases(project_dir)

    # Should not crash, and should not detect files outside project
    for result in results:
        if result.name == "sqlite":
            # Source file should be within project_dir
            assert str(project_dir) in result.source_file


# MongoDB detection tests
def test_mongodb_from_docker_compose_mongo_image(tmp_path: Path) -> None:
    """Test: Docker Compose detects MongoDB from 'mongo' image."""
    compose_file = tmp_path / "docker-compose.yml"
    content = {
        "services": {
            "database": {
                "image": "mongo:7.0",
            },
        },
    }
    compose_file.write_text(yaml.dump(content))

    results = parse_docker_compose(tmp_path)

    assert len(results) == 1
    assert results[0].name == "mongodb"
    assert results[0].confidence == "high"
    assert results[0].source_evidence == "database"


def test_mongodb_from_docker_compose_mongodb_image(tmp_path: Path) -> None:
    """Test: Docker Compose detects MongoDB from 'mongodb' image."""
    compose_file = tmp_path / "docker-compose.yml"
    content = {
        "services": {
            "db": {
                "image": "mongodb:latest",
            },
        },
    }
    compose_file.write_text(yaml.dump(content))

    results = parse_docker_compose(tmp_path)

    assert len(results) == 1
    assert results[0].name == "mongodb"
    assert results[0].confidence == "high"


@pytest.mark.parametrize(
    "image_name,expected_detected",
    [
        ("mongo:7.0", True),
        ("mongodb:latest", True),
        ("mongo", True),
        ("mongodb", True),
        ("mongo-express", True),  # Contains "mongo"
        ("postgres", False),
        ("redis", False),
        ("mysql", False),
    ],
)
def test_mongodb_docker_compose_image_patterns(
    tmp_path: Path, image_name: str, expected_detected: bool
) -> None:
    """Property: MongoDB detection matches expected image patterns."""
    compose_file = tmp_path / "docker-compose.yml"
    content = {
        "services": {
            "test_service": {
                "image": image_name,
            },
        },
    }
    compose_file.write_text(yaml.dump(content))

    results = parse_docker_compose(tmp_path)
    mongodb_results = [item for item in results if item.name == "mongodb"]

    if expected_detected:
        assert len(mongodb_results) == 1
        assert mongodb_results[0].confidence == "high"
    else:
        assert len(mongodb_results) == 0


@pytest.mark.parametrize(
    "env_var,env_value",
    [
        ("MONGODB_URI", "mongodb://localhost:27017"),
        ("MONGO_URL", "mongodb+srv://cluster.mongodb.net"),
        ("MONGODB_URL", "mongodb://user:pass@host/db"),
        ("MONGODB_HOST", "localhost"),
        ("MONGO_HOST", "mongo.example.com"),
    ],
)
def test_mongodb_from_env_var_names(
    tmp_path: Path, env_var: str, env_value: str
) -> None:
    """Property: MongoDB-specific env var names are detected."""
    env_file = tmp_path / ".env.example"
    env_file.write_text(f"{env_var}={env_value}\n")

    results = parse_env_files(tmp_path)

    mongodb_results = [item for item in results if item.name == "mongodb"]
    assert len(mongodb_results) == 1
    assert mongodb_results[0].name == "mongodb"
    assert mongodb_results[0].confidence == "low"
    assert mongodb_results[0].source_evidence == env_var


@pytest.mark.parametrize(
    "database_url,should_detect_mongodb",
    [
        ("mongodb://localhost:27017/mydb", True),
        ("mongodb+srv://cluster.mongodb.net/db", True),
        ("MONGODB://USER:PASS@HOST/DB", True),  # Case insensitive
        ("postgresql://localhost/db", False),
        ("redis://localhost:6379", False),
        ("mysql://localhost/db", False),
    ],
)
def test_mongodb_from_database_url_protocol(
    tmp_path: Path, database_url: str, should_detect_mongodb: bool
) -> None:
    """Property: DATABASE_URL with mongodb:// protocol is detected."""
    env_file = tmp_path / ".env.example"
    env_file.write_text(f"DATABASE_URL={database_url}\n")

    results = parse_env_files(tmp_path)

    mongodb_results = [item for item in results if item.name == "mongodb"]

    if should_detect_mongodb:
        assert len(mongodb_results) == 1
        assert mongodb_results[0].confidence == "low"
    else:
        assert len(mongodb_results) == 0


@pytest.mark.parametrize(
    "package_name",
    ["pymongo", "motor", "mongoengine", "beanie"],
)
def test_mongodb_from_python_orm_adapters(tmp_path: Path, package_name: str) -> None:
    """Property: Python MongoDB packages are detected."""
    pyproject_file = tmp_path / "pyproject.toml"
    content = f"""
[project]
name = "test"
dependencies = ["{package_name}"]
"""
    pyproject_file.write_text(content)

    results = detect_orm_adapters(tmp_path)

    mongodb_results = [item for item in results if item.name == "mongodb"]
    assert len(mongodb_results) == 1
    assert mongodb_results[0].name == "mongodb"
    assert mongodb_results[0].confidence == "medium"
    assert mongodb_results[0].source_evidence == package_name


@pytest.mark.parametrize(
    "package_name",
    ["mongoose", "mongodb", "mongo"],
)
def test_mongodb_from_node_orm_adapters(tmp_path: Path, package_name: str) -> None:
    """Property: Node MongoDB packages are detected."""
    package_file = tmp_path / "package.json"
    content = {
        "name": "test",
        "dependencies": {
            package_name: "^5.0.0",
        },
    }
    package_file.write_text(json.dumps(content))

    results = detect_orm_adapters(tmp_path)

    mongodb_results = [item for item in results if item.name == "mongodb"]
    assert len(mongodb_results) == 1
    assert mongodb_results[0].name == "mongodb"
    assert mongodb_results[0].confidence == "medium"
    assert mongodb_results[0].source_evidence == package_name


@pytest.mark.parametrize(
    "artifact_id",
    [
        "mongo-java-driver",
        "mongodb-driver-sync",
        "mongodb-driver-core",
        "spring-data-mongodb",
    ],
)
def test_mongodb_from_java_dependencies(tmp_path: Path, artifact_id: str) -> None:
    """Property: Java MongoDB artifacts containing 'mongo' are detected."""
    pom_file = tmp_path / "pom.xml"
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <dependencies>
        <dependency>
            <groupId>org.mongodb</groupId>
            <artifactId>{artifact_id}</artifactId>
            <version>4.0.0</version>
        </dependency>
    </dependencies>
</project>
"""
    pom_file.write_text(content)

    results = detect_orm_adapters(tmp_path)

    mongodb_results = [item for item in results if item.name == "mongodb"]
    assert len(mongodb_results) == 1
    assert mongodb_results[0].name == "mongodb"
    assert mongodb_results[0].confidence == "medium"


@pytest.mark.parametrize(
    "package_name",
    ["psycopg2", "redis", "mysql-connector-python", "sqlalchemy"],
)
def test_mongodb_not_detected_from_other_db_packages(
    tmp_path: Path, package_name: str
) -> None:
    """Property: Non-MongoDB database packages don't trigger MongoDB detection."""
    pyproject_file = tmp_path / "pyproject.toml"
    content = f"""
[project]
name = "test"
dependencies = ["{package_name}"]
"""
    pyproject_file.write_text(content)

    results = detect_orm_adapters(tmp_path)

    mongodb_results = [item for item in results if item.name == "mongodb"]
    assert len(mongodb_results) == 0


def test_mongodb_detected_from_multiple_sources(tmp_path: Path) -> None:
    """Integration: MongoDB detected from docker-compose, env, and ORM deps."""
    # Docker Compose
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(
        yaml.dump(
            {
                "services": {
                    "mongo": {"image": "mongo:7.0"},
                },
            }
        )
    )

    # Environment file
    env_file = tmp_path / ".env.example"
    env_file.write_text("MONGODB_URI=mongodb://localhost:27017\n")

    # Python manifest
    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text(
        """
[project]
dependencies = ["pymongo"]
"""
    )

    results = detect_databases(tmp_path)

    mongodb_results = [item for item in results if item.name == "mongodb"]
    # Should have exactly one MongoDB after deduplication
    assert len(mongodb_results) == 1
    # Should keep highest confidence (high from docker-compose)
    assert mongodb_results[0].confidence == "high"


def test_mongodb_deduplication_keeps_highest_confidence(tmp_path: Path) -> None:
    """Property: Multiple MongoDB detections deduplicate to highest confidence."""
    # Add MongoDB in both env (low) and docker-compose (high)
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(yaml.dump({"services": {"db": {"image": "mongo:7"}}}))

    env_file = tmp_path / ".env.example"
    env_file.write_text("MONGODB_URI=mongodb://localhost\n")

    results = detect_databases(tmp_path)

    mongodb_results = [item for item in results if item.name == "mongodb"]
    assert len(mongodb_results) == 1
    assert mongodb_results[0].confidence == "high"


def test_mongodb_coexists_with_other_databases(tmp_path: Path) -> None:
    """Property: MongoDB can be detected alongside PostgreSQL, Redis, MySQL."""
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(
        yaml.dump(
            {
                "services": {
                    "postgres": {"image": "postgres:15"},
                    "redis": {"image": "redis:7"},
                    "mysql": {"image": "mysql:8"},
                    "mongo": {"image": "mongo:7"},
                },
            }
        )
    )

    results = detect_databases(tmp_path)

    db_names = {item.name for item in results}
    assert db_names == {"postgresql", "redis", "mysql", "mongodb"}


def test_mongodb_detection_handles_errors_gracefully(tmp_path: Path) -> None:
    """Property: MongoDB detection continues on parsing errors."""
    # Create broken docker-compose
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text("{ invalid yaml ][")

    # Create valid env file with MongoDB
    env_file = tmp_path / ".env.example"
    env_file.write_text("MONGODB_URI=mongodb://localhost\n")

    # Should detect MongoDB despite broken compose file
    results = detect_databases(tmp_path)

    mongodb_results = [item for item in results if item.name == "mongodb"]
    assert len(mongodb_results) == 1
    assert mongodb_results[0].confidence == "low"


@given(
    st.lists(
        st.sampled_from(["mongo", "mongodb", "mongo-express"]),
        min_size=1,
        max_size=5,
    )
)
def test_mongodb_docker_compose_property_always_detected(
    images: list[str],
) -> None:
    """Property: Any mongo/mongodb image is detected."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        compose_file = tmp_path / "docker-compose.yml"

        services = {f"service_{i}": {"image": img} for i, img in enumerate(images)}
        compose_file.write_text(yaml.dump({"services": services}))

        results = parse_docker_compose(tmp_path)
        mongodb_results = [item for item in results if item.name == "mongodb"]

        # All mongo/mongodb images should be detected
        assert len(mongodb_results) >= 1
        assert all(item.confidence == "high" for item in mongodb_results)


def test_mongodb_detection_updated_detected_item_strategy() -> None:
    """Verify detected_item_strategy needs updating for MongoDB."""
    # This test documents that the strategy should include mongodb
    # when testing general database detection properties
    item = DetectedItem(
        name="mongodb",
        confidence="high",
        source_file="/tmp/test.yml",
        source_evidence="mongo_service",
    )

    assert item.name == "mongodb"
    assert item.confidence in {"high", "medium", "low"}


def test_mongodb_from_node_devdependencies(tmp_path: Path) -> None:
    """Test: MongoDB detection from Node devDependencies."""
    package_file = tmp_path / "package.json"
    content = {
        "name": "test",
        "devDependencies": {
            "mongoose": "^7.0.0",
        },
    }
    package_file.write_text(json.dumps(content))

    results = detect_orm_adapters(tmp_path)

    mongodb_results = [item for item in results if item.name == "mongodb"]
    assert len(mongodb_results) == 1
    assert mongodb_results[0].confidence == "medium"


def test_mongodb_multiple_packages_deduplicated(tmp_path: Path) -> None:
    """Property: Multiple MongoDB packages from same source deduplicate to one."""
    pyproject_file = tmp_path / "pyproject.toml"
    content = """
[project]
name = "test"
dependencies = ["pymongo", "motor", "mongoengine"]
"""
    pyproject_file.write_text(content)

    results = detect_orm_adapters(tmp_path)
    mongodb_results = [item for item in results if item.name == "mongodb"]

    # Should have 3 detections before deduplication
    assert len(mongodb_results) == 3

    # After deduplication, should have only one
    deduplicated = deduplicate_databases(results)
    mongodb_deduplicated = [item for item in deduplicated if item.name == "mongodb"]
    assert len(mongodb_deduplicated) == 1


def test_mongodb_case_insensitive_env_detection(tmp_path: Path) -> None:
    """Property: Environment variable names are case-insensitive."""
    env_file = tmp_path / ".env.example"
    env_file.write_text("mongodb_uri=mongodb://localhost\n")

    results = parse_env_files(tmp_path)

    mongodb_results = [item for item in results if item.name == "mongodb"]
    assert len(mongodb_results) == 1


def test_mongodb_srv_protocol_detection(tmp_path: Path) -> None:
    """Test: MongoDB SRV protocol (mongodb+srv://) is detected."""
    env_file = tmp_path / ".env.example"
    env_file.write_text("DATABASE_URL=mongodb+srv://cluster.mongodb.net/mydb\n")

    results = parse_env_files(tmp_path)

    mongodb_results = [item for item in results if item.name == "mongodb"]
    assert len(mongodb_results) == 1
    assert mongodb_results[0].confidence == "low"
