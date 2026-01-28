# Thread-Safe Linguist Data Cache

**Audit Reference**: Important #5 | Severity: 4/10
**Source**: `.claude/audit-reports/spec-2026-01-28.md`

## Problem

The linguist module uses a global mutable variable `_cached_data: dict[str, Any] | None = None` (`linguist.py:98`) to cache loaded YAML data. This is thread-unsafe: if two threads call detection concurrently, both may attempt to initialize the cache simultaneously, potentially reading partially-initialized data.

While clauded currently runs single-threaded, this is a latent defect that will surface if detection is ever parallelized or used as a library.

## Requirements

### FR-1: Thread-Safe Cache

Replace the global `_cached_data` variable with `functools.lru_cache` on the loading functions. `lru_cache` is thread-safe for initialization in CPython (GIL protects the cache dict).

The cached functions should be:
- `load_languages()` -> cached
- `load_heuristics()` -> cached
- `load_vendor_patterns()` -> cached

### FR-2: No Behavioral Change

The caching behavior must remain identical: load once on first call, return cached data on subsequent calls. No performance regression.

## Affected Files

- `src/clauded/linguist/__init__.py` or `src/clauded/detect/linguist.py:98`
- `tests/test_linguist.py` (verify caching still works)
