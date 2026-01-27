#!/usr/bin/env python3
"""
Fetch and vendor GitHub Linguist's canonical YAML files.

This script downloads the three essential Linguist data files:
  - languages.yml: Extension → language mapping
  - heuristics.yml: Disambiguation rules for ambiguous extensions
  - vendor.yml: Paths to exclude from detection

Files are stored in src/clauded/linguist/ for inclusion in the package.
No runtime network dependency - all files are vendored at build time.

Usage:
    python scripts/update_linguist_data.py
"""

import sys
import urllib.request
from pathlib import Path

# URLs to GitHub Linguist raw content
LINGUIST_BASE = (
    "https://raw.githubusercontent.com/github-linguist/linguist/master/lib/linguist"
)
FILES = {
    "languages.yml": f"{LINGUIST_BASE}/languages.yml",
    "heuristics.yml": f"{LINGUIST_BASE}/heuristics.yml",
    "vendor.yml": f"{LINGUIST_BASE}/vendor.yml",
}

VENDOR_DIR = Path(__file__).parent.parent / "src" / "clauded" / "linguist"


def fetch_file(name: str, url: str) -> bool:
    """Download a single file from GitHub Linguist."""
    try:
        print(f"Downloading {name}...", end=" ", flush=True)
        with urllib.request.urlopen(url) as response:
            content = response.read()

        # Verify basic YAML content (should start with # or ---)
        # This catches actual YAML files and avoids HTML error pages
        if not (content.startswith(b"#") or content.startswith(b"---")):
            print("FAILED (invalid YAML)")
            return False

        # Write to vendor directory
        target = VENDOR_DIR / name
        target.write_bytes(content)
        print(f"OK ({len(content)} bytes)")
        return True
    except Exception as e:
        print(f"FAILED ({e})")
        return False


def main() -> int:
    """Main entry point."""
    VENDOR_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Vendoring Linguist data to {VENDOR_DIR}\n")

    results = {}
    for name, url in FILES.items():
        results[name] = fetch_file(name, url)

    print()
    if all(results.values()):
        print("✓ All files downloaded successfully")
        return 0
    else:
        failed = [name for name, success in results.items() if not success]
        print(f"✗ Failed to download: {', '.join(failed)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
