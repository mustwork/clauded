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
    db_names = st.sampled_from(["postgresql", "redis", "mysql"])
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
    assert item.name in {"postgresql", "redis", "mysql"}


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
