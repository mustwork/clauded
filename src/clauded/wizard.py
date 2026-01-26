"""Interactive setup wizard for clauded."""

from pathlib import Path

import questionary
from questionary import Choice

from .config import Config


def run(project_path: Path) -> Config:
    """Run the interactive wizard and return a Config."""

    print("\n  clauded - VM Environment Setup\n")

    answers = {}

    # Python version (default: 3.12)
    answers["python"] = questionary.select(
        "Python version?",
        choices=["3.12", "3.11", "3.10", "None"],
        default="3.12",
    ).ask()

    if answers["python"] is None:  # User cancelled
        raise KeyboardInterrupt()

    # Node version (default: 20)
    answers["node"] = questionary.select(
        "Node.js version?",
        choices=["22", "20", "18", "None"],
        default="20",
    ).ask()

    if answers["node"] is None:
        raise KeyboardInterrupt()

    # Java version (default: 21)
    answers["java"] = questionary.select(
        "Java version?",
        choices=["21", "17", "11", "None"],
        default="21",
    ).ask()

    if answers["java"] is None:
        raise KeyboardInterrupt()

    # Kotlin version (default: 2.0)
    answers["kotlin"] = questionary.select(
        "Kotlin version?",
        choices=["2.0", "1.9", "None"],
        default="2.0",
    ).ask()

    if answers["kotlin"] is None:
        raise KeyboardInterrupt()

    # Rust version (default: stable)
    answers["rust"] = questionary.select(
        "Rust version?",
        choices=["stable", "nightly", "None"],
        default="stable",
    ).ask()

    if answers["rust"] is None:
        raise KeyboardInterrupt()

    # Go version (default: 1.22)
    answers["go"] = questionary.select(
        "Go version?",
        choices=["1.22", "1.21", "1.20", "None"],
        default="1.22",
    ).ask()

    if answers["go"] is None:
        raise KeyboardInterrupt()

    # Tools (multi-select, defaults: docker, git)
    answers["tools"] = questionary.checkbox(
        "Select tools:",
        choices=[
            Choice("docker", checked=True),
            Choice("git", checked=True),
            Choice("aws-cli", checked=False),
            Choice("gh", checked=False),
            Choice("gradle", checked=False),
        ],
    ).ask()

    if answers["tools"] is None:
        raise KeyboardInterrupt()

    # Databases (multi-select, no defaults)
    answers["databases"] = questionary.checkbox(
        "Select databases:",
        choices=["postgresql", "redis", "mysql"],
    ).ask()

    if answers["databases"] is None:
        raise KeyboardInterrupt()

    # Additional frameworks (multi-select) - claude-code is always included
    additional_frameworks = questionary.checkbox(
        "Additional frameworks:",
        choices=[
            Choice("playwright", checked=False),
        ],
    ).ask()

    if additional_frameworks is None:
        raise KeyboardInterrupt()

    # Always include claude-code
    answers["frameworks"] = ["claude-code"] + additional_frameworks

    # VM resources
    if questionary.confirm("Customize VM resources?", default=False).ask():
        answers["cpus"] = questionary.text("CPUs:", default="4").ask()
        answers["memory"] = questionary.text("Memory:", default="8GiB").ask()
        answers["disk"] = questionary.text("Disk:", default="20GiB").ask()
    else:
        answers["cpus"] = "4"
        answers["memory"] = "8GiB"
        answers["disk"] = "20GiB"

    return Config.from_wizard(answers, project_path)
