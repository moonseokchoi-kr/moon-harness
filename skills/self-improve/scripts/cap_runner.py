"""cap_runner.py — Phase D glue: apply 5-entry cap + truncation report.

Wraps:
  - hooks.lib.self_improve.cap.apply_cap (T-4)
  - hooks.lib.self_improve.cap.cap_report (T-4)

Contract (spec F13):
  - Enforces the 5-entry automatic-apply ceiling for project-tier candidates.
  - Excess candidates are routed to the harness proposal queue (by returning
    them in ``deferred``) or scheduled for the next retro run.
  - Silent truncation is FORBIDDEN: if truncation occurs, ``truncated=True``
    and ``deferred_count > 0`` are always present in the result.

Pure stdlib, no network, no LLM calls (F20). Never raises.
"""

from __future__ import annotations

from typing import Any, Dict, List

from hooks.lib.self_improve.cap import DEFAULT_CAP, apply_cap, cap_report


def run_cap(
    project_candidates: List[Any],
    cap: int = DEFAULT_CAP,
) -> Dict[str, Any]:
    """Apply the automatic-apply ceiling to project-tier candidates.

    Args:
        project_candidates: the list of PROJECT-tier approved candidates.
            The list must already be filtered to project tier only — harness
            candidates bypass the cap entirely.
        cap: maximum number of automatic applies in one retro run.
            Defaults to DEFAULT_CAP (5).

    Returns:
        A dict::

            {
                "applied":        list,  # candidates to apply now (len <= cap)
                "deferred":       list,  # excess candidates (route to next retro / harness queue)
                "truncated":      bool,  # True iff deferred is non-empty
                "applied_count":  int,
                "deferred_count": int,
            }

        ``truncated=True`` means the caller MUST report the truncation to the
        user — silent truncation is forbidden (F13).
    """
    # cap_report wraps apply_cap and returns the same shape we want.
    result = cap_report(project_candidates, cap)

    # cap_report already guarantees the shape; return as-is.
    return {
        "applied": result["applied"],
        "deferred": result["deferred"],
        "truncated": result["truncated"],
        "applied_count": result["applied_count"],
        "deferred_count": result["deferred_count"],
    }


def format_truncation_report(cap_result: Dict[str, Any]) -> str:
    """Return a human-readable truncation notice (empty string if no truncation).

    Callers embed this in their Phase D summary so the user is always informed
    of deferred candidates (F13: silent truncation forbidden).

    Args:
        cap_result: the dict returned by ``run_cap()``.

    Returns:
        A non-empty string when ``cap_result["truncated"]`` is True; otherwise
        an empty string.
    """
    if not isinstance(cap_result, dict) or not cap_result.get("truncated"):
        return ""

    applied = cap_result.get("applied_count", 0)
    deferred = cap_result.get("deferred_count", 0)
    return (
        f"[CAP] 자동 적용 상한 초과: {applied}건 적용, {deferred}건 다음 회고 또는 "
        f"harness-proposals 큐로 이동 (silent truncation 금지 — F13)."
    )
