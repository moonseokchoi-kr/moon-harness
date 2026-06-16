"""apply_writer.py — Phase D glue: apply project-tier changes + harness proposals.

Contract (spec F11, F13):
  - PROJECT tier, UPHELD/NARROW:
      * Append ``append_text`` to the target file (create if missing).
      * Append a rollback block to ``.harness/retro-log.md``.
      * NEVER edit plugin files (skills/, agents/, hooks/).
  - HARNESS tier, UPHELD/NARROW:
      * Write ``.harness/harness-proposals/{date}-{slug}.md`` (proposal only).
      * Do NOT touch any plugin file. No edit to SKILL.md, agents/*.md, hooks/.
  - Protected candidates MUST be filtered out by precheck_runner before reaching
    this module.  As a defence-in-depth, apply_writer also skips any target path
    that classify_tier() returns HARNESS *and* is_protected() returns True.

  All filesystem writes go through stdlib ``pathlib`` only (no atomic_write
  needed for append-only log; harness proposal uses write_text which is
  atomic enough for a new file).

Pure stdlib, no network, no LLM calls (F20). Never raises.
"""

from __future__ import annotations

import re
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from hooks.lib.self_improve.guard import is_protected
from hooks.lib.self_improve.tier import classify_tier

# ── Constants ─────────────────────────────────────────────────────────────────

_ROLLBACK_TEMPLATE = """\

### {date} apply — {target_path}
- critic: {critic_verdict}
- 근거: {evidence_markers}
- rollback: 아래 diff 역적용
  ```diff
{diff_block}
  ```
"""

_PROPOSAL_TEMPLATE = """\
# Harness Proposal: {slug}

**Date:** {date}
**Target file:** `{target_path}`
**Critic verdict:** {critic_verdict}
**Evidence markers:** {evidence_markers}
**Cross-project basis:** {cross_project_note}

## Proposed change

```diff
{diff_block}
```

## Rationale

{rationale}

## How to apply

1. Review the diff above.
2. Apply manually to `{target_path}`.
3. Commit with message: `chore: harness proposal {slug}`.
4. Delete this file after applying.
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _slugify(text: str) -> str:
    """Convert text to a safe filename slug."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9가-힣]+", "-", text)
    text = text.strip("-")
    return text[:60] if text else "proposal"


def _make_diff_block(append_text: str, indent: str = "  ") -> str:
    """Render append_text as a simple +diff block."""
    lines = append_text.splitlines()
    return "\n".join(f"{indent}+ {line}" if line.strip() else f"{indent}+" for line in lines)


# ── Public API ────────────────────────────────────────────────────────────────

def apply_project_change(
    target_path: str | Path,
    append_text: str,
    retro_log_path: str | Path,
    critic_verdict: str = "UPHELD",
    evidence_markers: str = "",
    rationale: str = "",
) -> Dict[str, Any]:
    """Apply a project-tier change to target_path and record a rollback block.

    Args:
        target_path: the file to append to (created if missing).
            MUST be a project-tier path. If it is a harness/protected path this
            function returns an error without writing.
        append_text: the text to append to target_path.
        retro_log_path: path to ``.harness/retro-log.md`` for rollback recording.
        critic_verdict: UPHELD | NARROW (for rollback record).
        evidence_markers: comma-separated LEARNING entry markers.
        rationale: one-line human description (for rollback record).

    Returns:
        ``{"ok": True, "path": str}`` on success.
        ``{"ok": False, "error": str}`` on failure (never raises).
    """
    target = Path(target_path)
    target_str = str(target).replace("\\", "/")

    # Defence-in-depth: refuse to write harness/protected paths.
    try:
        tier = classify_tier(target_str)
        protected = is_protected(target_str)
    except Exception:  # noqa: BLE001
        tier = "HARNESS"
        protected = True

    if tier == "HARNESS" or protected:
        return {
            "ok": False,
            "error": (
                f"apply_project_change refused to write harness/protected path: "
                f"'{target_str}' (tier={tier}, protected={protected}). "
                "Use write_harness_proposal() for harness-tier changes."
            ),
        }

    # Append to target file.
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(append_text)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"Failed to write {target}: {exc}"}

    # Record rollback block in retro-log.md.
    diff_block = _make_diff_block(append_text)
    rollback_block = _ROLLBACK_TEMPLATE.format(
        date=_today_str(),
        target_path=target_str,
        critic_verdict=critic_verdict,
        evidence_markers=evidence_markers or "(none)",
        diff_block=diff_block,
    )
    try:
        log = Path(retro_log_path)
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as fh:
            fh.write(rollback_block)
    except Exception as exc:  # noqa: BLE001
        # Rollback record failure is non-fatal for the apply itself, but report it.
        return {
            "ok": True,
            "path": str(target),
            "warning": f"Applied change but failed to write rollback block: {exc}",
        }

    return {"ok": True, "path": str(target)}


def write_harness_proposal(
    harness_dir: str | Path,
    target_path: str,
    append_text: str,
    critic_verdict: str = "UPHELD",
    evidence_markers: str = "",
    rationale: str = "",
    cross_project_note: str = "",
    slug_hint: str = "",
) -> Dict[str, Any]:
    """Write a harness-tier proposal file. NEVER edits any plugin file.

    Args:
        harness_dir: path to the ``.harness/`` directory.
        target_path: the plugin file the proposal targets (NOT written to).
        append_text: the proposed change text.
        critic_verdict: UPHELD | NARROW.
        evidence_markers: comma-separated LEARNING entry markers.
        rationale: one-line human description.
        cross_project_note: cross-project evidence summary.
        slug_hint: optional hint for the proposal filename slug.

    Returns:
        ``{"ok": True, "proposal_path": str}`` on success.
        ``{"ok": False, "error": str}`` on failure (never raises).
    """
    harness = Path(harness_dir)
    proposals_dir = harness / "harness-proposals"

    slug = _slugify(slug_hint or target_path)
    date_str = _today_str()
    filename = f"{date_str}-{slug}.md"
    proposal_path = proposals_dir / filename

    diff_block = _make_diff_block(append_text)
    content = _PROPOSAL_TEMPLATE.format(
        slug=slug,
        date=date_str,
        target_path=target_path,
        critic_verdict=critic_verdict,
        evidence_markers=evidence_markers or "(none)",
        cross_project_note=cross_project_note or "(not specified)",
        diff_block=diff_block,
        rationale=rationale or "(none)",
    )

    try:
        proposals_dir.mkdir(parents=True, exist_ok=True)
        proposal_path.write_text(content, encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"Failed to write proposal {proposal_path}: {exc}"}

    return {"ok": True, "proposal_path": str(proposal_path)}


def apply_change(
    tier: str,
    target_path: str,
    append_text: str,
    harness_dir: str | Path,
    retro_log_path: Optional[str | Path] = None,
    critic_verdict: str = "UPHELD",
    evidence_markers: str = "",
    rationale: str = "",
    cross_project_note: str = "",
    slug_hint: str = "",
) -> Dict[str, Any]:
    """Dispatch to apply_project_change or write_harness_proposal based on tier.

    This is the primary entry point for Phase D.  The caller supplies the
    pre-classified tier so the dispatcher does not re-classify.

    Args:
        tier: "PROJECT" or "HARNESS".
        target_path: the artifact being changed.
        append_text: text to append (project) or propose (harness).
        harness_dir: ``.harness/`` directory path.
        retro_log_path: path to retro-log.md; defaults to
            ``<harness_dir>/retro-log.md``.
        critic_verdict, evidence_markers, rationale, cross_project_note,
        slug_hint: forwarded to the appropriate sub-function.

    Returns:
        Result dict from the called sub-function.
    """
    if retro_log_path is None:
        retro_log_path = Path(harness_dir) / "retro-log.md"

    if tier == "PROJECT":
        return apply_project_change(
            target_path=target_path,
            append_text=append_text,
            retro_log_path=retro_log_path,
            critic_verdict=critic_verdict,
            evidence_markers=evidence_markers,
            rationale=rationale,
        )
    else:
        # HARNESS tier — proposal only, no plugin file edits.
        return write_harness_proposal(
            harness_dir=harness_dir,
            target_path=target_path,
            append_text=append_text,
            critic_verdict=critic_verdict,
            evidence_markers=evidence_markers,
            rationale=rationale,
            cross_project_note=cross_project_note,
            slug_hint=slug_hint or target_path,
        )
