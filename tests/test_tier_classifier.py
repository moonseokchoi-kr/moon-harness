"""tests/test_tier_classifier.py — classify_tier 단위 테스트.

오프라인 전용. 네트워크/LLM 무호출. F11 보수적 기본값(모호 → HARNESS) 검증.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hooks.lib.self_improve import (  # noqa: E402
    HARNESS,
    PROJECT,
    classify_tier,
)


# --- HARNESS-tier paths --------------------------------------------------

@pytest.mark.parametrize(
    "path",
    [
        "skills/self-improve/SKILL.md",
        "skills/pr-converge/scripts/foo.py",
        "skills/sdd/SKILL.md",
        "agents/harness-improvement-critic.md",
        "agents/sdd-reviewer.md",
        "hooks/enforcement/stop-pipeline.py",
        "hooks/lib/self_improve/tier.py",
        "hooks/file-ownership.sh",
        # worktree-rooted absolute paths still classify as harness
        "/Users/x/repo/skills/self-improve/SKILL.md",
        "/abs/agents/some-agent.md",
    ],
)
def test_harness_paths(path):
    assert classify_tier(path, {}) == HARNESS


# --- PROJECT-tier paths --------------------------------------------------

@pytest.mark.parametrize(
    "path",
    [
        "docs/lessons-learned.md",
        "docs/pitfalls.md",
        ".harness/LEARNING.md",
        ".harness/config/foo.json",
        "/abs/repo/.harness/state.json",
        "./docs/lessons-learned.md",
    ],
)
def test_project_paths(path):
    assert classify_tier(path, {}) == PROJECT


# --- Ambiguous -> HARNESS default (F11) ----------------------------------

@pytest.mark.parametrize(
    "path",
    [
        "src/main.py",
        "README.md",
        "docs/some-other.md",          # docs/ but not a known ledger
        "random/path/file.txt",
        "",                            # empty
        "   ",                         # whitespace only
    ],
)
def test_ambiguous_defaults_to_harness(path):
    assert classify_tier(path, {}) == HARNESS


def test_none_scope_flags_default_harness():
    # scope_flags omitted entirely
    assert classify_tier("unknown/thing.py") == HARNESS


def test_non_string_path_defaults_harness():
    # fail-safe: non-string falls through to HARNESS
    assert classify_tier(None, {}) == HARNESS  # type: ignore[arg-type]


# --- Scope flag overrides ------------------------------------------------

def test_force_harness_flag():
    assert classify_tier("docs/lessons-learned.md", {"force_harness": True}) == HARNESS


def test_cross_project_flag_forces_harness():
    assert classify_tier("docs/pitfalls.md", {"cross_project": True}) == HARNESS


def test_force_project_only_for_non_harness_path():
    # an unknown path with force_project becomes PROJECT
    assert classify_tier("src/foo.py", {"force_project": True}) == PROJECT


def test_force_project_cannot_downgrade_harness_path():
    # a harness artifact can never be forced down to project tier
    assert (
        classify_tier("skills/self-improve/SKILL.md", {"force_project": True})
        == HARNESS
    )


# --- HARNESS precedence over PROJECT-looking suffix ----------------------

def test_harness_wins_over_project_suffix():
    # a path that contains both: harness pattern must win
    assert classify_tier("hooks/lib/docs/lessons-learned.md", {}) == HARNESS
