"""Integration tests for Detection Enhancements feature.

Tests the complete detection pipeline with new MongoDB and Micronaut support.
"""

import tempfile
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from clauded.detect.database import detect_databases
from clauded.detect.framework import detect_frameworks_and_tools


class TestMongoDBDetectionIntegration:
    """Integration tests for MongoDB detection across all sources."""

    def test_mongodb_docker_compose_integration(self):
        """Test MongoDB detection from docker-compose integrates with pipeline."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)

            # Create docker-compose with MongoDB
            compose_file = project / "docker-compose.yml"
            compose_file.write_text(
                """
version: '3.8'
services:
  database:
    image: mongo:7.0
    ports:
      - "27017:27017"
"""
            )

            # Run complete detection pipeline
            databases = detect_databases(project)

            # Verify MongoDB detected with high confidence
            mongodb_items = [db for db in databases if db.name == "mongodb"]
            assert len(mongodb_items) == 1
            assert mongodb_items[0].confidence == "high"
            assert "docker-compose.yml" in mongodb_items[0].source_file
            # source_evidence is the service name from docker-compose
            assert mongodb_items[0].source_evidence == "database"

    def test_mongodb_env_file_integration(self):
        """Test MongoDB detection from env files integrates with pipeline."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)

            # Create .env.example with MongoDB URI
            env_file = project / ".env.example"
            env_file.write_text("MONGODB_URI=mongodb://localhost:27017/mydb\n")

            # Run complete detection pipeline
            databases = detect_databases(project)

            # Verify MongoDB detected with low confidence
            mongodb_items = [db for db in databases if db.name == "mongodb"]
            assert len(mongodb_items) == 1
            assert mongodb_items[0].confidence == "low"
            assert ".env.example" in mongodb_items[0].source_file
            assert mongodb_items[0].source_evidence == "MONGODB_URI"

    def test_mongodb_orm_python_integration(self):
        """Test MongoDB detection from Python ORM integrates with pipeline."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)

            # Create pyproject.toml with pymongo dependency
            pyproject = project / "pyproject.toml"
            pyproject.write_text(
                """
[project]
name = "testproject"
dependencies = ["pymongo>=4.0.0"]
"""
            )

            # Run complete detection pipeline
            databases = detect_databases(project)

            # Verify MongoDB detected with medium confidence
            mongodb_items = [db for db in databases if db.name == "mongodb"]
            assert len(mongodb_items) == 1
            assert mongodb_items[0].confidence == "medium"
            assert "pyproject.toml" in mongodb_items[0].source_file
            assert mongodb_items[0].source_evidence == "pymongo"

    def test_mongodb_orm_node_integration(self):
        """Test MongoDB detection from Node.js ORM integrates with pipeline."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)

            # Create package.json with mongoose dependency
            package_json = project / "package.json"
            package_json.write_text(
                """
{
  "name": "testproject",
  "dependencies": {
    "mongoose": "^7.0.0"
  }
}
"""
            )

            # Run complete detection pipeline
            databases = detect_databases(project)

            # Verify MongoDB detected with medium confidence
            mongodb_items = [db for db in databases if db.name == "mongodb"]
            assert len(mongodb_items) == 1
            assert mongodb_items[0].confidence == "medium"
            assert "package.json" in mongodb_items[0].source_file
            assert mongodb_items[0].source_evidence == "mongoose"

    def test_mongodb_multiple_sources_deduplication(self):
        """Test MongoDB from multiple sources is deduplicated correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)

            # Create multiple MongoDB indicators
            compose_file = project / "docker-compose.yml"
            compose_file.write_text(
                """
services:
  db:
    image: mongo:7.0
"""
            )

            env_file = project / ".env.example"
            env_file.write_text("MONGODB_URI=mongodb://localhost:27017\n")

            pyproject = project / "pyproject.toml"
            pyproject.write_text(
                """
[project]
name = "test"
dependencies = ["pymongo>=4.0.0"]
"""
            )

            # Run complete detection pipeline
            databases = detect_databases(project)

            # Verify MongoDB appears exactly once (deduplicated)
            mongodb_items = [db for db in databases if db.name == "mongodb"]
            assert len(mongodb_items) == 1

            # Verify highest confidence is kept (high from docker-compose)
            assert mongodb_items[0].confidence == "high"

    @given(
        mongodb_image=st.sampled_from(
            ["mongo", "mongodb", "mongo:7.0", "mongodb:latest", "mongo:6.0"]
        )
    )
    def test_mongodb_docker_images_property(self, mongodb_image):
        """Property: All MongoDB image variants are detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)

            compose_file = project / "docker-compose.yml"
            compose_file.write_text(
                f"""
services:
  db:
    image: {mongodb_image}
"""
            )

            databases = detect_databases(project)
            mongodb_items = [db for db in databases if db.name == "mongodb"]

            # Property: MongoDB is detected from any valid mongo image
            assert len(mongodb_items) >= 1

    @given(
        env_var_name=st.sampled_from(
            ["MONGODB_URI", "MONGO_URL", "MONGODB_URL", "MONGODB_HOST", "MONGO_HOST"]
        )
    )
    def test_mongodb_env_vars_property(self, env_var_name):
        """Property: All MongoDB env var patterns are detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)

            env_file = project / ".env.example"
            env_file.write_text(f"{env_var_name}=mongodb://localhost:27017\n")

            databases = detect_databases(project)
            mongodb_items = [db for db in databases if db.name == "mongodb"]

            # Property: MongoDB is detected from any valid env var name
            assert len(mongodb_items) >= 1
            assert mongodb_items[0].source_evidence == env_var_name

    @given(
        orm_package=st.sampled_from(
            ["pymongo", "motor", "mongoengine", "beanie", "mongoose", "mongodb"]
        )
    )
    def test_mongodb_orm_packages_property(self, orm_package):
        """Property: All MongoDB ORM packages are detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)

            # Test Python packages
            if orm_package in ["pymongo", "motor", "mongoengine", "beanie"]:
                pyproject = project / "pyproject.toml"
                pyproject.write_text(
                    f"""
[project]
name = "test"
dependencies = ["{orm_package}>=1.0.0"]
"""
                )
            # Test Node packages
            else:
                package_json = project / "package.json"
                package_json.write_text(
                    f"""
{{
  "name": "test",
  "dependencies": {{
    "{orm_package}": "^1.0.0"
  }}
}}
"""
                )

            databases = detect_databases(project)
            mongodb_items = [db for db in databases if db.name == "mongodb"]

            # Property: MongoDB is detected from any valid ORM package
            assert len(mongodb_items) >= 1
            assert mongodb_items[0].source_evidence == orm_package


class TestMicronautFrameworkIntegration:
    """Integration tests for Micronaut framework detection."""

    def test_micronaut_build_gradle_integration(self):
        """Test Micronaut detection from build.gradle integrates with pipeline."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)

            # Create build.gradle with Micronaut dependencies
            build_gradle = project / "build.gradle"
            build_gradle.write_text(
                """
plugins {
    id 'java'
}

dependencies {
    implementation 'io.micronaut:micronaut-http-server-netty:4.0.0'
    implementation 'io.micronaut:micronaut-validation:4.0.0'
}
"""
            )

            # Run complete detection pipeline
            frameworks, tools = detect_frameworks_and_tools(project)

            # Verify Micronaut detected
            micronaut_items = [fw for fw in frameworks if fw.name == "micronaut"]
            assert len(micronaut_items) >= 1
            assert micronaut_items[0].confidence == "high"
            assert "build.gradle" in micronaut_items[0].source_file

    @given(
        micronaut_artifact=st.sampled_from(
            [
                "micronaut-core",
                "micronaut-http",
                "micronaut-http-server",
                "micronaut-validation",
                "micronaut-data",
                "micronaut-security",
            ]
        )
    )
    def test_micronaut_artifacts_property(self, micronaut_artifact):
        """Property: All Micronaut artifacts are detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)

            build_gradle = project / "build.gradle"
            build_gradle.write_text(
                f"""
dependencies {{
    implementation 'io.micronaut:{micronaut_artifact}:4.0.0'
}}
"""
            )

            frameworks, _ = detect_frameworks_and_tools(project)
            micronaut_items = [fw for fw in frameworks if fw.name == "micronaut"]

            # Property: Micronaut is detected from any valid artifact
            assert len(micronaut_items) >= 1


class TestCompleteDetectionPipeline:
    """Integration tests for the complete detection enhancement pipeline."""

    def test_full_java_project_detection(self):
        """Test detection pipeline on Java project with MongoDB and Micronaut."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)

            # Create complete Java project structure
            build_gradle = project / "build.gradle"
            build_gradle.write_text(
                """
plugins {
    id 'java'
}

dependencies {
    implementation 'io.micronaut:micronaut-core:4.0.0'
    implementation 'org.mongodb:mongodb-driver-sync:4.9.0'
}
"""
            )

            compose_file = project / "docker-compose.yml"
            compose_file.write_text(
                """
services:
  db:
    image: mongo:7.0
"""
            )

            env_file = project / ".env.example"
            env_file.write_text("MONGODB_URI=mongodb://localhost:27017/mydb\n")

            # Run complete detection pipeline
            databases = detect_databases(project)
            frameworks, tools = detect_frameworks_and_tools(project)

            # Verify MongoDB detected (deduplicated from multiple sources)
            mongodb_items = [db for db in databases if db.name == "mongodb"]
            assert len(mongodb_items) == 1
            assert mongodb_items[0].confidence == "high"  # Highest confidence wins

            # Verify Micronaut detected
            micronaut_items = [fw for fw in frameworks if fw.name == "micronaut"]
            assert len(micronaut_items) >= 1

    def test_full_python_project_detection(self):
        """Test complete detection pipeline on Python project with MongoDB."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)

            # Create Python project with MongoDB
            pyproject = project / "pyproject.toml"
            pyproject.write_text(
                """
[project]
name = "myproject"
requires-python = ">=3.10"
dependencies = [
    "fastapi>=0.100.0",
    "pymongo>=4.0.0",
]
"""
            )

            compose_file = project / "docker-compose.yml"
            compose_file.write_text(
                """
services:
  mongodb:
    image: mongodb:7.0
  web:
    build: .
"""
            )

            # Run complete detection pipeline
            databases = detect_databases(project)
            frameworks, _ = detect_frameworks_and_tools(project)

            # Verify MongoDB detected and deduplicated
            mongodb_items = [db for db in databases if db.name == "mongodb"]
            assert len(mongodb_items) == 1

            # Verify FastAPI detected
            fastapi_items = [fw for fw in frameworks if fw.name == "fastapi"]
            assert len(fastapi_items) >= 1

    def test_full_node_project_detection(self):
        """Test complete detection pipeline on Node.js project with MongoDB."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)

            # Create Node.js project with MongoDB
            package_json = project / "package.json"
            package_json.write_text(
                """
{
  "name": "myapp",
  "engines": {
    "node": ">=18.0.0"
  },
  "dependencies": {
    "express": "^4.18.0",
    "mongoose": "^7.0.0"
  }
}
"""
            )

            env_file = project / ".env.example"
            env_file.write_text("MONGO_URL=mongodb+srv://cluster.mongodb.net/mydb\n")

            # Run complete detection pipeline
            databases = detect_databases(project)
            frameworks, _ = detect_frameworks_and_tools(project)

            # Verify MongoDB detected from multiple sources
            mongodb_items = [db for db in databases if db.name == "mongodb"]
            assert len(mongodb_items) == 1

            # Verify Express detected
            express_items = [fw for fw in frameworks if fw.name == "express"]
            assert len(express_items) >= 1
