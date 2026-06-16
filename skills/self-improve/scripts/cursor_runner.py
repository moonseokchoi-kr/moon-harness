"""cursor_runner.py — Phase A glue: load retro-state + get_new_entries.

Wraps:
  - hooks.lib.self_improve.state_io.load_state (T-1)
  - hooks.lib.self_improve.cursor.get_new_entries (T-3)

Contract (spec F8 / F13):
  - Returns a structured result dict. Never raises.
  - On ANY error (file missing, parse failure, cursor failure): returns
    ``{"ok": False, "entries": [], "last_marker": None, ...}``
    with the cursor NOT updated — the caller must NOT advance retro-state.json
    when ok=False (fail-safe: prefer reprocessing over silent skip).
  - On success: ``{"ok": True, "entries": [...], "last_marker": <str|None>}``

Filesystem I/O:
  - Reads: ``<harness_dir>/LEARNING.md`` (read-only — never written)
  - Reads: ``<harness_dir>/retro-state.json`` (read-only here; caller writes)

Pure stdlib, no network, no LLM calls (F20).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from hooks.lib.self_improve.cursor import get_new_entries
from hooks.lib.self_improve.state_io import load_state


def run_cursor(harness_dir: str | Path) -> Dict[str, Any]:
    """Load retro-state, read LEARNING.md, return new entries.

    Args:
        harness_dir: path to the ``.harness/`` directory (e.g.
            ``Path(repo_root) / ".harness"``).

    Returns:
        A dict with the following keys::

            {
                "ok":          bool,    # False on any error
                "entries":     list,    # new entry dicts (may be empty)
                "last_marker": str|None,# current last_processed_marker from state
                "error":       str,     # non-empty only when ok=False
            }

        When ok=False the caller MUST NOT advance the cursor.
    """
    result: Dict[str, Any] = {
        "ok": False,
        "entries": [],
        "last_marker": None,
        "error": "",
    }

    harness_path = Path(harness_dir) if not isinstance(harness_dir, Path) else harness_dir

    # ── 1. Load retro-state.json ─────────────────────────────────────────────
    state_path = harness_path / "retro-state.json"
    state: Optional[dict] = load_state(state_path)
    # state=None means file absent or parse error → first-run, treat all as new.
    last_marker: Optional[str] = None
    if state is not None:
        lm = state.get("last_processed_marker")
        last_marker = lm if isinstance(lm, str) else None

    result["last_marker"] = last_marker

    # ── 2. Read LEARNING.md ──────────────────────────────────────────────────
    learning_path = harness_path / "LEARNING.md"
    try:
        learning_text: str = learning_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        result["error"] = f"LEARNING.md not found: {learning_path}"
        return result
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"Failed to read LEARNING.md: {exc}"
        return result

    # ── 3. Call get_new_entries (pure, never raises) ─────────────────────────
    try:
        entries: List[Dict[str, Any]] = get_new_entries(learning_text, last_marker)
    except Exception as exc:  # noqa: BLE001
        # get_new_entries should never raise, but be defensive.
        result["error"] = f"get_new_entries failed unexpectedly: {exc}"
        return result

    result["ok"] = True
    result["entries"] = entries
    return result
