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

Marker comparison is **normalised**: leading markdown heading marks (``#``) and
surrounding whitespace are stripped from both sides before comparing, so
``"## 2026-06-10 — x / T-1"`` and ``"2026-06-10 — x / T-1"`` resolve to the same
entry.  Rationale: LEARNING.md headers read as ``## 2026-…`` on screen, so both
humans and agents naturally write the prefixed form when hand-authoring a marker
— and the documented ``retro-state.json`` schema example used to show the
prefixed form while ``parser.py`` emits the bare form.  A mismatch fell through
to the "marker not found" fail-safe, silently reprocessing the whole file on
every run with no error surfaced (observed live: retro #1 stored the prefixed
form, so retro #2's cursor returned 13/13 entries as "new").

Normalisation applies to **comparison only**.  The canonical *storage* format
stays the parser's output (no heading marks) — allowing both forms to be stored
would create a second source of truth.  Use ``marker_resolves()`` to ask whether
a stored marker actually matched an entry: the fail-safe path is otherwise
indistinguishable from a legitimate first run.

LEARNING.md is read-only input (never modified here).
Pure functions: no file I/O, no network, no LLM calls. stdlib only (F20).
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from hooks.lib.self_improve.parser import parse_learning_entry

_LEADING_HEADING_RE = re.compile(r"^[\s#]+")


def _normalise_marker(marker: object) -> str:
    """Strip leading heading marks/whitespace and trailing whitespace.

    Idempotent, and cannot merge two distinct markers: entry markers never begin
    with ``#`` (``parser.py`` strips the heading), so removing a leading ``#``
    run only ever removes syntax, never content.
    """
    if not isinstance(marker, str):
        return ""
    return _LEADING_HEADING_RE.sub("", marker).strip()


def marker_resolves(learning_text: str, last_marker: Optional[str] = None) -> bool:
    """Does ``last_marker`` actually match an entry in ``learning_text``?

    ``False`` means `get_new_entries` will take the "marker not found" fail-safe
    branch and return everything.  Callers should surface that distinctly from a
    legitimate first run (``last_marker`` empty/None), otherwise a broken cursor
    looks exactly like "no state yet".  An empty/None marker returns ``False``
    (there is nothing to resolve). Never raises.
    """
    if not isinstance(learning_text, str) or not learning_text.strip():
        return False
    target = _normalise_marker(last_marker)
    if not target:
        return False
    try:
        entries = parse_learning_entry(learning_text)
    except Exception:  # noqa: BLE001 - fail-safe
        return False
    return any(_normalise_marker(e.get("marker")) == target for e in entries)


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

    # Find the index of the entry whose marker equals last_marker (normalised —
    # see module docstring: `## `-prefixed and bare forms must resolve alike).
    target_marker = _normalise_marker(effective_marker)
    cursor_index: Optional[int] = None
    for i, entry in enumerate(all_entries):
        if _normalise_marker(entry.get("marker")) == target_marker:
            cursor_index = i
            break

    if cursor_index is None:
        # Marker not found in current file (entry may have been pruned, or
        # state is stale).  Fail-safe: return all entries to avoid skipping.
        return all_entries

    # Return everything *after* the matched entry.
    return all_entries[cursor_index + 1:]
