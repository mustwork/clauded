# Linguist Data

This directory contains vendored copies of GitHub Linguist's canonical language definition files.

## Files

- **languages.yml** (159 KB) — Complete mapping of file extensions and filenames to programming languages, with metadata for each language (color, type, editors modes, etc.)
- **heuristics.yml** (37 KB) — Disambiguation rules for ambiguous extensions (e.g., `.h` could be C or C++, `.pl` could be Perl or Prolog)
- **vendor.yml** (6.4 KB) — Regular expression patterns for paths that should be excluded from language detection (e.g., node_modules/, vendor/)

## Data Source

All files are downloaded from the official GitHub Linguist repository:
https://github.com/github-linguist/linguist/tree/master/lib/linguist

## Usage

To load Linguist data in your code:

```python
from clauded.linguist import load_languages, load_heuristics, load_vendor_patterns

# Load language definitions
languages = load_languages()  # dict[str, LanguageInfo]

# Load disambiguation rules
heuristics = load_heuristics()  # dict[str, Any]

# Load vendor exclusion patterns
vendor_patterns = load_vendor_patterns()  # list[str]
```

## Updating the Data

To fetch the latest Linguist data from GitHub:

```bash
python scripts/update_linguist_data.py
```

This script:
1. Downloads the three YAML files from GitHub Linguist
2. Validates that each file is valid YAML
3. Stores them in this directory (`src/clauded/linguist/`)
4. Requires no additional dependencies beyond Python's built-in `urllib`

The script can be run in CI/CD pipelines to periodically refresh the vendored data (recommended monthly or quarterly).

## No Runtime Network Dependency

All files are vendored at build time. The application does not make network requests to fetch language definitions at runtime. This ensures:

- Offline functionality
- Predictable performance
- No external service dependencies
- Deterministic builds

## File Sizes

These are compact YAML representations that add ~200 KB to the package:

| File | Size | Records |
|------|------|---------|
| languages.yml | 155 KB | 600+ languages |
| heuristics.yml | 37 KB | 128 disambiguation rules |
| vendor.yml | 6.4 KB | 200+ exclusion patterns |

## Schema Notes

### languages.yml

Each language entry contains:

- `type` — programming, markup, prose, or data
- `extensions` — list of file extensions (e.g., `.py`, `.java`)
- `filenames` — list of special filenames (e.g., `Dockerfile`, `Makefile`)
- `tm_scope` — TextMate scope for syntax highlighting
- `ace_mode` — Ace editor mode
- `language_id` — Internal GitHub identifier
- Optional: `aliases`, `color`, `group`, `interpreters`

### heuristics.yml

Disambiguation rules keyed by ambiguous extensions:

```yaml
disambiguations:
  - extensions: [.h]  # C/C++ header file
    rules:
      - language: C
        pattern: <regex>  # matches C code patterns
      - language: C++
        pattern: <regex>  # matches C++ code patterns
```

### vendor.yml

List of regex patterns to exclude from detection:

```yaml
- (^|/)node_modules/
- (^|/)vendor/
- (^|/)\\.venv/
```

## Testing

Property-based tests verify the integrity of all vendored data:

```bash
pytest tests/test_linguist.py -v
```

Tests verify:
- All files are valid YAML
- Expected languages are present (Python, JavaScript, Java, Rust, etc.)
- Common ambiguous extensions are covered by heuristics
- File structure invariants are maintained
- Extension uniqueness ratio
- Vendor patterns are properly formatted
