"""Interactive setup wizard for clauded."""

from pathlib import Path

import questionary
from questionary import Choice, Style

from .config import Config

# Custom style: no text inversion, only circle indicators
WIZARD_STYLE = Style(
    [
        ("highlighted", "noreverse"),  # Disable text inversion
        ("selected", "noreverse"),  # Disable inversion for checked items
        ("pointer", "noreverse fg:cyan"),  # Pointer without inversion
        ("answer", "fg:green"),  # Submitted answer
    ]
)


def run(project_path: Path) -> Config:
    """Run the interactive wizard and return a Config."""

    print("\n  clauded - VM Environment Setup\n")

    answers = {}

    # Python version (default: 3.12)
    answers["python"] = questionary.select(
        "Python version?",
        choices=["3.12", "3.11", "3.10", "None"],
        default="3.12",
        use_indicator=True,
        style=WIZARD_STYLE,
        instruction="(enter/→ next, ← previous)",
    ).ask()

    if answers["python"] is None:  # User cancelled
        raise KeyboardInterrupt()

    # Node version (default: 20)
    answers["node"] = questionary.select(
        "Node.js version?",
        choices=["22", "20", "18", "None"],
        default="20",
        use_indicator=True,
        style=WIZARD_STYLE,
        instruction="(enter/→ next, ← previous)",
    ).ask()

    if answers["node"] is None:
        raise KeyboardInterrupt()

    # Java version (default: 21)
    answers["java"] = questionary.select(
        "Java version?",
        choices=["21", "17", "11", "None"],
        default="21",
        use_indicator=True,
        style=WIZARD_STYLE,
        instruction="(enter/→ next, ← previous)",
    ).ask()

    if answers["java"] is None:
        raise KeyboardInterrupt()

    # Kotlin version (default: 2.0)
    answers["kotlin"] = questionary.select(
        "Kotlin version?",
        choices=["2.0", "1.9", "None"],
        default="2.0",
        use_indicator=True,
        style=WIZARD_STYLE,
        instruction="(enter/→ next, ← previous)",
    ).ask()

    if answers["kotlin"] is None:
        raise KeyboardInterrupt()

    # Rust version (default: stable)
    answers["rust"] = questionary.select(
        "Rust version?",
        choices=["stable", "nightly", "None"],
        default="stable",
        use_indicator=True,
        style=WIZARD_STYLE,
        instruction="(enter/→ next, ← previous)",
    ).ask()

    if answers["rust"] is None:
        raise KeyboardInterrupt()

    # Go version (default: 1.25.6)
    answers["go"] = questionary.select(
        "Go version?",
        choices=["1.25.6", "1.24.12", "None"],
        default="1.25.6",
        use_indicator=True,
        style=WIZARD_STYLE,
        instruction="(enter/→ next, ← previous)",
    ).ask()

    if answers["go"] is None:
        raise KeyboardInterrupt()

    # Tools (multi-select, default: docker)
    # Note: git and npm are always installed via common and node roles
    # Note: uv/poetry auto-installed with Python, maven/gradle with Java/Kotlin
    answers["tools"] = questionary.checkbox(
        "Select tools:",
        choices=[
            Choice("docker", checked=True),
            Choice("aws-cli", checked=False),
            Choice("gh", checked=False),
        ],
        style=WIZARD_STYLE,
        instruction="(space to select, enter/→ next, ← previous)",
    ).ask()

    if answers["tools"] is None:
        raise KeyboardInterrupt()

    # Databases (multi-select, no defaults)
    answers["databases"] = questionary.checkbox(
        "Select databases:",
        choices=["postgresql", "redis", "mysql"],
        style=WIZARD_STYLE,
        instruction="(space to select, enter/→ next, ← previous)",
    ).ask()

    if answers["databases"] is None:
        raise KeyboardInterrupt()

    # Additional frameworks (multi-select) - claude-code is always included
    additional_frameworks = questionary.checkbox(
        "Additional frameworks:",
        choices=[
            Choice("playwright", checked=False),
        ],
        style=WIZARD_STYLE,
        instruction="(space to select, enter/→ next, ← previous)",
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


def run_edit(config: Config, project_path: Path) -> Config:
    """Re-run wizard with current config values pre-selected.

    VM resources (CPUs, memory, disk) are preserved from the original config
    since they cannot be changed without recreating the VM.
    """

    print("\n  clauded - Edit VM Configuration\n")
    print("  (VM resources cannot be changed without recreation)\n")

    answers = {}

    # Python version - pre-select current value
    answers["python"] = questionary.select(
        "Python version?",
        choices=["3.12", "3.11", "3.10", "None"],
        default=config.python if config.python else "None",
        use_indicator=True,
        style=WIZARD_STYLE,
        instruction="(enter/→ next, ← previous)",
    ).ask()

    if answers["python"] is None:
        raise KeyboardInterrupt()

    # Node version - pre-select current value
    answers["node"] = questionary.select(
        "Node.js version?",
        choices=["22", "20", "18", "None"],
        default=config.node if config.node else "None",
        use_indicator=True,
        style=WIZARD_STYLE,
        instruction="(enter/→ next, ← previous)",
    ).ask()

    if answers["node"] is None:
        raise KeyboardInterrupt()

    # Java version - pre-select current value
    answers["java"] = questionary.select(
        "Java version?",
        choices=["21", "17", "11", "None"],
        default=config.java if config.java else "None",
        use_indicator=True,
        style=WIZARD_STYLE,
        instruction="(enter/→ next, ← previous)",
    ).ask()

    if answers["java"] is None:
        raise KeyboardInterrupt()

    # Kotlin version - pre-select current value
    answers["kotlin"] = questionary.select(
        "Kotlin version?",
        choices=["2.0", "1.9", "None"],
        default=config.kotlin if config.kotlin else "None",
        use_indicator=True,
        style=WIZARD_STYLE,
        instruction="(enter/→ next, ← previous)",
    ).ask()

    if answers["kotlin"] is None:
        raise KeyboardInterrupt()

    # Rust version - pre-select current value
    answers["rust"] = questionary.select(
        "Rust version?",
        choices=["stable", "nightly", "None"],
        default=config.rust if config.rust else "None",
        use_indicator=True,
        style=WIZARD_STYLE,
        instruction="(enter/→ next, ← previous)",
    ).ask()

    if answers["rust"] is None:
        raise KeyboardInterrupt()

    # Go version - pre-select current value
    answers["go"] = questionary.select(
        "Go version?",
        choices=["1.25.6", "1.24.12", "None"],
        default=config.go if config.go else "None",
        use_indicator=True,
        style=WIZARD_STYLE,
        instruction="(enter/→ next, ← previous)",
    ).ask()

    if answers["go"] is None:
        raise KeyboardInterrupt()

    # Tools - pre-check current selections
    # Note: git and npm are always installed via common and node roles
    # Note: uv/poetry auto-installed with Python, maven/gradle with Java/Kotlin
    answers["tools"] = questionary.checkbox(
        "Select tools:",
        choices=[
            Choice("docker", checked="docker" in config.tools),
            Choice("aws-cli", checked="aws-cli" in config.tools),
            Choice("gh", checked="gh" in config.tools),
        ],
        style=WIZARD_STYLE,
        instruction="(space to select, enter/→ next, ← previous)",
    ).ask()

    if answers["tools"] is None:
        raise KeyboardInterrupt()

    # Databases - pre-check current selections
    answers["databases"] = questionary.checkbox(
        "Select databases:",
        choices=[
            Choice("postgresql", checked="postgresql" in config.databases),
            Choice("redis", checked="redis" in config.databases),
            Choice("mysql", checked="mysql" in config.databases),
        ],
        style=WIZARD_STYLE,
        instruction="(space to select, enter/→ next, ← previous)",
    ).ask()

    if answers["databases"] is None:
        raise KeyboardInterrupt()

    # Additional frameworks - pre-check current selections (claude-code always included)
    additional_frameworks = questionary.checkbox(
        "Additional frameworks:",
        choices=[
            Choice("playwright", checked="playwright" in config.frameworks),
        ],
        style=WIZARD_STYLE,
        instruction="(space to select, enter/→ next, ← previous)",
    ).ask()

    if additional_frameworks is None:
        raise KeyboardInterrupt()

    answers["frameworks"] = ["claude-code"] + additional_frameworks

    # Preserve VM resources from original config (cannot be changed without recreation)
    answers["cpus"] = str(config.cpus)
    answers["memory"] = config.memory
    answers["disk"] = config.disk

    return Config.from_wizard(answers, project_path)
