"""Cursor engine for LEARNING.md new-entry extraction (spec F8).

Implements `get_new_entries` — a pure function that accepts LEARNING.md text
and an optional `last_marker` string, and returns only the entries that appear
*after* the cursor position (i.e., not yet processed).

Contract (F8):
- last_marker=None  → return ALL parsed entries (first-run / no state).
- last_marker=""    → equivalent to None; return all entries.
- last_marker=<m>   → return entries whose marker comes *after* the entry
                      whose marker equals <m>.  If <m> is not found, return
                      all entries (fail-safe: prefer reprocessing over skipping).
- 0 new entries     → caller should report "신규 없음" and not advance cursor.

LEARNING.md is read-only input (never modified here).
Pure function: no file I/O, no network, no LLM calls. stdlib only (F20).
"""

from __future__ import annotations

from typing import Dict, List, Optional

from hooks.lib.self_improve.parser import parse_learning_entry


def get_new_entries(
    learning_text: str,
    last_marker: Optional[str] = None,
) -> List[Dict[str, object]]:
    """Return entries from ``learning_text`` that follow the cursor position.

    Args:
        learning_text: the full text of LEARNING.md (caller supplies; this
            function never reads from disk).
        last_marker: the ``marker`` field of the last-processed entry, as
            stored in ``retro-state.json``.  ``None`` or empty string means
            "process everything" (first run or no previous state).

    Returns:
        A list of entry dicts (same shape as ``parse_learning_entry``). May be
        empty if no new entries exist after the cursor. Never raises.
    """
    # Fail-safe: non-string or empty input → no entries.
    if not isinstance(learning_text, str) or not learning_text.strip():
        return []

    all_entries: List[Dict[str, object]] = parse_learning_entry(learning_text)

    # Normalise: empty string behaves like None (no prior cursor).
    effective_marker: Optional[str] = last_marker if last_marker else None

    if effective_marker is None:
        # No cursor — treat entire file as new.
        return all_entries

    # Find the index of the entry whose marker equals last_marker.
    cursor_index: Optional[int] = None
    for i, entry in enumerate(all_entries):
        if entry.get("marker") == effective_marker:
            cursor_index = i
            break

    if cursor_index is None:
        # Marker not found in current file (entry may have been pruned, or
        # state is stale).  Fail-safe: return all entries to avoid skipping.
        return all_entries

    # Return everything *after* the matched entry.
    return all_entries[cursor_index + 1:]
