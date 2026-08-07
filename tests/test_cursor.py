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

from hooks.lib.self_improve.cursor import get_new_entries, marker_resolves

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


# ---------------------------------------------------------------------------
# 마커 형식 정규화 — `## ` 접두형과 비접두형은 동일하게 해석돼야 한다
#
# 회귀: retro #1이 SKILL.md의 (당시) 접두형 스키마 예시대로 저장했고, parser 는
# 비접두형 marker 를 만들기 때문에 완전일치 비교가 실패했다. 그러면 "미발견 →
# 전체 반환" fail-safe 가 발동해 매 실행이 전량 재처리된다(retro #2에서 13/13건
# 실측). 저장소 안에 두 형식이 이미 공존했는데도 **동일성을 단언하는 테스트가
# 없어서** 통과했다.
# ---------------------------------------------------------------------------


class TestMarkerPrefixNormalisation:
    def test_prefixed_and_bare_marker_are_equivalent(self, learning_text: str, all_entries):
        bare = "2026-06-12 — type-narrowing / T-15"
        baseline = get_new_entries(learning_text, bare)
        # 공허한 통과 방지 — 마커가 실제로 해석돼 결과가 전체보다 **작아야** 한다.
        # (해석 실패 시 fail-safe 가 양쪽 다 전체를 반환해 동등성이 무의미해진다)
        assert 0 < len(baseline) < len(all_entries), baseline
        for prefixed in (f"## {bare}", f"##{bare}", f"  ##  {bare}  ", f"# {bare}"):
            assert get_new_entries(learning_text, prefixed) == baseline, (
                f"형식 {prefixed!r} 이 비접두형과 다르게 해석됨"
            )

    def test_prefixed_last_entry_marker_yields_zero_new(self, learning_text: str):
        last = "2026-06-14 — last-entry / T-99"
        assert get_new_entries(learning_text, f"## {last}") == []
        assert get_new_entries(learning_text, last) == []

    def test_normalisation_is_idempotent(self, learning_text: str, all_entries):
        bare = "2026-06-12 — type-narrowing / T-15"
        once = get_new_entries(learning_text, f"## {bare}")
        twice = get_new_entries(learning_text, f"## ## {bare}")
        assert once == twice
        assert 0 < len(once) < len(all_entries)  # 공허한 통과 방지

    def test_unknown_marker_still_returns_all(self, learning_text: str, all_entries):
        """fail-safe 방향은 유지한다 — 누락보다 재처리가 낫다."""
        assert get_new_entries(learning_text, "## 2099-01-01 — nope / T-0") == all_entries


class TestMarkerResolves:
    """관측성: fail-safe 분기가 "첫 실행"과 구분돼야 한다."""

    def test_resolves_for_bare_marker(self, learning_text: str):
        assert marker_resolves(learning_text, "2026-06-12 — type-narrowing / T-15")

    def test_resolves_for_prefixed_marker(self, learning_text: str):
        assert marker_resolves(learning_text, "## 2026-06-12 — type-narrowing / T-15")

    def test_unresolved_marker_is_false(self, learning_text: str):
        assert not marker_resolves(learning_text, "2099-01-01 — nope / T-0")

    def test_empty_marker_is_false(self, learning_text: str):
        """첫 실행은 해석할 마커가 없다 — warning 은 호출자가 구분해 붙인다."""
        assert not marker_resolves(learning_text, None)
        assert not marker_resolves(learning_text, "")

    def test_empty_text_is_false(self):
        assert not marker_resolves("", "2026-06-12 — type-narrowing / T-15")
