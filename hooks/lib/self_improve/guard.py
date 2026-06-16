"""Protected-set guard for the self-improving harness.

The protected set is the closure of artifacts that the self-improvement loops
must never auto-modify: the loops' own skills (self-improve, pr-converge), the
critic agent that reviews proposed harness changes, and the enforcement gate
scripts that police the whole pipeline. Allowing the loop to rewrite any of
these would let it disable its own safety rails.

The set is a HARDCODED constant table (frozenset of path prefixes). It is
deliberately not configurable or data-driven — a protected entry cannot be
removed by editing a config file, only by editing this source (which is itself
a protected, human-gated change).

Pure, deterministic, stdlib-only (F20). No LLM/gh/network calls.
"""

from __future__ import annotations

from typing import FrozenSet

# --- Protected path-prefix table (hardcoded constant) --------------------
#
# Each entry is a POSIX-style path *prefix*. A target is protected if its
# normalized path equals an entry or sits underneath one (prefix + "/...").
# Matching is suffix-anchored: the protected segment may appear after a
# worktree / repo root prefix.

PROTECTED_SET: FrozenSet[str] = frozenset(
    {
        # the two self-improvement loops
        "skills/self-improve",
        "skills/pr-converge",
        # the critic agent that gates harness-tier proposals
        "agents/harness-improvement-critic.md",
        # enforcement gate scripts (the pipeline's safety rails)
        "hooks/enforcement",
    }
)


def _normalize(target_path: str) -> str:
    """Normalize a path to forward slashes, stripped.

    Fail-safe: non-string / empty input yields an empty string, which is not
    protected (the caller can then apply its own default-deny if desired).
    """
    if not isinstance(target_path, str):
        return ""
    p = target_path.strip().replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p.rstrip("/")


def _matches_prefix(path: str, prefix: str) -> bool:
    """True if ``path`` equals ``prefix`` or lives under it.

    The protected ``prefix`` may appear anywhere as a path segment boundary,
    so a worktree-rooted absolute path (e.g.
    ``/repo/skills/self-improve/SKILL.md``) still matches ``skills/self-improve``.
    """
    if not path or not prefix:
        return False
    # exact match
    if path == prefix:
        return True
    # path lives under the prefix: ".../<prefix>/<rest>"
    if path.endswith("/" + prefix):
        return True
    if ("/" + prefix + "/") in ("/" + path + "/"):
        return True
    # prefix at the very start: "<prefix>/<rest>"
    if path.startswith(prefix + "/"):
        return True
    return False


def is_protected(target_path: str) -> bool:
    """Return True if ``target_path`` is in the protected set.

    A protected artifact must NEVER be auto-modified by the self-improvement
    loops; callers treat a True result as a hard block (proposal-only at most).
    """
    path = _normalize(target_path)
    if not path:
        return False
    for prefix in PROTECTED_SET:
        if _matches_prefix(path, prefix):
            return True
    return False
