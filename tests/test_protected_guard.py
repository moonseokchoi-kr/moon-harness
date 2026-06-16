"""tests/test_protected_guard.py — is_protected / PROTECTED_SET 단위 테스트.

오프라인 전용. protected set은 하드코딩 상수 — 멤버/비멤버 경로 매칭 검증.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hooks.lib.self_improve import (  # noqa: E402
    PROTECTED_SET,
    is_protected,
)


def test_protected_set_is_frozenset():
    assert isinstance(PROTECTED_SET, frozenset)
    # the canonical members must be present
    assert "skills/self-improve" in PROTECTED_SET
    assert "skills/pr-converge" in PROTECTED_SET
    assert "agents/harness-improvement-critic.md" in PROTECTED_SET
    assert "hooks/enforcement" in PROTECTED_SET


# --- Protected (members + descendants) -----------------------------------

@pytest.mark.parametrize(
    "path",
    [
        "skills/self-improve",
        "skills/self-improve/SKILL.md",
        "skills/self-improve/scripts/router.py",
        "skills/pr-converge",
        "skills/pr-converge/SKILL.md",
        "agents/harness-improvement-critic.md",
        "hooks/enforcement",
        "hooks/enforcement/stop-pipeline.py",
        "hooks/enforcement/lib/constants.sh",
        # worktree-rooted absolute paths must still match
        "/Users/x/repo/skills/self-improve/SKILL.md",
        "/abs/hooks/enforcement/tdd-gate.sh",
        # backslash normalization
        "skills\\self-improve\\SKILL.md",
    ],
)
def test_protected_paths(path):
    assert is_protected(path) is True


# --- Not protected -------------------------------------------------------

@pytest.mark.parametrize(
    "path",
    [
        "skills/sdd/SKILL.md",
        "skills/self-improve-helper/foo.md",   # similar prefix but distinct dir
        "agents/sdd-reviewer.md",
        "agents/harness-improvement-critic-notes.md",  # not the exact file
        "hooks/file-ownership.sh",             # a hook, but not under enforcement/
        "hooks/lib/self_improve/tier.py",
        "docs/lessons-learned.md",
        "",
        "   ",
    ],
)
def test_unprotected_paths(path):
    assert is_protected(path) is False


def test_non_string_is_not_protected():
    assert is_protected(None) is False  # type: ignore[arg-type]
    assert is_protected(123) is False   # type: ignore[arg-type]
