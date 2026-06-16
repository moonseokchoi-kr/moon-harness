"""precheck_runner.py — Phase C glue: is_protected + classify_tier + run_prechecks.

Wraps:
  - hooks.lib.self_improve.guard.is_protected (T-2)
  - hooks.lib.self_improve.tier.classify_tier (T-2)
  - hooks.lib.self_improve.precheck.run_prechecks (T-3)

Contract:
  - Accepts a list of candidate entry dicts and a target_path per candidate.
  - For each candidate:
      1. is_protected(target_path) → True  → discard immediately (PROTECTED).
      2. classify_tier(target_path) → PROJECT | HARNESS.
      3. run_prechecks(candidate, target_file_text, entries) → precheck result.
  - Returns a structured list of per-candidate result dicts.

  The function never raises.  target_file_text must be supplied by the caller
  (read the target file before calling — this keeps I/O out of the core).

Pure stdlib, no network, no LLM calls (F20).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from hooks.lib.self_improve.guard import is_protected
from hooks.lib.self_improve.precheck import run_prechecks
from hooks.lib.self_improve.tier import classify_tier


def run_precheck_pipeline(
    candidates: List[Dict[str, Any]],
    target_file_text: str = "",
    entries: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Run the three-stage Phase C pipeline on each candidate.

    Each candidate dict is expected to have at least:
      - ``"marker"`` (str)
      - ``"body"`` (str)
      - ``"target_path"`` (str) — the artifact being changed

    Args:
        candidates: list of improvement candidate entry dicts.
        target_file_text: current text of the improvement target file.
            Pass ``""`` (empty) when the target file doesn't exist yet.
        entries: full list of new entries for sparsity counting.
            Defaults to ``candidates`` when omitted.

    Returns:
        A list (same length as ``candidates``) of result dicts::

            {
                "candidate":    dict,   # original candidate
                "target_path":  str,
                "tier":         str,    # "PROJECT" | "HARNESS"
                "protected":    bool,
                "discarded":    bool,   # True = do not proceed
                "discard_reason": str,  # non-empty when discarded=True
                "precheck":     dict,   # run_prechecks output (or {})
            }

        When ``protected=True``, the candidate is discarded immediately and
        ``precheck`` is ``{}``.  The caller MUST NOT dispatch a critic agent
        for discarded candidates.
    """
    if not isinstance(candidates, list):
        return []

    all_entries = entries if isinstance(entries, list) else candidates

    results: List[Dict[str, Any]] = []

    for candidate in candidates:
        if not isinstance(candidate, dict):
            results.append(
                {
                    "candidate": candidate,
                    "target_path": "",
                    "tier": "HARNESS",
                    "protected": False,
                    "discarded": True,
                    "discard_reason": "Candidate is not a dict.",
                    "precheck": {},
                }
            )
            continue

        target_path: str = candidate.get("target_path", "") or ""

        # ── Stage 1: Protected check ─────────────────────────────────────────
        try:
            protected: bool = is_protected(target_path)
        except Exception:  # noqa: BLE001
            protected = False  # fail-safe: unknown → not protected

        if protected:
            results.append(
                {
                    "candidate": candidate,
                    "target_path": target_path,
                    "tier": "HARNESS",  # protected implies harness scope
                    "protected": True,
                    "discarded": True,
                    "discard_reason": (
                        f"Target path '{target_path}' is in the protected set. "
                        "Auto-modification of protected artifacts is forbidden (F19)."
                    ),
                    "precheck": {},
                }
            )
            continue

        # ── Stage 2: Tier classification ─────────────────────────────────────
        try:
            tier: str = classify_tier(target_path)
        except Exception:  # noqa: BLE001
            tier = "HARNESS"  # fail-safe: conservative default (F11)

        # ── Stage 3: Pre-check pipeline ──────────────────────────────────────
        try:
            precheck_result: Dict[str, Any] = run_prechecks(
                candidate, target_file_text, all_entries
            )
        except Exception as exc:  # noqa: BLE001
            # run_prechecks should never raise; be defensive.
            precheck_result = {
                "conflict": False,
                "conflict_reason": "",
                "duplicate": False,
                "duplicate_reason": "",
                "too_sparse": True,
                "too_sparse_reason": f"run_prechecks raised unexpectedly: {exc}",
                "passed": False,
            }

        # Determine discard based on precheck outcome.
        passed: bool = bool(precheck_result.get("passed", False))
        discarded = not passed
        discard_reason = ""
        if not passed:
            reasons = []
            if precheck_result.get("conflict"):
                reasons.append(f"conflict: {precheck_result.get('conflict_reason', '')}")
            if precheck_result.get("duplicate"):
                reasons.append(f"duplicate: {precheck_result.get('duplicate_reason', '')}")
            if precheck_result.get("too_sparse"):
                reasons.append(f"too_sparse: {precheck_result.get('too_sparse_reason', '')}")
            discard_reason = "; ".join(reasons) if reasons else "precheck failed"

        results.append(
            {
                "candidate": candidate,
                "target_path": target_path,
                "tier": tier,
                "protected": False,
                "discarded": discarded,
                "discard_reason": discard_reason,
                "precheck": precheck_result,
            }
        )

    return results
