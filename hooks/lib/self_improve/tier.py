"""Tier classifier for self-improving harness changes.

Given a change descriptor (a target path plus optional scope flags), decide
whether the change belongs to the PROJECT tier (auto-applicable, repo-local)
or the HARNESS tier (cross-project, proposal-only behind the human gate).

F11 invariant: when classification is ambiguous, default to HARNESS. The
conservative default ensures that a misclassified change never silently
escalates from project-local to cross-project behavior.

Pure, deterministic, stdlib-only (F20). No LLM/gh/network calls.
"""

from __future__ import annotations

import re
from typing import Dict, Optional

# Literal is available in typing on 3.8+, but keep import guarded for clarity.
try:  # pragma: no cover - import shim only
    from typing import Literal

    Tier = Literal["PROJECT", "HARNESS"]
except ImportError:  # pragma: no cover
    Tier = str  # type: ignore[misc,assignment]

PROJECT: str = "PROJECT"
HARNESS: str = "HARNESS"

# --- Path pattern tables -------------------------------------------------
#
# Patterns are matched against a normalized, forward-slash POSIX-style path.
# The match is intentionally substring/regex based so that paths with leading
# directories (worktree roots, repo prefixes) still classify correctly.
#
# HARNESS patterns are checked FIRST: a path that looks like a shared harness
# artifact (skills, agents, hooks) is cross-project by definition and must win
# over any project-looking suffix.

HARNESS_PATTERNS = (
    # plugin skills (any depth, with or without SKILL.md)
    re.compile(r"(^|/)skills/"),
    # agent definitions
    re.compile(r"(^|/)agents/[^/]+\.md$"),
    re.compile(r"(^|/)agents/"),
    # hooks (bash + python enforcement glue, shared lib)
    re.compile(r"(^|/)hooks/"),
)

PROJECT_PATTERNS = (
    # learned-lesson / pitfall ledgers are repo-local knowledge
    re.compile(r"(^|/)docs/lessons-learned\.md$"),
    re.compile(r"(^|/)docs/pitfalls\.md$"),
    # per-repo harness config / logs (NOT the shared hooks/ tree)
    re.compile(r"(^|/)\.harness/"),
)


def _normalize(target_path: str) -> str:
    """Normalize a path to forward slashes, stripped, for matching.

    Fail-safe: a non-string or empty input yields an empty string, which
    matches no pattern and therefore falls through to the HARNESS default.
    """
    if not isinstance(target_path, str):
        return ""
    p = target_path.strip().replace("\\", "/")
    # collapse any accidental leading "./"
    while p.startswith("./"):
        p = p[2:]
    return p


def classify_tier(
    target_path: str, scope_flags: Optional[Dict[str, object]] = None
) -> str:
    """Classify a change target into PROJECT or HARNESS.

    Args:
        target_path: the artifact path being changed (any OS separator).
        scope_flags: optional descriptor flags. Recognized keys:
            - ``force_harness`` (truthy) -> always HARNESS.
            - ``force_project`` (truthy) -> PROJECT *only if* the path is not
              a harness artifact (a harness path can never be forced down to
              project tier; that would violate the cross-project invariant).
            - ``cross_project`` (truthy) -> HARNESS (observed in ≥2 repos).

    Returns:
        ``"PROJECT"`` or ``"HARNESS"``. Defaults to ``"HARNESS"`` whenever
        the path matches no known PROJECT pattern (F11 conservative default).
    """
    flags = scope_flags or {}

    # Explicit cross-project signal forces harness tier regardless of path.
    if flags.get("force_harness") or flags.get("cross_project"):
        return HARNESS

    path = _normalize(target_path)

    # HARNESS patterns win first — a shared artifact is cross-project by nature.
    for pat in HARNESS_PATTERNS:
        if pat.search(path):
            return HARNESS

    # PROJECT patterns: repo-local knowledge / config.
    for pat in PROJECT_PATTERNS:
        if pat.search(path):
            return PROJECT

    # A force_project flag only matters for paths that did not match a harness
    # pattern (we already returned above if they did). Honor it here.
    if flags.get("force_project"):
        return PROJECT

    # Ambiguous / unknown path -> conservative default (F11).
    return HARNESS
