"""Tests for the CCR Anthropic-transformer useBearer patch.

The role at src/clauded/roles/claude_code_router/tasks/main.yml flips the
default of `useBearer` in the bundled @musistudio/llms Anthropic transformer
from `false` to `true`. This is a textual patch against minified JS, so it
has two failure modes the production code can't catch on its own:

  1. The npm-installed CCR ships a different bundle (minifier output drift,
     or a CCR version bump). The pre-patch sentinel won't be found, and the
     replace task no-ops without anyone noticing — because Ansible's `replace`
     does not fail on zero-match by default.
  2. The role and the patch text drift apart (someone edits one but not
     the other).

These tests guard both: (1) by checking the role's literal regex/replace
strings still hit a checked-in fixture of the current CCR 1.0.73 bundle
excerpt; (2) by re-deriving the patch operation from the role's own task
file and asserting the result.

When CCR is bumped (`ccr_version` in defaults/main.yml), refresh the fixture
from the new bundle and re-run these tests — that's the boy-scout drift
detector.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
ROLE_TASKS = REPO_ROOT / "src/clauded/roles/claude_code_router/tasks/main.yml"
FIXTURE = REPO_ROOT / "tests/fixtures/ccr_anthropic_transformer_1_0_73.js"

PRE_PATCH = "this.useBearer = this.options?.UseBearer ?? false;"
POST_PATCH = "this.useBearer = this.options?.UseBearer ?? true;"


@pytest.fixture(scope="module")
def role_tasks() -> list[dict]:
    return yaml.safe_load(ROLE_TASKS.read_text())


@pytest.fixture(scope="module")
def patch_task(role_tasks: list[dict]) -> dict:
    matches = [
        t
        for t in role_tasks
        if t.get("name", "").startswith("Patch CCR Anthropic transformer")
    ]
    assert len(matches) == 1, "expected exactly one transformer-patch task"
    return matches[0]


def test_fixture_contains_unmodified_anthropic_class() -> None:
    src = FIXTURE.read_text()
    assert 'name = "Anthropic"' in src, "fixture is not the Anthropic class"
    assert PRE_PATCH in src, (
        "fixture missing the pre-patch sentinel — refresh the fixture from "
        "the current CCR bundle"
    )


def test_role_uses_expected_replacement(patch_task: dict) -> None:
    spec = patch_task["ansible.builtin.replace"]
    assert spec["replace"] == POST_PATCH


def test_role_regex_matches_pre_patch_sentinel(patch_task: dict) -> None:
    pattern = patch_task["ansible.builtin.replace"]["regexp"]
    assert re.search(
        pattern, PRE_PATCH
    ), f"role regex {pattern!r} does not match the pre-patch sentinel"


def test_role_regex_does_not_match_post_patch(patch_task: dict) -> None:
    pattern = patch_task["ansible.builtin.replace"]["regexp"]
    assert not re.search(pattern, POST_PATCH), (
        "role regex still matches the post-patch form — re-running the role "
        "would re-rewrite an already-patched line (semantic no-op but a "
        "false-positive `changed=true` on every reprovision)"
    )


def test_applying_role_replacement_to_fixture_yields_post_patch() -> None:
    spec = yaml.safe_load(ROLE_TASKS.read_text())
    patch = next(
        t["ansible.builtin.replace"]
        for t in spec
        if t.get("name", "").startswith("Patch CCR Anthropic transformer")
    )
    src = FIXTURE.read_text()
    patched = re.sub(patch["regexp"], patch["replace"], src)
    assert PRE_PATCH not in patched
    assert patched.count(POST_PATCH) == 1


def test_post_patch_sentinel_appears_exactly_once_in_fixture() -> None:
    """Single-occurrence guard: if the bundle ever contains two `?? false`
    matches, the role's `replace` would change both — and one of them might
    not be the Anthropic transformer. Refresh the fixture and audit the
    regex if this fails."""
    src = FIXTURE.read_text()
    assert src.count(PRE_PATCH) == 1
