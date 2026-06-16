"""Unit tests for hooks.lib.self_improve.cursor — get_new_entries (spec F8).

Tests cover:
- last_marker=None → all entries returned (first run)
- last_marker="" → treated as None → all entries returned
- last_marker points to a middle entry → only subsequent entries returned
- last_marker points to the LAST entry → empty list returned
- last_marker not found in file → fail-safe: all entries returned
- Empty / whitespace-only text → empty list
- Non-string input → empty list
- LEARNING.md text is never modified (read-only contract)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hooks.lib.self_improve.cursor import get_new_entries

FIXTURE_DIR = Path(__file__).parent / "fixtures"
MARKER_FIXTURE = FIXTURE_DIR / "sample_learning_with_markers.md"


@pytest.fixture(scope="module")
def learning_text() -> str:
    return MARKER_FIXTURE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def all_entries(learning_text: str):
    return get_new_entries(learning_text, last_marker=None)


# ---------------------------------------------------------------------------
# Baseline: parse all entries
# ---------------------------------------------------------------------------

class TestGetNewEntriesNoMarker:
    def test_none_marker_returns_all(self, learning_text: str, all_entries):
        assert len(all_entries) == 5

    def test_empty_string_marker_returns_all(self, learning_text: str):
        result = get_new_entries(learning_text, last_marker="")
        assert len(result) == 5

    def test_first_entry_marker_correct(self, all_entries):
        assert all_entries[0]["marker"] == "2026-06-10 — auth-refresh / T-12"

    def test_last_entry_marker_correct(self, all_entries):
        assert all_entries[-1]["marker"] == "2026-06-14 — last-entry / T-99"


# ---------------------------------------------------------------------------
# Cursor positioned in the middle
# ---------------------------------------------------------------------------

class TestGetNewEntriesMiddleMarker:
    """last_marker == second entry → entries 3, 4, 5 are returned."""

    SECOND_MARKER = "2026-06-11 — pr-feedback-dedup / T-7"

    def test_count_after_second(self, learning_text: str):
        result = get_new_entries(learning_text, last_marker=self.SECOND_MARKER)
        assert len(result) == 3

    def test_first_of_remaining_is_third_entry(self, learning_text: str):
        result = get_new_entries(learning_text, last_marker=self.SECOND_MARKER)
        assert result[0]["marker"] == "2026-06-12 — type-narrowing / T-15"

    def test_last_of_remaining_is_last_entry(self, learning_text: str):
        result = get_new_entries(learning_text, last_marker=self.SECOND_MARKER)
        assert result[-1]["marker"] == "2026-06-14 — last-entry / T-99"


# ---------------------------------------------------------------------------
# Cursor positioned at the LAST entry (edge case: nothing new)
# ---------------------------------------------------------------------------

class TestGetNewEntriesLastMarker:
    LAST_MARKER = "2026-06-14 — last-entry / T-99"

    def test_empty_list_when_cursor_at_last(self, learning_text: str):
        result = get_new_entries(learning_text, last_marker=self.LAST_MARKER)
        assert result == []

    def test_returns_list_not_none(self, learning_text: str):
        result = get_new_entries(learning_text, last_marker=self.LAST_MARKER)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Marker not found in file (fail-safe: return all)
# ---------------------------------------------------------------------------

class TestGetNewEntriesMarkerNotFound:
    STALE_MARKER = "2025-01-01 — does-not-exist / T-0"

    def test_all_returned_when_marker_not_found(self, learning_text: str):
        result = get_new_entries(learning_text, last_marker=self.STALE_MARKER)
        assert len(result) == 5

    def test_same_order_when_marker_not_found(self, learning_text: str):
        result = get_new_entries(learning_text, last_marker=self.STALE_MARKER)
        assert result[0]["marker"] == "2026-06-10 — auth-refresh / T-12"


# ---------------------------------------------------------------------------
# Degenerate inputs (fail-safe, no raises)
# ---------------------------------------------------------------------------

class TestGetNewEntriesEdgeCases:
    def test_empty_string_text(self):
        assert get_new_entries("", last_marker=None) == []

    def test_whitespace_only_text(self):
        assert get_new_entries("   \n\n\t", last_marker=None) == []

    def test_non_string_text(self):
        assert get_new_entries(None, last_marker=None) == []  # type: ignore[arg-type]

    def test_no_headers_text(self):
        text = "# Title\n\nSome preamble without any ## headers."
        assert get_new_entries(text, last_marker=None) == []

    def test_does_not_raise_on_bad_inputs(self):
        # Should never raise — fail-safe contract.
        try:
            get_new_entries(42, last_marker=object())  # type: ignore[arg-type]
        except Exception as exc:
            pytest.fail(f"get_new_entries raised unexpectedly: {exc}")


# ---------------------------------------------------------------------------
# Read-only contract: original text must not be modified
# ---------------------------------------------------------------------------

class TestLearningReadOnlyContract:
    def test_text_unchanged_after_call(self, learning_text: str):
        original = learning_text
        get_new_entries(learning_text, last_marker=None)
        assert learning_text == original

    def test_text_unchanged_with_middle_marker(self, learning_text: str):
        original = learning_text
        get_new_entries(learning_text, last_marker="2026-06-11 — pr-feedback-dedup / T-7")
        assert learning_text == original
