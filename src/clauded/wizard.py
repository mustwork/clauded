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

    # Tools (multi-select, defaults: docker, git)
    answers["tools"] = questionary.checkbox(
        "Select tools:",
        choices=[
            Choice("docker", checked=True),
            Choice("git", checked=True),
            Choice("aws-cli", checked=False),
            Choice("gh", checked=False),
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

    # Frameworks (multi-select, default: claude-code)
    answers["frameworks"] = questionary.checkbox(
        "Select frameworks:",
        choices=[
            Choice("claude-code", checked=True),
            Choice("playwright", checked=False),
        ],
    ).ask()

    if answers["frameworks"] is None:
        raise KeyboardInterrupt()

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
