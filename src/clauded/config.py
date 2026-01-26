"""Configuration management for .clauded.yaml files."""

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Config:
    """Represents a .clauded.yaml configuration."""

    version: str = "1"

    # VM settings
    vm_name: str = ""
    cpus: int = 4
    memory: str = "8GiB"
    disk: str = "20GiB"

    # Mount settings
    mount_host: str = ""
    mount_guest: str = "/workspace"

    # Environment
    python: str | None = None
    node: str | None = None
    java: str | None = None
    kotlin: str | None = None
    rust: str | None = None
    go: str | None = None
    tools: list[str] = field(default_factory=list)
    databases: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)

    @classmethod
    def from_wizard(cls, answers: dict, project_path: Path) -> "Config":
        """Create a Config from wizard answers."""
        path_hash = hashlib.md5(str(project_path).encode()).hexdigest()[:8]
        vm_name = f"clauded-{path_hash}"

        return cls(
            vm_name=vm_name,
            cpus=int(answers.get("cpus", 4)),
            memory=answers.get("memory", "8GiB"),
            disk=answers.get("disk", "20GiB"),
            mount_host=str(project_path),
            python=answers.get("python") if answers.get("python") != "None" else None,
            node=answers.get("node") if answers.get("node") != "None" else None,
            java=answers.get("java") if answers.get("java") != "None" else None,
            kotlin=answers.get("kotlin") if answers.get("kotlin") != "None" else None,
            rust=answers.get("rust") if answers.get("rust") != "None" else None,
            go=answers.get("go") if answers.get("go") != "None" else None,
            tools=answers.get("tools", []),
            databases=answers.get("databases", []),
            frameworks=answers.get("frameworks", []),
        )

    @classmethod
    def load(cls, path: Path) -> "Config":
        """Load config from a .clauded.yaml file."""
        with open(path) as f:
            data = yaml.safe_load(f)

        return cls(
            version=data.get("version", "1"),
            vm_name=data["vm"]["name"],
            cpus=data["vm"]["cpus"],
            memory=data["vm"]["memory"],
            disk=data["vm"]["disk"],
            mount_host=data["mount"]["host"],
            mount_guest=data["mount"]["guest"],
            python=data["environment"].get("python"),
            node=data["environment"].get("node"),
            java=data["environment"].get("java"),
            kotlin=data["environment"].get("kotlin"),
            rust=data["environment"].get("rust"),
            go=data["environment"].get("go"),
            tools=data["environment"].get("tools", []),
            databases=data["environment"].get("databases", []),
            frameworks=data["environment"].get("frameworks", []),
        )

    def save(self, path: Path) -> None:
        """Save config to a .clauded.yaml file."""
        data = {
            "version": self.version,
            "vm": {
                "name": self.vm_name,
                "cpus": self.cpus,
                "memory": self.memory,
                "disk": self.disk,
            },
            "mount": {
                "host": self.mount_host,
                "guest": self.mount_guest,
            },
            "environment": {
                "python": self.python,
                "node": self.node,
                "java": self.java,
                "kotlin": self.kotlin,
                "rust": self.rust,
                "go": self.go,
                "tools": self.tools,
                "databases": self.databases,
                "frameworks": self.frameworks,
            },
        }

        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
