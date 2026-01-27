"""CLI integration for detection feature.

This module provides functions to integrate detection into the CLI workflow.
It handles --detect and --no-detect flags, displays detection summaries, and
coordinates detection with wizard invocation.
"""

import json

import click

from .result import DetectionResult


def display_detection_summary(result: DetectionResult) -> None:
    """Display human-readable detection summary to console.

    CONTRACT:
      Inputs:
        - result: DetectionResult with detected languages, versions, tools, etc.

      Outputs:
        - None (prints to console)

      Invariants:
        - Non-empty sections displayed with headers
        - Empty sections omitted from display
        - Scan statistics displayed at end
        - Never raises exceptions

      Algorithm:
        1. Print header "Detection Results:"
        2. If languages detected:
           a. Print "Languages:" section
           b. For each language: display name, confidence, byte count
           c. Highlight primary language
        3. If versions detected:
           a. Print "Versions:" section
           b. For each runtime: display runtime, version, source file
        4. If frameworks detected:
           a. Print "Frameworks:" section
           b. For each framework: display name, confidence
        5. If tools detected:
           a. Print "Tools:" section
           b. For each tool: display name, confidence
        6. If databases detected:
           a. Print "Databases:" section
           b. For each database: display name, confidence
        7. Print scan statistics (files scanned, duration)
    """
    try:
        click.echo("\n📋 Auto-detected from project:\n")

        if result.languages:
            click.echo("Languages:")
            primary = result.get_primary_language()
            for lang in result.languages:
                size_kb = lang.byte_count / 1024
                primary_marker = " (primary)" if lang.name == primary else ""
                # SPEC-002: Differentiate confidence display
                if lang.confidence == "high":
                    confidence_marker = ""  # Brief indicator only
                elif lang.confidence == "medium":
                    confidence_marker = " (detected)"
                else:  # low
                    confidence_marker = " (suggestion)"
                click.echo(
                    f"  • {lang.name}{confidence_marker}{primary_marker} - "
                    f"{lang.file_count} files, {size_kb:.0f}KB"
                )
            click.echo()

        if result.versions:
            click.echo("Versions:")
            for runtime, spec in result.versions.items():
                click.echo(f"  • {runtime}: {spec.version} (from {spec.source_file})")
            click.echo()

        if result.frameworks:
            click.echo("Frameworks:")
            for item in result.frameworks:
                # SPEC-002: Differentiate confidence display
                if item.confidence == "high":
                    confidence_marker = ""
                elif item.confidence == "medium":
                    confidence_marker = " (detected)"
                else:
                    confidence_marker = " (suggestion)"
                click.echo(
                    f"  • {item.name}{confidence_marker} - from {item.source_file}"
                )
            click.echo()

        if result.tools:
            click.echo("Tools:")
            for item in result.tools:
                if item.confidence == "high":
                    confidence_marker = ""
                elif item.confidence == "medium":
                    confidence_marker = " (detected)"
                else:
                    confidence_marker = " (suggestion)"
                click.echo(
                    f"  • {item.name}{confidence_marker} - {item.source_evidence}"
                )
            click.echo()

        if result.databases:
            click.echo("Databases:")
            for item in result.databases:
                if item.confidence == "high":
                    confidence_marker = ""
                elif item.confidence == "medium":
                    confidence_marker = " (detected)"
                else:
                    confidence_marker = " (suggestion)"
                click.echo(
                    f"  • {item.name}{confidence_marker} - from {item.source_file}"
                )
            click.echo()

        if result.scan_stats:
            click.echo(
                f"Scan: {result.scan_stats.files_scanned} files scanned, "
                f"{result.scan_stats.files_excluded} excluded in "
                f"{result.scan_stats.duration_ms}ms\n"
            )

        click.echo("Press Enter to continue with these defaults...\n")
    except Exception:
        # Never raise exceptions - just silently continue
        pass


def display_detection_json(result: DetectionResult) -> None:
    """Display detection results as JSON for programmatic consumption.

    CONTRACT:
      Inputs:
        - result: DetectionResult with detected languages, versions, tools, etc.

      Outputs:
        - None (prints JSON to stdout)

      Invariants:
        - Valid JSON output (parseable)
        - All fields serialized (no Python-specific types)
        - Pretty-printed with indentation
        - Never raises exceptions

      Algorithm:
        1. Convert DetectionResult to dictionary:
           a. Serialize languages list
           b. Serialize versions dict
           c. Serialize frameworks, tools, databases lists
           d. Serialize scan_stats
        2. Use json.dumps with indent=2
        3. Print to stdout
    """
    # TODO: Implement JSON output
    # This is trivial - will implement directly
    data = {
        "languages": [
            {
                "name": lang.name,
                "confidence": lang.confidence,
                "byte_count": lang.byte_count,
                "source_files": lang.source_files[:5],  # Limit sample
            }
            for lang in result.languages
        ],
        "versions": {
            runtime: {
                "version": spec.version,
                "source_file": spec.source_file,
                "constraint_type": spec.constraint_type,
            }
            for runtime, spec in result.versions.items()
        },
        "frameworks": [
            {
                "name": item.name,
                "confidence": item.confidence,
                "source_file": item.source_file,
                "source_evidence": item.source_evidence,
            }
            for item in result.frameworks
        ],
        "tools": [
            {
                "name": item.name,
                "confidence": item.confidence,
                "source_file": item.source_file,
                "source_evidence": item.source_evidence,
            }
            for item in result.tools
        ],
        "databases": [
            {
                "name": item.name,
                "confidence": item.confidence,
                "source_file": item.source_file,
                "source_evidence": item.source_evidence,
            }
            for item in result.databases
        ],
        "scan_stats": (
            {
                "files_scanned": result.scan_stats.files_scanned,
                "files_excluded": result.scan_stats.files_excluded,
                "duration_ms": result.scan_stats.duration_ms,
            }
            if result.scan_stats
            else None
        ),
    }
    print(json.dumps(data, indent=2))


def create_wizard_defaults(result: DetectionResult) -> dict[str, str | list[str]]:
    """Convert detection result to wizard default values.

    CONTRACT:
      Inputs:
        - result: DetectionResult with detected languages, versions, tools, etc.

      Outputs:
        - dictionary with keys matching wizard answer structure:
          * python: detected Python version or latest if language detected
          * node: detected Node version or latest if language detected
          * java: detected Java version or latest if language detected
          * kotlin: detected Kotlin version or latest if language detected
          * rust: detected Rust version or latest if language detected
          * go: detected Go version or latest if language detected
          * tools: list of tool names to pre-check
          * databases: list of database names to pre-check
          * frameworks: list of framework names to pre-check

      Invariants:
        - All keys present (None if not detected)
        - Version strings normalized to match wizard choices
        - When language detected but no version found, uses latest version
        - Never raises exceptions

      Algorithm:
        1. Map detected languages to runtime names
        2. For each runtime:
           a. If version detected, normalize and use it
           b. Else if language detected, use latest version
           c. Else use "None"
        3. Extract tool names from result.tools (confidence high or medium)
        4. Extract database names from result.databases (confidence high or medium)
        5. Extract framework names from result.frameworks
        6. Return dictionary with all keys
    """
    try:
        from .wizard_integration import normalize_version_for_choice

        # Map Linguist language names to runtime keys
        # These are the language names from GitHub Linguist data
        language_to_runtime = {
            "Python": "python",
            "JavaScript": "node",
            "TypeScript": "node",
            "Java": "java",
            "Kotlin": "kotlin",
            "Rust": "rust",
            "Go": "go",
        }

        # Define wizard choices for each runtime (first choice is latest)
        runtime_choices = {
            "python": ["3.12", "3.11", "3.10", "None"],
            "node": ["22", "20", "18", "None"],
            "java": ["21", "17", "11", "None"],
            "kotlin": ["2.0", "1.9", "None"],
            "rust": ["stable", "nightly", "None"],
            "go": ["1.25.6", "1.24.12", "None"],
        }

        # Build set of detected languages (high/medium confidence)
        detected_runtimes: set[str] = set()
        for lang in result.languages:
            if lang.confidence in ("high", "medium"):
                runtime = language_to_runtime.get(lang.name)
                if runtime:
                    detected_runtimes.add(runtime)

        # Extract and normalize versions, using latest when language detected
        defaults: dict[str, str | list[str]] = {}
        for runtime, choices in runtime_choices.items():
            version_spec = result.versions.get(runtime)
            if version_spec:
                # Have explicit version - normalize it
                normalized = normalize_version_for_choice(
                    version_spec.version, runtime, choices
                )
                defaults[runtime] = normalized if normalized else choices[0]
            elif runtime in detected_runtimes:
                # Language detected but no version - use latest
                defaults[runtime] = choices[0]
            else:
                defaults[runtime] = "None"

        # Extract tools with high or medium confidence
        defaults["tools"] = [
            item.name for item in result.tools if item.confidence in ("high", "medium")
        ]

        # Extract databases with high or medium confidence
        defaults["databases"] = [
            item.name
            for item in result.databases
            if item.confidence in ("high", "medium")
        ]

        # Extract frameworks with high or medium confidence, always include claude-code
        frameworks = [
            item.name
            for item in result.frameworks
            if item.confidence in ("high", "medium")
        ]
        if "claude-code" not in frameworks:
            frameworks.insert(0, "claude-code")
        defaults["frameworks"] = frameworks

        # Add default VM resources
        defaults["cpus"] = "4"
        defaults["memory"] = "8GiB"
        defaults["disk"] = "20GiB"

        return defaults
    except Exception:
        # Graceful fallback on any error
        result_dict: dict[str, str | list[str]] = {
            "python": "None",
            "node": "None",
            "java": "None",
            "kotlin": "None",
            "rust": "None",
            "go": "None",
            "tools": [],
            "databases": [],
            "frameworks": ["claude-code"],
            "cpus": "4",
            "memory": "8GiB",
            "disk": "20GiB",
        }
        return result_dict
